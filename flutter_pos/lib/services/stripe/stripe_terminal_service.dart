import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_stripe/flutter_stripe.dart';
import 'package:stripe_terminal/stripe_terminal.dart';

class StripeTerminalService {
  final StripeTerminal _terminal = StripeTerminal.instance;
  bool _initialized = false;
  String? _backendUrl;
  Dio? _dio;
  StreamSubscription<PaymentStatusUpdate>? _statusSubscription;
  StreamSubscription<Reader>? _readerSubscription;

  /// `stripePublishableKey` is the public publishable key used to configure the
  /// Stripe SDK. Ephemeral reader connection tokens are fetched from the
  /// backend endpoint `{backendUrl}/stripe/connection-token`, which must return
  /// `{"secret": "<ephemeral_key_secret>"}`.
  Future<void> initialize({
    required String backendUrl,
    required String stripePublishableKey,
  }) async {
    if (_initialized) return;

    _backendUrl = backendUrl;
    _dio = Dio(BaseOptions(connectTimeout: const Duration(seconds: 10)));

    if (stripePublishableKey.isNotEmpty) {
      Stripe.publishableKey = stripePublishableKey;
      await Stripe.instance.applySettings();
    }

    _terminal.setConnectionTokenFactory((params) async {
      if (_backendUrl == null || _backendUrl!.isEmpty) {
        throw Exception('StripeTerminalService: backendUrl is not configured.');
      }
      final response = await _dio!.get<Map<String, dynamic>>(
        '$_backendUrl/stripe/connection-token',
      );
      if (response.data == null) {
        throw Exception('StripeTerminalService: empty connection token response.');
      }
      final secret = response.data!['secret'] as String?;
      if (secret == null || secret.isEmpty) {
        throw Exception(
            'StripeTerminalService: backend did not return a connection token secret.');
      }
      return secret;
    });

    _statusSubscription = _terminal.onConnectionStatusChange.listen((status) {
      // log status
    });
    _readerSubscription = _terminal.onReaderDisconnect.listen((_) {
      // log disconnect
    });

    _initialized = true;
  }

  Future<bool> discoverReaders({bool simulated = false}) async {
    if (!_initialized) return false;
    try {
      final readers = await _terminal.discoverReaders(
        isSimulated: simulated,
        discoveryMethod: DiscoveryMethod.bluetoothScan,
      ).toList();
      return readers.isNotEmpty;
    } catch (e) {
      return false;
    }
  }

  Future<bool> connectToReader(Reader reader) async {
    if (!_initialized) return false;
    try {
      final result = await _terminal.connectBluetoothReader(reader);
      return result;
    } catch (e) {
      return false;
    }
  }

  Future<bool> collectPayment(double amount) async {
    if (!_initialized) return false;
    try {
      final intent = await _terminal.createPaymentIntent(
        amount: (amount * 100).toInt(),
        currency: 'usd',
      );
      final processed = await _terminal.collectPaymentMethod(intent);
      final captured = await _terminal.processPayment(processed);
      return captured.status == PaymentIntentStatus.succeeded;
    } catch (e) {
      return false;
    }
  }

  Future<void> disconnect() async {
    await _statusSubscription?.cancel();
    await _readerSubscription?.cancel();
    _dio?.close(force: true);
    _dio = null;
    if (_initialized) {
      await _terminal.disconnectReader();
      _initialized = false;
    }
  }
}