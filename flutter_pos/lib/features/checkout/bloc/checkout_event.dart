import 'package:equatable/equatable.dart';

import '../../../core/models/order_payload.dart';

abstract class CheckoutEvent extends Equatable {
  const CheckoutEvent();

  @override
  List<Object?> get props => [];
}

class BuildOrder extends CheckoutEvent {
  final String? stateCode;
  final String? zipCode;
  final String? county;

  const BuildOrder({this.stateCode, this.zipCode, this.county});

  @override
  List<Object?> get props => [stateCode, zipCode, county];
}

class SetTip extends CheckoutEvent {
  final double tipAmount;

  const SetTip(this.tipAmount);

  @override
  List<Object?> get props => [tipAmount];
}

class SetSplitPayments extends CheckoutEvent {
  final List<SplitPayment> splitPayments;

  const SetSplitPayments(this.splitPayments);

  @override
  List<Object?> get props => [splitPayments];
}

class SetPaymentMethod extends CheckoutEvent {
  final String paymentMethod;

  const SetPaymentMethod(this.paymentMethod);

  @override
  List<Object?> get props => [paymentMethod];
}

class ProcessPayment extends CheckoutEvent {
  final bool splitBill;

  const ProcessPayment({this.splitBill = false});

  @override
  List<Object?> get props => [splitBill];
}

class SaveOrder extends CheckoutEvent {
  final OrderPayload payload;

  const SaveOrder(this.payload);

  @override
  List<Object?> get props => [payload];
}
