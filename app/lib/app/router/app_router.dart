import 'package:flutter/material.dart';

import '../../features/anime/presentation/pages/anime_detail_page.dart';
import '../../features/player/presentation/pages/player_page.dart';
import '../../features/shell/presentation/pages/main_shell_page.dart';
import 'app_routes.dart';

class AppRouter {
  AppRouter._();

  static const String home = AppRoutes.home;

  static Route<dynamic> onGenerateRoute(RouteSettings settings) {
    switch (settings.name) {
      case AppRoutes.home:
        return MaterialPageRoute<void>(
          builder: (_) => const MainShellPage(),
          settings: settings,
        );
      case AppRoutes.animeDetail:
        final args = settings.arguments;
        if (args is AnimeDetailPageArgs) {
          return MaterialPageRoute<void>(
            builder: (_) => AnimeDetailPage(args: args),
            settings: settings,
          );
        }

        return MaterialPageRoute<void>(
          builder: (_) =>
              const _RouteErrorPage(message: 'Invalid anime detail arguments.'),
          settings: settings,
        );
      case AppRoutes.player:
        final args = settings.arguments;
        if (args is PlayerPageArgs) {
          return MaterialPageRoute<void>(
            builder: (_) => PlayerPage(args: args),
            settings: settings,
          );
        }

        return MaterialPageRoute<void>(
          builder: (_) =>
              const _RouteErrorPage(message: 'Invalid player arguments.'),
          settings: settings,
        );
      default:
        return MaterialPageRoute<void>(
          builder: (_) =>
              _RouteErrorPage(message: 'Route not found: ${settings.name}'),
          settings: settings,
        );
    }
  }
}

class _RouteErrorPage extends StatelessWidget {
  const _RouteErrorPage({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Navigation Error')),
      body: Center(child: Text(message)),
    );
  }
}
