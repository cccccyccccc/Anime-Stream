import 'anime_episode.dart';

class AnimeDetail {
  const AnimeDetail({
    required this.id,
    required this.title,
    required this.description,
    required this.source,
    required this.episodes,
    this.posterUrl = '',
    this.fansubGroup = '',
    this.publishedAt = '',
    this.tags = const <String>[],
  });

  final String id;
  final String title;
  final String description;
  final String source;
  final String posterUrl;
  final String fansubGroup;
  final String publishedAt;
  final List<String> tags;
  final List<AnimeEpisode> episodes;

  factory AnimeDetail.fromMap(Map<String, dynamic> map) {
    final rawEpisodes = map['episodes'];
    final episodes = <AnimeEpisode>[];

    if (rawEpisodes is List) {
      for (final item in rawEpisodes) {
        if (item is Map) {
          episodes.add(AnimeEpisode.fromMap(item.cast<String, dynamic>()));
        }
      }
    }

    final rawTags = map['tags'];
    final tags = <String>[];
    if (rawTags is List) {
      for (final item in rawTags) {
        tags.add(item.toString());
      }
    }

    return AnimeDetail(
      id: (map['id'] ?? '').toString(),
      title: (map['title'] ?? '').toString(),
      description: (map['description'] ?? '').toString(),
      source: (map['source'] ?? 'mikan.tangbai.cc').toString(),
      posterUrl: (map['posterUrl'] ?? map['cover'] ?? '').toString(),
      fansubGroup: (map['fansubGroup'] ?? map['group'] ?? '').toString(),
      publishedAt: (map['publishedAt'] ?? map['pubDate'] ?? '').toString(),
      tags: tags,
      episodes: episodes,
    );
  }
}
