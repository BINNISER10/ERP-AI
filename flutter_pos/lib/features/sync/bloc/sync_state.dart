import 'package:equatable/equatable.dart';

import '../../../core/database/app_database.dart';

class SyncState extends Equatable {
  final List<OrderRow> pendingOrders;
  final bool online;
  final bool syncing;
  final String? error;
  final String? lastSync;

  const SyncState({
    this.pendingOrders = const [],
    this.online = false,
    this.syncing = false,
    this.error,
    this.lastSync,
  });

  SyncState copyWith({
    List<OrderRow>? pendingOrders,
    bool? online,
    bool? syncing,
    String? error,
    String? lastSync,
  }) {
    return SyncState(
      pendingOrders: pendingOrders ?? this.pendingOrders,
      online: online ?? this.online,
      syncing: syncing ?? this.syncing,
      error: error ?? this.error,
      lastSync: lastSync ?? this.lastSync,
    );
  }

  @override
  List<Object?> get props => [pendingOrders, online, syncing, error, lastSync];
}
