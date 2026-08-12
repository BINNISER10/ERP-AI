import 'package:uuid/uuid.dart';

import '../database/app_database.dart';
import '../models/order_payload.dart';
import '../utils/tax_calculator.dart';

class PosRepository {
  final AppDatabase database;

  PosRepository(this.database);

  Future<List<ProductRow>> getProducts(String? categoryId) => database.getProductsByCategory(categoryId);

  Future<int> addToCart({
    required ProductRow product,
    required double quantity,
    required double price,
    List<int> taxIds = const [],
    Modifier modifiers = const Modifier(),
  }) {
    final effectivePrice = modifiers.applyToPrice(price);
    return database.insertCartItem(
      CartItemsCompanion.insert(
        productServerId: product.serverId,
        name: product.name,
        quantity: Value(quantity),
        priceUnit: Value(effectivePrice),
        taxIdsJson: Value(taxIds.isEmpty ? null : taxIds.toString()),
        modifiersJson: Value(modifiers.toJson().toString()),
        costOfGoodsSold: Value(product.standardPrice * quantity),
        subtotal: Value(effectivePrice * quantity),
      ),
    );
  }

  Future<List<CartItemRow>> getCart() => database.getCartItems();

  Future<int> removeFromCart(int id) => database.deleteCartItem(id);

  Future<int> clearCart() => database.clearCart();

  Future<OrderPayload> buildOrder({
    int? partnerId,
    int? companyId,
    double tipAmount = 0.0,
    bool splitBill = false,
    List<SplitPayment>? splitPayments,
    String? paymentMethod,
    String? stateCode,
    String? zipCode,
    String? note,
  }) async {
    final cart = await database.getCartItems();
    final lines = <OrderLine>[];
    double subtotal = 0.0;
    double tax = 0.0;

    for (final item in cart) {
      final taxIds = _parseTaxIds(item.taxIdsJson);
      double price = item.priceUnit;
      double itemSubtotal = price * item.quantity;
      double itemTax = 0.0;

      // US state tax path
      if (stateCode != null && stateCode.isNotEmpty) {
        itemTax = await TaxCalculator.totalTaxFor(itemSubtotal, stateCode, zipCode: zipCode);
      } else if (taxIds.isNotEmpty) {
        // Fallback flat tax calculation based on stored tax rows.
        itemTax = itemSubtotal * 0.0825; // placeholder if no local tax data
      }

      subtotal += itemSubtotal;
      tax += itemTax;

      lines.add(
        OrderLine(
          productId: int.parse(item.productServerId),
          name: item.name,
          quantity: item.quantity,
          priceUnit: price,
          discount: item.discount,
          taxIds: taxIds,
          costOfGoodsSold: item.costOfGoodsSold,
        ),
      );
    }

    final total = subtotal + tax + tipAmount;

    return OrderPayload(
      clientOrderRef: const Uuid().v4(),
      orderDate: DateTime.now(),
      partnerId: partnerId,
      companyId: companyId,
      lines: lines,
      amountTotal: total,
      amountTax: tax,
      tipAmount: tipAmount,
      splitBill: splitBill,
      splitPayments: splitPayments,
      paymentMethod: paymentMethod,
      stateCode: stateCode,
      zipCode: zipCode,
      note: note,
    );
  }

  Future<void> storeOrder(OrderPayload payload) async {
    await database.insertOrder(
      OrdersCompanion.insert(
        clientOrderRef: payload.clientOrderRef,
        orderDate: Value(payload.orderDate),
        amountTotal: Value(payload.amountTotal),
        amountTax: Value(payload.amountTax),
        tipAmount: Value(payload.tipAmount),
        splitBill: Value(payload.splitBill),
        paymentMethod: Value(payload.paymentMethod),
        stateCode: Value(payload.stateCode),
        zipCode: Value(payload.zipCode),
        payloadJson: payload.toJsonString(),
      ),
    );
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
