import '../../../../core/network/api_client.dart';
import '../../domain/entities/play_session.dart';
import '../../domain/repositories/player_repository.dart';

class GatewayPlayerRepository implements PlayerRepository {
  GatewayPlayerRepository({required ApiClient apiClient})
    : _apiClient = apiClient;

  final ApiClient _apiClient;

  @override
  Future<PlaySession> createPlaySession({
    required String animeTitle,
    required String sourceId,
    required String episodeId,
  }) async {
    final normalizedSourceId = sourceId.trim();
    if (normalizedSourceId.isEmpty) {
      throw ArgumentError(
        'Missing sourceId for play session. Please open the anime from Home/Search and retry.',
      );
    }

    final normalizedEpisodeId = episodeId.trim().isEmpty
        ? 'latest'
        : episodeId.trim();

    final response = await _apiClient.postJson(
      '/play/session',
      body: <String, dynamic>{
        'animeTitle': animeTitle,
        'sourceId': normalizedSourceId,
        'episodeId': normalizedEpisodeId,
      },
    );

    return PlaySession.fromMap(response);
  }

  @override
  Future<PlaySession> getPlaySessionStatus({required String sessionId}) async {
    final response = await _apiClient.getJson(
      '/play/session/$sessionId/status',
    );
    return PlaySession.fromMap(response);
  }

  @override
  Future<PlaySession> retryPlaySession({required String sessionId}) async {
    final response = await _apiClient.postJson(
      '/play/session/$sessionId/retry',
      body: const <String, dynamic>{},
    );
    return PlaySession.fromMap(response);
  }

  @override
  Future<void> cancelPlaySession({required String sessionId}) async {
    final normalizedSessionId = sessionId.trim();
    if (normalizedSessionId.isEmpty) {
      return;
    }

    await _apiClient.postJson(
      '/play/session/$normalizedSessionId/cancel',
      body: const <String, dynamic>{},
    );
  }
}
