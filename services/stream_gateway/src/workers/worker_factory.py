"""Worker factory for gateway.

Default worker kinds are `mock`. Additional kinds allow stepping from simulation
into local process execution without changing gateway orchestration flow.
"""

from __future__ import annotations

from dataclasses import dataclass

from workers.contracts import BtWorkerContract, TranscodeWorkerContract
from workers.external_bt_worker_stub import ExternalBtWorkerStub
from workers.external_transcode_worker_stub import ExternalTranscodeWorkerStub
from workers.local_ffmpeg_transcode_worker import LocalFfmpegTranscodeWorker
from workers.mock_bt_worker import MockBtWorker
from workers.mock_transcode_worker import MockTranscodeWorker
from workers.qbittorrent_bt_worker import QbittorrentBtWorker

WorkerKind = str
SUPPORTED_BT_WORKER_KINDS: tuple[str, ...] = (
    'mock',
    'external_stub',
    'qbittorrent',
)
SUPPORTED_TRANSCODE_WORKER_KINDS: tuple[str, ...] = (
    'mock',
    'external_stub',
    'local_ffmpeg',
)
SUPPORTED_WORKER_KINDS: tuple[str, ...] = tuple(
    sorted(set(SUPPORTED_BT_WORKER_KINDS + SUPPORTED_TRANSCODE_WORKER_KINDS))
)


@dataclass(frozen=True)
class WorkerBundle:
    bt_worker: BtWorkerContract
    transcode_worker: TranscodeWorkerContract


def create_worker_bundle(
    *,
    bt_worker_kind: WorkerKind,
    transcode_worker_kind: WorkerKind,
    output_hls_url: str,
    stream_root: str,
    public_base_url: str,
    ffmpeg_bin: str = 'ffmpeg',
    ffprobe_bin: str = 'ffprobe',
    probe_timeout_seconds: int = 20,
    qbt_base_url: str = 'http://127.0.0.1:8081',
    qbt_username: str = 'admin',
    qbt_password: str = 'adminadmin',
    qbt_timeout_seconds: float = 10.0,
    qbt_playable_progress_percent: int = 8,
) -> WorkerBundle:
    bt_worker = _create_bt_worker(
        bt_worker_kind,
        qbt_base_url=qbt_base_url,
        qbt_username=qbt_username,
        qbt_password=qbt_password,
        qbt_timeout_seconds=qbt_timeout_seconds,
        qbt_playable_progress_percent=qbt_playable_progress_percent,
    )
    transcode_worker = _create_transcode_worker(
        transcode_worker_kind,
        output_hls_url=output_hls_url,
        stream_root=stream_root,
        public_base_url=public_base_url,
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_bin=ffprobe_bin,
        probe_timeout_seconds=probe_timeout_seconds,
    )

    return WorkerBundle(
        bt_worker=bt_worker,
        transcode_worker=transcode_worker,
    )


def _create_bt_worker(
    kind: WorkerKind,
    *,
    qbt_base_url: str,
    qbt_username: str,
    qbt_password: str,
    qbt_timeout_seconds: float,
    qbt_playable_progress_percent: int,
) -> BtWorkerContract:
    normalized = _normalize_kind(
        kind,
        supported=SUPPORTED_BT_WORKER_KINDS,
        kind_label='bt',
    )
    if normalized == 'mock':
        return MockBtWorker()
    if normalized == 'external_stub':
        return ExternalBtWorkerStub()
    if normalized == 'qbittorrent':
        return QbittorrentBtWorker(
            base_url=qbt_base_url,
            username=qbt_username,
            password=qbt_password,
            timeout_seconds=qbt_timeout_seconds,
            playable_progress_percent=qbt_playable_progress_percent,
        )

    raise ValueError(f'Unsupported bt worker kind: {kind}')


def _create_transcode_worker(
    kind: WorkerKind,
    *,
    output_hls_url: str,
    stream_root: str,
    public_base_url: str,
    ffmpeg_bin: str,
    ffprobe_bin: str,
    probe_timeout_seconds: int,
) -> TranscodeWorkerContract:
    normalized = _normalize_kind(
        kind,
        supported=SUPPORTED_TRANSCODE_WORKER_KINDS,
        kind_label='transcode',
    )
    if normalized == 'mock':
        return MockTranscodeWorker(output_hls_url=output_hls_url)
    if normalized == 'external_stub':
        return ExternalTranscodeWorkerStub(output_hls_url=output_hls_url)
    if normalized == 'local_ffmpeg':
        return LocalFfmpegTranscodeWorker(
            output_hls_url=output_hls_url,
            stream_root=stream_root,
            public_base_url=public_base_url,
            ffmpeg_bin=ffmpeg_bin,
            ffprobe_bin=ffprobe_bin,
            probe_timeout_seconds=probe_timeout_seconds,
        )

    raise ValueError(f'Unsupported transcode worker kind: {kind}')


def _normalize_kind(
    kind: WorkerKind,
    *,
    supported: tuple[str, ...],
    kind_label: str,
) -> str:
    value = (kind or '').strip().lower()
    if value in supported:
        return value

    supported_text = ', '.join(supported)
    raise ValueError(
        f'Unsupported {kind_label} worker kind: {kind}. Supported: {supported_text}',
    )
