import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_pos/core/models/modifier.dart';

void main() {
  group('Modifier', () {
    test('applyToPrice adds surcharges and subtracts discounts', () {
      const modifier = Modifier(
        surcharges: {'extra_shot': 1.00},
        discounts: {'loyalty': 0.50},
      );
      expect(modifier.applyToPrice(5.00), 5.50);
    });

    test('never returns a negative price', () {
      const modifier = Modifier(discounts: {'huge': 100.00});
      expect(modifier.applyToPrice(5.00), 0.0);
    });

    test('serializes and deserializes roundtrip', () {
      const modifier = Modifier(
        exclude: ['milk'],
        substitute: {'milk': 'oat'},
        extraQty: {'milk': 0.5},
      );
      final json = modifier.toJson();
      final decoded = Modifier.fromJson(json);
      expect(decoded.exclude, ['milk']);
      expect(decoded.substitute['milk'], 'oat');
      expect(decoded.extraQty['milk'], 0.5);
    });
  });
}
