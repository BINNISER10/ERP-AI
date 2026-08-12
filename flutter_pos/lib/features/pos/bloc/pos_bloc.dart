import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/database/app_database.dart';
import '../../../core/repository/pos_repository.dart';
import 'pos_event.dart';
import 'pos_state.dart';

class PosBloc extends Bloc<PosEvent, PosState> {
  final AppDatabase database;
  late final PosRepository _repository;

  PosBloc({required this.database}) : super(const PosState()) {
    _repository = PosRepository(database);

    on<LoadCart>(_onLoadCart);
    on<AddToCart>(_onAddToCart);
    on<UpdateCartQuantity>(_onUpdateQuantity);
    on<RemoveFromCart>(_onRemoveFromCart);
    on<ClearCart>(_onClearCart);
  }

  Future<void> _onLoadCart(LoadCart event, Emitter<PosState> emit) async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final cart = await _repository.getCart();
      emit(state.copyWith(cart: cart, loading: false));
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  Future<void> _onAddToCart(AddToCart event, Emitter<PosState> emit) async {
    try {
      await _repository.addToCart(
        product: event.product,
        quantity: event.quantity,
        price: event.price,
        taxIds: event.taxIds,
        modifiers: event.modifiers,
      );
      final cart = await _repository.getCart();
      emit(state.copyWith(cart: cart));
    } catch (e) {
      emit(state.copyWith(error: e.toString()));
    }
  }

  Future<void> _onUpdateQuantity(UpdateCartQuantity event, Emitter<PosState> emit) async {
    // Simplified: delete and re-insert with new quantity.
    try {
      final existing = state.cart.firstWhere((i) => i.id == event.cartItemId);
      final product = await (database.select(database.products)
            ..where((p) => p.serverId.equals(existing.productServerId)))
          .getSingle();
      await database.deleteCartItem(event.cartItemId);
      await _repository.addToCart(
        product: product,
        quantity: event.quantity,
        price: existing.priceUnit,
        taxIds: _parseTaxIds(existing.taxIdsJson),
      );
      final cart = await _repository.getCart();
      emit(state.copyWith(cart: cart));
    } catch (e) {
      emit(state.copyWith(error: e.toString()));
    }
  }

  Future<void> _onRemoveFromCart(RemoveFromCart event, Emitter<PosState> emit) async {
    try {
      await _repository.removeFromCart(event.cartItemId);
      final cart = await _repository.getCart();
      emit(state.copyWith(cart: cart));
    } catch (e) {
      emit(state.copyWith(error: e.toString()));
    }
  }

  Future<void> _onClearCart(ClearCart event, Emitter<PosState> emit) async {
    await _repository.clearCart();
    emit(state.copyWith(cart: []));
  }

  List<int> _parseTaxIds(String? raw) {
    if (raw == null || raw.isEmpty || raw == '[]') return [];
    try {
      final cleaned = raw.replaceAll('[', '').replaceAll(']', '').split(',');
      return cleaned.where((s) => s.trim().isNotEmpty).map(int.parse).toList();
    } catch (_) {
      return [];
    }
  }
}
