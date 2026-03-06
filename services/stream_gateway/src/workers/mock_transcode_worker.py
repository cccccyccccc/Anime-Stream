"""Mock transcode worker for local stream gateway.

Provides a deterministic timeline, plus retry/cancel/list operations to model a
real queue worker contract.
"""

from __future__ import annotations

import threading
import time
from typing import Any

_TERMINAL_STATES = {'completed', 'failed', 'canceled'}


class MockTranscodeWorker:
    """Simulates transcode-to-HLS pipeline timeline."""

    def __init__(self, *, output_hls_url: str) -> None:
        self._output_hls_url = output_hls_url
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

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
        job_id = f'trans-{now_ms}-{prefix}'
        created_at = time.time()

        normalized_failure_mode = self._normalize_failure_mode(failure_mode)
        normalized_max_retries = max(0, int(max_retries))

        base_job = {
            'jobId': job_id,
            'sessionId': session_id,
            'source': 'transcode-worker',
            'status': 'queued',
            'progressPercent': 0,
            'message': 'Queued for ffprobe.',
            'createdAt': self._to_iso(created_at),
            'updatedAt': self._to_iso(created_at),
            'inputRef': input_ref,
            'attempt': 0,
            'maxRetries': normalized_max_retries,
            'retryCount': 0,
            'canRetry': normalized_max_retries > 0,
            'failureMode': normalized_failure_mode,
        }

        wrapper = {
            'createdAtEpoch': created_at,
            'base': base_job,
            'attempt': 0,
            'maxRetries': normalized_max_retries,
            'failureMode': normalized_failure_mode,
            'failedAttempts': 0,
            'terminal': False,
        }

        with self._lock:
            self._jobs[job_id] = wrapper
            return self._evaluate_job_locked(wrapper)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None
            return self._evaluate_job_locked(wrapper)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            snapshots = [self._evaluate_job_locked(wrapper) for wrapper in self._jobs.values()]

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

            base = wrapper.get('base', {})
            status = str(base.get('status', '')).lower()
            if status != 'failed':
                return None

            attempt = int(wrapper.get('attempt', 0))
            max_retries = int(wrapper.get('maxRetries', 0))
            if attempt >= max_retries:
                base['canRetry'] = False
                base['message'] = 'Retry limit reached for transcode worker.'
                base['updatedAt'] = self._to_iso(time.time())
                wrapper['base'] = base
                wrapper['terminal'] = True
                return dict(base)

            wrapper['attempt'] = attempt + 1
            wrapper['terminal'] = False
            wrapper['createdAtEpoch'] = time.time()

            base['status'] = 'queued'
            base['progressPercent'] = 0
            base['message'] = f"Retry attempt {wrapper['attempt']} queued."
            base['attempt'] = wrapper['attempt']
            base['retryCount'] = wrapper['attempt']
            base['canRetry'] = wrapper['attempt'] < max_retries
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base

            return dict(base)

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            wrapper = self._jobs.get(job_id)
            if wrapper is None:
                return None

            base = wrapper.get('base', {})
            status = str(base.get('status', '')).lower()
            if status in _TERMINAL_STATES:
                return dict(base)

            base['status'] = 'canceled'
            base['progressPercent'] = int(base.get('progressPercent', 0))
            base['message'] = 'Transcode job canceled by request.'
            base['canRetry'] = False
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base
            wrapper['terminal'] = True

            return dict(base)

    def _evaluate_job_locked(self, wrapper: dict[str, Any]) -> dict[str, Any]:
        created_at_epoch = float(wrapper.get('createdAtEpoch', time.time()))
        elapsed = max(0.0, time.time() - created_at_epoch)

        base: dict[str, Any] = dict(wrapper.get('base', {}))
        current_status = str(base.get('status', '')).lower()

        if wrapper.get('terminal') or current_status in _TERMINAL_STATES:
            wrapper['base'] = base
            return dict(base)

        if elapsed < 1.0:
            status = 'queued'
            progress = 5
            message = 'Queued for ffprobe.'
        elif elapsed < 2.5:
            status = 'probing'
            progress = 20
            message = 'Running ffprobe metadata scan.'
        elif elapsed < 4.5:
            status = 'segmenting'
            progress = 64
            message = 'Encoding and segmenting HLS chunks.'
        elif elapsed < 6.5:
            status = 'packaging'
            progress = 88
            message = 'Writing playlists and finalizing manifests.'
        else:
            status = 'completed'
            progress = 100
            message = 'Transcode worker produced playable HLS.'

        failure_mode = self._normalize_failure_mode(str(wrapper.get('failureMode', 'none')))
        should_fail = False
        if status in {'segmenting', 'packaging'}:
            if failure_mode == 'always':
                should_fail = True
            elif failure_mode == 'once' and int(wrapper.get('failedAttempts', 0)) == 0:
                should_fail = True

        if should_fail:
            status = 'failed'
            progress = 61
            message = 'Transcode worker simulated encoder failure.'
            wrapper['failedAttempts'] = int(wrapper.get('failedAttempts', 0)) + 1

        base['status'] = status
        base['progressPercent'] = progress
        base['message'] = message
        base['attempt'] = int(wrapper.get('attempt', 0))
        base['retryCount'] = int(wrapper.get('attempt', 0))
        base['maxRetries'] = int(wrapper.get('maxRetries', 0))
        base['canRetry'] = base['attempt'] < base['maxRetries']
        base['failureMode'] = failure_mode
        base['updatedAt'] = self._to_iso(time.time())

        if status == 'completed':
            base['streamUrl'] = self._output_hls_url
            base['playlistPath'] = f"/hls/{base.get('sessionId', 'session')}/index.m3u8"
            wrapper['terminal'] = True
        elif status == 'failed':
            base['errorCode'] = 'TRANSCODE_SIMULATED_FAILURE'
            wrapper['terminal'] = True

        wrapper['base'] = base
        return dict(base)

    def _normalize_failure_mode(self, raw: str) -> str:
        value = (raw or '').strip().lower()
        if value in {'once', 'always'}:
            return value
        return 'none'

    def _to_iso(self, epoch_seconds: float) -> str:
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(epoch_seconds))
