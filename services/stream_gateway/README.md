# stream_gateway

Skeleton for torrent-to-stream backend service.

## Quick start

Mock source mode (fully local static payload):

```powershell
Set-Location 'D:\Codes_Works\Projects\Project9_animation\services\stream_gateway'
python .\src\mock_gateway.py --host 0.0.0.0 --port 8080 --source mock
```

Mikan source mode (list/detail from `https://mikan.tangbai.cc`) + mock workers:

```powershell
Set-Location 'D:\Codes_Works\Projects\Project9_animation\services\stream_gateway'
python .\src\mock_gateway.py --host 0.0.0.0 --port 8080 --source mikan --bt-worker mock --transcode-worker mock
```

Mikan mode + local ffmpeg transcode worker:

```powershell
Set-Location 'D:\Codes_Works\Projects\Project9_animation\services\stream_gateway'
python .\src\mock_gateway.py --host 0.0.0.0 --port 8080 --source mikan --bt-worker mock --transcode-worker local_ffmpeg --stream-root .\runtime\streams --public-base-url http://10.0.2.2:8080 --default-debug-input-ref D:/Codes_Works/Projects/Project9_animation/runtime/media/sample.mp4
```

Mikan mode + qBittorrent BT worker + local ffmpeg transcode worker:

```powershell
Set-Location 'D:\Codes_Works\Projects\Project9_animation\services\stream_gateway'
python .\src\mock_gateway.py --host 0.0.0.0 --port 8080 --source mikan --bt-worker qbittorrent --transcode-worker local_ffmpeg --public-base-url http://10.0.2.2:8080 --qbt-base-url http://127.0.0.1:8081 --qbt-username admin --qbt-password adminadmin --qbt-playable-progress-percent 8
```

Contract placeholder mode (`external_stub`) for BT/transcode:

```powershell
Set-Location 'D:\Codes_Works\Projects\Project9_animation\services\stream_gateway'
python .\src\mock_gateway.py --host 0.0.0.0 --port 8080 --source mikan --bt-worker external_stub --transcode-worker external_stub
```

Health check:

```powershell
curl http://127.0.0.1:8080/health
```

## API surface
- `GET /home`
- `GET /search?q=`
- `GET /anime/{id}`
- `POST /play/session`
- `GET /play/session/{id}/status`
- `POST /play/session/{id}/retry`
- `GET /workers/overview`
- `GET /workers/bt/jobs`
- `POST /workers/bt/jobs`
- `GET /workers/bt/jobs/{id}`
- `POST /workers/bt/jobs/{id}/retry`
- `POST /workers/bt/jobs/{id}/cancel`
- `GET /workers/transcode/jobs`
- `POST /workers/transcode/jobs`
- `GET /workers/transcode/jobs/{id}`
- `POST /workers/transcode/jobs/{id}/retry`
- `POST /workers/transcode/jobs/{id}/cancel`
- `GET /streams/{session}/{attempt}/index.m3u8` (and `.ts` segments)

## Current behavior
- `--source mikan` returns real home/search/detail payloads parsed from mikan pages.
- `POST /play/session` returns `status=preparing` and pipeline metadata:
  - `pipelineStage`
  - `progressPercent`
  - `statusMessage`
  - `btJobId`
  - `transcodeJobId`
  - `canRetry`
  - `resolvedInputRef` (when transcode input path is normalized)
- `GET /play/session/{id}/status` auto-advances pipeline:
  - `bt:*` -> `transcode:*` -> `playable`
- `POST /play/session/{id}/retry` retries the failed worker stage when allowed.
- Session still defaults to sample HLS URL unless transcode worker returns real `streamUrl`.
- In mikan mode, session payload may include `magnet` and `torrentUrl` metadata.
- `/health` reports source/worker/runtime fields:
  - `sourceMode`
  - `btWorkerMode`
  - `transcodeWorkerMode`
  - `publicBaseUrl`
  - `streamRoot`
  - `defaultDebugInputRef`

## Local ffmpeg worker notes
- `local_ffmpeg` accepts **local file input** only (`C:\...\video.mp4` or `file:///...`).
- You can inject input path for play session via `debugInputRef` in `POST /play/session` body.
- Or set startup arg `--default-debug-input-ref` so app requests without debug params can also use local ffmpeg input.
- Generated HLS output is served under `/streams/...`.

## qBittorrent BT worker notes
- Use `--bt-worker qbittorrent` to enable real BT progress from qBittorrent WebUI API.
- Required args: `--qbt-base-url`, `--qbt-username`, `--qbt-password`.
- `--qbt-playable-progress-percent` controls when BT stage is considered playable and allows transcode stage to start.
- qB worker now returns `outputCandidates` (video file paths) and selected `outputRef`; gateway will auto-pick the best local media file for `local_ffmpeg` transcode.
- qB worker now includes temporary status-query/not-found grace windows and stalled-download auto-resume attempts to reduce false `failed` states.

## Failure simulation for debug
You can inject deterministic failures when creating session:
- request body `debugFailStage`: `bt` or `transcode`
- request body `debugFailMode`: `once` or `always`
- request body `debugMaxRetries`: integer `0..5`

Example:

```json
{
  "animeTitle": "Debug Anime",
  "sourceId": "dbg-1",
  "episodeId": "ep-01",
  "debugFailStage": "bt",
  "debugFailMode": "once",
  "debugMaxRetries": 2,
  "debugInputRef": "D:/media/sample.mp4"
}
```

## Planned modules
- `src/source_adapter/`: fetch + parse source pages
- `src/workers/`: worker contracts + mock workers + external stubs + local ffmpeg worker + qBittorrent BT worker
- `src/bt_worker/`: real torrent session and sequential download strategy
- `src/transcode_worker/`: real ffprobe + ffmpeg jobs
- `src/delivery/`: HLS session orchestration and delivery endpoints

## Environment
Copy `config/.env.example` to `config/.env` before implementation.

