import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_pos/core/utils/tax_calculator.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('TaxCalculator', () {
    test('US state tax enabled by default', () async {
      await TaxCalculator.setUsStateTaxEnabled(true);
      expect(await TaxCalculator.isUsStateTaxEnabled(), isTrue);
    });

    test('calculates California state tax', () async {
      final tax = await TaxCalculator.totalTaxFor(100.0, 'CA');
      expect(tax, closeTo(7.25, 0.01));
    });

    test('calculates Los Angeles county tax when county matched', () async {
      final tax = await TaxCalculator.totalTaxFor(100.0, 'CA', county: 'Los Angeles');
      expect(tax, closeTo(8.75, 0.01));
    });

    test('returns no tax for unsupported state', () async {
      final tax = await TaxCalculator.totalTaxFor(100.0, 'ZZ');
      expect(tax, 0.0);
    });
  });
}
