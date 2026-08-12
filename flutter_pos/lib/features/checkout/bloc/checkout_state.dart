import 'package:equatable/equatable.dart';

import '../../../core/models/order_payload.dart';

class CheckoutState extends Equatable {
  final OrderPayload? payload;
  final double tipAmount;
  final List<SplitPayment>? splitPayments;
  final String paymentMethod;
  final bool processing;
  final bool paid;
  final String? error;

  const CheckoutState({
    this.payload,
    this.tipAmount = 0.0,
    this.splitPayments,
    this.paymentMethod = 'cash',
    this.processing = false,
    this.paid = false,
    this.error,
  });

  CheckoutState copyWith({
    OrderPayload? payload,
    double? tipAmount,
    List<SplitPayment>? splitPayments,
    String? paymentMethod,
    bool? processing,
    bool? paid,
    String? error,
  }) {
    return CheckoutState(
      payload: payload ?? this.payload,
      tipAmount: tipAmount ?? this.tipAmount,
      splitPayments: splitPayments ?? this.splitPayments,
      paymentMethod: paymentMethod ?? this.paymentMethod,
      processing: processing ?? this.processing,
      paid: paid ?? this.paid,
      error: error ?? this.error,
    );
  }

  @override
  List<Object?> get props => [payload, tipAmount, splitPayments, paymentMethod, processing, paid, error];
}
