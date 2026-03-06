import '../../../../core/config/app_constants.dart';
import '../../domain/entities/play_session.dart';
import '../../domain/repositories/player_repository.dart';

class MockPlayerRepository implements PlayerRepository {
  @override
  Future<PlaySession> createPlaySession({
    required String animeTitle,
    required String sourceId,
    required String episodeId,
  }) async {
    return PlaySession(
      sessionId: 'mock-$sourceId-$episodeId',
      animeTitle: animeTitle,
      streamUrl: AppConstants.sampleHlsUrl,
      source: 'mikan.tangbai.cc',
      status: PlaySessionStatus.playable,
      progressPercent: 100,
      pipelineStage: 'playable',
      statusMessage: 'Mock session is ready.',
      canRetry: false,
    );
  }

  @override
  Future<PlaySession> getPlaySessionStatus({required String sessionId}) async {
    return PlaySession(
      sessionId: sessionId,
      animeTitle: 'Mock Anime',
      streamUrl: AppConstants.sampleHlsUrl,
      source: 'mikan.tangbai.cc',
      status: PlaySessionStatus.playable,
      progressPercent: 100,
      pipelineStage: 'playable',
      statusMessage: 'Mock session is ready.',
      canRetry: false,
    );
  }

  @override
  Future<PlaySession> retryPlaySession({required String sessionId}) async {
    return getPlaySessionStatus(sessionId: sessionId);
  }

  @override
  Future<void> cancelPlaySession({required String sessionId}) async {
    return;
  }
}
