/// Flavor configuration for the Nexus POS build variants.
class Flavor {
  final String name;
  final String defaultCurrencyCode;
  final String defaultCurrencySymbol;
  final bool usStateTaxEnabled;
  final bool stripeTerminalEnabled;
  final bool tipsEnabled;
  final bool splitBillEnabled;
  final String defaultPaymentMethod;

  const Flavor({
    required this.name,
    this.defaultCurrencyCode = 'USD',
    this.defaultCurrencySymbol = '\$',
    this.usStateTaxEnabled = true,
    this.stripeTerminalEnabled = false,
    this.tipsEnabled = false,
    this.splitBillEnabled = false,
    this.defaultPaymentMethod = 'cash',
  });

  static const Flavor standard = Flavor(name: 'nexus_pos');

  static const Flavor usPos = Flavor(
    name: 'nexus_us_pos',
    defaultCurrencyCode: 'USD',
    defaultCurrencySymbol: '\$',
    usStateTaxEnabled: true,
    stripeTerminalEnabled: true,
    tipsEnabled: true,
    splitBillEnabled: true,
    defaultPaymentMethod: 'card',
  );
}
