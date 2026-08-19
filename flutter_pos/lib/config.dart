/// Build-time configuration for the POS app.
///
/// Override at build/run time with --dart-define:
///   flutter run --dart-define=ODOO_BASE_URL=https://erp.example.com
///   flutter run --dart-define=AI_BASE_URL=https://ai.example.com
library;

const String odooBaseUrl = String.fromEnvironment(
  'ODOO_BASE_URL',
  defaultValue: 'http://localhost:8069',
);

const String aiBaseUrl = String.fromEnvironment(
  'AI_BASE_URL',
  defaultValue: 'http://localhost:8000',
);

const String stripePublishableKey = String.fromEnvironment(
  'STRIPE_PUBLISHABLE_KEY',
  defaultValue: '',
);
