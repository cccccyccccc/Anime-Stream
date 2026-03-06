class AppConfig {
  AppConfig._();

  static const bool useMockGateway = bool.fromEnvironment(
    'USE_MOCK_GATEWAY',
    defaultValue: true,
  );

  static const String gatewayBaseUrl = String.fromEnvironment(
    'GATEWAY_BASE_URL',
    defaultValue: 'http://10.0.2.2:8080',
  );

  static const int apiTimeoutSeconds = int.fromEnvironment(
    'API_TIMEOUT_SECONDS',
    defaultValue: 10,
  );
}
