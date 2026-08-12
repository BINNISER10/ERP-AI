import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class TaxRate {
  final String stateCode;
  final String? county;
  final String? city;
  final double rate;
  final String taxType;

  TaxRate({
    required this.stateCode,
    this.county,
    this.city,
    required this.rate,
    this.taxType = 'state',
  });

  factory TaxRate.fromJson(Map<String, dynamic> json) {
    return TaxRate(
      stateCode: json['state'] as String,
      county: json['county'] as String?,
      city: json['city'] as String?,
      rate: (json['rate'] as num).toDouble(),
      taxType: json['jurisdiction'] as String? ?? 'state',
    );
  }
}

class TaxCalculator {
  static Future<bool> isUsStateTaxEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('enable_us_state_tax') ?? true;
  }

  static Future<void> setUsStateTaxEnabled(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('enable_us_state_tax', value);
  }

  /// Default static US tax table; in production, this should come from the server.
  static final List<TaxRate> _defaultRates = [
    TaxRate(stateCode: 'CA', rate: 0.0725, taxType: 'state'),
    TaxRate(stateCode: 'NY', rate: 0.04, taxType: 'state'),
    TaxRate(stateCode: 'TX', rate: 0.0625, taxType: 'state'),
    TaxRate(stateCode: 'FL', rate: 0.06, taxType: 'state'),
    TaxRate(stateCode: 'NV', rate: 0.0685, taxType: 'state'),
    TaxRate(stateCode: 'CA', county: 'Los Angeles', rate: 0.015, taxType: 'county'),
    TaxRate(stateCode: 'NY', city: 'New York City', rate: 0.04875, taxType: 'city'),
  ];

  static Future<List<TaxRate>> loadRates() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('us_tax_rates');
    if (raw == null) return _defaultRates;
    try {
      final decoded = jsonDecode(raw) as List;
      return decoded.map((e) => TaxRate.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {
      return _defaultRates;
    }
  }

  static Future<List<TaxRate>> calculateUsTax(
    double amount,
    String stateCode, {
    String? zipCode,
    String? county,
    String? city,
  }) async {
    if (!await isUsStateTaxEnabled()) {
      return [];
    }
    final rates = await loadRates();
    final matches = rates.where((r) {
      final stateMatch = r.stateCode.toUpperCase() == stateCode.toUpperCase();
      final countyMatch = r.county == null || (county != null && r.county!.toLowerCase() == county.toLowerCase());
      final cityMatch = r.city == null || (city != null && r.city!.toLowerCase() == city.toLowerCase());
      return stateMatch && countyMatch && cityMatch;
    }).toList();
    return matches;
  }

  static Future<double> totalTaxFor(
    double amount,
    String stateCode, {
    String? zipCode,
    String? county,
    String? city,
  }) async {
    final rates = await calculateUsTax(amount, stateCode, zipCode: zipCode, county: county, city: city);
    double tax = 0.0;
    for (final r in rates) {
      tax += amount * r.rate;
    }
    return double.parse(tax.toStringAsFixed(2));
  }
}
