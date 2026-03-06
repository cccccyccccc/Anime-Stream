import '../entities/play_session.dart';

abstract class PlayerRepository {
  Future<PlaySession> createPlaySession({
    required String animeTitle,
    required String sourceId,
    required String episodeId,
  });

  Future<PlaySession> getPlaySessionStatus({required String sessionId});

  Future<PlaySession> retryPlaySession({required String sessionId});

  Future<void> cancelPlaySession({required String sessionId});
}
