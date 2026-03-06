import 'package:flutter/material.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/di/app_dependencies.dart';
import '../../../library/domain/entities/playback_progress.dart';
import '../../../player/presentation/pages/player_page.dart';
import '../../domain/entities/anime_detail.dart';
import '../../domain/entities/anime_episode.dart';
import '../../domain/entities/anime_summary.dart';
import '../widgets/poster_thumbnail.dart';

class AnimeDetailPageArgs {
  const AnimeDetailPageArgs({required this.animeId, required this.title});

  final String animeId;
  final String title;
}

class AnimeDetailPage extends StatefulWidget {
  const AnimeDetailPage({super.key, required this.args});

  final AnimeDetailPageArgs args;

  @override
  State<AnimeDetailPage> createState() => _AnimeDetailPageState();
}

class _AnimeDetailPageState extends State<AnimeDetailPage> {
  late Future<AnimeDetail> _detailFuture;
  bool _isFavorite = false;
  bool _favoriteLoading = false;
  Map<String, PlaybackProgress> _progressMap =
      const <String, PlaybackProgress>{};

  @override
  void initState() {
    super.initState();
    _detailFuture = AppDependencies.animeRepository.fetchDetail(
      widget.args.animeId,
    );
    _loadFavoriteState();
    _loadEpisodeProgress();
  }

  Future<void> _loadFavoriteState() async {
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

  Future<void> _loadEpisodeProgress() async {
    final progressItems = await AppDependencies.libraryStore.getAllProgress();
    final map = <String, PlaybackProgress>{};

    for (final item in progressItems) {
      if (item.animeId == widget.args.animeId) {
        map[item.key] = item;
      }
    }

    if (!mounted) {
      return;
    }

    setState(() {
      _progressMap = map;
    });
  }

  Future<void> _refresh() async {
    setState(() {
      _detailFuture = AppDependencies.animeRepository.fetchDetail(
        widget.args.animeId,
      );
    });

    await _detailFuture;
    await _loadEpisodeProgress();
  }

  Future<void> _toggleFavorite(AnimeDetail detail) async {
    if (_favoriteLoading) {
      return;
    }

    setState(() {
      _favoriteLoading = true;
    });

    final firstEpisodeId = detail.episodes.isNotEmpty
        ? detail.episodes.first.id
        : 'ep-unknown';
    final firstSubtitle = detail.episodes.isNotEmpty
        ? detail.episodes.first.subtitle
        : '';

    final summary = AnimeSummary(
      id: detail.id,
      title: detail.title,
      subtitle: firstSubtitle,
      latestEpisodeId: firstEpisodeId,
      source: detail.source,
      posterUrl: detail.posterUrl,
      fansubGroup: detail.fansubGroup,
      publishedAt: detail.publishedAt,
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

  Future<void> _playEpisode(AnimeDetail detail, AnimeEpisode episode) async {
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      const SnackBar(content: Text('Creating play session...')),
    );

    try {
      final session = await AppDependencies.playerRepository.createPlaySession(
        animeTitle: detail.title,
        sourceId: detail.id,
        episodeId: episode.id,
      );

      if (!mounted) {
        return;
      }

      await Navigator.pushNamed(
        context,
        AppRoutes.player,
        arguments: PlayerPageArgs(
          animeId: detail.id,
          animeTitle: session.animeTitle,
          episodeId: episode.id,
          episodeTitle: session.episodeTitle.isNotEmpty
              ? session.episodeTitle
              : episode.title,
          streamUrl: session.streamUrl,
          source: session.source,
          posterUrl: detail.posterUrl,
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

      await _loadEpisodeProgress();
    } catch (error) {
      if (!mounted) {
        return;
      }

      messenger.showSnackBar(
        SnackBar(content: Text('Play session failed: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.args.title)),
      body: FutureBuilder<AnimeDetail>(
        future: _detailFuture,
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
                    title: const Text('Failed to load anime detail'),
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

          final detail = snapshot.data;
          if (detail == null) {
            return const Center(child: Text('Detail not available'));
          }

          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        PosterThumbnail(
                          imageUrl: detail.posterUrl,
                          width: 110,
                          height: 156,
                          borderRadius: 12,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                detail.title,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              const SizedBox(height: 8),
                              if (detail.fansubGroup.isNotEmpty)
                                Text('Fansub: ${detail.fansubGroup}'),
                              if (detail.publishedAt.isNotEmpty)
                                Text('Published: ${detail.publishedAt}'),
                              Text('Source: ${detail.source}'),
                              const SizedBox(height: 8),
                              FilledButton.tonalIcon(
                                onPressed: _favoriteLoading
                                    ? null
                                    : () => _toggleFavorite(detail),
                                icon: Icon(
                                  _isFavorite
                                      ? Icons.favorite
                                      : Icons.favorite_border,
                                ),
                                label: Text(
                                  _isFavorite ? 'Favorited' : 'Favorite',
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          detail.description.isEmpty
                              ? 'No description'
                              : detail.description,
                        ),
                        if (detail.tags.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: detail.tags
                                .map((tag) => Chip(label: Text(tag)))
                                .toList(growable: false),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Text('Episodes', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                if (detail.episodes.isEmpty)
                  const Card(child: ListTile(title: Text('No episodes found')))
                else
                  ...detail.episodes.map((episode) {
                    final progress =
                        _progressMap[PlaybackProgress.buildKey(
                          detail.id,
                          episode.id,
                        )];

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Card(
                        child: ListTile(
                          title: Text(episode.title),
                          subtitle: Text(_episodeSubtitle(episode, progress)),
                          trailing: FilledButton.tonal(
                            onPressed: () => _playEpisode(detail, episode),
                            child: const Text('Play'),
                          ),
                        ),
                      ),
                    );
                  }),
              ],
            ),
          );
        },
      ),
    );
  }

  String _episodeSubtitle(AnimeEpisode episode, PlaybackProgress? progress) {
    final parts = <String>[];

    if (episode.subtitle.isNotEmpty) {
      parts.add(episode.subtitle);
    }

    if (episode.publishedAt.isNotEmpty) {
      parts.add(episode.publishedAt);
    }

    if (progress != null) {
      final percent = (progress.progressRatio * 100).round();
      parts.add('Progress $percent%');
    }

    if (parts.isEmpty) {
      return 'No subtitle';
    }

    return parts.join(' · ');
  }
}
