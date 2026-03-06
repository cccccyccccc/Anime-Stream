"""qBittorrent-backed BT worker.

This worker drives BT progress from qBittorrent Web API so gateway can evolve
from fully mocked timeline toward real torrent download orchestration.
"""

from __future__ import annotations

from pathlib import Path
import re
import threading
import time
from typing import Any

from workers.qbittorrent_client import (
    QbittorrentApiError,
    QbittorrentClient,
    QbittorrentConfig,
)

_TERMINAL_STATES = {'completed', 'failed', 'canceled'}
_VIDEO_EXTENSIONS = {
    '.mp4',
    '.mkv',
    '.avi',
    '.mov',
    '.m4v',
    '.ts',
    '.m2ts',
    '.wmv',
    '.flv',
    '.webm',
}
_HASH_RESOLVE_TIMEOUT_SECONDS = 45
_STATUS_QUERY_FAILURE_GRACE_COUNT = 3
_TORRENT_NOT_FOUND_GRACE_SECONDS = 30
_STALLED_RESUME_INTERVAL_SECONDS = 20
_STALLED_DOWNLOAD_STATES = {'stalleddl', 'pauseddl'}
_STREAMING_TUNE_INTERVAL_SECONDS = 15


class QbittorrentBtWorker:
    """BT worker implementation backed by qBittorrent Web API."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: float = 10.0,
        playable_progress_percent: int = 8,
    ) -> None:
        self._client = QbittorrentClient(
            QbittorrentConfig(
                base_url=base_url,
                username=username,
                password=password,
                timeout_seconds=timeout_seconds,
            )
        )
        self._playable_progress_percent = max(1, min(99, int(playable_progress_percent)))

        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        *,
        session_id: str,
        magnet: str = '',
        torrent_url: str = '',
        max_retries: int = 2,
        failure_mode: str = 'none',
    ) -> dict[str, Any]:
        del failure_mode

        now_ms = int(time.time() * 1000)
        prefix = ''.join(ch for ch in session_id if ch.isalnum())[:10] or 'session'
        job_id = f'bt-qbt-{now_ms}-{prefix}'
        created_at = time.time()

        uri = (magnet or '').strip() or (torrent_url or '').strip()
        max_retries_normalized = max(0, int(max_retries))

        base = {
            'jobId': job_id,
            'sessionId': session_id,
            'source': 'qbittorrent-worker',
            'status': 'queued',
            'progressPercent': 0,
            'message': 'Queued for qBittorrent add request.',
            'createdAt': self._to_iso(created_at),
            'updatedAt': self._to_iso(created_at),
            'magnet': magnet,
            'torrentUrl': torrent_url,
            'attempt': 0,
            'maxRetries': max_retries_normalized,
            'retryCount': 0,
            'canRetry': max_retries_normalized > 0,
            'workerKind': 'qbittorrent',
            'qbtBaseUrl': self._client.base_url,
            'playableProgressPercent': self._playable_progress_percent,
        }

        wrapper = {
            'base': base,
            'attempt': 0,
            'maxRetries': max_retries_normalized,
            'terminal': False,
            'torrentHash': self._extract_btih(uri),
            'sourceUri': uri,
            'createdAtEpoch': created_at,
            'cancelRequested': False,
            'statusQueryFailureCount': 0,
            'torrentNotFoundSinceEpoch': 0.0,
            'lastResumeEpoch': 0.0,
            'streamingTuneDone': False,
            'lastStreamingTuneEpoch': 0.0,
        }

        if not uri:
            base['status'] = 'failed'
            base['message'] = 'Missing magnet/torrent URL for qBittorrent worker.'
            base['errorCode'] = 'BT_URI_MISSING'
            base['canRetry'] = False
            wrapper['terminal'] = True
            with self._lock:
                self._jobs[job_id] = wrapper
                return dict(base)

        try:
            self._client.add_torrent(uri=uri)
            base['message'] = 'Torrent add request sent to qBittorrent.'
        except QbittorrentApiError as exc:
            base['status'] = 'failed'
            base['message'] = f'Failed to add torrent: {exc}'
            base['errorCode'] = 'BT_ADD_FAILED'
            base['canRetry'] = max_retries_normalized > 0
            wrapper['terminal'] = True

        with self._lock:
            self._jobs[job_id] = wrapper
            return self._refresh_job_locked(wrapper)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None
            return self._refresh_job_locked(wrapper)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            snapshots = [self._refresh_job_locked(wrapper) for wrapper in self._jobs.values()]

        snapshots.sort(
            key=lambda item: str(item.get('createdAt', '')),
            reverse=True,
        )
        return snapshots

    def retry_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None

            base = wrapper['base']
            status = str(base.get('status', '')).lower()
            if status != 'failed':
                return None

            attempt = int(wrapper.get('attempt', 0))
            max_retries = int(wrapper.get('maxRetries', 0))
            if attempt >= max_retries:
                base['canRetry'] = False
                base['message'] = 'Retry limit reached for qBittorrent worker.'
                base['updatedAt'] = self._to_iso(time.time())
                wrapper['base'] = base
                wrapper['terminal'] = True
                return dict(base)

            next_attempt = attempt + 1
            wrapper['attempt'] = next_attempt
            wrapper['terminal'] = False
            wrapper['cancelRequested'] = False
            wrapper['statusQueryFailureCount'] = 0
            wrapper['torrentNotFoundSinceEpoch'] = 0.0
            wrapper['lastResumeEpoch'] = 0.0
            wrapper['streamingTuneDone'] = False
            wrapper['lastStreamingTuneEpoch'] = 0.0

            base['status'] = 'queued'
            base['progressPercent'] = int(base.get('progressPercent', 0))
            base['message'] = f'Retry attempt {next_attempt} requested in qBittorrent.'
            base['attempt'] = next_attempt
            base['retryCount'] = next_attempt
            base['canRetry'] = next_attempt < max_retries
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base

            torrent_hash = str(wrapper.get('torrentHash', '')).strip().lower()
            if torrent_hash:
                try:
                    self._client.resume_torrent(torrent_hash)
                except QbittorrentApiError as exc:
                    base['status'] = 'failed'
                    base['message'] = f'qBittorrent resume failed: {exc}'
                    base['errorCode'] = 'BT_RETRY_FAILED'
                    base['canRetry'] = next_attempt < max_retries
                    base['updatedAt'] = self._to_iso(time.time())
                    wrapper['base'] = base
                    wrapper['terminal'] = True

            return self._refresh_job_locked(wrapper)

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None

            base = wrapper['base']
            status = str(base.get('status', '')).lower()
            if status in _TERMINAL_STATES:
                return dict(base)

            torrent_hash = str(wrapper.get('torrentHash', '')).strip().lower()
            if torrent_hash:
                try:
                    self._client.delete_torrent(torrent_hash, delete_files=True)
                except QbittorrentApiError as exc:
                    base['status'] = 'failed'
                    base['message'] = f'Cancel failed: {exc}'
                    base['errorCode'] = 'BT_CANCEL_FAILED'
                    base['canRetry'] = False
                    base['updatedAt'] = self._to_iso(time.time())
                    wrapper['base'] = base
                    wrapper['terminal'] = True
                    return dict(base)

            wrapper['cancelRequested'] = True
            base['status'] = 'canceled'
            base['message'] = 'qBittorrent job canceled.'
            base['canRetry'] = False
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base
            wrapper['terminal'] = True
            return dict(base)

    def _refresh_job_locked(self, wrapper: dict[str, Any]) -> dict[str, Any]:
        base: dict[str, Any] = dict(wrapper.get('base', {}))
        now = time.time()

        status = str(base.get('status', '')).lower()
        if wrapper.get('terminal') or status in _TERMINAL_STATES:
            wrapper['base'] = base
            return dict(base)

        source_uri = str(wrapper.get('sourceUri', '')).strip()
        torrent_hash = str(wrapper.get('torrentHash', '')).strip().lower()
        if not torrent_hash:
            torrent_hash = self._try_resolve_hash(source_uri)
            if torrent_hash:
                wrapper['torrentHash'] = torrent_hash
                base['torrentHash'] = torrent_hash

        if not torrent_hash:
            age_seconds = max(0, now - float(wrapper.get('createdAtEpoch', now)))
            if age_seconds > _HASH_RESOLVE_TIMEOUT_SECONDS:
                base['status'] = 'failed'
                base['message'] = 'Unable to resolve torrent hash from qBittorrent.'
                base['errorCode'] = 'BT_HASH_UNRESOLVED'
                base['canRetry'] = int(wrapper.get('attempt', 0)) < int(wrapper.get('maxRetries', 0))
                base['updatedAt'] = self._to_iso(now)
                wrapper['base'] = base
                wrapper['terminal'] = True
                return dict(base)

            base['status'] = 'queued'
            base['message'] = 'Waiting for qBittorrent torrent hash resolution.'
            base['progressPercent'] = 5
            base['updatedAt'] = self._to_iso(now)
            wrapper['base'] = base
            return dict(base)

        try:
            infos = self._client.list_torrents(hashes=torrent_hash)
        except QbittorrentApiError as exc:
            failure_count = int(wrapper.get('statusQueryFailureCount', 0)) + 1
            wrapper['statusQueryFailureCount'] = failure_count

            if failure_count < _STATUS_QUERY_FAILURE_GRACE_COUNT:
                base['status'] = 'fetching_metadata'
                base['message'] = (
                    f'Temporary qBittorrent status query failure '
                    f'({failure_count}/{_STATUS_QUERY_FAILURE_GRACE_COUNT}).'
                )
                base['canRetry'] = True
                base.pop('errorCode', None)
                base['updatedAt'] = self._to_iso(now)
                wrapper['base'] = base
                return dict(base)

            base['status'] = 'failed'
            base['message'] = f'qBittorrent status query failed: {exc}'
            base['errorCode'] = 'BT_STATUS_QUERY_FAILED'
            base['canRetry'] = int(wrapper.get('attempt', 0)) < int(wrapper.get('maxRetries', 0))
            base['updatedAt'] = self._to_iso(now)
            wrapper['base'] = base
            wrapper['terminal'] = True
            return dict(base)

        wrapper['statusQueryFailureCount'] = 0

        if not infos:
            not_found_since = float(wrapper.get('torrentNotFoundSinceEpoch', 0.0) or 0.0)
            if not_found_since <= 0:
                not_found_since = now
                wrapper['torrentNotFoundSinceEpoch'] = not_found_since

            elapsed = max(0, int(now - not_found_since))
            if elapsed < _TORRENT_NOT_FOUND_GRACE_SECONDS:
                base['status'] = 'queued'
                base['message'] = (
                    f'Waiting for torrent registration in qBittorrent '
                    f'({elapsed}s).'
                )
                base['progressPercent'] = max(5, int(base.get('progressPercent', 0)))
                base['canRetry'] = True
                base.pop('errorCode', None)
                base['updatedAt'] = self._to_iso(now)
                wrapper['base'] = base
                return dict(base)

            base['status'] = 'failed'
            base['message'] = 'Torrent not found in qBittorrent.'
            base['errorCode'] = 'BT_TORRENT_NOT_FOUND'
            base['canRetry'] = int(wrapper.get('attempt', 0)) < int(wrapper.get('maxRetries', 0))
            base['updatedAt'] = self._to_iso(now)
            wrapper['base'] = base
            wrapper['terminal'] = True
            return dict(base)

        wrapper['torrentNotFoundSinceEpoch'] = 0.0

        info = infos[0]

        raw_progress = float(info.get('progress') or 0)
        progress_percent = max(0, min(100, int(round(raw_progress * 100))))
        state = str(info.get('state') or '').strip()
        lowered_state = state.lower()

        base['torrentHash'] = torrent_hash
        base['qbtState'] = state or 'unknown'
        base['qbtName'] = str(info.get('name') or '')
        base['qbtSavePath'] = str(info.get('save_path') or '')
        base['qbtDlSpeed'] = self._as_int(info.get('dlspeed'))
        base['qbtUpSpeed'] = self._as_int(info.get('upspeed'))
        base['qbtNumSeeds'] = self._as_int(info.get('num_seeds'))
        base['qbtNumLeechs'] = self._as_int(info.get('num_leechs'))
        base['qbtEta'] = self._as_int(info.get('eta'))
        base['progressPercent'] = progress_percent
        base['updatedAt'] = self._to_iso(now)
        streaming_tune_note = self._try_enable_streaming_priority(
            wrapper,
            torrent_hash=torrent_hash,
            info=info,
            now=now,
        )

        if lowered_state in {'error', 'missingfiles'}:
            base['status'] = 'failed'
            base['message'] = f'qBittorrent state={state or "error"}.'
            base['errorCode'] = 'BT_QBT_ERROR_STATE'
            base['canRetry'] = int(wrapper.get('attempt', 0)) < int(wrapper.get('maxRetries', 0))
            wrapper['base'] = base
            wrapper['terminal'] = True
            return dict(base)

        if progress_percent >= self._playable_progress_percent:
            output_candidates = self._build_output_candidates(info, torrent_hash=torrent_hash)
            output_ref = self._resolve_output_ref(
                info,
                torrent_hash=torrent_hash,
                output_candidates=output_candidates,
            )
            base['status'] = 'completed'
            base['message'] = (
                f'qBittorrent reached playable threshold '
                f'({progress_percent}% >= {self._playable_progress_percent}%).'
            )
            base['outputRef'] = output_ref
            if output_candidates:
                base['outputCandidates'] = [
                    candidate['path']
                    for candidate in output_candidates[:16]
                ]
                base['selectedOutputRef'] = output_ref
                base['outputCandidateCount'] = len(output_candidates)
            base['canRetry'] = False
            base.pop('errorCode', None)
            base['updatedAt'] = self._to_iso(now)
            wrapper['base'] = base
            wrapper['terminal'] = True
            return dict(base)

        resume_note = self._try_resume_stalled_download(
            wrapper,
            torrent_hash=torrent_hash,
            lowered_state=lowered_state,
        )

        mapped_status, message = self._map_non_terminal_state(
            lowered_state,
            progress_percent=progress_percent,
        )
        if resume_note:
            message = f'{message} {resume_note}'
        if streaming_tune_note:
            message = f'{message} {streaming_tune_note}'

        base['status'] = mapped_status
        base['message'] = message
        base['canRetry'] = True
        base.pop('errorCode', None)

        wrapper['base'] = base
        return dict(base)

    def _try_resume_stalled_download(
        self,
        wrapper: dict[str, Any],
        *,
        torrent_hash: str,
        lowered_state: str,
    ) -> str:
        if lowered_state not in _STALLED_DOWNLOAD_STATES:
            return ''

        now = time.time()
        last_resume_epoch = float(wrapper.get('lastResumeEpoch', 0.0) or 0.0)
        if now - last_resume_epoch < _STALLED_RESUME_INTERVAL_SECONDS:
            return ''

        wrapper['lastResumeEpoch'] = now
        try:
            self._client.resume_torrent(torrent_hash)
            return 'Auto-resume requested.'
        except QbittorrentApiError as exc:
            return f'Auto-resume failed: {exc}'

    def _try_enable_streaming_priority(
        self,
        wrapper: dict[str, Any],
        *,
        torrent_hash: str,
        info: dict[str, Any],
        now: float,
    ) -> str:
        if wrapper.get('streamingTuneDone'):
            return ''

        last_tune_epoch = float(wrapper.get('lastStreamingTuneEpoch', 0.0) or 0.0)
        if now - last_tune_epoch < _STREAMING_TUNE_INTERVAL_SECONDS:
            return ''

        wrapper['lastStreamingTuneEpoch'] = now

        seq_enabled = self._coerce_bool(info.get('seq_dl'))
        first_last_enabled = self._coerce_bool(info.get('f_l_piece_prio'))

        notes: list[str] = []
        tune_ok = True

        if not seq_enabled:
            try:
                self._client.enable_sequential_download(torrent_hash)
                notes.append('Enabled sequential download.')
                seq_enabled = True
            except QbittorrentApiError as exc:
                tune_ok = False
                notes.append(f'Sequential tune failed: {exc}')

        if not first_last_enabled:
            try:
                self._client.enable_first_last_piece_priority(torrent_hash)
                notes.append('Enabled first/last piece priority.')
                first_last_enabled = True
            except QbittorrentApiError as exc:
                tune_ok = False
                notes.append(f'First/last tune failed: {exc}')

        if seq_enabled and first_last_enabled:
            wrapper['streamingTuneDone'] = True
        elif tune_ok:
            wrapper['streamingTuneDone'] = False

        return ' '.join(notes).strip()

    def _coerce_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return int(value) != 0

        text = str(value or '').strip().lower()
        return text in {'1', 'true', 'yes', 'on'}
    def _build_output_candidates(
        self,
        info: dict[str, Any],
        *,
        torrent_hash: str,
    ) -> list[dict[str, Any]]:
        save_path = str(info.get('save_path') or '').strip()

        try:
            files = self._client.list_files(torrent_hash=torrent_hash)
        except QbittorrentApiError:
            return []

        candidates: list[dict[str, Any]] = []
        for file_item in files:
            name = str(file_item.get('name') or '').strip().replace('\\', '/')
            if not name:
                continue

            ext = Path(name).suffix.lower()
            if ext not in _VIDEO_EXTENSIONS:
                continue

            absolute_path = self._join_save_path(save_path, name)
            candidates.append(
                {
                    'path': absolute_path,
                    'name': name,
                    'size': self._as_int(file_item.get('size')),
                    'priority': self._as_int(file_item.get('priority')),
                    'progress': self._as_float(file_item.get('progress')),
                }
            )

        candidates.sort(
            key=lambda item: (
                float(item.get('progress', 0.0)),
                int(item.get('size', 0)),
            ),
            reverse=True,
        )
        return candidates

    def _resolve_output_ref(
        self,
        info: dict[str, Any],
        *,
        torrent_hash: str,
        output_candidates: list[dict[str, Any]],
    ) -> str:
        if output_candidates:
            first_path = str(output_candidates[0].get('path') or '').strip()
            if first_path:
                return first_path

        content_path = str(info.get('content_path') or '').strip()
        if content_path:
            return content_path

        save_path = str(info.get('save_path') or '').strip()
        name = str(info.get('name') or '').strip()
        if save_path and name:
            joined = save_path.rstrip('/\\') + '/' + name.lstrip('/\\')
            return joined

        return f'bt://qbittorrent/{torrent_hash}'

    def _join_save_path(self, save_path: str, relative_name: str) -> str:
        rel = relative_name.replace('\\', '/').lstrip('/')
        if not save_path:
            return rel

        try:
            joined = (Path(save_path).expanduser() / Path(rel)).resolve()
            return str(joined)
        except Exception:  # noqa: BLE001
            return save_path.rstrip('/\\') + '/' + rel

    def _try_resolve_hash(self, source_uri: str) -> str:
        if not source_uri:
            return ''

        guessed = self._extract_btih(source_uri)
        if guessed:
            return guessed

        try:
            items = self._client.list_torrents()
        except QbittorrentApiError:
            return ''

        for item in items:
            magnet_uri = str(item.get('magnet_uri') or '').strip()
            if magnet_uri and magnet_uri == source_uri:
                return str(item.get('hash') or '').strip().lower()

        return ''

    def _map_non_terminal_state(
        self,
        lowered_state: str,
        *,
        progress_percent: int,
    ) -> tuple[str, str]:
        if lowered_state in {'queueddl', 'metadl', 'checkingdl', 'allocating'}:
            return ('fetching_metadata', 'qBittorrent is preparing torrent metadata.')

        if lowered_state in {'downloading', 'forceddl'}:
            return ('downloading', f'qBittorrent downloading pieces ({progress_percent}%).')

        if lowered_state in {'stalleddl'}:
            return ('buffering', f'qBittorrent waiting for peers ({progress_percent}%).')

        if lowered_state in {'pauseddl'}:
            return ('buffering', 'qBittorrent download paused.')

        if lowered_state in {'queuedup', 'uploading', 'stalledup', 'pausedup', 'forcedup'}:
            return ('downloading', f'qBittorrent state={lowered_state} ({progress_percent}%).')

        return ('downloading', f'qBittorrent state={lowered_state or "unknown"} ({progress_percent}%).')

    def _extract_btih(self, value: str) -> str:
        raw = (value or '').strip()
        if not raw:
            return ''

        match = re.search(r'btih:([A-Za-z0-9]{32,40})', raw, flags=re.IGNORECASE)
        if not match:
            return ''

        return match.group(1).strip().lower()

    def _as_int(self, raw: Any) -> int:
        try:
            return int(raw)
        except Exception:  # noqa: BLE001
            return 0

    def _as_float(self, raw: Any) -> float:
        try:
            return float(raw)
        except Exception:  # noqa: BLE001
            return 0.0

    def _to_iso(self, epoch_seconds: float) -> str:
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(epoch_seconds))











