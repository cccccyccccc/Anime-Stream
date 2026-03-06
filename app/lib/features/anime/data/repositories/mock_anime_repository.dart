import '../../domain/entities/anime_detail.dart';
import '../../domain/entities/anime_episode.dart';
import '../../domain/entities/anime_summary.dart';
import '../../domain/repositories/anime_repository.dart';

class MockAnimeRepository implements AnimeRepository {
  static const List<AnimeSummary> _mockItems = [
    AnimeSummary(
      id: 'kusuriya-s2',
      title: 'The Apothecary Diaries S2 - 09',
      subtitle: '1080p · 24m · New',
      latestEpisodeId: 'ep-09',
      source: 'mikan.tangbai.cc',
      posterUrl: 'https://picsum.photos/seed/kusuriya/300/420',
      fansubGroup: 'Lagrange',
      publishedAt: '2026-03-05 22:12',
    ),
    AnimeSummary(
      id: 'solo-leveling-s2',
      title: 'Solo Leveling S2 - 11',
      subtitle: '1080p · 24m · New',
      latestEpisodeId: 'ep-11',
      source: 'mikan.tangbai.cc',
      posterUrl: 'https://picsum.photos/seed/solo/300/420',
      fansubGroup: 'Nekomoe',
      publishedAt: '2026-03-04 18:05',
    ),
    AnimeSummary(
      id: 'frieren',
      title: 'Frieren - 27',
      subtitle: '1080p · 24m',
      latestEpisodeId: 'ep-27',
      source: 'mikan.tangbai.cc',
      posterUrl: 'https://picsum.photos/seed/frieren/300/420',
      fansubGroup: 'Snow-Raws',
      publishedAt: '2026-03-02 12:40',
    ),
  ];

  @override
  Future<List<AnimeSummary>> fetchHome() async {
    await Future<void>.delayed(const Duration(milliseconds: 300));
    return _mockItems;
  }

  @override
  Future<List<AnimeSummary>> search(String query) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));

    if (query.trim().isEmpty) {
      return _mockItems;
    }

    final normalized = query.trim().toLowerCase();
    return _mockItems
        .where((item) => item.title.toLowerCase().contains(normalized))
        .toList(growable: false);
  }

  @override
  Future<AnimeDetail> fetchDetail(String animeId) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));

    final target = _mockItems.firstWhere(
      (item) => item.id == animeId,
      orElse: () => _mockItems.first,
    );

    return AnimeDetail(
      id: target.id,
      title: target.title,
      description:
          'Mock detail data from local source adapter placeholder. Replace this with parsed fields from mikan adapter.',
      source: target.source,
      posterUrl: target.posterUrl,
      fansubGroup: target.fansubGroup,
      publishedAt: target.publishedAt,
      tags: const <String>['Anime', '1080p', 'Subbed'],
      episodes: [
        AnimeEpisode(
          id: target.latestEpisodeId,
          title: target.title,
          subtitle: target.subtitle,
          publishedAt: target.publishedAt,
        ),
        AnimeEpisode(
          id: '${target.latestEpisodeId}-preview',
          title: '${target.title} (Preview)',
          subtitle: '720p · 2m',
          publishedAt: target.publishedAt,
        ),
      ],
    );
  }
}
