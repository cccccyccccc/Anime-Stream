class PlaySession {
  const PlaySession({
    required this.sessionId,
    required this.animeTitle,
    required this.streamUrl,
    required this.source,
    required this.status,
    this.episodeTitle = '',
    this.magnet = '',
    this.torrentUrl = '',
    this.pipelineStage = '',
    this.statusMessage = '',
    this.progressPercent = 0,
    this.btJobId = '',
    this.transcodeJobId = '',
    this.canRetry = false,
    this.failedStage = '',
    this.resolvedInputRef = '',
    this.btJobStatus = '',
    this.transcodeJobStatus = '',
    this.btErrorCode = '',
    this.transcodeErrorCode = '',
    this.btOutputRef = '',
    this.btOutputCandidateCount = 0,
    this.transcodeInputRef = '',
  });

  final String sessionId;
  final String animeTitle;
  final String streamUrl;
  final String source;
  final PlaySessionStatus status;
  final String episodeTitle;
  final String magnet;
  final String torrentUrl;
  final String pipelineStage;
  final String statusMessage;
  final int progressPercent;
  final String btJobId;
  final String transcodeJobId;
  final bool canRetry;
  final String failedStage;
  final String resolvedInputRef;
  final String btJobStatus;
  final String transcodeJobStatus;
  final String btErrorCode;
  final String transcodeErrorCode;
  final String btOutputRef;
  final int btOutputCandidateCount;
  final String transcodeInputRef;

  factory PlaySession.fromMap(Map<String, dynamic> map) {
    final btJob = _extractMap(map['btJob']);
    final transcodeJob = _extractMap(map['transcodeJob']);

    return PlaySession(
      sessionId: (map['sessionId'] ?? '').toString(),
      animeTitle: (map['animeTitle'] ?? '').toString(),
      streamUrl: (map['streamUrl'] ?? '').toString(),
      source: (map['source'] ?? 'mikan.tangbai.cc').toString(),
      status: _statusFromRaw(map['status']?.toString()),
      episodeTitle: (map['episodeTitle'] ?? '').toString(),
      magnet: (map['magnet'] ?? '').toString(),
      torrentUrl: (map['torrentUrl'] ?? '').toString(),
      pipelineStage: (map['pipelineStage'] ?? '').toString(),
      statusMessage: (map['statusMessage'] ?? '').toString(),
      progressPercent: _parsePercent(map['progressPercent']),
      btJobId: (map['btJobId'] ?? '').toString(),
      transcodeJobId: (map['transcodeJobId'] ?? '').toString(),
      canRetry: _parseBool(map['canRetry']),
      failedStage: (map['failedStage'] ?? '').toString(),
      resolvedInputRef: (map['resolvedInputRef'] ?? '').toString(),
      btJobStatus: (map['btJobStatus'] ?? btJob['status'] ?? '').toString(),
      transcodeJobStatus:
          (map['transcodeJobStatus'] ?? transcodeJob['status'] ?? '')
              .toString(),
      btErrorCode: (btJob['errorCode'] ?? '').toString(),
      transcodeErrorCode: (transcodeJob['errorCode'] ?? '').toString(),
      btOutputRef: (btJob['outputRef'] ?? '').toString(),
      btOutputCandidateCount: _parseInt(btJob['outputCandidateCount']),
      transcodeInputRef: (transcodeJob['inputRef'] ?? '').toString(),
    );
  }

  static Map<String, dynamic> _extractMap(dynamic raw) {
    if (raw is! Map) {
      return const <String, dynamic>{};
    }

    return raw.map((key, value) => MapEntry(key.toString(), value));
  }

  static bool _parseBool(dynamic raw) {
    if (raw is bool) {
      return raw;
    }

    final normalized = (raw ?? '').toString().trim().toLowerCase();
    return normalized == '1' || normalized == 'true' || normalized == 'yes';
  }

  static int _parsePercent(dynamic raw) {
    final value = double.tryParse((raw ?? '0').toString()) ?? 0;
    if (value < 0) {
      return 0;
    }
    if (value > 100) {
      return 100;
    }
    return value.round();
  }

  static int _parseInt(dynamic raw) {
    if (raw is int) {
      return raw;
    }
    if (raw is num) {
      return raw.toInt();
    }
    return int.tryParse((raw ?? '').toString()) ?? 0;
  }

  static PlaySessionStatus _statusFromRaw(String? raw) {
    switch (raw?.toLowerCase()) {
      case 'playable':
        return PlaySessionStatus.playable;
      case 'failed':
        return PlaySessionStatus.failed;
      default:
        return PlaySessionStatus.preparing;
    }
  }
}

enum PlaySessionStatus { preparing, playable, failed }
