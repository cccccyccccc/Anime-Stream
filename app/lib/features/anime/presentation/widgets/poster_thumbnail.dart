import 'package:flutter/material.dart';

class PosterThumbnail extends StatelessWidget {
  const PosterThumbnail({
    super.key,
    required this.imageUrl,
    this.width = 52,
    this.height = 72,
    this.borderRadius = 10,
  });

  final String imageUrl;
  final double width;
  final double height;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    final hasImage = imageUrl.trim().isNotEmpty;

    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: SizedBox(
        width: width,
        height: height,
        child: hasImage
            ? Image.network(
                imageUrl,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) => _fallback(),
              )
            : _fallback(),
      ),
    );
  }

  Widget _fallback() {
    return const ColoredBox(
      color: Color(0xFF1F2937),
      child: Center(
        child: Icon(Icons.movie_creation_outlined, color: Colors.white70),
      ),
    );
  }
}
