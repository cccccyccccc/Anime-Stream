import 'package:flutter/material.dart';

import '../../../../core/config/app_config.dart';
import '../../../../core/config/app_constants.dart';
import '../../../../core/di/app_dependencies.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  static const int _maxJobCards = 6;
  static const Set<String> _terminalJobStatuses = <String>{
    'completed',
    'failed',
    'canceled',
  };

  late bool _showDiagnostics;
  Future<_GatewayDiagnosticsData>? _diagnosticsFuture;
  final Set<String> _pendingActions = <String>{};

  @override
  void initState() {
    super.initState();
    _showDiagnostics = !AppConfig.useMockGateway;
    if (_showDiagnostics) {
      _diagnosticsFuture = _loadDiagnostics();
    }
  }

  Future<_GatewayDiagnosticsData> _loadDiagnostics() async {
    final client = AppDependencies.gatewayApiClient;

    final health = await client.getJson('/health');
    final overview = await client.getJson('/workers/overview');
    final btJobsResult = await client.getJson('/workers/bt/jobs');
    final transcodeJobsResult = await client.getJson('/workers/transcode/jobs');

    final btJobs = _extractItems(btJobsResult);
    final transcodeJobs = _extractItems(transcodeJobsResult);

    return _GatewayDiagnosticsData(
      health: health,
      workersOverview: overview,
      btJobs: btJobs.take(_maxJobCards).toList(growable: false),
      transcodeJobs: transcodeJobs.take(_maxJobCards).toList(growable: false),
    );
  }

  List<Map<String, dynamic>> _extractItems(Map<String, dynamic> result) {
    final raw = result['items'];
    if (raw is! List) {
      return const <Map<String, dynamic>>[];
    }

    return raw
        .whereType<Map>()
        .map((item) => item.cast<String, dynamic>())
        .toList(growable: false);
  }

  Future<void> _refreshDiagnostics() async {
    if (!_showDiagnostics) {
      return;
    }

    setState(() {
      _diagnosticsFuture = _loadDiagnostics();
    });

    final future = _diagnosticsFuture;
    if (future != null) {
      await future;
    }
  }

  void _enableDiagnostics() {
    setState(() {
      _showDiagnostics = true;
      _diagnosticsFuture = _loadDiagnostics();
    });
  }

  Future<void> _runWorkerAction({
    required String worker,
    required String jobId,
    required String action,
  }) async {
    final trimmedJobId = jobId.trim();
    if (trimmedJobId.isEmpty) {
      return;
    }

    final key = _actionKey(worker: worker, jobId: trimmedJobId, action: action);
    if (_pendingActions.contains(key)) {
      return;
    }

    setState(() {
      _pendingActions.add(key);
    });

    try {
      await AppDependencies.gatewayApiClient.postJson(
        '/workers/$worker/jobs/$trimmedJobId/$action',
        body: const <String, dynamic>{},
      );

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '${worker.toUpperCase()} job $action accepted: $trimmedJobId',
          ),
        ),
      );

      await _refreshDiagnostics();
    } catch (error) {
      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to $action $worker job: $error')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _pendingActions.remove(key);
        });
      }
    }
  }

  String _actionKey({
    required String worker,
    required String jobId,
    required String action,
  }) {
    return '$worker:$jobId:$action';
  }

  bool _isActionPending({
    required String worker,
    required String jobId,
    required String action,
  }) {
    final key = _actionKey(worker: worker, jobId: jobId, action: action);
    return _pendingActions.contains(key);
  }

  @override
  Widget build(BuildContext context) {
    if (!_showDiagnostics) {
      return _buildManualModeView();
    }

    return FutureBuilder<_GatewayDiagnosticsData>(
      future: _diagnosticsFuture,
      builder: (context, snapshot) {
        return RefreshIndicator(
          onRefresh: _refreshDiagnostics,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              _buildStaticCards(),
              const SizedBox(height: 10),
              if (snapshot.connectionState == ConnectionState.waiting)
                const Card(
                  child: ListTile(
                    leading: SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    title: Text('Loading gateway diagnostics...'),
                  ),
                )
              else if (snapshot.hasError)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.error_outline),
                    title: const Text('Gateway diagnostics failed'),
                    subtitle: Text(snapshot.error.toString()),
                    trailing: FilledButton(
                      onPressed: _refreshDiagnostics,
                      child: const Text('Retry'),
                    ),
                  ),
                )
              else
                ..._buildDiagnosticsCards(context, snapshot.data),
            ],
          ),
        );
      },
    );
  }

  Widget _buildManualModeView() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildStaticCards(),
        const SizedBox(height: 10),
        Card(
          child: ListTile(
            leading: const Icon(Icons.build_circle_outlined),
            title: const Text('Gateway diagnostics are off'),
            subtitle: const Text(
              'You are using mock repositories. Enable diagnostics to query /health and worker queues.',
            ),
            trailing: FilledButton(
              onPressed: _enableDiagnostics,
              child: const Text('Enable'),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildStaticCards() {
    return Column(
      children: [
        const Card(
          child: ListTile(
            leading: Icon(Icons.storage),
            title: Text('Data Source'),
            subtitle: Text(AppConstants.sourceHost),
          ),
        ),
        const SizedBox(height: 10),
        Card(
          child: ListTile(
            leading: const Icon(Icons.cloud),
            title: const Text('Gateway Mode'),
            subtitle: Text(
              AppConfig.useMockGateway
                  ? 'Mock repository (default for local development)'
                  : 'Remote gateway: ${AppConfig.gatewayBaseUrl}',
            ),
          ),
        ),
        const SizedBox(height: 10),
        const Card(
          child: ListTile(
            leading: Icon(Icons.info_outline),
            title: Text('Single-device mode'),
            subtitle: Text('No login. Data is local-only.'),
          ),
        ),
      ],
    );
  }

  List<Widget> _buildDiagnosticsCards(
    BuildContext context,
    _GatewayDiagnosticsData? data,
  ) {
    if (data == null) {
      return const <Widget>[];
    }

    final health = data.health;
    final sourceMode = _s(health['sourceMode'], fallback: 'unknown');
    final service = _s(health['service'], fallback: 'unknown-service');
    final sessionCount = _s(health['sessionCount'], fallback: '0');
    final btWorkerMode = _s(health['btWorkerMode'], fallback: 'unknown');
    final transcodeWorkerMode = _s(
      health['transcodeWorkerMode'],
      fallback: 'unknown',
    );

    final btInfo = _extractWorkerInfo(data.workersOverview, 'bt');
    final transcodeInfo = _extractWorkerInfo(data.workersOverview, 'transcode');

    return <Widget>[
      Card(
        child: ListTile(
          leading: const Icon(Icons.monitor_heart_outlined),
          title: Text(
            'Gateway Health: ${_s(health['status'], fallback: 'unknown')}',
          ),
          subtitle: Text(
            'Service: $service\nSource mode: $sourceMode\nWorkers: BT=$btWorkerMode, Transcode=$transcodeWorkerMode\nSessions: $sessionCount',
          ),
          isThreeLine: true,
          trailing: IconButton(
            onPressed: _refreshDiagnostics,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh diagnostics',
          ),
        ),
      ),
      const SizedBox(height: 10),
      Card(
        child: ListTile(
          leading: const Icon(Icons.hub_outlined),
          title: const Text('Worker Overview'),
          subtitle: Text(
            'BT: ${btInfo.total} jobs (${btInfo.statusSummary})\n'
            'Transcode: ${transcodeInfo.total} jobs (${transcodeInfo.statusSummary})',
          ),
          isThreeLine: true,
        ),
      ),
      const SizedBox(height: 16),
      Text('Recent BT Jobs', style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 8),
      ..._buildJobCards(data.btJobs, kindLabel: 'BT', workerKey: 'bt'),
      const SizedBox(height: 16),
      Text(
        'Recent Transcode Jobs',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      const SizedBox(height: 8),
      ..._buildJobCards(
        data.transcodeJobs,
        kindLabel: 'Transcode',
        workerKey: 'transcode',
      ),
    ];
  }

  _WorkerInfo _extractWorkerInfo(Map<String, dynamic> overview, String key) {
    final raw = overview[key];
    if (raw is! Map) {
      return const _WorkerInfo(total: 0, statusSummary: 'no data');
    }

    final map = raw.cast<String, dynamic>();
    final total = int.tryParse(_s(map['total'], fallback: '0')) ?? 0;

    final countsRaw = map['statusCounts'];
    if (countsRaw is! Map) {
      return _WorkerInfo(total: total, statusSummary: 'no status counts');
    }

    final parts = <String>[];
    for (final entry in countsRaw.entries) {
      parts.add('${entry.key}:${entry.value}');
    }

    return _WorkerInfo(
      total: total,
      statusSummary: parts.isEmpty ? 'none' : parts.join(', '),
    );
  }

  List<Widget> _buildJobCards(
    List<Map<String, dynamic>> items, {
    required String kindLabel,
    required String workerKey,
  }) {
    if (items.isEmpty) {
      return const <Widget>[
        Card(
          child: ListTile(
            leading: Icon(Icons.inbox_outlined),
            title: Text('No jobs yet'),
            subtitle: Text('Create playback sessions to enqueue worker jobs.'),
          ),
        ),
      ];
    }

    return items
        .map(
          (item) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: _buildJobCard(
              item,
              kindLabel: kindLabel,
              workerKey: workerKey,
            ),
          ),
        )
        .toList(growable: false);
  }

  Widget _buildJobCard(
    Map<String, dynamic> item, {
    required String kindLabel,
    required String workerKey,
  }) {
    final status = _s(item['status'], fallback: 'unknown');
    final loweredStatus = status.toLowerCase();
    final jobId = _s(item['jobId']);
    final canRetry = _toBool(item['canRetry']) && loweredStatus == 'failed';
    final canCancel = !_isTerminalStatus(loweredStatus);

    final retryPending = _isActionPending(
      worker: workerKey,
      jobId: jobId,
      action: 'retry',
    );
    final cancelPending = _isActionPending(
      worker: workerKey,
      jobId: jobId,
      action: 'cancel',
    );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '$kindLabel · $status',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 6),
            Text(
              'Job: ${_s(item['jobId'])}\n'
              'Session: ${_s(item['sessionId'])}\n'
              'Progress: ${_s(item['progressPercent'], fallback: '0')}%\n'
              '${_s(item['message'])}',
            ),
            if (canRetry || canCancel) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (canRetry)
                    FilledButton.tonalIcon(
                      onPressed: retryPending
                          ? null
                          : () => _runWorkerAction(
                              worker: workerKey,
                              jobId: jobId,
                              action: 'retry',
                            ),
                      icon: const Icon(Icons.replay_outlined),
                      label: Text(retryPending ? 'Retrying...' : 'Retry'),
                    ),
                  if (canCancel)
                    OutlinedButton.icon(
                      onPressed: cancelPending
                          ? null
                          : () => _runWorkerAction(
                              worker: workerKey,
                              jobId: jobId,
                              action: 'cancel',
                            ),
                      icon: const Icon(Icons.stop_circle_outlined),
                      label: Text(cancelPending ? 'Canceling...' : 'Cancel'),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  bool _toBool(dynamic value) {
    if (value is bool) {
      return value;
    }

    if (value is num) {
      return value != 0;
    }

    final text = (value ?? '').toString().trim().toLowerCase();
    return text == 'true' || text == '1' || text == 'yes';
  }

  bool _isTerminalStatus(String status) {
    return _terminalJobStatuses.contains(status.trim().toLowerCase());
  }

  String _s(dynamic value, {String fallback = '-'}) {
    final text = (value ?? '').toString().trim();
    return text.isEmpty ? fallback : text;
  }
}

class _GatewayDiagnosticsData {
  const _GatewayDiagnosticsData({
    required this.health,
    required this.workersOverview,
    required this.btJobs,
    required this.transcodeJobs,
  });

  final Map<String, dynamic> health;
  final Map<String, dynamic> workersOverview;
  final List<Map<String, dynamic>> btJobs;
  final List<Map<String, dynamic>> transcodeJobs;
}

class _WorkerInfo {
  const _WorkerInfo({required this.total, required this.statusSummary});

  final int total;
  final String statusSummary;
}
