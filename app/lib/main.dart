import 'package:flutter/material.dart';

import 'app/app.dart';
import 'core/di/app_dependencies.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  AppDependencies.debugPrintConfig();
  runApp(const AnimeStreamApp());
}
