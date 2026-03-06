class AnimeSummary {
  const AnimeSummary({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.latestEpisodeId,
    required this.source,
    this.posterUrl = '',
    this.fansubGroup = '',
    this.publishedAt = '',
  });

  final String id;
  final String title;
  final String subtitle;
  final String latestEpisodeId;
  final String source;
  final String posterUrl;
  final String fansubGroup;
  final String publishedAt;

  factory AnimeSummary.fromMap(Map<String, dynamic> map) {
    return AnimeSummary(
      id: (map['id'] ?? '').toString(),
      title: (map['title'] ?? '').toString(),
      subtitle: (map['subtitle'] ?? '').toString(),
      latestEpisodeId: (map['latestEpisodeId'] ?? map['episodeId'] ?? '')
          .toString(),
      source: (map['source'] ?? 'mikan.tangbai.cc').toString(),
      posterUrl: (map['posterUrl'] ?? map['cover'] ?? '').toString(),
      fansubGroup: (map['fansubGroup'] ?? map['group'] ?? '').toString(),
      publishedAt: (map['publishedAt'] ?? map['pubDate'] ?? '').toString(),
    );
  }

  Map<String, dynamic> toMap() {
    return <String, dynamic>{
      'id': id,
      'title': title,
      'subtitle': subtitle,
      'latestEpisodeId': latestEpisodeId,
      'source': source,
      'posterUrl': posterUrl,
      'fansubGroup': fansubGroup,
      'publishedAt': publishedAt,
    };
  }
}
