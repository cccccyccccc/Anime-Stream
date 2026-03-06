# Streaming Pipeline Draft

## Target flow
1. Fetch anime metadata and torrent/magnet references from `https://mikan.tangbai.cc/`.
2. Submit torrent/magnet to BT worker for sequential download.
3. Detect playable media files (`ffprobe`).
4. Produce stream output:
   - Preferred: HLS (`m3u8 + ts/fmp4`) via `ffmpeg`.
   - Optional: RTMP ingest then convert to HLS.
5. Flutter app requests `play-session` and receives a playable URL.

## Service boundaries
- `source-adapter`: source fetch + parse.
- `bt-worker`: torrent session and piece priority.
- `transcode-worker`: ffmpeg pipeline.
- `delivery`: expose HLS playlist and segments.

## Compliance
Only process content with clear authorization or lawful rights.
