"""Local ffmpeg-based transcode worker.

This worker runs ffprobe/ffmpeg as local subprocesses and outputs HLS files
under a configurable stream root. It is intended as a practical bridge between
mock simulation and a future production worker queue.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

_TERMINAL_STATES = {'completed', 'failed', 'canceled'}


class LocalFfmpegTranscodeWorker:
    """Runs local ffprobe + ffmpeg jobs and exposes queue-like controls."""

    def __init__(
        self,
        *,
        output_hls_url: str,
        stream_root: str,
        public_base_url: str,
        ffmpeg_bin: str = 'ffmpeg',
        ffprobe_bin: str = 'ffprobe',
        probe_timeout_seconds: int = 20,
    ) -> None:
        self._output_hls_url = output_hls_url.strip()
        self._stream_root = Path(stream_root).expanduser().resolve()
        self._public_base_url = public_base_url.rstrip('/')
        self._ffmpeg_bin = ffmpeg_bin
        self._ffprobe_bin = ffprobe_bin
        self._probe_timeout_seconds = max(5, int(probe_timeout_seconds))

        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

        self._stream_root.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        *,
        session_id: str,
        input_ref: str,
        max_retries: int = 2,
        failure_mode: str = 'none',
    ) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        prefix = ''.join(ch for ch in session_id if ch.isalnum())[:10] or 'session'
        job_id = f'trans-local-{now_ms}-{prefix}'
        created_at = time.time()

        normalized_max_retries = max(0, int(max_retries))
        normalized_failure_mode = (failure_mode or '').strip().lower()
        if normalized_failure_mode not in {'none', 'once', 'always'}:
            normalized_failure_mode = 'none'

        base_job = {
            'jobId': job_id,
            'sessionId': session_id,
            'source': 'local-ffmpeg-worker',
            'status': 'queued',
            'progressPercent': 0,
            'message': 'Queued for local ffmpeg pipeline.',
            'createdAt': self._to_iso(created_at),
            'updatedAt': self._to_iso(created_at),
            'inputRef': input_ref,
            'attempt': 0,
            'maxRetries': normalized_max_retries,
            'retryCount': 0,
            'canRetry': normalized_max_retries > 0,
            'failureMode': normalized_failure_mode,
            'workerKind': 'local_ffmpeg',
            'streamRoot': str(self._stream_root),
        }

        wrapper = {
            'base': base_job,
            'attempt': 0,
            'maxRetries': normalized_max_retries,
            'terminal': False,
            'cancelRequested': False,
            'process': None,
            'thread': None,
        }

        with self._lock:
            self._jobs[job_id] = wrapper
            self._start_job_locked(job_id)
            return dict(wrapper['base'])

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None
            return dict(wrapper['base'])

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            snapshots = [dict(wrapper['base']) for wrapper in self._jobs.values()]

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
                base['message'] = 'Retry limit reached for local ffmpeg worker.'
                base['updatedAt'] = self._to_iso(time.time())
                wrapper['base'] = base
                wrapper['terminal'] = True
                return dict(base)

            next_attempt = attempt + 1
            wrapper['attempt'] = next_attempt
            wrapper['terminal'] = False
            wrapper['cancelRequested'] = False
            wrapper['process'] = None

            base['status'] = 'queued'
            base['progressPercent'] = 0
            base['message'] = f'Retry attempt {next_attempt} queued.'
            base['attempt'] = next_attempt
            base['retryCount'] = next_attempt
            base['canRetry'] = next_attempt < max_retries
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base

            self._start_job_locked(job_id)
            return dict(base)

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        process: subprocess.Popen[str] | None = None

        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None

            base = wrapper['base']
            status = str(base.get('status', '')).lower()
            if status in _TERMINAL_STATES:
                return dict(base)

            wrapper['cancelRequested'] = True
            process = wrapper.get('process')
            base['status'] = 'canceling'
            base['message'] = 'Cancel requested for local ffmpeg worker.'
            base['canRetry'] = False
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base

        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:  # noqa: BLE001
                pass

        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None
            return dict(wrapper['base'])

    def _start_job_locked(self, job_id: str) -> None:
        wrapper = self._jobs.get(job_id)
        if wrapper is None:
            return

        thread = threading.Thread(
            target=self._run_job,
            args=(job_id,),
            daemon=True,
        )
        wrapper['thread'] = thread
        thread.start()

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return

            base = wrapper['base']
            base['status'] = 'probing'
            base['progressPercent'] = 10
            base['message'] = 'Running ffprobe metadata scan.'
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base

        input_ref, session_id, attempt = self._snapshot_job_context(job_id)
        if input_ref is None or session_id is None or attempt is None:
            return

        try:
            input_path = self._resolve_input_path(input_ref)
        except Exception as exc:  # noqa: BLE001
            self._mark_failed(
                job_id,
                message=f'Unsupported inputRef: {exc}',
                error_code='TRANSCODE_INPUT_NOT_SUPPORTED',
            )
            return

        if not input_path.exists() or not input_path.is_file():
            self._mark_failed(
                job_id,
                message=f'Input media file not found: {input_path}',
                error_code='TRANSCODE_INPUT_NOT_FOUND',
            )
            return

        probe_result = self._run_ffprobe(input_path)
        if probe_result is not None:
            error_code, message = probe_result
            self._mark_failed(job_id, message=message, error_code=error_code)
            return

        session_dir = self._sanitize_path_segment(session_id)
        attempt_dir = f'attempt_{attempt}'
        output_dir = self._stream_root / session_dir / attempt_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        playlist_path = output_dir / 'index.m3u8'
        segment_pattern = output_dir / 'segment_%05d.ts'
        ffmpeg_log = output_dir / 'ffmpeg.log'

        relative_playlist = f'{session_dir}/{attempt_dir}/index.m3u8'
        stream_url = self._build_stream_url(relative_playlist)

        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return

            base = wrapper['base']
            base['status'] = 'segmenting'
            base['progressPercent'] = 35
            base['message'] = 'Transcoding media and generating HLS segments.'
            base['playlistPath'] = str(playlist_path)
            base['streamPath'] = f"/streams/{relative_playlist.replace(os.sep, '/')}"
            base['streamUrl'] = stream_url
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base

        command = [
            self._ffmpeg_bin,
            '-y',
            '-i',
            str(input_path),
            '-map',
            '0:v:0',
            '-map',
            '0:a?',
            '-c:v',
            'libx264',
            '-preset',
            'veryfast',
            '-g',
            '48',
            '-keyint_min',
            '48',
            '-sc_threshold',
            '0',
            '-c:a',
            'aac',
            '-b:a',
            '128k',
            '-hls_time',
            '4',
            '-hls_playlist_type',
            'vod',
            '-hls_segment_filename',
            str(segment_pattern),
            str(playlist_path),
        ]

        process: subprocess.Popen[str] | None = None
        start_epoch = time.time()
        try:
            with ffmpeg_log.open('w', encoding='utf-8') as log_file:
                process = subprocess.Popen(
                    command,
                    stdout=log_file,
                    stderr=log_file,
                    text=True,
                )
                with self._lock:
                    wrapper = self._jobs.get(job_id)
                    if wrapper is None:
                        return
                    wrapper['process'] = process

                while process.poll() is None:
                    if self._is_cancel_requested(job_id):
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except Exception:  # noqa: BLE001
                            process.kill()
                        self._mark_canceled(job_id, 'Local ffmpeg worker canceled.')
                        return

                    elapsed = max(0.0, time.time() - start_epoch)
                    progress = min(95, 40 + int(elapsed * 3))
                    self._update_running_progress(
                        job_id,
                        progress=progress,
                        message='ffmpeg is encoding and packaging HLS output.',
                    )
                    time.sleep(0.5)

                return_code = int(process.returncode or 0)
                if return_code != 0:
                    log_tail = self._tail_text(ffmpeg_log, max_chars=1800)
                    self._mark_failed(
                        job_id,
                        message='ffmpeg failed. ' + (log_tail or 'See ffmpeg log.'),
                        error_code='FFMPEG_FAILED',
                    )
                    return

                if not playlist_path.exists():
                    self._mark_failed(
                        job_id,
                        message='ffmpeg finished but playlist was not generated.',
                        error_code='FFMPEG_OUTPUT_MISSING',
                    )
                    return

                self._mark_completed(
                    job_id,
                    stream_url=stream_url,
                    playlist_path=playlist_path,
                )
        except FileNotFoundError:
            self._mark_failed(
                job_id,
                message='ffmpeg binary not found. Configure --ffmpeg-bin.',
                error_code='FFMPEG_NOT_FOUND',
            )
        except Exception as exc:  # noqa: BLE001
            self._mark_failed(
                job_id,
                message=f'Local ffmpeg worker exception: {exc}',
                error_code='FFMPEG_WORKER_EXCEPTION',
            )
        finally:
            with self._lock:
                wrapper = self._jobs.get(job_id)
                if wrapper is not None:
                    wrapper['process'] = None

    def _snapshot_job_context(self, job_id: str) -> tuple[str | None, str | None, int | None]:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None, None, None

            base = wrapper['base']
            input_ref = str(base.get('inputRef', '')).strip()
            session_id = str(base.get('sessionId', '')).strip()
            attempt = int(wrapper.get('attempt', 0))
            return input_ref, session_id, attempt

    def _run_ffprobe(self, input_path: Path) -> tuple[str, str] | None:
        command = [
            self._ffprobe_bin,
            '-v',
            'error',
            '-show_entries',
            'format=duration',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            str(input_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._probe_timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            return (
                'FFPROBE_NOT_FOUND',
                'ffprobe binary not found. Configure --ffprobe-bin.',
            )
        except subprocess.TimeoutExpired:
            return (
                'FFPROBE_TIMEOUT',
                f'ffprobe timed out after {self._probe_timeout_seconds}s.',
            )
        except Exception as exc:  # noqa: BLE001
            return ('FFPROBE_EXCEPTION', f'ffprobe failed unexpectedly: {exc}')

        if int(result.returncode or 0) != 0:
            stderr_text = (result.stderr or '').strip()
            return ('FFPROBE_FAILED', f'ffprobe failed: {stderr_text or "unknown error"}')

        return None

    def _resolve_input_path(self, input_ref: str) -> Path:
        value = (input_ref or '').strip()
        if not value:
            raise ValueError('inputRef is empty')

        lowered = value.lower()
        if lowered.startswith('file://'):
            parsed = urlparse(value)
            path_text = unquote(parsed.path or '')
            if parsed.netloc and parsed.netloc not in {'', 'localhost'}:
                path_text = f'//{parsed.netloc}{path_text}'

            if os.name == 'nt' and re.match(r'^/[A-Za-z]:', path_text):
                path_text = path_text[1:]
            return Path(path_text).expanduser().resolve()

        if '://' in value:
            raise ValueError('only local file paths or file:// URIs are supported')

        return Path(value).expanduser().resolve()

    def _build_stream_url(self, relative_playlist: str) -> str:
        normalized = relative_playlist.replace('\\', '/').lstrip('/')
        if self._public_base_url:
            return f'{self._public_base_url}/streams/{normalized}'
        if self._output_hls_url:
            return self._output_hls_url
        return f'/streams/{normalized}'

    def _is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return False
            return bool(wrapper.get('cancelRequested', False))

    def _update_running_progress(self, job_id: str, *, progress: int, message: str) -> None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return

            base = wrapper['base']
            status = str(base.get('status', '')).lower()
            if status in _TERMINAL_STATES:
                return

            base['status'] = 'segmenting'
            base['progressPercent'] = max(0, min(100, int(progress)))
            base['message'] = message
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base

    def _mark_completed(self, job_id: str, *, stream_url: str, playlist_path: Path) -> None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return

            base = wrapper['base']
            base['status'] = 'completed'
            base['progressPercent'] = 100
            base['message'] = 'Local ffmpeg worker produced playable HLS.'
            base['streamUrl'] = stream_url
            base['playlistPath'] = str(playlist_path)
            base['canRetry'] = False
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base
            wrapper['terminal'] = True
            wrapper['cancelRequested'] = False

    def _mark_canceled(self, job_id: str, message: str) -> None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return

            base = wrapper['base']
            base['status'] = 'canceled'
            base['message'] = message
            base['canRetry'] = False
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base
            wrapper['terminal'] = True
            wrapper['cancelRequested'] = False

    def _mark_failed(self, job_id: str, *, message: str, error_code: str) -> None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return

            base = wrapper['base']
            attempt = int(wrapper.get('attempt', 0))
            max_retries = int(wrapper.get('maxRetries', 0))

            base['status'] = 'failed'
            base['progressPercent'] = max(0, min(100, int(base.get('progressPercent', 0))))
            base['message'] = message
            base['errorCode'] = error_code
            base['canRetry'] = attempt < max_retries
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base
            wrapper['terminal'] = True
            wrapper['cancelRequested'] = False

    def _sanitize_path_segment(self, value: str) -> str:
        text = (value or '').strip()
        if not text:
            return 'session'

        sanitized = re.sub(r'[^a-zA-Z0-9_-]+', '_', text).strip('_')
        return sanitized or 'session'

    def _tail_text(self, path: Path, *, max_chars: int) -> str:
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:  # noqa: BLE001
            return ''
        if len(text) <= max_chars:
            return text.strip()
        return text[-max_chars:].strip()

    def _to_iso(self, epoch_seconds: float) -> str:
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(epoch_seconds))
