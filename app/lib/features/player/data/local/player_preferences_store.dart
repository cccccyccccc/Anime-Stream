import 'package:shared_preferences/shared_preferences.dart';

class PlayerPreferencesStore {
  static const String _speedKey = 'player.playback_speed.v1';
  static const double _defaultSpeed = 1.0;

  Future<double> getPlaybackSpeed() async {
    final prefs = await SharedPreferences.getInstance();
    final speed = prefs.getDouble(_speedKey) ?? _defaultSpeed;
    if (speed < 0.5 || speed > 3.0) {
      return _defaultSpeed;
    }
    return speed;
  }

  Future<void> setPlaybackSpeed(double speed) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_speedKey, speed);
  }
}
