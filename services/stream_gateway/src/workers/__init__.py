"""Worker implementations and contracts for stream gateway."""

from workers.contracts import BtWorkerContract, TranscodeWorkerContract
from workers.external_bt_worker_stub import ExternalBtWorkerStub
from workers.external_transcode_worker_stub import ExternalTranscodeWorkerStub
from workers.local_ffmpeg_transcode_worker import LocalFfmpegTranscodeWorker
from workers.mock_bt_worker import MockBtWorker
from workers.mock_transcode_worker import MockTranscodeWorker
from workers.qbittorrent_bt_worker import QbittorrentBtWorker
from workers.qbittorrent_client import (
    QbittorrentApiError,
    QbittorrentClient,
    QbittorrentConfig,
)
from workers.worker_factory import (
    SUPPORTED_BT_WORKER_KINDS,
    SUPPORTED_TRANSCODE_WORKER_KINDS,
    SUPPORTED_WORKER_KINDS,
    WorkerBundle,
    create_worker_bundle,
)

__all__ = [
    'BtWorkerContract',
    'TranscodeWorkerContract',
    'MockBtWorker',
    'MockTranscodeWorker',
    'ExternalBtWorkerStub',
    'ExternalTranscodeWorkerStub',
    'LocalFfmpegTranscodeWorker',
    'QbittorrentApiError',
    'QbittorrentClient',
    'QbittorrentConfig',
    'QbittorrentBtWorker',
    'SUPPORTED_BT_WORKER_KINDS',
    'SUPPORTED_TRANSCODE_WORKER_KINDS',
    'SUPPORTED_WORKER_KINDS',
    'WorkerBundle',
    'create_worker_bundle',
]
