import 'package:equatable/equatable.dart';

import '../../../core/database/app_database.dart';

class PosState extends Equatable {
  final List<CartItemRow> cart;
  final bool loading;
  final String? error;

  const PosState({
    this.cart = const [],
    this.loading = false,
    this.error,
  });

  PosState copyWith({
    List<CartItemRow>? cart,
    bool? loading,
    String? error,
  }) {
    return PosState(
      cart: cart ?? this.cart,
      loading: loading ?? this.loading,
      error: error ?? this.error,
    );
  }

  double get subtotal => cart.fold(0.0, (sum, i) => sum + (i.priceUnit * i.quantity));

  double get tax => cart.fold(0.0, (sum, i) => sum + i.taxAmount);

  double get total => cart.fold(0.0, (sum, i) => sum + i.total);

  @override
  List<Object?> get props => [cart, loading, error];
}
