class AnimeEpisode {
  const AnimeEpisode({
    required this.id,
    required this.title,
    required this.subtitle,
    this.publishedAt = '',
  });

  final String id;
  final String title;
  final String subtitle;
  final String publishedAt;

  factory AnimeEpisode.fromMap(Map<String, dynamic> map) {
    return AnimeEpisode(
      id: (map['id'] ?? '').toString(),
      title: (map['title'] ?? '').toString(),
      subtitle: (map['subtitle'] ?? map['size'] ?? '').toString(),
      publishedAt: (map['publishedAt'] ?? map['pubDate'] ?? '').toString(),
    );
  }
}
