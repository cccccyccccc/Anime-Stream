# anime_stream_app

Flutter client for single-device anime streaming.

## Implemented scaffold
- App shell with 4 tabs: Home, Search, Library, Profile.
- Repository-driven data flow with Mock/Gateway switch.
- Anime detail page with poster, metadata, episode list, and favorite toggle.
- Player page integrated with `video_player`.
- Player controls: seek `-10s/+10s`, play/pause, speed selector, timeline scrubbing.
- Playback speed persistence by `shared_preferences`.
- Local persistence for favorites/history using `shared_preferences`.
- Resume playback progress by `animeId + episodeId`.
- Episode-level progress indicators on anime detail page.
- Home `Continue Watching` section from local history + progress.
- Session metadata passthrough (`episodeTitle`, `magnet`, `torrentUrl`) from gateway to player detail cards.
- Session pipeline status rendering (`pipelineStage`, `progressPercent`, `statusMessage`) with auto-refresh while preparing.
- Player auto-switches to latest session `streamUrl` when gateway stream becomes ready.
- Player supports retrying failed pipeline sessions (`canRetry` + retry action).
- Player session diagnostics now includes `resolvedInputRef`, worker status/error codes, and BT output selection details.
- Profile includes gateway diagnostics panel (`/health`, worker overview, recent BT/transcode jobs).
- Profile diagnostics supports BT/Transcode job controls (`retry` / `cancel`) with auto-refresh.
- Library filtering for favorites/history with keyword search.
- Watch history grouped by date (Today/Yesterday/Date).

## Runtime config
By default, app uses mock repositories.

- `--dart-define=USE_MOCK_GATEWAY=false`
- `--dart-define=GATEWAY_BASE_URL=http://10.0.2.2:8080`
- `--dart-define=API_TIMEOUT_SECONDS=8`

## Gateway mode start order
1. Start local gateway service first (choose one source mode):
   - Mock source:
     - `python ..\services\stream_gateway\src\mock_gateway.py --host 0.0.0.0 --port 8080 --source mock`
   - Mikan source:
     - `python ..\services\stream_gateway\src\mock_gateway.py --host 0.0.0.0 --port 8080 --source mikan`
2. Install deps and run Flutter in gateway mode:
   - `flutter pub get`
   - `flutter run --dart-define=USE_MOCK_GATEWAY=false --dart-define=GATEWAY_BASE_URL=http://10.0.2.2:8080 --dart-define=API_TIMEOUT_SECONDS=8`

## Next development targets
1. Replace mock BT/transcode timeline with real torrent + ffmpeg workers.
2. Replace sample HLS URL with gateway-managed session stream URL.
3. Add download manager and offline watch strategy.




