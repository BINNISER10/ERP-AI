import 'dart:convert';

import 'modifier.dart';

class OrderPayload {
  final String clientOrderRef;
  final DateTime orderDate;
  final int? partnerId;
  final int? companyId;
  final List<OrderLine> lines;
  final double amountTotal;
  final double amountTax;
  final double tipAmount;
  final bool splitBill;
  final List<SplitPayment>? splitPayments;
  final String? paymentMethod;
  final String? stateCode;
  final String? zipCode;
  final String? note;

  OrderPayload({
    required this.clientOrderRef,
    required this.orderDate,
    this.partnerId,
    this.companyId,
    required this.lines,
    required this.amountTotal,
    required this.amountTax,
    this.tipAmount = 0.0,
    this.splitBill = false,
    this.splitPayments,
    this.paymentMethod,
    this.stateCode,
    this.zipCode,
    this.note,
  });

  Map<String, dynamic> toJson() => {
        'client_order_ref': clientOrderRef,
        'order_date': orderDate.toIso8601String(),
        'partner_id': partnerId,
        'company_id': companyId,
        'lines': lines.map((l) => l.toJson()).toList(),
        'amount_total': amountTotal,
        'amount_tax': amountTax,
        'tip_amount': tipAmount,
        'split_bill': splitBill,
        'split_payments': splitPayments?.map((p) => p.toJson()).toList(),
        'payment_method': paymentMethod,
        'state_code': stateCode,
        'zip_code': zipCode,
        'note': note,
      };

  String toJsonString() => jsonEncode(toJson());

  factory OrderPayload.fromJson(Map<String, dynamic> json) {
    return OrderPayload(
      clientOrderRef: json['client_order_ref'] as String,
      orderDate: DateTime.parse(json['order_date'] as String),
      partnerId: json['partner_id'] as int?,
      companyId: json['company_id'] as int?,
      lines: (json['lines'] as List).map((e) => OrderLine.fromJson(e as Map<String, dynamic>)).toList(),
      amountTotal: (json['amount_total'] as num).toDouble(),
      amountTax: (json['amount_tax'] as num).toDouble(),
      tipAmount: (json['tip_amount'] as num?)?.toDouble() ?? 0.0,
      splitBill: json['split_bill'] as bool? ?? false,
      splitPayments: json['split_payments'] != null
          ? (json['split_payments'] as List)
              .map((e) => SplitPayment.fromJson(e as Map<String, dynamic>))
              .toList()
          : null,
      paymentMethod: json['payment_method'] as String?,
      stateCode: json['state_code'] as String?,
      zipCode: json['zip_code'] as String?,
      note: json['note'] as String?,
    );
  }
}

class OrderLine {
  final int productId;
  final String name;
  final double quantity;
  final double priceUnit;
  final double discount;
  final List<int> taxIds;
  final Modifier modifiers;
  final double costOfGoodsSold;

  OrderLine({
    required this.productId,
    required this.name,
    required this.quantity,
    required this.priceUnit,
    this.discount = 0.0,
    this.taxIds = const [],
    this.modifiers = const Modifier(),
    this.costOfGoodsSold = 0.0,
  });

  Map<String, dynamic> toJson() => {
        'product_id': productId,
        'name': name,
        'quantity': quantity,
        'price_unit': priceUnit,
        'discount': discount,
        'tax_ids': taxIds,
        'modifiers': modifiers.toJson(),
        'cost_of_goods_sold': costOfGoodsSold,
      };

  factory OrderLine.fromJson(Map<String, dynamic> json) {
    return OrderLine(
      productId: json['product_id'] as int,
      name: json['name'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      priceUnit: (json['price_unit'] as num).toDouble(),
      discount: (json['discount'] as num?)?.toDouble() ?? 0.0,
      taxIds: List<int>.from(json['tax_ids'] ?? []),
      modifiers: json['modifiers'] != null
          ? Modifier.fromJson(json['modifiers'] as Map<String, dynamic>)
          : const Modifier(),
      costOfGoodsSold: (json['cost_of_goods_sold'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class SplitPayment {
  final double amount;
  final String method;
  final double? tip;

  SplitPayment({required this.amount, required this.method, this.tip});

  Map<String, dynamic> toJson() => {
        'amount': amount,
        'method': method,
        'tip': tip,
      };

  factory SplitPayment.fromJson(Map<String, dynamic> json) {
    return SplitPayment(
      amount: (json['amount'] as num).toDouble(),
      method: json['method'] as String,
      tip: (json['tip'] as num?)?.toDouble(),
    );
  }
}
