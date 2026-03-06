import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../../../anime/domain/entities/anime_summary.dart';
import '../../domain/entities/playback_progress.dart';
import '../../domain/entities/watch_history_item.dart';

class LibraryStore {
  static const String _favoritesKey = 'library.favorites.v1';
  static const String _historyKey = 'library.history.v1';
  static const String _progressKey = 'library.progress.v1';
  static const int _maxHistoryItems = 100;
  static const int _maxProgressItems = 300;

  Future<List<AnimeSummary>> getFavorites() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_favoritesKey) ?? <String>[];

    final items = <AnimeSummary>[];
    for (final entry in raw) {
      try {
        final decoded = jsonDecode(entry);
        if (decoded is Map) {
          items.add(AnimeSummary.fromMap(decoded.cast<String, dynamic>()));
        }
      } catch (_) {
        // Ignore invalid entry.
      }
    }

    return items;
  }

  Future<bool> isFavorite(String animeId) async {
    final favorites = await getFavorites();
    return favorites.any((item) => item.id == animeId);
  }

  Future<bool> toggleFavorite(AnimeSummary item) async {
    final favorites = await getFavorites();
    final exists = favorites.any((e) => e.id == item.id);

    if (exists) {
      favorites.removeWhere((e) => e.id == item.id);
    } else {
      favorites.insert(0, item);
    }

    await _saveFavorites(favorites);
    return !exists;
  }

  Future<void> removeFavorite(String animeId) async {
    final favorites = await getFavorites();
    favorites.removeWhere((item) => item.id == animeId);
    await _saveFavorites(favorites);
  }

  Future<List<WatchHistoryItem>> getHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_historyKey) ?? <String>[];

    final items = <WatchHistoryItem>[];
    for (final entry in raw) {
      try {
        final decoded = jsonDecode(entry);
        if (decoded is Map) {
          items.add(WatchHistoryItem.fromMap(decoded.cast<String, dynamic>()));
        }
      } catch (_) {
        // Ignore invalid entry.
      }
    }

    items.sort((a, b) => b.playedAt.compareTo(a.playedAt));
    return items;
  }

  Future<void> addHistory(WatchHistoryItem item) async {
    final history = await getHistory();
    history.removeWhere(
      (e) => e.animeId == item.animeId && e.episodeId == item.episodeId,
    );
    history.insert(0, item);

    if (history.length > _maxHistoryItems) {
      history.removeRange(_maxHistoryItems, history.length);
    }

    await _saveHistory(history);
  }

  Future<void> clearHistory() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_historyKey);
  }

  Future<List<PlaybackProgress>> getAllProgress() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_progressKey) ?? <String>[];

    final items = <PlaybackProgress>[];
    for (final entry in raw) {
      try {
        final decoded = jsonDecode(entry);
        if (decoded is Map) {
          items.add(PlaybackProgress.fromMap(decoded.cast<String, dynamic>()));
        }
      } catch (_) {
        // Ignore invalid entry.
      }
    }

    items.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
    return items;
  }

  Future<PlaybackProgress?> getProgress(
    String animeId,
    String episodeId,
  ) async {
    final items = await getAllProgress();
    final key = PlaybackProgress.buildKey(animeId, episodeId);

    for (final item in items) {
      if (item.key == key) {
        return item;
      }
    }

    return null;
  }

  Future<void> saveProgress(PlaybackProgress progress) async {
    final items = await getAllProgress();
    items.removeWhere((item) => item.key == progress.key);

    final normalizedDuration = progress.durationMs < 0
        ? 0
        : progress.durationMs;
    final normalizedPosition = progress.positionMs < 0
        ? 0
        : progress.positionMs;

    final isValid = normalizedDuration > 0 && normalizedPosition > 0;
    final isAlmostFinished =
        isValid && normalizedPosition >= (normalizedDuration - 2000);

    if (isValid && !isAlmostFinished) {
      items.insert(
        0,
        progress.copyWith(
          positionMs: normalizedPosition,
          durationMs: normalizedDuration,
        ),
      );
    }

    if (items.length > _maxProgressItems) {
      items.removeRange(_maxProgressItems, items.length);
    }

    await _saveProgress(items);
  }

  Future<void> clearProgress() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_progressKey);
  }

  Future<void> _saveFavorites(List<AnimeSummary> favorites) async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = favorites
        .map((item) => jsonEncode(item.toMap()))
        .toList(growable: false);
    await prefs.setStringList(_favoritesKey, encoded);
  }

  Future<void> _saveHistory(List<WatchHistoryItem> history) async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = history
        .map((item) => jsonEncode(item.toMap()))
        .toList(growable: false);
    await prefs.setStringList(_historyKey, encoded);
  }

  Future<void> _saveProgress(List<PlaybackProgress> progressItems) async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = progressItems
        .map((item) => jsonEncode(item.toMap()))
        .toList(growable: false);
    await prefs.setStringList(_progressKey, encoded);
  }
}
