import 'package:flutter/material.dart';

import '../core/config/app_constants.dart';
import 'router/app_router.dart';
import 'theme/app_theme.dart';

class AnimeStreamApp extends StatelessWidget {
  const AnimeStreamApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppConstants.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      initialRoute: AppRouter.home,
      onGenerateRoute: AppRouter.onGenerateRoute,
    );
  }
}
