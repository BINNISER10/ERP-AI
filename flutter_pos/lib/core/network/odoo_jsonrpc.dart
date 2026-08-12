import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:logger/logger.dart';

class OdooJsonRpcClient {
  final Logger _logger = Logger();
  final Dio _dio;
  final String baseUrl;
  final String database;
  int? _uid;
  String? _password;

  OdooJsonRpcClient({required this.baseUrl, required this.database})
      : _dio = Dio(
          BaseOptions(
            baseUrl: baseUrl,
            connectTimeout: const Duration(seconds: 30),
            receiveTimeout: const Duration(seconds: 60),
            headers: {'Content-Type': 'application/json'},
          ),
        ) {
    (_dio.httpClientAdapter as IOHttpClientAdapter).onHttpClientCreate =
        (HttpClient client) {
      client.badCertificateCallback = (X509Certificate cert, String host, int port) => true;
      return client;
    };
  }

  int? get uid => _uid;

  Future<bool> get isOnline async {
    final result = await Connectivity().checkConnectivity();
    return result != ConnectivityResult.none;
  }

  Future<Map<String, dynamic>> _call(
    String method,
    Map<String, dynamic> params, {
    int retries = 3,
    Duration? retryDelay,
  }) async {
    retryDelay ??= const Duration(seconds: 2);

    final payload = {
      'jsonrpc': '2.0',
      'method': 'call',
      'id': DateTime.now().millisecondsSinceEpoch,
      'params': params,
    };

    for (var attempt = 0; attempt < retries; attempt++) {
      try {
        final online = await isOnline;
        if (!online) {
          throw Exception('Device is offline. Request queued for sync.');
        }

        final response = await _dio.post<Map<String, dynamic>>(
          '/jsonrpc',
          data: payload,
        );

        if (response.data == null) {
          throw Exception('Empty response from server.');
        }

        final data = response.data!;
        if (data.containsKey('error')) {
          throw Exception('Odoo error: ${data['error']}');
        }
        return data['result'] as Map<String, dynamic>;
      } on DioException catch (e) {
        _logger.e('JSON-RPC attempt $attempt failed', error: e);
        if (attempt == retries - 1) {
          rethrow;
        }
        await Future.delayed(retryDelay * (attempt + 1));
      } catch (e) {
        _logger.e('JSON-RPC error', error: e);
        if (attempt == retries - 1) {
          rethrow;
        }
        await Future.delayed(retryDelay * (attempt + 1));
      }
    }

    throw Exception('JSON-RPC call failed after $retries attempts.');
  }

  Future<Map<String, dynamic>> authenticate({required String login, required String password}) async {
    final result = await _call(
      'call',
      {
        'service': 'common',
        'method': 'login',
        'args': [database, login, password],
      },
    );
    if (result['result'] == false) {
      throw Exception('Authentication failed');
    }
    _uid = (result['result'] as int);
    _password = password;
    return result;
  }

  Future<Map<String, dynamic>> callKw({
    required String model,
    required String method,
    List<dynamic> args = const [],
    Map<String, dynamic> kwargs = const {},
  }) async {
    if (_uid == null || _password == null) {
      throw Exception('Not authenticated. Call authenticate() first.');
    }
    return _call(
      'call',
      {
        'service': 'object',
        'method': 'execute_kw',
        'args': [
          database,
          _uid,
          _password,
          model,
          method,
          args,
          kwargs,
        ],
      },
    );
  }

  Future<Map<String, dynamic>> customGateway(
    String method,
    Map<String, dynamic> params,
  ) async {
    final body = {
      'jsonrpc': '2.0',
      'method': method,
      'id': DateTime.now().millisecondsSinceEpoch,
      'params': params,
    };
    final response = await _dio.post<Map<String, dynamic>>(
      '/nexus_pos/jsonrpc',
      data: body,
    );
    if (response.data == null) throw Exception('Empty response');
    if (response.data!.containsKey('error')) {
      throw Exception('Gateway error: ${response.data!['error']}');
    }
    return response.data!['result'] as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> authenticatePos({required String login, required String password}) async {
    return customGateway('authenticate', {'login': login, 'password': password});
  }

  Future<Map<String, dynamic>> getCatalog({int? companyId}) async {
    return customGateway('get_catalog', {'company_id': companyId});
  }

  Future<Map<String, dynamic>> postOfflineOrders(List<Map<String, dynamic>> orders) async {
    return customGateway('post_offline_orders', {'orders': orders});
  }
}
