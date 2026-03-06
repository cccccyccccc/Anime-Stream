import 'package:flutter/material.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../core/config/app_constants.dart';
import '../../../home/presentation/pages/home_page.dart';
import '../../../library/presentation/pages/library_page.dart';
import '../../../profile/presentation/pages/profile_page.dart';
import '../../../search/presentation/pages/search_page.dart';

class MainShellPage extends StatefulWidget {
  const MainShellPage({super.key});

  @override
  State<MainShellPage> createState() => _MainShellPageState();
}

class _MainShellPageState extends State<MainShellPage> {
  int _currentIndex = 0;
  int _homeRefreshTrigger = 0;
  int _libraryRefreshTrigger = 0;

  void _onTabTap(int index) {
    if (index == 0) {
      _homeRefreshTrigger++;
    }

    if (index == 2) {
      _libraryRefreshTrigger++;
    }

    setState(() {
      _currentIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      HomePage(refreshTrigger: _homeRefreshTrigger),
      const SearchPage(),
      LibraryPage(refreshTrigger: _libraryRefreshTrigger),
      const ProfilePage(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text(AppConstants.appName),
        actions: [
          IconButton(
            onPressed: () {},
            tooltip: 'Global Search',
            icon: const Icon(Icons.search),
          ),
          SizedBox(width: AppSpacing.sm),
        ],
      ),
      body: IndexedStack(index: _currentIndex, children: pages),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: _onTabTap,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
          BottomNavigationBarItem(
            icon: Icon(Icons.travel_explore),
            label: 'Search',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.video_library),
            label: 'Library',
          ),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}
