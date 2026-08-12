class Modifier {
  final List<String> exclude;
  final Map<String, String> substitute;
  final Map<String, double> extraQty;
  final Map<String, double> surcharges;
  final Map<String, double> discounts;

  const Modifier({
    this.exclude = const [],
    this.substitute = const {},
    this.extraQty = const {},
    this.surcharges = const {},
    this.discounts = const {},
  });

  Map<String, dynamic> toJson() => {
        'exclude': exclude,
        'substitute': substitute,
        'extra_qty': extraQty,
        'surcharges': surcharges,
        'discounts': discounts,
      };

  factory Modifier.fromJson(Map<String, dynamic> json) {
    return Modifier(
      exclude: List<String>.from(json['exclude'] ?? []),
      substitute: Map<String, String>.from(json['substitute'] ?? {}),
      extraQty: Map<String, double>.from(
        (json['extra_qty'] ?? {}).map((k, v) => MapEntry(k, (v as num).toDouble())),
      ),
      surcharges: Map<String, double>.from(
        (json['surcharges'] ?? {}).map((k, v) => MapEntry(k, (v as num).toDouble())),
      ),
      discounts: Map<String, double>.from(
        (json['discounts'] ?? {}).map((k, v) => MapEntry(k, (v as num).toDouble())),
      ),
    );
  }

  double applyToPrice(double base) {
    double price = base;
    for (final v in surcharges.values) {
      price += v;
    }
    for (final v in discounts.values) {
      price -= v;
    }
    return price > 0 ? price : 0;
  }
}
