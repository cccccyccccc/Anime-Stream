class PlaybackProgress {
  const PlaybackProgress({
    required this.animeId,
    required this.episodeId,
    required this.positionMs,
    required this.durationMs,
    required this.updatedAt,
  });

  final String animeId;
  final String episodeId;
  final int positionMs;
  final int durationMs;
  final DateTime updatedAt;

  String get key => buildKey(animeId, episodeId);

  double get progressRatio {
    if (durationMs <= 0) {
      return 0;
    }

    final ratio = positionMs / durationMs;
    if (ratio < 0) {
      return 0;
    }
    if (ratio > 1) {
      return 1;
    }
    return ratio;
  }

  PlaybackProgress copyWith({
    int? positionMs,
    int? durationMs,
    DateTime? updatedAt,
  }) {
    return PlaybackProgress(
      animeId: animeId,
      episodeId: episodeId,
      positionMs: positionMs ?? this.positionMs,
      durationMs: durationMs ?? this.durationMs,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  static String buildKey(String animeId, String episodeId) {
    return '$animeId::$episodeId';
  }

  factory PlaybackProgress.fromMap(Map<String, dynamic> map) {
    final updatedAtRaw = (map['updatedAt'] ?? '').toString();
    final parsed = DateTime.tryParse(updatedAtRaw) ?? DateTime.now().toUtc();

    return PlaybackProgress(
      animeId: (map['animeId'] ?? '').toString(),
      episodeId: (map['episodeId'] ?? '').toString(),
      positionMs: int.tryParse((map['positionMs'] ?? '0').toString()) ?? 0,
      durationMs: int.tryParse((map['durationMs'] ?? '0').toString()) ?? 0,
      updatedAt: parsed,
    );
  }

  Map<String, dynamic> toMap() {
    return <String, dynamic>{
      'animeId': animeId,
      'episodeId': episodeId,
      'positionMs': positionMs,
      'durationMs': durationMs,
      'updatedAt': updatedAt.toUtc().toIso8601String(),
    };
  }
}
