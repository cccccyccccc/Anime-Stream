import 'package:flutter/material.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/di/app_dependencies.dart';
import '../../../anime/domain/entities/anime_summary.dart';
import '../../../anime/presentation/pages/anime_detail_page.dart';
import '../../../anime/presentation/widgets/poster_thumbnail.dart';
import '../../../player/presentation/pages/player_page.dart';
import '../../domain/entities/playback_progress.dart';
import '../../domain/entities/watch_history_item.dart';

class LibraryPage extends StatefulWidget {
  const LibraryPage({super.key, this.refreshTrigger = 0});

  final int refreshTrigger;

  @override
  State<LibraryPage> createState() => _LibraryPageState();
}

class _LibraryPageState extends State<LibraryPage> {
  late Future<_LibraryData> _future;
  final TextEditingController _filterController = TextEditingController();
  String _query = '';

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  @override
  void didUpdateWidget(covariant LibraryPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshTrigger != widget.refreshTrigger) {
      _refresh();
    }
  }

  @override
  void dispose() {
    _filterController.dispose();
    super.dispose();
  }

  Future<_LibraryData> _load() async {
    final favorites = await AppDependencies.libraryStore.getFavorites();
    final history = await AppDependencies.libraryStore.getHistory();
    final progressItems = await AppDependencies.libraryStore.getAllProgress();
    final progressMap = <String, PlaybackProgress>{
      for (final item in progressItems) item.key: item,
    };

    return _LibraryData(
      favorites: favorites,
      history: history,
      progressMap: progressMap,
    );
  }

  Future<void> _refresh() async {
    setState(() {
      _future = _load();
    });

    await _future;
  }

  void _openDetail(AnimeSummary item) {
    Navigator.pushNamed(
      context,
      AppRoutes.animeDetail,
      arguments: AnimeDetailPageArgs(animeId: item.id, title: item.title),
    );
  }

  Future<void> _playFavorite(AnimeSummary item) async {
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

      Navigator.pushNamed(
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
    } catch (error) {
      if (!mounted) {
        return;
      }

      messenger.showSnackBar(
        SnackBar(content: Text('Play session failed: $error')),
      );
    }
  }

  Future<void> _replayHistory(WatchHistoryItem item) async {
    final messenger = ScaffoldMessenger.of(context);
    final sourceId = item.animeId.trim();
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
        animeTitle: item.animeTitle,
        sourceId: sourceId,
        episodeId: item.episodeId,
      );

      if (!mounted) {
        return;
      }

      Navigator.pushNamed(
        context,
        AppRoutes.player,
        arguments: PlayerPageArgs(
          animeId: item.animeId,
          animeTitle: session.animeTitle,
          episodeId: item.episodeId,
          episodeTitle: session.episodeTitle.isNotEmpty
              ? session.episodeTitle
              : item.episodeTitle,
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
    } catch (error) {
      if (!mounted) {
        return;
      }

      messenger.showSnackBar(
        SnackBar(content: Text('Play session failed: $error')),
      );
    }
  }

  Future<void> _removeFavorite(AnimeSummary item) async {
    await AppDependencies.libraryStore.removeFavorite(item.id);
    await _refresh();
  }

  Future<void> _clearHistory() async {
    await AppDependencies.libraryStore.clearHistory();
    await AppDependencies.libraryStore.clearProgress();
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_LibraryData>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: ListTile(
                  title: const Text('Library load failed'),
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
            const _LibraryData(
              favorites: <AnimeSummary>[],
              history: <WatchHistoryItem>[],
              progressMap: <String, PlaybackProgress>{},
            );

        final query = _query.trim().toLowerCase();
        final filteredFavorites = query.isEmpty
            ? data.favorites
            : data.favorites
                  .where((item) => _favoriteMatchesQuery(item, query))
                  .toList(growable: false);

        final filteredHistory = query.isEmpty
            ? data.history
            : data.history
                  .where((item) => _historyMatchesQuery(item, query))
                  .toList(growable: false);

        final groupedHistory = _groupHistoryByDate(filteredHistory);

        return RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              TextField(
                controller: _filterController,
                onChanged: (value) {
                  setState(() {
                    _query = value;
                  });
                },
                decoration: InputDecoration(
                  hintText: 'Filter favorites/history',
                  prefixIcon: const Icon(Icons.filter_alt_outlined),
                  suffixIcon: _query.trim().isEmpty
                      ? null
                      : IconButton(
                          onPressed: () {
                            _filterController.clear();
                            setState(() {
                              _query = '';
                            });
                          },
                          icon: const Icon(Icons.close),
                          tooltip: 'Clear',
                        ),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Text(
                    'Favorites',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const Spacer(),
                  Text('${filteredFavorites.length} items'),
                ],
              ),
              const SizedBox(height: 8),
              if (filteredFavorites.isEmpty)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.bookmark_border),
                    title: Text(
                      data.favorites.isEmpty
                          ? 'No favorites yet'
                          : 'No favorite matches "$query"',
                    ),
                    subtitle: const Text(
                      'Add favorites from anime detail page.',
                    ),
                  ),
                )
              else
                ...filteredFavorites.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Card(
                      child: ListTile(
                        onTap: () => _openDetail(item),
                        leading: PosterThumbnail(imageUrl: item.posterUrl),
                        title: Text(item.title),
                        subtitle: Text(item.subtitle),
                        trailing: PopupMenuButton<String>(
                          onSelected: (value) {
                            if (value == 'play') {
                              _playFavorite(item);
                            } else if (value == 'remove') {
                              _removeFavorite(item);
                            }
                          },
                          itemBuilder: (context) => const [
                            PopupMenuItem<String>(
                              value: 'play',
                              child: Text('Play'),
                            ),
                            PopupMenuItem<String>(
                              value: 'remove',
                              child: Text('Remove Favorite'),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              const SizedBox(height: 18),
              Row(
                children: [
                  Text(
                    'Watch History',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const Spacer(),
                  if (data.history.isNotEmpty)
                    TextButton(
                      onPressed: _clearHistory,
                      child: const Text('Clear'),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              if (groupedHistory.isEmpty)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.history),
                    title: Text(
                      data.history.isEmpty
                          ? 'No history yet'
                          : 'No history matches "$query"',
                    ),
                    subtitle: const Text('Playback records will appear here.'),
                  ),
                )
              else
                ...groupedHistory.expand((group) {
                  final widgets = <Widget>[
                    Padding(
                      padding: const EdgeInsets.only(top: 4, bottom: 8),
                      child: Text(
                        group.label,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                  ];

                  widgets.addAll(
                    group.items.map((item) {
                      final progress =
                          data.progressMap[PlaybackProgress.buildKey(
                            item.animeId,
                            item.episodeId,
                          )];

                      return Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Card(
                          child: ListTile(
                            leading: PosterThumbnail(imageUrl: item.posterUrl),
                            title: Text(item.animeTitle),
                            subtitle: Text(_historySubtitle(item, progress)),
                            isThreeLine: true,
                            trailing: FilledButton.tonal(
                              onPressed: () => _replayHistory(item),
                              child: const Text('Replay'),
                            ),
                          ),
                        ),
                      );
                    }),
                  );

                  return widgets;
                }),
            ],
          ),
        );
      },
    );
  }

  bool _favoriteMatchesQuery(AnimeSummary item, String query) {
    if (item.title.toLowerCase().contains(query)) {
      return true;
    }

    if (item.subtitle.toLowerCase().contains(query)) {
      return true;
    }

    if (item.fansubGroup.toLowerCase().contains(query)) {
      return true;
    }

    return false;
  }

  bool _historyMatchesQuery(WatchHistoryItem item, String query) {
    if (item.animeTitle.toLowerCase().contains(query)) {
      return true;
    }

    if (item.episodeTitle.toLowerCase().contains(query)) {
      return true;
    }

    return false;
  }

  List<_HistoryGroup> _groupHistoryByDate(List<WatchHistoryItem> historyItems) {
    final groups = <String, List<WatchHistoryItem>>{};

    for (final item in historyItems) {
      final local = item.playedAt.toLocal();
      final key = _dateKey(local);
      groups.putIfAbsent(key, () => <WatchHistoryItem>[]).add(item);
    }

    final sortedKeys = groups.keys.toList(growable: false)
      ..sort((a, b) => b.compareTo(a));

    return sortedKeys
        .map(
          (key) => _HistoryGroup(
            label: _dateLabelFromKey(key),
            items: groups[key] ?? <WatchHistoryItem>[],
          ),
        )
        .toList(growable: false);
  }

  String _historySubtitle(WatchHistoryItem item, PlaybackProgress? progress) {
    final lines = <String>[
      item.episodeTitle,
      _formatPlayedAt(item.playedAt.toLocal()),
    ];

    if (progress != null) {
      final percent = (progress.progressRatio * 100).round();
      lines.add('Resume at $percent%');
    }

    return lines.join('\n');
  }

  String _dateKey(DateTime dateTime) {
    String two(int value) => value.toString().padLeft(2, '0');
    return '${dateTime.year}-${two(dateTime.month)}-${two(dateTime.day)}';
  }

  String _dateLabelFromKey(String key) {
    final parts = key.split('-');
    if (parts.length != 3) {
      return key;
    }

    final year = int.tryParse(parts[0]) ?? 0;
    final month = int.tryParse(parts[1]) ?? 1;
    final day = int.tryParse(parts[2]) ?? 1;
    final date = DateTime(year, month, day);

    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));

    if (date == today) {
      return 'Today';
    }

    if (date == yesterday) {
      return 'Yesterday';
    }

    return key;
  }

  String _formatPlayedAt(DateTime dateTime) {
    String two(int value) => value.toString().padLeft(2, '0');
    return '${dateTime.year}-${two(dateTime.month)}-${two(dateTime.day)} '
        '${two(dateTime.hour)}:${two(dateTime.minute)}';
  }
}

class _LibraryData {
  const _LibraryData({
    required this.favorites,
    required this.history,
    required this.progressMap,
  });

  final List<AnimeSummary> favorites;
  final List<WatchHistoryItem> history;
  final Map<String, PlaybackProgress> progressMap;
}

class _HistoryGroup {
  const _HistoryGroup({required this.label, required this.items});

  final String label;
  final List<WatchHistoryItem> items;
}
