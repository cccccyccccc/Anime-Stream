import 'package:flutter/material.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/di/app_dependencies.dart';
import '../../../anime/domain/entities/anime_summary.dart';
import '../../../anime/presentation/pages/anime_detail_page.dart';
import '../../../anime/presentation/widgets/poster_thumbnail.dart';
import '../../../player/presentation/pages/player_page.dart';

class SearchPage extends StatefulWidget {
  const SearchPage({super.key});

  @override
  State<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  final TextEditingController _controller = TextEditingController();
  List<AnimeSummary> _results = <AnimeSummary>[];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _search();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final result = await AppDependencies.animeRepository.search(
        _controller.text.trim(),
      );
      if (!mounted) {
        return;
      }

      setState(() {
        _results = result;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _error = error.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  Future<void> _openPlayer(AnimeSummary item) async {
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

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Play session failed: $error')));
    }
  }

  void _openDetail(AnimeSummary item) {
    Navigator.pushNamed(
      context,
      AppRoutes.animeDetail,
      arguments: AnimeDetailPageArgs(animeId: item.id, title: item.title),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        TextField(
          controller: _controller,
          onSubmitted: (_) => _search(),
          decoration: InputDecoration(
            hintText: 'Search anime title, group, or keyword',
            prefixIcon: const Icon(Icons.search),
            suffixIcon: IconButton(
              onPressed: _loading ? null : _search,
              icon: const Icon(Icons.send),
              tooltip: 'Search',
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (_loading)
          const Center(child: CircularProgressIndicator())
        else if (_error != null)
          Card(
            child: ListTile(
              title: const Text('Search failed'),
              subtitle: Text(_error!),
              trailing: FilledButton(
                onPressed: _search,
                child: const Text('Retry'),
              ),
            ),
          )
        else if (_results.isEmpty)
          const Card(
            child: ListTile(
              title: Text('No result'),
              subtitle: Text('Try another keyword.'),
            ),
          )
        else
          ..._results.map(
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
    );
  }
}
