"""Worker contracts used by gateway orchestration.

These protocols isolate gateway business flow from concrete worker
implementations, so mock workers can be replaced by real queue workers later.
"""

from __future__ import annotations

from typing import Any, Protocol


class BtWorkerContract(Protocol):
    """Contract for BT download workers."""

    def create_job(
        self,
        *,
        session_id: str,
        magnet: str = '',
        torrent_url: str = '',
        max_retries: int = 2,
        failure_mode: str = 'none',
    ) -> dict[str, Any]: ...

    def get_job(self, job_id: str) -> dict[str, Any] | None: ...

    def list_jobs(self) -> list[dict[str, Any]]: ...

    def retry_job(self, job_id: str) -> dict[str, Any] | None: ...

    def cancel_job(self, job_id: str) -> dict[str, Any] | None: ...


class TranscodeWorkerContract(Protocol):
    """Contract for transcode workers."""

    def create_job(
        self,
        *,
        session_id: str,
        input_ref: str,
        max_retries: int = 2,
        failure_mode: str = 'none',
    ) -> dict[str, Any]: ...

    def get_job(self, job_id: str) -> dict[str, Any] | None: ...

    def list_jobs(self) -> list[dict[str, Any]]: ...

    def retry_job(self, job_id: str) -> dict[str, Any] | None: ...

    def cancel_job(self, job_id: str) -> dict[str, Any] | None: ...
