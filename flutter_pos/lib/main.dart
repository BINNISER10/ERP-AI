import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'core/database/app_database.dart';
import 'core/network/odoo_jsonrpc.dart';
import 'features/pos/bloc/pos_bloc.dart';
import 'features/catalog/bloc/catalog_bloc.dart';
import 'features/checkout/bloc/checkout_bloc.dart';
import 'features/sync/bloc/sync_bloc.dart';
import 'services/printing/thermal_printer_service.dart';
import 'services/stripe/stripe_terminal_service.dart';
import 'app.dart';
import 'config.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final database = AppDatabase();
  final client = OdooJsonRpcClient(baseUrl: odooBaseUrl, database: 'nexus_erp');
  final printer = ThermalPrinterService();
  final stripeTerminal = StripeTerminalService();
  final syncBloc = SyncBloc(client: client, database: database);

  await database.setup();

  // Push offline orders automatically once connectivity returns.
  StreamSubscription<List<ConnectivityResult>>? sub;
  sub = Connectivity().onConnectivityChanged.listen((results) {
    if (results.any((r) => r != ConnectivityResult.none)) {
      syncBloc.add(const SyncPendingOrders());
    }
  });

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
        BlocProvider.value(value: syncBloc),
      ],
      child: const NexusPosApp(),
    ),
  );

  // Trigger an initial sync attempt shortly after startup.
  Future.delayed(const Duration(seconds: 10), () {
    if (sub.isActive) syncBloc.add(const SyncPendingOrders());
  });
}