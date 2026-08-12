import 'dart:convert';
import 'dart:io';

import 'package:logger/logger.dart';

import '../../core/models/order_payload.dart';

class KdsService {
  final Logger _logger = Logger();

  Future<bool> sendToKitchen(
    OrderPayload payload, {
    String host = 'kds.local',
    int port = 8081,
  }) async {
    try {
      final client = HttpClient();
      final request = await client.post(host, port, '/api/kds/order');
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode(payload.toJson()));
      final response = await request.close();
      return response.statusCode == 200 || response.statusCode == 201;
    } catch (e) {
      _logger.e('KDS send failed', error: e);
      return false;
    }
  }

  Future<void> broadcastOrder(OrderPayload payload) async {
    // Broadcast over local UDP for kitchen displays.
    // This is a stub implementation.
  }
}
