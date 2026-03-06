import 'dart:async';
import 'dart:convert';
import 'dart:io';

class ApiClient {
  ApiClient({
    required this.baseUrl,
    HttpClient? httpClient,
    Duration requestTimeout = const Duration(seconds: 10),
  }) : _httpClient = httpClient ?? HttpClient(),
       _requestTimeout = requestTimeout {
    _httpClient.connectionTimeout = _requestTimeout;
  }

  final String baseUrl;
  final HttpClient _httpClient;
  final Duration _requestTimeout;

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, String>? queryParameters,
  }) async {
    final uri = _buildUri(path, queryParameters: queryParameters);

    try {
      final request = await _httpClient.getUrl(uri).timeout(_requestTimeout);
      final response = await request.close().timeout(_requestTimeout);
      return _decodeJsonResponse(response, uri: uri);
    } on TimeoutException {
      throw ApiException('Request timeout for $uri');
    }
  }

  Future<Map<String, dynamic>> postJson(
    String path, {
    required Map<String, dynamic> body,
  }) async {
    final uri = _buildUri(path);

    try {
      final request = await _httpClient.postUrl(uri).timeout(_requestTimeout);
      request.headers.contentType = ContentType.json;
      final payload = utf8.encode(jsonEncode(body));
      request.headers.contentLength = payload.length;
      request.add(payload);

      final response = await request.close().timeout(_requestTimeout);
      return _decodeJsonResponse(response, uri: uri);
    } on TimeoutException {
      throw ApiException('Request timeout for $uri');
    }
  }

  Uri _buildUri(String path, {Map<String, String>? queryParameters}) {
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    final base = Uri.parse(baseUrl);

    return base.replace(
      path: '${base.path}$normalizedPath'.replaceAll('//', '/'),
      queryParameters: queryParameters?.isEmpty ?? true
          ? null
          : queryParameters,
    );
  }

  Future<Map<String, dynamic>> _decodeJsonResponse(
    HttpClientResponse response, {
    required Uri uri,
  }) async {
    final raw = await utf8.decoder.bind(response).join();

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        'HTTP ${response.statusCode} for $uri',
        statusCode: response.statusCode,
        responseBody: raw,
      );
    }

    if (raw.isEmpty) {
      return <String, dynamic>{};
    }

    final decoded = jsonDecode(raw);
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }

    if (decoded is Map) {
      return decoded.cast<String, dynamic>();
    }

    throw ApiException(
      'Unexpected response format for $uri',
      responseBody: raw,
    );
  }
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.responseBody});

  final String message;
  final int? statusCode;
  final String? responseBody;

  @override
  String toString() {
    final body = responseBody?.trim() ?? '';
    if (body.isEmpty) {
      return 'ApiException(message: $message, statusCode: $statusCode)';
    }

    final compact = body.replaceAll(RegExp(r'\s+'), ' ');
    final preview = compact.length > 260
        ? '${compact.substring(0, 260)}...'
        : compact;

    return 'ApiException(message: $message, statusCode: $statusCode, responseBody: $preview)';
  }
}
