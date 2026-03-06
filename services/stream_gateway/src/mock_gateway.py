#!/usr/bin/env python3
"""Local stream gateway for Flutter development.

Supported API shape:
- GET  /health
- GET  /home
- GET  /search?q=
- GET  /anime/{id}
- POST /play/session
- GET  /play/session/{id}/status
- POST /play/session/{id}/retry
- POST /play/session/{id}/cancel
- GET  /workers/overview
- GET  /workers/bt/jobs
- POST /workers/bt/jobs
- GET  /workers/bt/jobs/{id}
- POST /workers/bt/jobs/{id}/retry
- POST /workers/bt/jobs/{id}/cancel
- GET  /workers/transcode/jobs
- POST /workers/transcode/jobs
- GET  /workers/transcode/jobs/{id}
- POST /workers/transcode/jobs/{id}/retry
- POST /workers/transcode/jobs/{id}/cancel
- GET  /streams/{session}/{attempt}/index.m3u8

Modes:
- mock  (default): static in-memory payloads
- mikan: fetches anime data from mikan.tangbai.cc
"""

from __future__ import annotations

import argparse
import json
import os
import mimetypes
import re
import shutil
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from source_adapter.mikan_source import MikanSourceAdapter
from workers.contracts import BtWorkerContract, TranscodeWorkerContract
from workers.worker_factory import (
    SUPPORTED_BT_WORKER_KINDS,
    SUPPORTED_TRANSCODE_WORKER_KINDS,
    create_worker_bundle,
)

SAMPLE_HLS_URL = 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8'

_TRANSCODE_INPUT_VIDEO_EXTENSIONS = {
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

ANIME_ITEMS: list[dict[str, Any]] = [
    {
        'id': 'kusuriya-s2',
        'title': 'The Apothecary Diaries S2 - 09',
        'subtitle': '1080p · 24m · New',
        'latestEpisodeId': 'ep-09',
        'source': 'mikan.tangbai.cc',
        'posterUrl': 'https://picsum.photos/seed/kusuriya/300/420',
        'fansubGroup': 'Lagrange',
        'publishedAt': '2026-03-05 22:12',
    },
    {
        'id': 'solo-leveling-s2',
        'title': 'Solo Leveling S2 - 11',
        'subtitle': '1080p · 24m · New',
        'latestEpisodeId': 'ep-11',
        'source': 'mikan.tangbai.cc',
        'posterUrl': 'https://picsum.photos/seed/solo/300/420',
        'fansubGroup': 'Nekomoe',
        'publishedAt': '2026-03-04 18:05',
    },
    {
        'id': 'frieren',
        'title': 'Frieren - 27',
        'subtitle': '1080p · 24m',
        'latestEpisodeId': 'ep-27',
        'source': 'mikan.tangbai.cc',
        'posterUrl': 'https://picsum.photos/seed/frieren/300/420',
        'fansubGroup': 'Snow-Raws',
        'publishedAt': '2026-03-02 12:40',
    },
]

SESSIONS: dict[str, dict[str, Any]] = {}
SESSIONS_LOCK = threading.Lock()


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = 'MockGateway/0.8'

    source_mode = 'mock'
    bt_worker_mode = 'mock'
    transcode_worker_mode = 'mock'
    stream_root = Path('runtime/streams').resolve()
    public_base_url = 'http://127.0.0.1:8080'
    default_debug_input_ref = ''
    mikan_adapter: MikanSourceAdapter | None = None

    bt_worker: BtWorkerContract
    transcode_worker: TranscodeWorkerContract

    _default_workers = create_worker_bundle(
        bt_worker_kind='mock',
        transcode_worker_kind='mock',
        output_hls_url=SAMPLE_HLS_URL,
        stream_root=str(stream_root),
        public_base_url=public_base_url,
    )
    bt_worker = _default_workers.bt_worker
    transcode_worker = _default_workers.transcode_worker

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        print('[gateway]', fmt % args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == '/health':
                payload: dict[str, Any] = {
                    'status': 'ok',
                    'service': 'mock-stream-gateway',
                    'sourceMode': self.source_mode,
                    'btWorkerMode': self.bt_worker_mode,
                    'transcodeWorkerMode': self.transcode_worker_mode,
                    'publicBaseUrl': self.public_base_url,
                    'streamRoot': str(self.stream_root),
                    'defaultDebugInputRef': self.default_debug_input_ref,
                    'sessionCount': len(SESSIONS),
                }
                if self.source_mode == 'mikan' and self.mikan_adapter is not None:
                    payload['sourceBaseUrl'] = self.mikan_adapter.base_url
                self._send_json(HTTPStatus.OK, payload)
                return

            if path == '/home':
                self._send_json(HTTPStatus.OK, {'items': self._home_items()})
                return

            if path == '/search':
                query = parse_qs(parsed.query).get('q', [''])[0].strip()
                self._send_json(HTTPStatus.OK, {'items': self._search_items(query)})
                return

            if path == '/workers/overview':
                self._send_json(HTTPStatus.OK, self._workers_overview())
                return

            if path == '/workers/bt/jobs':
                self._send_json(HTTPStatus.OK, {'items': self.bt_worker.list_jobs()})
                return

            if path == '/workers/transcode/jobs':
                self._send_json(HTTPStatus.OK, {'items': self.transcode_worker.list_jobs()})
                return

            if path.startswith('/streams/'):
                self._handle_stream_file(path[len('/streams/'):])
                return

            anime_match = re.fullmatch(r'/anime/([^/]+)', path)
            if anime_match:
                anime_id = anime_match.group(1)
                self._handle_anime_detail(anime_id)
                return

            session_status_match = re.fullmatch(r'/play/session/([^/]+)/status', path)
            if session_status_match:
                session_id = session_status_match.group(1)
                self._handle_session_status(session_id)
                return

            bt_job_match = re.fullmatch(r'/workers/bt/jobs/([^/]+)', path)
            if bt_job_match:
                self._handle_bt_job_status(bt_job_match.group(1))
                return

            transcode_job_match = re.fullmatch(r'/workers/transcode/jobs/([^/]+)', path)
            if transcode_job_match:
                self._handle_transcode_job_status(transcode_job_match.group(1))
                return

            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'not_found', 'path': path})
        except BrokenPipeError:
            return
        except Exception as exc:  # noqa: BLE001
            self._handle_unexpected_error('GET', path, exc)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == '/play/session':
                self._handle_create_play_session()
                return

            retry_session_match = re.fullmatch(r'/play/session/([^/]+)/retry', path)
            if retry_session_match:
                self._handle_retry_play_session(retry_session_match.group(1))
                return

            cancel_session_match = re.fullmatch(r'/play/session/([^/]+)/cancel', path)
            if cancel_session_match:
                self._handle_cancel_play_session(cancel_session_match.group(1))
                return

            if path == '/workers/bt/jobs':
                self._handle_create_bt_job()
                return

            if path == '/workers/transcode/jobs':
                self._handle_create_transcode_job()
                return

            retry_bt_match = re.fullmatch(r'/workers/bt/jobs/([^/]+)/retry', path)
            if retry_bt_match:
                self._handle_retry_bt_job(retry_bt_match.group(1))
                return

            retry_trans_match = re.fullmatch(r'/workers/transcode/jobs/([^/]+)/retry', path)
            if retry_trans_match:
                self._handle_retry_transcode_job(retry_trans_match.group(1))
                return

            cancel_bt_match = re.fullmatch(r'/workers/bt/jobs/([^/]+)/cancel', path)
            if cancel_bt_match:
                self._handle_cancel_bt_job(cancel_bt_match.group(1))
                return

            cancel_trans_match = re.fullmatch(r'/workers/transcode/jobs/([^/]+)/cancel', path)
            if cancel_trans_match:
                self._handle_cancel_transcode_job(cancel_trans_match.group(1))
                return

            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'not_found', 'path': path})
        except BrokenPipeError:
            return
        except Exception as exc:  # noqa: BLE001
            self._handle_unexpected_error('POST', path, exc)

    def _handle_unexpected_error(self, method: str, path: str, exc: Exception) -> None:
        trace = traceback.format_exc(limit=6)
        print(f'[gateway] unhandled {method} {path}: {exc}')
        print(trace)

        try:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    'error': 'internal_server_error',
                    'message': str(exc),
                    'method': method,
                    'path': path,
                },
            )
        except Exception:  # noqa: BLE001
            return

    def _handle_create_play_session(self) -> None:
        body = self._read_json_body()
        if body is None:
            return

        anime_title = str(body.get('animeTitle') or 'Unknown Anime').strip()
        episode_id = str(body.get('episodeId') or '').strip() or 'latest'
        raw_source_id = str(body.get('sourceId') or '').strip()
        source_id = self._resolve_source_id(
            source_id=raw_source_id,
            anime_title=anime_title,
        )
        print(
            '[gateway] create_session '
            f'sourceMode={self.source_mode} '
            f"animeTitle='{anime_title}' "
            f"episodeId='{episode_id}' "
            f"sourceIdRaw='{raw_source_id}' "
            f"sourceIdResolved='{source_id}'"
        )

        if not source_id:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    'error': 'invalid_request',
                    'message': 'sourceId is required and could not be resolved from animeTitle.',
                    'sourceMode': self.source_mode,
                    'animeTitle': anime_title,
                    'sourceId': raw_source_id,
                    'episodeId': episode_id,
                },
            )
            return
        debug_fail_stage = str(body.get('debugFailStage') or '').strip().lower()
        if debug_fail_stage not in {'bt', 'transcode'}:
            debug_fail_stage = ''

        debug_fail_mode = str(body.get('debugFailMode') or '').strip().lower()
        if debug_fail_mode not in {'once', 'always'}:
            debug_fail_mode = 'none'

        debug_max_retries = self._parse_int(
            body.get('debugMaxRetries'),
            default=2,
            minimum=0,
            maximum=5,
        )
        debug_input_ref = str(body.get('debugInputRef') or '').strip()
        if not debug_input_ref:
            debug_input_ref = str(self.default_debug_input_ref or '').strip()

        now_ms = int(time.time() * 1000)
        session_id = f'sess-{now_ms}-{source_id[:12] or "source"}'

        episode_meta = self._resolve_episode_meta(source_id=source_id, episode_id=episode_id)

        episode_title = ''
        magnet = ''
        torrent_url = ''
        if episode_meta:
            episode_title = str(episode_meta.get('title', '')).strip()
            magnet = str(episode_meta.get('magnet', '')).strip()
            torrent_url = str(episode_meta.get('torrentUrl', '')).strip()

        bt_job = self.bt_worker.create_job(
            session_id=session_id,
            magnet=magnet,
            torrent_url=torrent_url,
            max_retries=debug_max_retries,
            failure_mode=debug_fail_mode if debug_fail_stage == 'bt' else 'none',
        )

        now_iso = _utc_now_iso()
        session: dict[str, Any] = {
            'sessionId': session_id,
            'animeTitle': anime_title,
            'streamUrl': SAMPLE_HLS_URL,
            'source': 'mikan.tangbai.cc',
            'status': 'preparing',
            'episodeId': episode_id,
            'episodeTitle': episode_title,
            'magnet': magnet,
            'torrentUrl': torrent_url,
            'pipelineStage': f"bt:{bt_job.get('status', 'queued')}",
            'progressPercent': self._coerce_percent(bt_job.get('progressPercent', 5)),
            'statusMessage': str(bt_job.get('message', 'Session created.')),
            'btJobId': str(bt_job.get('jobId', '')),
            'transcodeJobId': '',
            'canRetry': bool(bt_job.get('canRetry', False)),
            'failedStage': '',
            'debugFailStage': debug_fail_stage,
            'debugFailMode': debug_fail_mode,
            'debugMaxRetries': debug_max_retries,
            'debugInputRef': debug_input_ref,
            'createdAt': now_iso,
            'updatedAt': now_iso,
        }

        if not session['episodeTitle']:
            session['episodeTitle'] = episode_id

        self._update_session_pipeline(session)

        with SESSIONS_LOCK:
            SESSIONS[session_id] = session

        self._send_json(HTTPStatus.OK, self._session_response(session))

    def _handle_retry_play_session(self, session_id: str) -> None:
        with SESSIONS_LOCK:
            session = SESSIONS.get(session_id)

        if session is None:
            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'session_not_found'})
            return

        current = self._update_session_pipeline(dict(session))
        if str(current.get('status', '')).lower() != 'failed':
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    'error': 'retry_not_allowed',
                    'message': 'Session is not in failed state.',
                    'session': self._session_response(current),
                },
            )
            return

        failed_stage = str(current.get('failedStage', '')).strip().lower()
        if not failed_stage:
            pipeline_stage = str(current.get('pipelineStage', '')).strip().lower()
            if pipeline_stage.startswith('bt:'):
                failed_stage = 'bt'
            elif pipeline_stage.startswith('transcode:'):
                failed_stage = 'transcode'

        retried_job: dict[str, Any] | None
        if failed_stage == 'bt':
            bt_job_id = str(current.get('btJobId', '')).strip()
            retried_job = self.bt_worker.retry_job(bt_job_id) if bt_job_id else None
            if retried_job is not None:
                current['transcodeJobId'] = ''
        elif failed_stage == 'transcode':
            transcode_job_id = str(current.get('transcodeJobId', '')).strip()
            retried_job = (
                self.transcode_worker.retry_job(transcode_job_id)
                if transcode_job_id
                else None
            )
        else:
            retried_job = None

        if retried_job is None:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    'error': 'retry_not_allowed',
                    'message': 'No retryable worker job was found.',
                    'session': self._session_response(current),
                },
            )
            return

        current['status'] = 'preparing'
        current['canRetry'] = False
        current['failedStage'] = ''
        current['statusMessage'] = str(retried_job.get('message', 'Retry queued.'))
        current['updatedAt'] = _utc_now_iso()

        updated = self._update_session_pipeline(current)
        with SESSIONS_LOCK:
            SESSIONS[session_id] = updated

        self._send_json(HTTPStatus.OK, self._session_response(updated))

    def _handle_cancel_play_session(self, session_id: str) -> None:
        with SESSIONS_LOCK:
            session = SESSIONS.get(session_id)

        if session is None:
            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'session_not_found'})
            return

        current = dict(session)
        bt_job_id = str(current.get('btJobId', '')).strip()
        transcode_job_id = str(current.get('transcodeJobId', '')).strip()

        bt_job = self.bt_worker.cancel_job(bt_job_id) if bt_job_id else None
        transcode_job = (
            self.transcode_worker.cancel_job(transcode_job_id)
            if transcode_job_id
            else None
        )

        cleanup = self._cleanup_session_stream_artifacts(
            session=current,
            transcode_job=transcode_job,
        )

        current['status'] = 'failed'
        current['pipelineStage'] = 'canceled'
        current['statusMessage'] = 'Session canceled by player exit; cleanup requested.'
        current['progressPercent'] = 0
        current['canRetry'] = False
        current['failedStage'] = ''
        current['updatedAt'] = _utc_now_iso()

        if bt_job is not None:
            current['btJobStatus'] = str(bt_job.get('status', '')).strip().lower()
        if transcode_job is not None:
            current['transcodeJobStatus'] = str(transcode_job.get('status', '')).strip().lower()

        with SESSIONS_LOCK:
            SESSIONS.pop(session_id, None)

        response_payload: dict[str, Any] = {
            'sessionId': session_id,
            'removed': True,
            'cleanup': cleanup,
            'session': self._session_response(current),
        }
        if bt_job is not None:
            response_payload['btJob'] = bt_job
        if transcode_job is not None:
            response_payload['transcodeJob'] = transcode_job

        self._send_json(HTTPStatus.OK, response_payload)

    def _cleanup_session_stream_artifacts(
        self,
        *,
        session: dict[str, Any],
        transcode_job: dict[str, Any] | None,
    ) -> dict[str, Any]:
        candidates: set[Path] = set()
        removed_paths: list[str] = []
        errors: list[str] = []

        stream_root = self.stream_root.resolve()

        session_id = str(session.get('sessionId', '')).strip()
        if session_id:
            session_dir_name = self._sanitize_stream_session_id(session_id)
            if session_dir_name:
                candidates.add((stream_root / session_dir_name).resolve())

        playlist_paths: list[str] = []
        if transcode_job is not None:
            playlist_paths.append(str(transcode_job.get('playlistPath', '')).strip())

        transcode_job_id = str(session.get('transcodeJobId', '')).strip()
        if transcode_job is None and transcode_job_id:
            latest = self.transcode_worker.get_job(transcode_job_id)
            if isinstance(latest, dict):
                playlist_paths.append(str(latest.get('playlistPath', '')).strip())

        for raw in playlist_paths:
            if not raw:
                continue
            try:
                playlist_path = Path(raw).expanduser().resolve()
            except Exception:  # noqa: BLE001
                continue

            attempt_dir = playlist_path.parent
            session_dir = attempt_dir.parent if attempt_dir != attempt_dir.parent else attempt_dir

            if self._is_path_within_root(session_dir, stream_root):
                candidates.add(session_dir)
            elif self._is_path_within_root(attempt_dir, stream_root):
                candidates.add(attempt_dir)

        for candidate in sorted(candidates, key=lambda item: len(str(item)), reverse=True):
            try:
                if not candidate.exists():
                    continue
                if not self._is_path_within_root(candidate, stream_root):
                    continue

                if candidate.is_dir():
                    shutil.rmtree(candidate)
                else:
                    candidate.unlink(missing_ok=True)

                removed_paths.append(str(candidate))
            except Exception as exc:  # noqa: BLE001
                errors.append(f'{candidate}: {exc}')

        return {
            'removedPaths': removed_paths,
            'errors': errors,
        }

    def _is_path_within_root(self, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except Exception:  # noqa: BLE001
            return False

    def _sanitize_stream_session_id(self, value: str) -> str:
        text = (value or '').strip()
        if not text:
            return ''

        sanitized = re.sub(r'[^a-zA-Z0-9_-]+', '_', text).strip('_')
        return sanitized
    def _handle_session_status(self, session_id: str) -> None:
        with SESSIONS_LOCK:
            session = SESSIONS.get(session_id)

        if session is None:
            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'session_not_found'})
            return

        updated = self._update_session_pipeline(dict(session))
        with SESSIONS_LOCK:
            SESSIONS[session_id] = updated

        self._send_json(HTTPStatus.OK, self._session_response(updated))

    def _handle_create_bt_job(self) -> None:
        body = self._read_json_body()
        if body is None:
            return

        session_id = str(body.get('sessionId') or 'manual-job').strip()
        magnet = str(body.get('magnet') or '').strip()
        torrent_url = str(body.get('torrentUrl') or '').strip()
        max_retries = self._parse_int(body.get('maxRetries'), default=2, minimum=0, maximum=5)
        failure_mode = str(body.get('failureMode') or 'none').strip().lower()

        job = self.bt_worker.create_job(
            session_id=session_id,
            magnet=magnet,
            torrent_url=torrent_url,
            max_retries=max_retries,
            failure_mode=failure_mode,
        )
        self._send_json(HTTPStatus.OK, job)

    def _handle_bt_job_status(self, job_id: str) -> None:
        job = self.bt_worker.get_job(job_id)
        if job is None:
            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'bt_job_not_found', 'jobId': job_id})
            return
        self._send_json(HTTPStatus.OK, job)

    def _handle_retry_bt_job(self, job_id: str) -> None:
        job = self.bt_worker.retry_job(job_id)
        if job is None:
            self._send_json(
                HTTPStatus.CONFLICT,
                {'error': 'retry_not_allowed', 'jobId': job_id},
            )
            return
        self._send_json(HTTPStatus.OK, job)

    def _handle_cancel_bt_job(self, job_id: str) -> None:
        job = self.bt_worker.cancel_job(job_id)
        if job is None:
            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'bt_job_not_found', 'jobId': job_id})
            return
        self._send_json(HTTPStatus.OK, job)

    def _handle_create_transcode_job(self) -> None:
        body = self._read_json_body()
        if body is None:
            return

        session_id = str(body.get('sessionId') or 'manual-job').strip()
        input_ref = str(body.get('inputRef') or '').strip()
        max_retries = self._parse_int(body.get('maxRetries'), default=2, minimum=0, maximum=5)
        failure_mode = str(body.get('failureMode') or 'none').strip().lower()

        job = self.transcode_worker.create_job(
            session_id=session_id,
            input_ref=input_ref,
            max_retries=max_retries,
            failure_mode=failure_mode,
        )

        self._send_json(HTTPStatus.OK, job)

    def _handle_transcode_job_status(self, job_id: str) -> None:
        job = self.transcode_worker.get_job(job_id)
        if job is None:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {'error': 'transcode_job_not_found', 'jobId': job_id},
            )
            return
        self._send_json(HTTPStatus.OK, job)

    def _handle_retry_transcode_job(self, job_id: str) -> None:
        job = self.transcode_worker.retry_job(job_id)
        if job is None:
            self._send_json(
                HTTPStatus.CONFLICT,
                {'error': 'retry_not_allowed', 'jobId': job_id},
            )
            return
        self._send_json(HTTPStatus.OK, job)

    def _handle_cancel_transcode_job(self, job_id: str) -> None:
        job = self.transcode_worker.cancel_job(job_id)
        if job is None:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {'error': 'transcode_job_not_found', 'jobId': job_id},
            )
            return
        self._send_json(HTTPStatus.OK, job)

    def _handle_stream_file(self, relative_path: str) -> None:
        normalized = (relative_path or '').strip().lstrip('/')
        if not normalized:
            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'stream_not_found'})
            return

        root = self.stream_root.resolve()
        target = (root / normalized).resolve()

        try:
            target.relative_to(root)
        except Exception:  # noqa: BLE001
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {'error': 'stream_access_denied', 'path': normalized},
            )
            return

        if not target.exists() or not target.is_file():
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {'error': 'stream_not_found', 'path': normalized},
            )
            return

        content_type = self._stream_content_type(target)

        try:
            content_length = target.stat().st_size
            self.send_response(int(HTTPStatus.OK))
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(content_length))
            self.end_headers()

            with target.open('rb') as file_obj:
                while True:
                    chunk = file_obj.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except BrokenPipeError:
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {'error': 'stream_read_failed', 'message': str(exc)},
            )

    def _stream_content_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == '.m3u8':
            return 'application/vnd.apple.mpegurl'
        if suffix == '.ts':
            return 'video/mp2t'
        if suffix == '.mp4':
            return 'video/mp4'

        guessed, _ = mimetypes.guess_type(path.name)
        return guessed or 'application/octet-stream'

    def _read_json_body(self) -> dict[str, Any] | None:
        transfer_encoding = str(self.headers.get('Transfer-Encoding', '') or '').lower()

        raw_body = b''
        if 'chunked' in transfer_encoding:
            raw_body = self._read_chunked_request_body()
        else:
            content_length_raw = str(self.headers.get('Content-Length', '0') or '0')
            try:
                content_length = int(content_length_raw)
            except ValueError:
                content_length = 0

            raw_body = self.rfile.read(content_length) if content_length > 0 else b''

        if not raw_body:
            raw_body = b'{}'

        try:
            body = json.loads(raw_body.decode('utf-8'))
            if not isinstance(body, dict):
                raise ValueError('body must be a JSON object')
            return body
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {'error': 'invalid_json', 'message': str(exc)},
            )
            return None

    def _read_chunked_request_body(self) -> bytes:
        chunks: list[bytes] = []

        while True:
            size_line = self.rfile.readline()
            if not size_line:
                break

            stripped = size_line.strip()
            if not stripped:
                continue

            size_token = stripped.split(b';', 1)[0]
            chunk_size = int(size_token, 16)
            if chunk_size <= 0:
                while True:
                    trailer = self.rfile.readline()
                    if trailer in {b'', b'\r\n', b'\n'}:
                        break
                break

            chunk = self.rfile.read(chunk_size)
            if chunk:
                chunks.append(chunk)

            terminator = self.rfile.read(2)
            if terminator not in {b'\r\n', b'\n', b''}:
                continue

        return b''.join(chunks)

    def _home_items(self) -> list[dict[str, Any]]:
        if self.source_mode != 'mikan' or self.mikan_adapter is None:
            return ANIME_ITEMS

        try:
            items = self.mikan_adapter.fetch_home()
            if items:
                return items
        except Exception as exc:  # noqa: BLE001
            print(f'[gateway] mikan /home fallback to mock due to error: {exc}')

        return ANIME_ITEMS

    def _search_items(self, query: str) -> list[dict[str, Any]]:
        if self.source_mode == 'mikan' and self.mikan_adapter is not None:
            try:
                return self.mikan_adapter.search(query)
            except Exception as exc:  # noqa: BLE001
                print(f'[gateway] mikan /search fallback to mock due to error: {exc}')

        lowered = query.lower().strip()
        if not lowered:
            return ANIME_ITEMS

        return [
            item
            for item in ANIME_ITEMS
            if lowered in str(item.get('title', '')).lower()
        ]

    def _handle_anime_detail(self, anime_id: str) -> None:
        if self.source_mode == 'mikan' and self.mikan_adapter is not None:
            try:
                payload = self.mikan_adapter.fetch_detail(anime_id)
                self._send_json(HTTPStatus.OK, payload)
                return
            except Exception as exc:  # noqa: BLE001
                self._send_json(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        'error': 'source_fetch_failed',
                        'message': str(exc),
                        'animeId': anime_id,
                    },
                )
                return

        anime = next((item for item in ANIME_ITEMS if item['id'] == anime_id), None)
        if anime is None:
            self._send_json(HTTPStatus.NOT_FOUND, {'error': 'anime_not_found'})
            return

        payload = {
            **anime,
            'description': 'Mock anime detail payload from local gateway.',
            'tags': ['Anime', '1080p', 'Subbed'],
            'episodes': [
                {
                    'id': anime['latestEpisodeId'],
                    'title': anime['title'],
                    'subtitle': anime['subtitle'],
                    'publishedAt': anime['publishedAt'],
                },
                {
                    'id': 'preview-01',
                    'title': f"{anime['title']} (Preview)",
                    'subtitle': '720p · 2m',
                    'publishedAt': anime['publishedAt'],
                },
            ],
        }
        self._send_json(HTTPStatus.OK, payload)

    def _resolve_source_id(self, *, source_id: str, anime_title: str) -> str:
        candidate = str(source_id or '').strip()
        if candidate:
            normalized_candidate = self._normalize_source_id_candidate(candidate)
            if normalized_candidate:
                return normalized_candidate
            return candidate

        if self.source_mode != 'mikan' or self.mikan_adapter is None:
            return ''

        normalized_title = str(anime_title or '').strip()
        if not normalized_title:
            return ''

        queries = self._build_source_lookup_queries(normalized_title)
        for query in queries:
            resolved = self._resolve_source_id_by_query(query)
            if resolved:
                print(f"[gateway] sourceId resolved via search query='{query}' -> '{resolved}'")
                return resolved

        try:
            home_items = self.mikan_adapter.fetch_home()
            resolved = self._resolve_source_id_from_items(items=home_items, queries=queries)
            if resolved:
                print(f"[gateway] sourceId resolved via home fallback -> '{resolved}'")
                return resolved
        except Exception as exc:  # noqa: BLE001
            print(f'[gateway] sourceId home fallback failed: {exc}')

        print(
            '[gateway] sourceId unresolved '
            f'sourceMode={self.source_mode} '
            f"animeTitle='{normalized_title}' "
            f'queries={queries}'
        )
        return ''

    def _normalize_source_id_candidate(self, raw: str) -> str:
        value = str(raw or '').strip()
        if not value:
            return ''

        if value.isdigit():
            return value

        match = re.search(r'/Bangumi/(\d+)', value, flags=re.IGNORECASE)
        if match is not None:
            return match.group(1)

        return value

    def _build_source_lookup_queries(self, title: str) -> list[str]:
        base = re.sub(r'\s+', ' ', title).strip()
        if not base:
            return []

        candidates = [base]

        season_trimmed = re.sub(
            r'\s*(?:s\d+|season\s*\d+|第\s*\d+\s*季)\s*$',
            '',
            base,
            flags=re.IGNORECASE,
        ).strip()
        if season_trimmed:
            candidates.append(season_trimmed)

        bracket_trimmed = re.sub(r'\s*[\[\(（【][^\]\)）】]{1,32}[\]\)）】]\s*$', '', base).strip()
        if bracket_trimmed:
            candidates.append(bracket_trimmed)

        trimmed = re.sub(
            r'\s*(?:-|_|–|—)\s*(?:ep\s*\d+|e\d+|第\s*\d+\s*[话話集]|\d{1,3})\s*$',
            '',
            base,
            flags=re.IGNORECASE,
        ).strip()
        if trimmed:
            candidates.append(trimmed)

        trimmed = re.sub(r'\s*第\s*\d+\s*[话話集]\s*$', '', base, flags=re.IGNORECASE).strip()
        if trimmed:
            candidates.append(trimmed)

        trimmed = re.sub(r'\s*\([^)]*\)\s*$', '', base).strip()
        if trimmed:
            candidates.append(trimmed)

        result: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            key = item.lower()
            if not item or key in seen:
                continue
            result.append(item)
            seen.add(key)

        return result

    def _resolve_source_id_by_query(self, query: str) -> str:
        if self.mikan_adapter is None:
            return ''

        try:
            items = self.mikan_adapter.search(query)
        except Exception as exc:  # noqa: BLE001
            print(f'[gateway] mikan source resolve failed ({query}): {exc}')
            return ''

        return self._resolve_source_id_from_items(items=items, queries=[query])

    def _resolve_source_id_from_items(
        self,
        *,
        items: list[dict[str, Any]],
        queries: list[str],
    ) -> str:
        if not isinstance(items, list) or not items:
            return ''

        query_lowers = [q.lower().strip() for q in queries if q and q.strip()]
        best_score = -1
        best_id = ''
        fallback_id = ''

        for item in items:
            if not isinstance(item, dict):
                continue

            resolved = str(item.get('id', '')).strip()
            if not resolved:
                continue

            normalized_resolved = self._normalize_source_id_candidate(resolved)
            if not normalized_resolved:
                continue

            if not fallback_id:
                fallback_id = normalized_resolved

            title = str(item.get('title', '')).strip().lower()
            score = 0
            for query_lower in query_lowers:
                score = max(
                    score,
                    self._score_source_candidate(title=title, query_lower=query_lower),
                )

            if score > best_score:
                best_score = score
                best_id = normalized_resolved

        if best_id and best_score > 0:
            return best_id

        if not query_lowers:
            return fallback_id

        return ''

    def _score_source_candidate(self, *, title: str, query_lower: str) -> int:
        if not title or not query_lower:
            return 0

        if title == query_lower:
            return 300

        if query_lower in title:
            return 200 + len(query_lower)

        if title in query_lower:
            return 150 + len(title)

        score = 0
        query_tokens = [token for token in query_lower.split(' ') if token]
        for token in query_tokens:
            if token in title:
                score += 20 + len(token)

        return score


    def _resolve_episode_meta(
        self,
        *,
        source_id: str,
        episode_id: str,
    ) -> dict[str, Any] | None:
        if self.source_mode != 'mikan' or self.mikan_adapter is None:
            return None

        try:
            return self.mikan_adapter.resolve_episode(
                anime_id=source_id,
                episode_id=episode_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(f'[gateway] mikan resolve episode failed: {exc}')
            return None


    def _resolve_transcode_input_ref(
        self,
        input_ref: str,
        *,
        bt_job: dict[str, Any],
    ) -> str:
        candidate = (input_ref or '').strip()
        if self.transcode_worker_mode != 'local_ffmpeg':
            return candidate

        candidates: list[str] = []
        if candidate:
            candidates.append(candidate)

        output_candidates_raw = bt_job.get('outputCandidates')
        if isinstance(output_candidates_raw, list):
            for raw in output_candidates_raw:
                value = str(raw or '').strip()
                if value:
                    candidates.append(value)

        bt_output_ref = str(bt_job.get('outputRef', '')).strip()
        if bt_output_ref:
            candidates.append(bt_output_ref)

        for item in candidates:
            resolved = self._resolve_local_media_input(item)
            if resolved:
                return resolved

        return candidate

    def _resolve_local_media_input(self, raw_input: str) -> str:
        value = (raw_input or '').strip()
        if not value:
            return ''

        lowered = value.lower()
        if lowered.startswith('file://'):
            value = self._file_uri_to_path(value)
            if not value:
                return ''

        if '://' in value:
            return ''

        try:
            path = Path(value).expanduser().resolve()
        except Exception:  # noqa: BLE001
            return ''

        if path.is_file():
            return str(path)

        if path.is_dir():
            preferred = self._pick_preferred_media_file(path)
            if preferred is not None:
                return str(preferred)
            return ''

        return ''

    def _file_uri_to_path(self, file_uri: str) -> str:
        try:
            parsed = urlparse(file_uri)
        except Exception:  # noqa: BLE001
            return ''

        path_text = unquote(parsed.path or '')
        netloc = str(parsed.netloc or '').strip()
        if netloc and netloc.lower() != 'localhost':
            path_text = f'//{netloc}{path_text}'

        if os.name == 'nt' and re.match(r'^/[A-Za-z]:', path_text):
            path_text = path_text[1:]

        return path_text.strip()

    def _pick_preferred_media_file(self, root: Path) -> Path | None:
        candidates: list[tuple[int, Path]] = []

        try:
            iterator = root.rglob('*')
        except Exception:  # noqa: BLE001
            return None

        for item in iterator:
            if not item.is_file():
                continue
            if item.suffix.lower() not in _TRANSCODE_INPUT_VIDEO_EXTENSIONS:
                continue

            try:
                size = int(item.stat().st_size)
            except Exception:  # noqa: BLE001
                size = 0

            candidates.append((size, item))

        if not candidates:
            return None

        candidates.sort(key=lambda entry: entry[0], reverse=True)
        return candidates[0][1]

    def _update_session_pipeline(self, session: dict[str, Any]) -> dict[str, Any]:
        session['canRetry'] = False
        session['failedStage'] = ''

        bt_job_id = str(session.get('btJobId', '')).strip()
        if not bt_job_id:
            session['status'] = 'failed'
            session['pipelineStage'] = 'failed'
            session['statusMessage'] = 'Missing bt job id.'
            session['progressPercent'] = 0
            session['updatedAt'] = _utc_now_iso()
            return session

        bt_job = self.bt_worker.get_job(bt_job_id)
        if bt_job is None:
            session['status'] = 'failed'
            session['pipelineStage'] = 'failed'
            session['statusMessage'] = 'BT job not found.'
            session['progressPercent'] = 0
            session['updatedAt'] = _utc_now_iso()
            return session

        bt_status = str(bt_job.get('status', '')).lower()
        session['btJobStatus'] = bt_status or 'unknown'
        session['btProgressPercent'] = self._coerce_percent(bt_job.get('progressPercent', 0))

        if bt_status == 'failed':
            session['status'] = 'failed'
            session['pipelineStage'] = 'bt:failed'
            session['statusMessage'] = str(bt_job.get('message', 'BT worker failed.'))
            session['progressPercent'] = min(
                89,
                self._coerce_percent(bt_job.get('progressPercent', 0)),
            )
            session['canRetry'] = bool(bt_job.get('canRetry', False))
            session['failedStage'] = 'bt'
            session['updatedAt'] = _utc_now_iso()
            return session

        if bt_status == 'canceled':
            session['status'] = 'failed'
            session['pipelineStage'] = 'bt:canceled'
            session['statusMessage'] = str(bt_job.get('message', 'BT worker canceled.'))
            session['progressPercent'] = self._coerce_percent(bt_job.get('progressPercent', 0))
            session['canRetry'] = False
            session['failedStage'] = 'bt'
            session['updatedAt'] = _utc_now_iso()
            return session

        if bt_status != 'completed':
            session['status'] = 'preparing'
            session['pipelineStage'] = f'bt:{bt_status or "queued"}'
            session['statusMessage'] = str(bt_job.get('message', 'BT worker running.'))
            session['progressPercent'] = min(
                89,
                self._coerce_percent(bt_job.get('progressPercent', 0)),
            )
            session['updatedAt'] = _utc_now_iso()
            return session

        transcode_job_id = str(session.get('transcodeJobId', '')).strip()
        if not transcode_job_id:
            debug_fail_stage = str(session.get('debugFailStage', '')).strip().lower()
            debug_fail_mode = str(session.get('debugFailMode', 'none')).strip().lower()
            debug_max_retries = self._parse_int(
                session.get('debugMaxRetries'),
                default=2,
                minimum=0,
                maximum=5,
            )

            chosen_input_ref = str(session.get('debugInputRef', '')).strip()
            if not chosen_input_ref:
                chosen_input_ref = str(bt_job.get('outputRef', '')).strip()

            resolved_input_ref = self._resolve_transcode_input_ref(
                chosen_input_ref,
                bt_job=bt_job,
            )
            final_input_ref = resolved_input_ref or chosen_input_ref
            session['resolvedInputRef'] = final_input_ref

            transcode_job = self.transcode_worker.create_job(
                session_id=str(session.get('sessionId', 'manual-job')),
                input_ref=final_input_ref,
                max_retries=debug_max_retries,
                failure_mode=debug_fail_mode if debug_fail_stage == 'transcode' else 'none',
            )
            transcode_job_id = str(transcode_job.get('jobId', '')).strip()
            session['transcodeJobId'] = transcode_job_id
        else:
            transcode_job = self.transcode_worker.get_job(transcode_job_id)

        if transcode_job is None:
            session['status'] = 'failed'
            session['pipelineStage'] = 'failed'
            session['statusMessage'] = 'Transcode job not found.'
            session['progressPercent'] = 0
            session['updatedAt'] = _utc_now_iso()
            return session

        transcode_status = str(transcode_job.get('status', '')).lower()
        session['transcodeJobStatus'] = transcode_status or 'unknown'
        session['transcodeProgressPercent'] = self._coerce_percent(
            transcode_job.get('progressPercent', 0)
        )

        if transcode_status == 'failed':
            session['status'] = 'failed'
            session['pipelineStage'] = 'transcode:failed'
            session['statusMessage'] = str(
                transcode_job.get('message', 'Transcode worker failed.')
            )
            session['progressPercent'] = min(
                99,
                max(60, self._coerce_percent(transcode_job.get('progressPercent', 0))),
            )
            session['canRetry'] = bool(transcode_job.get('canRetry', False))
            session['failedStage'] = 'transcode'
            session['updatedAt'] = _utc_now_iso()
            return session

        if transcode_status == 'canceled':
            session['status'] = 'failed'
            session['pipelineStage'] = 'transcode:canceled'
            session['statusMessage'] = str(
                transcode_job.get('message', 'Transcode worker canceled.')
            )
            session['progressPercent'] = self._coerce_percent(
                transcode_job.get('progressPercent', 0)
            )
            session['canRetry'] = False
            session['failedStage'] = 'transcode'
            session['updatedAt'] = _utc_now_iso()
            return session

        if transcode_status != 'completed':
            trans_progress = self._coerce_percent(transcode_job.get('progressPercent', 0))
            session['status'] = 'preparing'
            session['pipelineStage'] = f'transcode:{transcode_status or "queued"}'
            session['statusMessage'] = str(
                transcode_job.get('message', 'Transcode worker running.')
            )
            session['progressPercent'] = min(99, 60 + int(trans_progress * 0.4))
            session['updatedAt'] = _utc_now_iso()
            return session

        stream_url = str(transcode_job.get('streamUrl', '')).strip()
        if stream_url:
            session['streamUrl'] = stream_url

        session['status'] = 'playable'
        session['pipelineStage'] = 'playable'
        session['statusMessage'] = str(
            transcode_job.get('message', 'HLS playlist is ready.')
        )
        session['progressPercent'] = 100
        session['canRetry'] = False
        session['failedStage'] = ''
        session['updatedAt'] = _utc_now_iso()
        return session

    def _session_response(self, session: dict[str, Any]) -> dict[str, Any]:
        payload = dict(session)

        bt_job_id = str(payload.get('btJobId', '')).strip()
        if bt_job_id:
            bt_job = self.bt_worker.get_job(bt_job_id)
            if bt_job is not None:
                payload['btJob'] = bt_job

        transcode_job_id = str(payload.get('transcodeJobId', '')).strip()
        if transcode_job_id:
            transcode_job = self.transcode_worker.get_job(transcode_job_id)
            if transcode_job is not None:
                payload['transcodeJob'] = transcode_job

        return payload

    def _workers_overview(self) -> dict[str, Any]:
        bt_jobs = self.bt_worker.list_jobs()
        trans_jobs = self.transcode_worker.list_jobs()

        return {
            'bt': {
                'total': len(bt_jobs),
                'statusCounts': self._status_counts(bt_jobs),
            },
            'transcode': {
                'total': len(trans_jobs),
                'statusCounts': self._status_counts(trans_jobs),
            },
        }

    def _status_counts(self, items: list[dict[str, Any]]) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in items:
            status = str(item.get('status', 'unknown')).strip().lower() or 'unknown'
            result[status] = result.get(status, 0) + 1
        return result

    def _coerce_percent(self, raw: Any) -> int:
        try:
            value = float(raw)
        except Exception:  # noqa: BLE001
            return 0

        if value < 0:
            return 0
        if value > 100:
            return 100
        return int(round(value))

    def _parse_int(
        self,
        raw: Any,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            value = int(raw)
        except Exception:  # noqa: BLE001
            value = default

        if value < minimum:
            return minimum
        if value > maximum:
            return maximum
        return value

    def _send_json(self, status: HTTPStatus | int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(int(status))
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _utc_now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _build_default_public_base_url(host: str, port: int) -> str:
    normalized_host = (host or '').strip()
    if normalized_host in {'', '0.0.0.0', '::'}:
        normalized_host = '127.0.0.1'
    return f'http://{normalized_host}:{port}'


def main() -> None:
    parser = argparse.ArgumentParser(description='Local stream gateway server')
    parser.add_argument('--host', default='0.0.0.0', help='bind host')
    parser.add_argument('--port', type=int, default=8080, help='bind port')
    parser.add_argument(
        '--source',
        default='mock',
        choices=['mock', 'mikan'],
        help='data source mode',
    )
    parser.add_argument(
        '--bt-worker',
        default='mock',
        choices=list(SUPPORTED_BT_WORKER_KINDS),
        help='bt worker kind',
    )
    parser.add_argument(
        '--transcode-worker',
        default='mock',
        choices=list(SUPPORTED_TRANSCODE_WORKER_KINDS),
        help='transcode worker kind',
    )
    parser.add_argument(
        '--stream-root',
        default='./runtime/streams',
        help='local stream root for generated HLS assets',
    )
    parser.add_argument(
        '--public-base-url',
        default='',
        help='public base URL used in generated streamUrl (for emulator use http://10.0.2.2:8080)',
    )
    parser.add_argument(
        '--default-debug-input-ref',
        default='',
        help='default local media path used as debugInputRef when request does not provide one',
    )
    parser.add_argument(
        '--ffmpeg-bin',
        default='ffmpeg',
        help='ffmpeg executable path for local_ffmpeg worker',
    )
    parser.add_argument(
        '--ffprobe-bin',
        default='ffprobe',
        help='ffprobe executable path for local_ffmpeg worker',
    )
    parser.add_argument(
        '--probe-timeout-seconds',
        type=int,
        default=20,
        help='ffprobe timeout seconds for local_ffmpeg worker',
    )
    parser.add_argument(
        '--qbt-base-url',
        default='http://127.0.0.1:8081',
        help='qBittorrent WebUI base URL for qbittorrent BT worker',
    )
    parser.add_argument(
        '--qbt-username',
        default='admin',
        help='qBittorrent username for qbittorrent BT worker',
    )
    parser.add_argument(
        '--qbt-password',
        default='adminadmin',
        help='qBittorrent password for qbittorrent BT worker',
    )
    parser.add_argument(
        '--qbt-timeout-seconds',
        type=float,
        default=10.0,
        help='qBittorrent API timeout seconds',
    )
    parser.add_argument(
        '--qbt-playable-progress-percent',
        type=int,
        default=8,
        help='progress percent threshold treated as playable buffer for qbittorrent BT worker',
    )
    parser.add_argument(
        '--mikan-base-url',
        default='https://mikan.tangbai.cc',
        help='mikan source base URL',
    )
    parser.add_argument(
        '--mikan-timeout',
        type=float,
        default=10.0,
        help='mikan request timeout (seconds)',
    )
    parser.add_argument(
        '--mikan-cache-ttl',
        type=int,
        default=180,
        help='mikan cache ttl (seconds)',
    )
    parser.add_argument(
        '--mikan-max-home-items',
        type=int,
        default=24,
        help='max items returned by /home in mikan mode',
    )
    args = parser.parse_args()

    stream_root = Path(args.stream_root).expanduser().resolve()
    stream_root.mkdir(parents=True, exist_ok=True)

    public_base_url = args.public_base_url.strip() or _build_default_public_base_url(
        args.host,
        args.port,
    )

    GatewayHandler.source_mode = args.source
    GatewayHandler.bt_worker_mode = args.bt_worker
    GatewayHandler.transcode_worker_mode = args.transcode_worker
    GatewayHandler.stream_root = stream_root
    GatewayHandler.public_base_url = public_base_url
    GatewayHandler.default_debug_input_ref = args.default_debug_input_ref.strip()

    worker_bundle = create_worker_bundle(
        bt_worker_kind=args.bt_worker,
        transcode_worker_kind=args.transcode_worker,
        output_hls_url=SAMPLE_HLS_URL,
        stream_root=str(stream_root),
        public_base_url=public_base_url,
        ffmpeg_bin=args.ffmpeg_bin,
        ffprobe_bin=args.ffprobe_bin,
        probe_timeout_seconds=args.probe_timeout_seconds,
        qbt_base_url=args.qbt_base_url,
        qbt_username=args.qbt_username,
        qbt_password=args.qbt_password,
        qbt_timeout_seconds=args.qbt_timeout_seconds,
        qbt_playable_progress_percent=args.qbt_playable_progress_percent,
    )
    GatewayHandler.bt_worker = worker_bundle.bt_worker
    GatewayHandler.transcode_worker = worker_bundle.transcode_worker

    if args.source == 'mikan':
        GatewayHandler.mikan_adapter = MikanSourceAdapter(
            base_url=args.mikan_base_url,
            request_timeout=args.mikan_timeout,
            cache_ttl_seconds=args.mikan_cache_ttl,
            max_home_items=args.mikan_max_home_items,
        )

    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print(f'[gateway] listening on http://{args.host}:{args.port}')
    print(f'[gateway] source mode: {args.source}')
    print(f'[gateway] bt worker mode: {args.bt_worker}')
    print(f'[gateway] transcode worker mode: {args.transcode_worker}')
    if args.bt_worker == 'qbittorrent':
        print(f'[gateway] qBittorrent base: {args.qbt_base_url}')
    print(f'[gateway] stream root: {stream_root}')
    print(f'[gateway] public base url: {public_base_url}')
    if args.default_debug_input_ref.strip():
        print(f'[gateway] default debug input ref: {args.default_debug_input_ref.strip()}')
    if args.source == 'mikan':
        print(f'[gateway] source base: {args.mikan_base_url}')
    print('[gateway] endpoints: /health /home /search /anime/{id} /play/session')
    print('[gateway] session control: /play/session/{id}/status /play/session/{id}/retry /play/session/{id}/cancel')
    print('[gateway] worker endpoints: /workers/overview /workers/bt/jobs /workers/transcode/jobs')
    print('[gateway] stream endpoints: /streams/{session}/{attempt}/index.m3u8')
    print(f'[gateway] sample stream: {SAMPLE_HLS_URL}')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print('[gateway] stopped')


if __name__ == '__main__':
    main()


























