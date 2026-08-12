import 'dart:async';

import 'package:flutter_stripe/flutter_stripe.dart';
import 'package:stripe_terminal/stripe_terminal.dart';

class StripeTerminalService {
  final StripeTerminal _terminal = StripeTerminal.instance;
  bool _initialized = false;
  StreamSubscription<PaymentStatusUpdate>? _statusSubscription;
  StreamSubscription<Reader>? _readerSubscription;

  Future<void> initialize({required String backendUrl, String? token}) async {
    if (_initialized) return;

    Stripe.publishableKey = token ?? '';
    await Stripe.instance.applySettings();

    _terminal.setConnectionTokenFactory(
      (params) async {
        // In production, fetch from backend /connection_token.
        return token ?? '';
      },
    );

    _statusSubscription = _terminal.onConnectionStatusChange.listen((status) {
      // log status
    });
    _readerSubscription = _terminal.onReaderDisconnect.listen((_) {
      // log disconnect
    });

    _initialized = true;
  }

  Future<bool> discoverReaders() async {
    if (!_initialized) return false;
    try {
      final readers = await _terminal.discoverReaders(
        isSimulated: true,
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
    if (_initialized) {
      await _terminal.disconnectReader();
      _initialized = false;
    }
  }
}
