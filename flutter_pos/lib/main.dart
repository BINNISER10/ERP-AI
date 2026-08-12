import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:logger/logger.dart';

import 'core/database/app_database.dart';
import 'core/network/odoo_jsonrpc.dart';
import 'features/pos/bloc/pos_bloc.dart';
import 'features/catalog/bloc/catalog_bloc.dart';
import 'features/checkout/bloc/checkout_bloc.dart';
import 'features/sync/bloc/sync_bloc.dart';
import 'services/printing/thermal_printer_service.dart';
import 'services/stripe/stripe_terminal_service.dart';
import 'app.dart';

final Logger logger = Logger();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final database = AppDatabase();
  final client = OdooJsonRpcClient(baseUrl: 'http://localhost:8069', database: 'nexus_erp');
  final printer = ThermalPrinterService();
  final stripeTerminal = StripeTerminalService();

  await database.setup();

  runApp(
    MultiBlocProvider(
      providers: [
        BlocProvider(
          create: (_) => CatalogBloc(client: client, database: database),
        ),
        BlocProvider(
          create: (_) => PosBloc(database: database),
        ),
        BlocProvider(
          create: (_) => CheckoutBloc(
            client: client,
            database: database,
            printer: printer,
            stripeTerminal: stripeTerminal,
          ),
        ),
        BlocProvider(
          create: (_) => SyncBloc(client: client, database: database),
        ),
      ],
      child: const NexusPosApp(),
    ),
  );
}
