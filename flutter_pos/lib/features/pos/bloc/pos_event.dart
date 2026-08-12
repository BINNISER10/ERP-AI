import 'package:equatable/equatable.dart';

import '../../../core/database/app_database.dart';
import '../../../core/models/modifier.dart';

abstract class PosEvent extends Equatable {
  const PosEvent();

  @override
  List<Object?> get props => [];
}

class LoadCart extends PosEvent {}

class AddToCart extends PosEvent {
  final ProductRow product;
  final double quantity;
  final double price;
  final List<int> taxIds;
  final Modifier modifiers;

  const AddToCart({
    required this.product,
    required this.quantity,
    required this.price,
    this.taxIds = const [],
    this.modifiers = const Modifier(),
  });

  @override
  List<Object?> get props => [product, quantity, price, taxIds, modifiers];
}

class UpdateCartQuantity extends PosEvent {
  final int cartItemId;
  final double quantity;

  const UpdateCartQuantity(this.cartItemId, this.quantity);

  @override
  List<Object?> get props => [cartItemId, quantity];
}

class RemoveFromCart extends PosEvent {
  final int cartItemId;

  const RemoveFromCart(this.cartItemId);

  @override
  List<Object?> get props => [cartItemId];
}

class ClearCart extends PosEvent {}
