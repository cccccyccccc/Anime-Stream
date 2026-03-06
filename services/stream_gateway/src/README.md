# src modules

Current modules:
- `source_adapter/mikan_source.py`: mikan.tangbai.cc parser (home/search/detail)
- `workers/contracts.py`: worker contracts used by gateway orchestration
- `workers/worker_factory.py`: worker bundle creation (BT: `mock`/`external_stub`/`qbittorrent`; transcode: `mock`/`external_stub`/`local_ffmpeg`)
- `workers/mock_bt_worker.py`: BT worker timeline simulation + retry/cancel/list
- `workers/mock_transcode_worker.py`: transcode worker timeline simulation + retry/cancel/list
- `workers/external_bt_worker_stub.py`: placeholder for real external BT worker integration
- `workers/external_transcode_worker_stub.py`: placeholder for real external transcode integration
- `workers/local_ffmpeg_transcode_worker.py`: local ffprobe+ffmpeg HLS worker (file input)
- `workers/qbittorrent_client.py`: stdlib-only qBittorrent Web API client
- `workers/qbittorrent_bt_worker.py`: qBittorrent-backed BT worker with playable threshold + output file candidates
- `mock_gateway.py`: local API server with `--source mock|mikan`, worker mode args, and `/streams/*` delivery endpoint

Planned modules:
- `bt_worker`: real torrent session and sequential download strategy
- `transcode_worker`: production queue and fault recovery
- `delivery`: advanced HLS session orchestration and cache policy
