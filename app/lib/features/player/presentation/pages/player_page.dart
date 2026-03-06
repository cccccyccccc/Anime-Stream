import 'dart:async';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../../../core/config/app_constants.dart';
import '../../../../core/di/app_dependencies.dart';
import '../../../anime/domain/entities/anime_summary.dart';
import '../../../library/domain/entities/playback_progress.dart';
import '../../../library/domain/entities/watch_history_item.dart';
import '../../domain/entities/play_session.dart';

class PlayerPageArgs {
  const PlayerPageArgs({
    required this.animeId,
    required this.animeTitle,
    required this.episodeId,
    required this.episodeTitle,
    required this.streamUrl,
    required this.source,
    this.posterUrl = '',
    this.sessionId,
    this.status,
    this.magnet = '',
    this.torrentUrl = '',
    this.pipelineStage = '',
    this.statusMessage = '',
    this.progressPercent = 0,
    this.btJobId = '',
    this.transcodeJobId = '',
    this.canRetry = false,
    this.failedStage = '',
    this.resolvedInputRef = '',
    this.btJobStatus = '',
    this.transcodeJobStatus = '',
    this.btErrorCode = '',
    this.transcodeErrorCode = '',
    this.btOutputRef = '',
    this.btOutputCandidateCount = 0,
    this.transcodeInputRef = '',
  });

  final String animeId;
  final String animeTitle;
  final String episodeId;
  final String episodeTitle;
  final String streamUrl;
  final String source;
  final String posterUrl;
  final String? sessionId;
  final PlaySessionStatus? status;
  final String magnet;
  final String torrentUrl;
  final String pipelineStage;
  final String statusMessage;
  final int progressPercent;
  final String btJobId;
  final String transcodeJobId;
  final bool canRetry;
  final String failedStage;
  final String resolvedInputRef;
  final String btJobStatus;
  final String transcodeJobStatus;
  final String btErrorCode;
  final String transcodeErrorCode;
  final String btOutputRef;
  final int btOutputCandidateCount;
  final String transcodeInputRef;
}

class PlayerPage extends StatefulWidget {
  const PlayerPage({super.key, required this.args});

  final PlayerPageArgs args;

  @override
  State<PlayerPage> createState() => _PlayerPageState();
}

class _PlayerPageState extends State<PlayerPage> {
  static const List<double> _speedOptions = <double>[0.75, 1.0, 1.25, 1.5, 2.0];

  VideoPlayerController? _controller;
  Timer? _progressTimer;
  Timer? _statusPollTimer;

  String? _playerError;
  String? _resumeInfo;

  bool _initializing = true;
  bool _refreshingStatus = false;
  bool _favoriteLoading = false;
  bool _isFavorite = false;
  bool _isScrubbing = false;

  PlaySessionStatus? _sessionStatus;
  String _pipelineStage = '';
  String _statusMessage = '';
  int _statusProgress = 0;
  String _btJobId = '';
  String _transcodeJobId = '';
  bool _canRetry = false;
  String _activeStreamUrl = '';
  String _failedStage = '';
  String _resolvedInputRef = '';
  String _btJobStatus = '';
  String _transcodeJobStatus = '';
  String _btErrorCode = '';
  String _transcodeErrorCode = '';
  String _btOutputRef = '';
  int _btOutputCandidateCount = 0;
  String _transcodeInputRef = '';

  double _playbackSpeed = 1.0;
  double _scrubPositionMs = 0;
  bool _sessionCleanupRequested = false;

  @override
  void initState() {
    super.initState();
    _sessionStatus = widget.args.status;
    _pipelineStage = widget.args.pipelineStage;
    _statusMessage = widget.args.statusMessage;
    _statusProgress = widget.args.progressPercent;
    _btJobId = widget.args.btJobId;
    _transcodeJobId = widget.args.transcodeJobId;
    _canRetry = widget.args.canRetry;
    _activeStreamUrl = widget.args.streamUrl.trim();
    _failedStage = widget.args.failedStage;
    _resolvedInputRef = widget.args.resolvedInputRef;
    _btJobStatus = widget.args.btJobStatus;
    _transcodeJobStatus = widget.args.transcodeJobStatus;
    _btErrorCode = widget.args.btErrorCode;
    _transcodeErrorCode = widget.args.transcodeErrorCode;
    _btOutputRef = widget.args.btOutputRef;
    _btOutputCandidateCount = widget.args.btOutputCandidateCount;
    _transcodeInputRef = widget.args.transcodeInputRef;

    _recordHistory();
    _loadFavoriteState();
    _loadPlaybackSpeed();
    _initPlayer();

    _configureStatusPolling();
    if ((widget.args.sessionId ?? '').isNotEmpty &&
        _sessionStatus == PlaySessionStatus.preparing) {
      unawaited(_refreshSessionStatus(silent: true));
    }
  }

  @override
  void dispose() {
    unawaited(_persistProgress(force: true));
    _progressTimer?.cancel();
    _statusPollTimer?.cancel();
    unawaited(_cancelSessionOnExit());
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _recordHistory() async {
    if (widget.args.animeId.isEmpty || widget.args.episodeId.isEmpty) {
      return;
    }

    final item = WatchHistoryItem(
      animeId: widget.args.animeId,
      animeTitle: widget.args.animeTitle,
      episodeId: widget.args.episodeId,
      episodeTitle: widget.args.episodeTitle,
      streamUrl: _activeStreamUrl.isEmpty
          ? widget.args.streamUrl
          : _activeStreamUrl,
      source: widget.args.source,
      playedAt: DateTime.now().toUtc(),
      posterUrl: widget.args.posterUrl,
    );

    await AppDependencies.libraryStore.addHistory(item);
  }

  Future<void> _loadFavoriteState() async {
    if (widget.args.animeId.isEmpty) {
      return;
    }

    final favored = await AppDependencies.libraryStore.isFavorite(
      widget.args.animeId,
    );
    if (!mounted) {
      return;
    }

    setState(() {
      _isFavorite = favored;
    });
  }

  Future<void> _toggleFavorite() async {
    if (_favoriteLoading || widget.args.animeId.isEmpty) {
      return;
    }

    setState(() {
      _favoriteLoading = true;
    });

    final summary = AnimeSummary(
      id: widget.args.animeId,
      title: widget.args.animeTitle,
      subtitle: widget.args.episodeTitle,
      latestEpisodeId: widget.args.episodeId,
      source: widget.args.source,
      posterUrl: widget.args.posterUrl,
    );

    try {
      final favored = await AppDependencies.libraryStore.toggleFavorite(
        summary,
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _isFavorite = favored;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            favored ? 'Added to favorites' : 'Removed from favorites',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _favoriteLoading = false;
        });
      }
    }
  }

  Future<void> _loadPlaybackSpeed() async {
    final speed = await AppDependencies.playerPreferencesStore
        .getPlaybackSpeed();
    if (!mounted) {
      return;
    }

    setState(() {
      _playbackSpeed = speed;
    });

    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }

    await controller.setPlaybackSpeed(speed);
  }

  Future<void> _setPlaybackSpeed(double speed) async {
    final normalized = speed.clamp(0.5, 3.0).toDouble();
    if ((_playbackSpeed - normalized).abs() < 0.001) {
      return;
    }

    final controller = _controller;
    if (controller != null && controller.value.isInitialized) {
      await controller.setPlaybackSpeed(normalized);
    }

    await AppDependencies.playerPreferencesStore.setPlaybackSpeed(normalized);

    if (mounted) {
      setState(() {
        _playbackSpeed = normalized;
      });
    }
  }

  bool _isSampleStreamUrl(String rawUrl) {
    return rawUrl.trim() == AppConstants.sampleHlsUrl;
  }

  bool _shouldDeferSamplePlayback(String rawUrl) {
    if (!_isSampleStreamUrl(rawUrl)) {
      return false;
    }

    return _sessionStatus != PlaySessionStatus.playable;
  }

  Future<void> _clearController() async {
    final oldController = _controller;
    if (oldController == null) {
      return;
    }

    _controller = null;
    await oldController.dispose();
  }

  Future<void> _initPlayer() async {
    setState(() {
      _initializing = true;
      _playerError = null;
      _resumeInfo = null;
      _isScrubbing = false;
      _scrubPositionMs = 0;
    });

    unawaited(_persistProgress(force: true));
    _progressTimer?.cancel();

    final rawUrl = _activeStreamUrl.trim();
    if (rawUrl.isEmpty) {
      setState(() {
        _initializing = false;
        _playerError = 'Empty stream URL';
      });
      return;
    }

    if (_shouldDeferSamplePlayback(rawUrl)) {
      await _clearController();
      if (!mounted) {
        return;
      }

      final statusMessage = _statusMessage.trim();
      final fallbackMessage = _sessionStatus == PlaySessionStatus.failed
          ? 'Session failed before playable stream was ready.'
          : 'Waiting for playable stream from gateway.';

      setState(() {
        _initializing = false;
        _playerError = statusMessage.isNotEmpty
            ? statusMessage
            : fallbackMessage;
      });
      return;
    }

    Uri uri;
    try {
      uri = Uri.parse(rawUrl);
    } catch (_) {
      setState(() {
        _initializing = false;
        _playerError = 'Invalid stream URL: $rawUrl';
      });
      return;
    }

    final oldController = _controller;
    final newController = VideoPlayerController.networkUrl(uri);

    try {
      await newController.initialize();
      await _restoreProgressIfAvailable(newController);
      await newController.setLooping(false);
      await newController.setPlaybackSpeed(_playbackSpeed);
      await newController.play();

      if (!mounted) {
        await newController.dispose();
        return;
      }

      setState(() {
        _controller = newController;
        _initializing = false;
      });

      _startProgressTicker();

      if (oldController != null) {
        await oldController.dispose();
      }
    } catch (error) {
      await newController.dispose();
      if (!mounted) {
        return;
      }

      setState(() {
        _initializing = false;
        _playerError = 'Player init failed: $error';
      });
    }
  }

  Future<void> _maybeSwitchStreamUrl(
    PlaySession session, {
    required bool silent,
  }) async {
    final nextUrl = session.streamUrl.trim();
    if (nextUrl.isEmpty) {
      return;
    }

    final currentUrl = _activeStreamUrl.trim();
    if (nextUrl == currentUrl) {
      return;
    }

    if (mounted) {
      setState(() {
        _activeStreamUrl = nextUrl;
      });
    } else {
      _activeStreamUrl = nextUrl;
    }

    await _initPlayer();
    unawaited(_recordHistory());

    if (!mounted || silent) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Stream URL updated from latest session status.'),
      ),
    );
  }

  Future<void> _restoreProgressIfAvailable(
    VideoPlayerController controller,
  ) async {
    if (widget.args.animeId.isEmpty || widget.args.episodeId.isEmpty) {
      return;
    }

    final saved = await AppDependencies.libraryStore.getProgress(
      widget.args.animeId,
      widget.args.episodeId,
    );
    if (saved == null) {
      return;
    }

    final duration = controller.value.duration;
    if (duration <= Duration.zero) {
      return;
    }

    final durationMs = duration.inMilliseconds;
    final maxSeekMs = durationMs > 1000 ? durationMs - 1000 : durationMs;
    final targetMs = saved.positionMs.clamp(0, maxSeekMs).toInt();
    if (targetMs <= 0) {
      return;
    }

    await controller.seekTo(Duration(milliseconds: targetMs));

    if (mounted) {
      setState(() {
        _resumeInfo = 'Resumed at ${_formatPercent(saved.progressRatio)}';
      });
    }
  }

  void _configureStatusPolling() {
    _statusPollTimer?.cancel();

    final hasSession = (widget.args.sessionId ?? '').isNotEmpty;
    if (!hasSession || _sessionStatus != PlaySessionStatus.preparing) {
      return;
    }

    _statusPollTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      unawaited(_refreshSessionStatus(silent: true));
    });
  }

  Future<void> _refreshSessionStatus({bool silent = false}) async {
    final sessionId = widget.args.sessionId;
    if (sessionId == null || sessionId.isEmpty) {
      return;
    }

    if (!silent) {
      setState(() {
        _refreshingStatus = true;
      });
    }

    try {
      final session = await AppDependencies.playerRepository
          .getPlaySessionStatus(sessionId: sessionId);

      if (!mounted) {
        return;
      }

      setState(() {
        _sessionStatus = session.status;
        _pipelineStage = session.pipelineStage;
        _statusMessage = session.statusMessage;
        _statusProgress = session.progressPercent;
        _btJobId = session.btJobId;
        _transcodeJobId = session.transcodeJobId;
        _canRetry = session.canRetry;
        _failedStage = session.failedStage;
        _resolvedInputRef = session.resolvedInputRef;
        _btJobStatus = session.btJobStatus;
        _transcodeJobStatus = session.transcodeJobStatus;
        _btErrorCode = session.btErrorCode;
        _transcodeErrorCode = session.transcodeErrorCode;
        _btOutputRef = session.btOutputRef;
        _btOutputCandidateCount = session.btOutputCandidateCount;
        _transcodeInputRef = session.transcodeInputRef;
      });

      _configureStatusPolling();
      await _maybeSwitchStreamUrl(session, silent: silent);
    } catch (error) {
      if (!mounted || silent) {
        return;
      }

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Status refresh failed: $error')));
    } finally {
      if (!silent && mounted) {
        setState(() {
          _refreshingStatus = false;
        });
      }
    }
  }

  Future<void> _retrySessionPipeline() async {
    final sessionId = widget.args.sessionId;
    if (sessionId == null || sessionId.isEmpty) {
      return;
    }

    setState(() {
      _refreshingStatus = true;
    });

    try {
      final session = await AppDependencies.playerRepository.retryPlaySession(
        sessionId: sessionId,
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _sessionStatus = session.status;
        _pipelineStage = session.pipelineStage;
        _statusMessage = session.statusMessage;
        _statusProgress = session.progressPercent;
        _btJobId = session.btJobId;
        _transcodeJobId = session.transcodeJobId;
        _canRetry = session.canRetry;
        _failedStage = session.failedStage;
        _resolvedInputRef = session.resolvedInputRef;
        _btJobStatus = session.btJobStatus;
        _transcodeJobStatus = session.transcodeJobStatus;
        _btErrorCode = session.btErrorCode;
        _transcodeErrorCode = session.transcodeErrorCode;
        _btOutputRef = session.btOutputRef;
        _btOutputCandidateCount = session.btOutputCandidateCount;
        _transcodeInputRef = session.transcodeInputRef;
      });

      _configureStatusPolling();
      await _maybeSwitchStreamUrl(session, silent: false);

      if (!mounted) {
        return;
      }

      if (_sessionStatus == PlaySessionStatus.preparing) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Retry queued, pipeline resumed.')),
        );
      }
    } catch (error) {
      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Retry failed: $error')));
    } finally {
      if (mounted) {
        setState(() {
          _refreshingStatus = false;
        });
      }
    }
  }

  Future<void> _cancelSessionOnExit() async {
    if (_sessionCleanupRequested) {
      return;
    }

    final sessionId = widget.args.sessionId?.trim() ?? '';
    if (sessionId.isEmpty) {
      return;
    }

    _sessionCleanupRequested = true;
    try {
      await AppDependencies.playerRepository.cancelPlaySession(
        sessionId: sessionId,
      );
    } catch (_) {
      // Best effort cleanup on page exit.
    }
  }

  void _startProgressTicker() {
    _progressTimer?.cancel();
    _progressTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      unawaited(_persistProgress());
    });
  }

  Future<void> _persistProgress({bool force = false}) async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }

    if (!force && !controller.value.isPlaying) {
      return;
    }

    final duration = controller.value.duration;
    final position = controller.value.position;

    if (duration <= Duration.zero) {
      return;
    }

    final progress = PlaybackProgress(
      animeId: widget.args.animeId,
      episodeId: widget.args.episodeId,
      positionMs: position.inMilliseconds,
      durationMs: duration.inMilliseconds,
      updatedAt: DateTime.now().toUtc(),
    );

    await AppDependencies.libraryStore.saveProgress(progress);
  }

  Future<void> _togglePlayPause() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }

    if (controller.value.isPlaying) {
      await controller.pause();
      await _persistProgress(force: true);
    } else {
      await controller.play();
    }

    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _seekRelative(Duration offset) async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }

    final currentMs = controller.value.position.inMilliseconds;
    await _seekToMilliseconds(currentMs + offset.inMilliseconds);
  }

  Future<void> _seekToMilliseconds(int positionMs) async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }

    final durationMs = controller.value.duration.inMilliseconds;
    if (durationMs <= 0) {
      return;
    }

    final targetMs = positionMs.clamp(0, durationMs).toInt();
    await controller.seekTo(Duration(milliseconds: targetMs));
    await _persistProgress(force: true);
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    final canControl = controller != null && controller.value.isInitialized;
    final isPlaying = controller?.value.isPlaying ?? false;
    final resumeInfo = _resumeInfo;

    return PopScope<Object?>(
      canPop: true,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) {
          return;
        }
        unawaited(_cancelSessionOnExit());
      },
      child: Scaffold(
        appBar: AppBar(title: Text(widget.args.animeTitle)),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _buildVideoSurface(controller),
            const SizedBox(height: 12),
            _buildProgressSection(controller),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: canControl
                      ? () => unawaited(
                          _seekRelative(const Duration(seconds: -10)),
                        )
                      : null,
                  icon: const Icon(Icons.replay_10),
                  label: const Text('-10s'),
                ),
                FilledButton.tonal(
                  onPressed: canControl ? _togglePlayPause : null,
                  child: Text(canControl && isPlaying ? 'Pause' : 'Play'),
                ),
                OutlinedButton.icon(
                  onPressed: canControl
                      ? () => unawaited(
                          _seekRelative(const Duration(seconds: 10)),
                        )
                      : null,
                  icon: const Icon(Icons.forward_10),
                  label: const Text('+10s'),
                ),
                SizedBox(
                  width: 140,
                  child: DropdownButtonFormField<double>(
                    key: ValueKey<double>(_playbackSpeed),
                    initialValue: _playbackSpeed,
                    decoration: const InputDecoration(
                      labelText: 'Speed',
                      isDense: true,
                    ),
                    onChanged: canControl
                        ? (value) {
                            if (value == null) {
                              return;
                            }
                            unawaited(_setPlaybackSpeed(value));
                          }
                        : null,
                    items: _speedOptions
                        .map(
                          (speed) => DropdownMenuItem<double>(
                            value: speed,
                            child: Text('${_formatSpeed(speed)}x'),
                          ),
                        )
                        .toList(growable: false),
                  ),
                ),
                OutlinedButton(
                  onPressed: _initPlayer,
                  child: const Text('Reload Stream'),
                ),
              ],
            ),
            if ((resumeInfo ?? '').isNotEmpty) ...[
              const SizedBox(height: 10),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.replay_circle_filled),
                  title: const Text('Resume'),
                  subtitle: Text(resumeInfo!),
                ),
              ),
            ],
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                title: const Text('Favorite'),
                subtitle: Text(
                  _isFavorite
                      ? 'Saved in your local favorites'
                      : 'Add this anime to local favorites',
                ),
                trailing: FilledButton.tonalIcon(
                  onPressed: _favoriteLoading ? null : _toggleFavorite,
                  icon: Icon(
                    _isFavorite ? Icons.favorite : Icons.favorite_border,
                  ),
                  label: Text(_isFavorite ? 'Favorited' : 'Favorite'),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Card(
              child: ListTile(
                title: const Text('Episode'),
                subtitle: Text(widget.args.episodeTitle),
              ),
            ),
            const SizedBox(height: 10),
            if ((widget.args.sessionId ?? '').isNotEmpty)
              Card(
                child: ListTile(
                  title: const Text('Session ID'),
                  subtitle: Text(widget.args.sessionId!),
                ),
              ),
            if (widget.args.magnet.trim().isNotEmpty) ...[
              const SizedBox(height: 10),
              Card(
                child: ListTile(
                  title: const Text('Magnet'),
                  subtitle: Text(widget.args.magnet),
                ),
              ),
            ],
            if (widget.args.torrentUrl.trim().isNotEmpty) ...[
              const SizedBox(height: 10),
              Card(
                child: ListTile(
                  title: const Text('Torrent URL'),
                  subtitle: Text(widget.args.torrentUrl),
                ),
              ),
            ],
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                title: const Text('Stream URL'),
                subtitle: Text(
                  _activeStreamUrl.isEmpty
                      ? widget.args.streamUrl
                      : _activeStreamUrl,
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                title: const Text('Source'),
                subtitle: Text(widget.args.source),
              ),
            ),
            const SizedBox(height: 10),
            _buildSessionStatusCard(),
            if (_playerError != null) ...[
              const SizedBox(height: 10),
              Card(
                child: ListTile(
                  title: const Text('Player Error'),
                  subtitle: Text(_playerError!),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSessionStatusCard() {
    final stage = _pipelineStage.trim();
    final message = _statusMessage.trim();
    final progress = _statusProgress.clamp(0, 100).toInt();
    final isPreparing = _sessionStatus == PlaySessionStatus.preparing;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'Session Status',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const Spacer(),
                if (_canRetry) ...[
                  FilledButton.tonal(
                    onPressed: _refreshingStatus ? null : _retrySessionPipeline,
                    child: const Text('Retry Pipeline'),
                  ),
                  const SizedBox(width: 8),
                ],
                FilledButton(
                  onPressed: _refreshingStatus ? null : _refreshSessionStatus,
                  child: Text(_refreshingStatus ? 'Refreshing...' : 'Refresh'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text('State: ${_statusLabel(_sessionStatus)}'),
            if (stage.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Stage: $stage'),
            ],
            if (message.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(message),
            ],
            if (progress > 0 || isPreparing) ...[
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: LinearProgressIndicator(value: progress / 100),
              ),
              const SizedBox(height: 6),
              Text('Progress: $progress%'),
            ],
            if (isPreparing) ...[
              const SizedBox(height: 4),
              const Text('Auto-refreshing every 3 seconds while preparing.'),
            ],
            if (_btJobId.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('BT Job: $_btJobId'),
            ],
            if (_transcodeJobId.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Transcode Job: $_transcodeJobId'),
            ],
            if (_btJobStatus.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('BT Status: ${_btJobStatus.trim()}'),
            ],
            if (_transcodeJobStatus.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Transcode Status: ${_transcodeJobStatus.trim()}'),
            ],
            if (_failedStage.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Failed Stage: ${_failedStage.trim()}'),
            ],
            if (_resolvedInputRef.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Resolved Input: ${_resolvedInputRef.trim()}'),
            ],
            if (_transcodeInputRef.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Transcode Input: ${_transcodeInputRef.trim()}'),
            ],
            if (_btOutputRef.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('BT Output Ref: ${_btOutputRef.trim()}'),
            ],
            if (_btOutputCandidateCount > 0) ...[
              const SizedBox(height: 4),
              Text('BT Output Candidates: $_btOutputCandidateCount'),
            ],
            if (_btErrorCode.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('BT Error: ${_btErrorCode.trim()}'),
            ],
            if (_transcodeErrorCode.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Transcode Error: ${_transcodeErrorCode.trim()}'),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildVideoSurface(VideoPlayerController? controller) {
    if (_initializing) {
      return const AspectRatio(
        aspectRatio: 16 / 9,
        child: ColoredBox(
          color: Colors.black,
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    if (controller == null || !controller.value.isInitialized) {
      return const AspectRatio(
        aspectRatio: 16 / 9,
        child: ColoredBox(
          color: Colors.black,
          child: Center(
            child: Text(
              'Video unavailable',
              style: TextStyle(color: Colors.white70),
            ),
          ),
        ),
      );
    }

    return AspectRatio(
      aspectRatio: controller.value.aspectRatio,
      child: VideoPlayer(controller),
    );
  }

  Widget _buildProgressSection(VideoPlayerController? controller) {
    if (controller == null || !controller.value.isInitialized) {
      return const SizedBox.shrink();
    }

    return ValueListenableBuilder<VideoPlayerValue>(
      valueListenable: controller,
      builder: (context, value, _) {
        final durationMs = value.duration.inMilliseconds;
        final maxMs = durationMs <= 0 ? 1.0 : durationMs.toDouble();
        final liveMs = value.position.inMilliseconds.clamp(
          0,
          durationMs <= 0 ? 0 : durationMs,
        );
        final sliderMs = _isScrubbing
            ? _scrubPositionMs.clamp(0, maxMs).toDouble()
            : liveMs.toDouble();
        final canScrub = durationMs > 0;

        return Column(
          children: [
            Slider(
              value: sliderMs,
              min: 0,
              max: maxMs,
              onChangeStart: canScrub
                  ? (position) {
                      setState(() {
                        _isScrubbing = true;
                        _scrubPositionMs = position;
                      });
                    }
                  : null,
              onChanged: canScrub
                  ? (position) {
                      setState(() {
                        _scrubPositionMs = position;
                      });
                    }
                  : null,
              onChangeEnd: canScrub
                  ? (position) {
                      setState(() {
                        _isScrubbing = false;
                        _scrubPositionMs = position;
                      });
                      unawaited(_seekToMilliseconds(position.round()));
                    }
                  : null,
            ),
            Row(
              children: [
                Text(
                  _formatDuration(Duration(milliseconds: sliderMs.round())),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const Spacer(),
                Text(
                  _formatDuration(value.duration),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  String _statusLabel(PlaySessionStatus? status) {
    switch (status) {
      case PlaySessionStatus.playable:
        return 'Playable';
      case PlaySessionStatus.failed:
        return 'Failed';
      case PlaySessionStatus.preparing:
        return 'Preparing';
      case null:
        return 'Unknown';
    }
  }

  String _formatPercent(double ratio) {
    final value = (ratio * 100).round();
    return '$value%';
  }

  String _formatDuration(Duration duration) {
    if (duration <= Duration.zero) {
      return '00:00';
    }

    final totalSeconds = duration.inSeconds;
    final hours = totalSeconds ~/ 3600;
    final minutes = (totalSeconds % 3600) ~/ 60;
    final seconds = totalSeconds % 60;

    String two(int value) => value.toString().padLeft(2, '0');

    if (hours > 0) {
      return '${two(hours)}:${two(minutes)}:${two(seconds)}';
    }

    return '${two(minutes)}:${two(seconds)}';
  }

  String _formatSpeed(double speed) {
    if (speed == speed.roundToDouble()) {
      return speed.toStringAsFixed(0);
    }
    return speed.toStringAsFixed(2);
  }
}
