import 'package:flutter/foundation.dart';

import '../../features/anime/data/repositories/gateway_anime_repository.dart';
import '../../features/anime/data/repositories/mock_anime_repository.dart';
import '../../features/anime/domain/repositories/anime_repository.dart';
import '../../features/library/data/local/library_store.dart';
import '../../features/player/data/local/player_preferences_store.dart';
import '../../features/player/data/repositories/gateway_player_repository.dart';
import '../../features/player/data/repositories/mock_player_repository.dart';
import '../../features/player/domain/repositories/player_repository.dart';
import '../config/app_config.dart';
import '../network/api_client.dart';

class AppDependencies {
  AppDependencies._();

  static final ApiClient _apiClient = ApiClient(
    baseUrl: AppConfig.gatewayBaseUrl,
    requestTimeout: Duration(seconds: AppConfig.apiTimeoutSeconds),
  );

  static final ApiClient gatewayApiClient = _apiClient;

  static final AnimeRepository animeRepository = AppConfig.useMockGateway
      ? MockAnimeRepository()
      : GatewayAnimeRepository(apiClient: _apiClient);

  static final PlayerRepository playerRepository = AppConfig.useMockGateway
      ? MockPlayerRepository()
      : GatewayPlayerRepository(apiClient: _apiClient);

  static final LibraryStore libraryStore = LibraryStore();
  static final PlayerPreferencesStore playerPreferencesStore =
      PlayerPreferencesStore();

  static void debugPrintConfig() {
    debugPrint('USE_MOCK_GATEWAY=${AppConfig.useMockGateway}');
    debugPrint('GATEWAY_BASE_URL=${AppConfig.gatewayBaseUrl}');
    debugPrint('API_TIMEOUT_SECONDS=${AppConfig.apiTimeoutSeconds}');
  }
}
