import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'tables.dart';

export 'tables.dart';

part 'app_database.g.dart';

@DriftDatabase(tables: [Products, ProductCategories, Taxes, CartItems, Orders, SyncState])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
        onCreate: (m) => m.createAll(),
        onUpgrade: (m, from, to) async {
          // Incremental schema migrations go here.
        },
      );

  Future<void> setup() async {
    final prefs = await SharedPreferences.getInstance();
    // Default to USD for the US POS build target unless configured otherwise.
    if (!prefs.containsKey('currency_symbol')) {
      await prefs.setString('currency_symbol', '\$');
      await prefs.setString('currency_code', 'USD');
      await prefs.setInt('currency_decimals', 2);
    }
    if (!prefs.containsKey('enable_us_state_tax')) {
      await prefs.setBool('enable_us_state_tax', true);
    }
  }

  Future<String> get currencySymbol async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('currency_symbol') ?? '\$';
  }

  Future<bool> get usStateTaxEnabled async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('enable_us_state_tax') ?? true;
  }

  Future<void> saveSyncState(String key, String value) async {
    await into(syncState).insertOnConflictUpdate(
      SyncStateCompanion(
        key: Value(key),
        value: Value(value),
        updatedAt: Value(DateTime.now()),
      ),
    );
  }

  Future<String?> getSyncState(String key) async {
    final row = await (select(syncState)..where((s) => s.key.equals(key))).getSingleOrNull();
    return row?.value;
  }

  Future<List<ProductRow>> getProductsByCategory(String? categoryId) async {
    if (categoryId == null) return select(products).get();
    return (select(products)..where((p) => p.categoryId.equals(categoryId))).get();
  }

  Future<void> upsertProducts(List<ProductsCompanion> rows) async {
    await batch((batch) {
      for (final row in rows) {
        batch.insertAllOnConflictUpdate(products, [row]);
      }
    });
  }

  Future<void> upsertCategories(List<ProductCategoriesCompanion> rows) async {
    await batch((batch) {
      for (final row in rows) {
        batch.insertAllOnConflictUpdate(productCategories, [row]);
      }
    });
  }

  Future<void> upsertTaxes(List<TaxesCompanion> rows) async {
    await batch((batch) {
      for (final row in rows) {
        batch.insertAllOnConflictUpdate(taxes, [row]);
      }
    });
  }

  Future<int> insertCartItem(CartItemsCompanion item) => into(cartItems).insert(item);

  Future<List<CartItemRow>> getCartItems() => select(cartItems).get();

  Future<int> deleteCartItem(int id) => (delete(cartItems)..where((i) => i.id.equals(id))).go();

  Future<int> clearCart() => delete(cartItems).go();

  Future<int> insertOrder(OrdersCompanion order) => into(orders).insert(order);

  Future<List<OrderRow>> getPendingOrders() =>
      (select(orders)..where((o) => o.synced.equals(false))).get();

  Future<int> markOrderSynced(int id) =>
      (update(orders)..where((o) => o.id.equals(id))).write(const OrdersCompanion(synced: Value(true)));
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'nexus_pos.sqlite'));
    return NativeDatabase(file);
  });
}
