import 'package:flutter/material.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/di/app_dependencies.dart';
import '../../../anime/domain/entities/anime_summary.dart';
import '../../../anime/presentation/pages/anime_detail_page.dart';
import '../../../anime/presentation/widgets/poster_thumbnail.dart';
import '../../../library/domain/entities/playback_progress.dart';
import '../../../library/domain/entities/watch_history_item.dart';
import '../../../player/presentation/pages/player_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key, this.refreshTrigger = 0});

  final int refreshTrigger;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late Future<_HomeData> _homeFuture;

  @override
  void initState() {
    super.initState();
    _homeFuture = _loadHomeData();
  }

  @override
  void didUpdateWidget(covariant HomePage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshTrigger != widget.refreshTrigger) {
      _refresh();
    }
  }

  Future<_HomeData> _loadHomeData() async {
    final homeFuture = AppDependencies.animeRepository.fetchHome();
    final historyFuture = AppDependencies.libraryStore.getHistory();
    final progressFuture = AppDependencies.libraryStore.getAllProgress();

    final homeItems = await homeFuture;
    final history = await historyFuture;
    final progressItems = await progressFuture;

    return _HomeData(
      homeItems: homeItems,
      continueItems: _buildContinueItems(history, progressItems),
    );
  }

  Future<void> _refresh() async {
    setState(() {
      _homeFuture = _loadHomeData();
    });

    await _homeFuture;
  }

  List<_ContinueWatchingItem> _buildContinueItems(
    List<WatchHistoryItem> history,
    List<PlaybackProgress> progressItems,
  ) {
    final progressMap = <String, PlaybackProgress>{
      for (final item in progressItems) item.key: item,
    };

    final continueItems = <_ContinueWatchingItem>[];
    for (final historyItem in history) {
      final key = PlaybackProgress.buildKey(
        historyItem.animeId,
        historyItem.episodeId,
      );
      final progress = progressMap[key];
      if (progress == null) {
        continue;
      }

      final ratio = progress.progressRatio;
      if (ratio <= 0 || ratio >= 1) {
        continue;
      }

      continueItems.add(
        _ContinueWatchingItem(history: historyItem, progress: progress),
      );

      if (continueItems.length >= 8) {
        break;
      }
    }

    return continueItems;
  }

  Future<void> _openPlayer(AnimeSummary item) async {
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      const SnackBar(content: Text('Creating play session...')),
    );

    try {
      final session = await AppDependencies.playerRepository.createPlaySession(
        animeTitle: item.title,
        sourceId: item.id,
        episodeId: item.latestEpisodeId,
      );

      if (!mounted) {
        return;
      }

      await Navigator.pushNamed(
        context,
        AppRoutes.player,
        arguments: PlayerPageArgs(
          animeId: item.id,
          animeTitle: session.animeTitle,
          episodeId: item.latestEpisodeId,
          episodeTitle: session.episodeTitle.isNotEmpty
              ? session.episodeTitle
              : item.title,
          streamUrl: session.streamUrl,
          source: session.source,
          posterUrl: item.posterUrl,
          sessionId: session.sessionId,
          status: session.status,
          magnet: session.magnet,
          torrentUrl: session.torrentUrl,
          pipelineStage: session.pipelineStage,
          statusMessage: session.statusMessage,
          progressPercent: session.progressPercent,
          btJobId: session.btJobId,
          transcodeJobId: session.transcodeJobId,
          canRetry: session.canRetry,
          failedStage: session.failedStage,
          resolvedInputRef: session.resolvedInputRef,
          btJobStatus: session.btJobStatus,
          transcodeJobStatus: session.transcodeJobStatus,
          btErrorCode: session.btErrorCode,
          transcodeErrorCode: session.transcodeErrorCode,
          btOutputRef: session.btOutputRef,
          btOutputCandidateCount: session.btOutputCandidateCount,
          transcodeInputRef: session.transcodeInputRef,
        ),
      );

      if (!mounted) {
        return;
      }
      await _refresh();
    } catch (error) {
      if (!mounted) {
        return;
      }

      messenger.showSnackBar(
        SnackBar(content: Text('Play session failed: $error')),
      );
    }
  }

  Future<void> _resumeFromHistory(_ContinueWatchingItem item) async {
    final messenger = ScaffoldMessenger.of(context);
    final sourceId = item.history.animeId.trim();
    if (sourceId.isEmpty) {
      messenger.showSnackBar(
        const SnackBar(
          content: Text(
            'History item is missing source ID. Reopen this anime from Home/Search once.',
          ),
        ),
      );
      return;
    }

    messenger.showSnackBar(
      const SnackBar(content: Text('Creating play session...')),
    );

    try {
      final session = await AppDependencies.playerRepository.createPlaySession(
        animeTitle: item.history.animeTitle,
        sourceId: sourceId,
        episodeId: item.history.episodeId,
      );

      if (!mounted) {
        return;
      }

      await Navigator.pushNamed(
        context,
        AppRoutes.player,
        arguments: PlayerPageArgs(
          animeId: item.history.animeId,
          animeTitle: session.animeTitle,
          episodeId: item.history.episodeId,
          episodeTitle: session.episodeTitle.isNotEmpty
              ? session.episodeTitle
              : item.history.episodeTitle,
          streamUrl: session.streamUrl,
          source: session.source,
          posterUrl: item.history.posterUrl,
          sessionId: session.sessionId,
          status: session.status,
          magnet: session.magnet,
          torrentUrl: session.torrentUrl,
          pipelineStage: session.pipelineStage,
          statusMessage: session.statusMessage,
          progressPercent: session.progressPercent,
          btJobId: session.btJobId,
          transcodeJobId: session.transcodeJobId,
          canRetry: session.canRetry,
          failedStage: session.failedStage,
          resolvedInputRef: session.resolvedInputRef,
          btJobStatus: session.btJobStatus,
          transcodeJobStatus: session.transcodeJobStatus,
          btErrorCode: session.btErrorCode,
          transcodeErrorCode: session.transcodeErrorCode,
          btOutputRef: session.btOutputRef,
          btOutputCandidateCount: session.btOutputCandidateCount,
          transcodeInputRef: session.transcodeInputRef,
        ),
      );

      if (!mounted) {
        return;
      }
      await _refresh();
    } catch (error) {
      if (!mounted) {
        return;
      }

      messenger.showSnackBar(
        SnackBar(content: Text('Play session failed: $error')),
      );
    }
  }

  Future<void> _openDetail(AnimeSummary item) async {
    await Navigator.pushNamed(
      context,
      AppRoutes.animeDetail,
      arguments: AnimeDetailPageArgs(animeId: item.id, title: item.title),
    );

    if (!mounted) {
      return;
    }
    await _refresh();
  }

  Future<void> _openDetailFromHistory(WatchHistoryItem item) async {
    await Navigator.pushNamed(
      context,
      AppRoutes.animeDetail,
      arguments: AnimeDetailPageArgs(
        animeId: item.animeId,
        title: item.animeTitle,
      ),
    );

    if (!mounted) {
      return;
    }
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_HomeData>(
      future: _homeFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: const [
              _HeroCard(),
              SizedBox(height: 16),
              Center(child: CircularProgressIndicator()),
            ],
          );
        }

        if (snapshot.hasError) {
          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              const _HeroCard(),
              const SizedBox(height: 16),
              Card(
                child: ListTile(
                  title: const Text('Failed to load home feed'),
                  subtitle: Text(snapshot.error.toString()),
                  trailing: FilledButton(
                    onPressed: _refresh,
                    child: const Text('Retry'),
                  ),
                ),
              ),
            ],
          );
        }

        final data =
            snapshot.data ??
            const _HomeData(
              homeItems: <AnimeSummary>[],
              continueItems: <_ContinueWatchingItem>[],
            );

        return RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              const _HeroCard(),
              const SizedBox(height: 16),
              Text(
                'Continue Watching',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              if (data.continueItems.isEmpty)
                const Card(
                  child: ListTile(
                    leading: Icon(Icons.play_circle_outline),
                    title: Text('No unfinished episodes'),
                    subtitle: Text(
                      'Watch an episode and your progress will appear here.',
                    ),
                  ),
                )
              else
                ...data.continueItems.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            GestureDetector(
                              onTap: () => _openDetailFromHistory(item.history),
                              child: PosterThumbnail(
                                imageUrl: item.history.posterUrl,
                                width: 62,
                                height: 86,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  GestureDetector(
                                    onTap: () =>
                                        _openDetailFromHistory(item.history),
                                    child: Text(
                                      item.history.animeTitle,
                                      style: Theme.of(
                                        context,
                                      ).textTheme.titleMedium,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    item.history.episodeTitle,
                                    style: Theme.of(
                                      context,
                                    ).textTheme.bodyMedium,
                                  ),
                                  const SizedBox(height: 8),
                                  ClipRRect(
                                    borderRadius: BorderRadius.circular(999),
                                    child: LinearProgressIndicator(
                                      minHeight: 8,
                                      value: item.progress.progressRatio,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    _continueSubtitle(item),
                                    style: Theme.of(
                                      context,
                                    ).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 10),
                            FilledButton.tonal(
                              onPressed: () => _resumeFromHistory(item),
                              child: const Text('Resume'),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              const SizedBox(height: 16),
              Text(
                'Latest Updates',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              if (data.homeItems.isEmpty)
                const Card(
                  child: ListTile(
                    title: Text('No updates yet'),
                    subtitle: Text('Pull to refresh after source sync.'),
                  ),
                )
              else
                ...data.homeItems.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Card(
                      child: ListTile(
                        onTap: () => _openDetail(item),
                        leading: PosterThumbnail(imageUrl: item.posterUrl),
                        title: Text(item.title),
                        subtitle: Text(item.subtitle),
                        trailing: FilledButton.tonal(
                          onPressed: () => _openPlayer(item),
                          child: const Text('Play'),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  String _continueSubtitle(_ContinueWatchingItem item) {
    final percent = (item.progress.progressRatio * 100).round();
    final position = _formatDuration(
      Duration(milliseconds: item.progress.positionMs),
    );
    final duration = _formatDuration(
      Duration(milliseconds: item.progress.durationMs),
    );
    return '$percent% · $position / $duration';
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
}

class _HeroCard extends StatelessWidget {
  const _HeroCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Torrent Streaming Ready',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'Mikan source + play-session workflow is wired to repository layer. Detail page, favorites, history, and continue watching are available locally.',
            ),
          ],
        ),
      ),
    );
  }
}

class _HomeData {
  const _HomeData({required this.homeItems, required this.continueItems});

  final List<AnimeSummary> homeItems;
  final List<_ContinueWatchingItem> continueItems;
}

class _ContinueWatchingItem {
  const _ContinueWatchingItem({required this.history, required this.progress});

  final WatchHistoryItem history;
  final PlaybackProgress progress;
}
