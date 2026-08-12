import 'dart:async';
import 'dart:io';

import 'package:logger/logger.dart';

/// Mada POS service for Saudi Arabia local debit card terminals.
/// Wraps a serial/USB or network bridge to the Mada terminal.
class MadaPosService {
  final Logger _logger = Logger();
  Socket? _socket;
  StreamSubscription? _subscription;

  Future<bool> connect({required String host, int port = 4444}) async {
    try {
      _socket = await Socket.connect(host, port);
      _subscription = _socket!.listen(
        (data) => _logger.i('Mada recv: ${String.fromCharCodes(data)}'),
        onError: (e) => _logger.e('Mada error', error: e),
        onDone: () => _logger.i('Mada disconnected'),
      );
      return true;
    } catch (e) {
      _logger.e('Mada connect failed', error: e);
      return false;
    }
  }

  Future<bool> requestPayment(double amount, String currency) async {
    if (_socket == null) return false;
    final request = _buildMadaPacket(amount, currency);
    _socket!.write(request);
    // In a real integration, await terminal response and parse it.
    return true;
  }

  List<int> _buildMadaPacket(double amount, String currency) {
    // ISO 8583-like packet stub.
    final amountCents = (amount * 100).toInt().toString().padLeft(12, '0');
    final packet = 'SALE|$amountCents|$currency\x03';
    return packet.codeUnits;
  }

  Future<void> disconnect() async {
    await _subscription?.cancel();
    _socket?.destroy();
  }
}
