import '../../../../core/network/api_client.dart';
import '../../domain/entities/anime_detail.dart';
import '../../domain/entities/anime_summary.dart';
import '../../domain/repositories/anime_repository.dart';

class GatewayAnimeRepository implements AnimeRepository {
  GatewayAnimeRepository({required ApiClient apiClient})
    : _apiClient = apiClient;

  final ApiClient _apiClient;

  @override
  Future<List<AnimeSummary>> fetchHome() async {
    final data = await _apiClient.getJson('/home');
    final items = _extractItems(data);
    return items.map(AnimeSummary.fromMap).toList(growable: false);
  }

  @override
  Future<List<AnimeSummary>> search(String query) async {
    final data = await _apiClient.getJson(
      '/search',
      queryParameters: <String, String>{'q': query},
    );
    final items = _extractItems(data);
    return items.map(AnimeSummary.fromMap).toList(growable: false);
  }

  @override
  Future<AnimeDetail> fetchDetail(String animeId) async {
    final data = await _apiClient.getJson('/anime/$animeId');
    return AnimeDetail.fromMap(data);
  }

  List<Map<String, dynamic>> _extractItems(Map<String, dynamic> json) {
    final dynamic rawItems = json['items'] ?? json['results'] ?? <dynamic>[];
    if (rawItems is! List) {
      return <Map<String, dynamic>>[];
    }

    return rawItems
        .whereType<Map>()
        .map((item) => item.cast<String, dynamic>())
        .toList(growable: false);
  }
}
