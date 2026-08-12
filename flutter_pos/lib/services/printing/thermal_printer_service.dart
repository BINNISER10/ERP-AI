import 'dart:typed_data';

import 'package:esc_pos_printer/esc_pos_printer.dart';
import 'package:esc_pos_utils/esc_pos_utils.dart';

import '../../core/models/order_payload.dart';

class ThermalPrinterService {
  NetworkPrinter? _printer;

  Future<void> discover() async {
    // Placeholder: in a real app, scan mDNS/UDP for local printers.
  }

  Future<bool> connect({required String host, int port = 9100}) async {
    try {
      const paper = PaperSize.mm80;
      final profile = await CapabilityProfile.load();
      _printer = NetworkPrinter(paper, profile);
      final resp = await _printer!.connect(host, port: port);
      return resp != null;
    } catch (e) {
      return false;
    }
  }

  Future<void> printReceipt(OrderPayload payload) async {
    if (_printer == null) {
      // Skip printing if no printer connected.
      return;
    }

    final p = _printer!;
    p.reset();
    p.text('Nexus POS', styles: const PosStyles(align: PosAlign.center, bold: true, height: PosTextSize.size2));
    p.text('Receipt', styles: const PosStyles(align: PosAlign.center));
    p.hr();
    p.text('Ref: ${payload.clientOrderRef}');
    p.text('Date: ${payload.orderDate}');
    p.hr();
    for (final line in payload.lines) {
      p.text('${line.name} x${line.quantity.toStringAsFixed(2)}');
      p.text('  @ \$${line.priceUnit.toStringAsFixed(2)}  \$${(line.priceUnit * line.quantity).toStringAsFixed(2)}');
    }
    p.hr();
    p.text('Subtotal: \$${(payload.amountTotal - payload.amountTax - payload.tipAmount).toStringAsFixed(2)}');
    p.text('Tax:      \$${payload.amountTax.toStringAsFixed(2)}');
    p.text('Tip:      \$${payload.tipAmount.toStringAsFixed(2)}');
    p.text('TOTAL:    \$${payload.amountTotal.toStringAsFixed(2)}', styles: const PosStyles(bold: true, height: PosTextSize.size2));
    p.hr();
    p.text('Thank you!', styles: const PosStyles(align: PosAlign.center));
    p.cut();
  }

  Future<void> printKitchenTicket(OrderPayload payload) async {
    if (_printer == null) return;
    final p = _printer!;
    p.reset();
    p.text('KITCHEN ORDER', styles: const PosStyles(align: PosAlign.center, bold: true, height: PosTextSize.size2));
    p.text('Ref: ${payload.clientOrderRef}');
    p.hr();
    for (final line in payload.lines) {
      p.text('${line.quantity.toStringAsFixed(0)}x ${line.name}');
      if (line.modifiers.toJson().isNotEmpty) {
        p.text('  M: ${line.modifiers.toJson()}', styles: const PosStyles(italic: true));
      }
    }
    p.cut();
  }

  Uint8List? ticket(OrderPayload payload) {
    // For advanced usage: return raw ESC/POS bytes for remote printing.
    return null;
  }
}
