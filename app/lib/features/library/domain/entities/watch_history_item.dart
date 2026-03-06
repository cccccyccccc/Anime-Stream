class WatchHistoryItem {
  const WatchHistoryItem({
    required this.animeId,
    required this.animeTitle,
    required this.episodeId,
    required this.episodeTitle,
    required this.streamUrl,
    required this.source,
    required this.playedAt,
    this.posterUrl = '',
  });

  final String animeId;
  final String animeTitle;
  final String episodeId;
  final String episodeTitle;
  final String streamUrl;
  final String source;
  final DateTime playedAt;
  final String posterUrl;

  factory WatchHistoryItem.fromMap(Map<String, dynamic> map) {
    final playedAtRaw = (map['playedAt'] ?? '').toString();
    final parsed = DateTime.tryParse(playedAtRaw) ?? DateTime.now().toUtc();

    return WatchHistoryItem(
      animeId: (map['animeId'] ?? '').toString(),
      animeTitle: (map['animeTitle'] ?? '').toString(),
      episodeId: (map['episodeId'] ?? '').toString(),
      episodeTitle: (map['episodeTitle'] ?? '').toString(),
      streamUrl: (map['streamUrl'] ?? '').toString(),
      source: (map['source'] ?? '').toString(),
      playedAt: parsed,
      posterUrl: (map['posterUrl'] ?? '').toString(),
    );
  }

  Map<String, dynamic> toMap() {
    return <String, dynamic>{
      'animeId': animeId,
      'animeTitle': animeTitle,
      'episodeId': episodeId,
      'episodeTitle': episodeTitle,
      'streamUrl': streamUrl,
      'source': source,
      'playedAt': playedAt.toUtc().toIso8601String(),
      'posterUrl': posterUrl,
    };
  }
}
