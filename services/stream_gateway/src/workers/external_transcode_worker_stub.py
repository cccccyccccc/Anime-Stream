"""External transcode worker stub.

Placeholder implementation that mimics remote transcode queue handoff. It
exists to lock the gateway contract ahead of real ffmpeg worker integration.
"""

from __future__ import annotations

import threading
import time
from typing import Any

_TERMINAL_STATES = {'completed', 'failed', 'canceled'}


class ExternalTranscodeWorkerStub:
    """Simulates an external transcode worker handoff, then fails as pending integration."""

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
        del max_retries, failure_mode

        now_ms = int(time.time() * 1000)
        prefix = ''.join(ch for ch in session_id if ch.isalnum())[:10] or 'session'
        job_id = f'trans-ext-{now_ms}-{prefix}'
        created_at = time.time()

        base = {
            'jobId': job_id,
            'sessionId': session_id,
            'source': 'transcode-worker-external-stub',
            'status': 'queued',
            'progressPercent': 0,
            'message': 'Queued for external transcode worker dispatch.',
            'createdAt': self._to_iso(created_at),
            'updatedAt': self._to_iso(created_at),
            'inputRef': input_ref,
            'attempt': 0,
            'maxRetries': 0,
            'retryCount': 0,
            'canRetry': False,
            'failureMode': 'none',
            'expectedStreamUrl': self._output_hls_url,
        }

        wrapper = {
            'createdAtEpoch': created_at,
            'base': base,
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
        del job_id
        return None

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
            base['message'] = 'External transcode worker request canceled.'
            base['canRetry'] = False
            base['updatedAt'] = self._to_iso(time.time())
            wrapper['base'] = base
            wrapper['terminal'] = True
            return dict(base)

    def _evaluate_job_locked(self, wrapper: dict[str, Any]) -> dict[str, Any]:
        base = dict(wrapper.get('base', {}))
        status = str(base.get('status', '')).lower()
        if wrapper.get('terminal') or status in _TERMINAL_STATES:
            wrapper['base'] = base
            return dict(base)

        elapsed = max(0.0, time.time() - float(wrapper.get('createdAtEpoch', time.time())))

        if elapsed < 1.0:
            base['status'] = 'queued'
            base['progressPercent'] = 5
            base['message'] = 'Queued for external transcode worker dispatch.'
        elif elapsed < 2.5:
            base['status'] = 'dispatching'
            base['progressPercent'] = 20
            base['message'] = 'Dispatching transcode task to external queue.'
        else:
            base['status'] = 'failed'
            base['progressPercent'] = 20
            base['message'] = 'External transcode worker is not integrated yet.'
            base['errorCode'] = 'TRANSCODE_EXTERNAL_STUB_NOT_IMPLEMENTED'
            base['canRetry'] = False
            wrapper['terminal'] = True

        base['updatedAt'] = self._to_iso(time.time())
        wrapper['base'] = base
        return dict(base)

    def _to_iso(self, epoch_seconds: float) -> str:
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(epoch_seconds))
