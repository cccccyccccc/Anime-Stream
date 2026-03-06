import '../entities/anime_detail.dart';
import '../entities/anime_summary.dart';

abstract class AnimeRepository {
  Future<List<AnimeSummary>> fetchHome();

  Future<List<AnimeSummary>> search(String query);

  Future<AnimeDetail> fetchDetail(String animeId);
}
