import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/database/app_database.dart' hide SyncState;
import '../../../core/network/odoo_jsonrpc.dart';
import 'sync_event.dart';
import 'sync_state.dart';

class SyncBloc extends Bloc<SyncEvent, SyncState> {
  final OdooJsonRpcClient client;
  final AppDatabase database;

  SyncBloc({required this.client, required this.database}) : super(const SyncState()) {
    on<SyncPendingOrders>(_onSyncPendingOrders);
    on<CheckConnectivity>(_onCheckConnectivity);
  }

  Future<void> _onCheckConnectivity(CheckConnectivity event, Emitter<SyncState> emit) async {
    final result = await Connectivity().checkConnectivity();
    emit(state.copyWith(online: result.any((r) => r != ConnectivityResult.none)));
  }

  Future<void> _onSyncPendingOrders(SyncPendingOrders event, Emitter<SyncState> emit) async {
    if (state.syncing) return;
    emit(state.copyWith(syncing: true, error: null));
    try {
      final result = await Connectivity().checkConnectivity();
      final online = result.any((r) => r != ConnectivityResult.none);
      if (!online) {
        emit(state.copyWith(online: false, syncing: false, error: 'No internet connection.'));
        return;
      }

      final orders = await database.getPendingOrders();
      if (orders.isEmpty) {
        emit(state.copyWith(pendingOrders: orders, syncing: false, lastSync: DateTime.now().toIso8601String()));
        return;
      }

      final orderMaps = <Map<String, dynamic>>[];
      for (final order in orders) {
        final decoded = _decodePayload(order.payloadJson);
        if (decoded != null) {
          orderMaps.add(decoded);
        }
      }

      final result2 = await client.postOfflineOrders(orderMaps);
      final created = result2['created'] as List? ?? [];
      for (final c in created) {
        final ref = c['client_order_ref'] as String?;
        final index = c['index'] as int?;
        if (ref != null) {
          await database.markOrderSyncedByRef(ref);
        } else if (index != null && index < orders.length) {
          await database.markOrderSynced(orders[index].id);
        }
      }

      final errors = result2['errors'] as List? ?? [];
      if (errors.isNotEmpty) {
        emit(state.copyWith(
          syncing: false,
          error: 'Sync completed with ${errors.length} error(s).',
          lastSync: DateTime.now().toIso8601String(),
        ));
        return;
      }

      final remaining = await database.getPendingOrders();
      emit(state.copyWith(
        pendingOrders: remaining,
        syncing: false,
        online: true,
        lastSync: DateTime.now().toIso8601String(),
      ));
    } catch (e) {
      emit(state.copyWith(syncing: false, error: e.toString()));
    }
  }

  Map<String, dynamic>? _decodePayload(String raw) {
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) return decoded;
      return null;
    } catch (_) {
      return null;
    }
  }
}
