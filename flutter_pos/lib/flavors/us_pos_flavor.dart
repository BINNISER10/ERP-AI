import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../app.dart';
import '../config.dart';
import '../core/database/app_database.dart';
import '../core/network/odoo_jsonrpc.dart';
import '../core/utils/tax_calculator.dart';
import '../features/catalog/bloc/catalog_bloc.dart';
import '../features/checkout/bloc/checkout_bloc.dart';
import '../features/pos/bloc/pos_bloc.dart';
import '../features/sync/bloc/sync_bloc.dart';
import '../flavor.dart';
import '../services/printing/thermal_printer_service.dart';
import '../services/stripe/stripe_terminal_service.dart';

class NexusUsPosApp extends StatelessWidget {
  final Flavor flavor;

  const NexusUsPosApp({super.key, required this.flavor});

  @override
  Widget build(BuildContext context) {
    return NexusPosApp();
  }
}

Future<void> configureUsPos() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('currency_symbol', '\$');
  await prefs.setString('currency_code', 'USD');
  await prefs.setInt('currency_decimals', 2);
  await prefs.setBool('enable_us_state_tax', true);
  await TaxCalculator.setUsStateTaxEnabled(true);
}

Future<void> runUsPos() async {
  WidgetsFlutterBinding.ensureInitialized();

  await configureUsPos();

  const flavor = Flavor.usPos;
  final database = AppDatabase();
  final client = OdooJsonRpcClient(baseUrl: odooBaseUrl, database: 'nexus_erp');
  final printer = ThermalPrinterService();
  final stripeTerminal = StripeTerminalService();
  final syncBloc = SyncBloc(client: client, database: database);

  // Activate Stripe Terminal for US card reader processing.
  if (flavor.stripeTerminalEnabled && stripePublishableKey.isNotEmpty) {
    await stripeTerminal.initialize(
      backendUrl: aiBaseUrl,
      stripePublishableKey: stripePublishableKey,
    );
  }

  await database.setup();

  // Push offline orders automatically once connectivity returns.
  Connectivity().onConnectivityChanged.listen((results) {
    if (results.any((r) => r != ConnectivityResult.none)) {
      syncBloc.add(const SyncPendingOrders());
    }
  });

  runApp(
    MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => CatalogBloc(client: client, database: database)),
        BlocProvider(create: (_) => PosBloc(database: database)),
        BlocProvider(
          create: (_) => CheckoutBloc(
            client: client,
            database: database,
            printer: printer,
            stripeTerminal: stripeTerminal,
          )..add(const SetPaymentMethod('card')),
        ),
        BlocProvider.value(value: syncBloc),
      ],
      child: const NexusUsPosApp(flavor: flavor),
    ),
  );
}