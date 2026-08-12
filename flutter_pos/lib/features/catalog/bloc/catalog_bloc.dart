import 'dart:convert';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/database/app_database.dart';
import '../../../core/network/odoo_jsonrpc.dart';
import 'catalog_event.dart';
import 'catalog_state.dart';

class CatalogBloc extends Bloc<CatalogEvent, CatalogState> {
  final OdooJsonRpcClient client;
  final AppDatabase database;

  CatalogBloc({required this.client, required this.database}) : super(const CatalogState()) {
    on<LoadCatalog>(_onLoadCatalog);
    on<SyncCatalog>(_onSyncCatalog);
    on<SelectCategory>(_onSelectCategory);
  }

  Future<void> _onLoadCatalog(LoadCatalog event, Emitter<CatalogState> emit) async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final products = await database.getProductsByCategory(state.selectedCategoryId);
      final categories = await database.select(database.productCategories).get();
      emit(state.copyWith(products: products, categories: categories, loading: false));
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  Future<void> _onSyncCatalog(SyncCatalog event, Emitter<CatalogState> emit) async {
    emit(state.copyWith(syncing: true, error: null));
    try {
      final result = await client.getCatalog();

      final productRows = <ProductsCompanion>[];
      for (final p in (result['products'] as List).cast<Map<String, dynamic>>()) {
        productRows.add(
          ProductsCompanion.insert(
            serverId: (p['id'] as int).toString(),
            name: p['name'] as String,
            defaultCode: Value(p['default_code'] as String?),
            barcode: Value(p['barcode'] as String?),
            listPrice: Value((p['list_price'] as num?)?.toDouble() ?? 0.0),
            standardPrice: Value((p['standard_price'] as num?)?.toDouble() ?? 0.0),
            uomName: Value(p['uom_name'] as String?),
            categoryId: Value(p['categ_id']?.toString()),
            taxesIdJson: Value(jsonEncode(p['taxes_id'] ?? [])),
            qtyAvailable: Value((p['qty_available'] as num?)?.toDouble() ?? 0.0),
            image128: Value(p['image_128'] as String?),
            lastSyncedAt: Value(DateTime.now()),
          ),
        );
      }
      await database.upsertProducts(productRows);

      final categoryRows = <ProductCategoriesCompanion>[];
      for (final c in (result['categories'] as List).cast<Map<String, dynamic>>()) {
        categoryRows.add(
          ProductCategoriesCompanion.insert(
            serverId: (c['id'] as int).toString(),
            name: c['name'] as String,
            parentId: Value(c['parent_id']?.toString()),
          ),
        );
      }
      await database.upsertCategories(categoryRows);

      final taxRows = <TaxesCompanion>[];
      for (final t in (result['taxes'] as List).cast<Map<String, dynamic>>()) {
        taxRows.add(
          TaxesCompanion.insert(
            serverId: (t['id'] as int).toString(),
            name: t['name'] as String,
            amount: Value((t['amount'] as num?)?.toDouble() ?? 0.0),
            amountType: Value(t['amount_type'] as String? ?? 'percent'),
          ),
        );
      }
      await database.upsertTaxes(taxRows);

      await database.saveSyncState('last_catalog_sync', DateTime.now().toIso8601String());

      final products = await database.getProductsByCategory(state.selectedCategoryId);
      final categories = await database.select(database.productCategories).get();
      emit(state.copyWith(products: products, categories: categories, syncing: false));
    } catch (e) {
      emit(state.copyWith(syncing: false, error: e.toString()));
    }
  }

  Future<void> _onSelectCategory(SelectCategory event, Emitter<CatalogState> emit) async {
    emit(state.copyWith(selectedCategoryId: event.categoryId, loading: true));
    final products = await database.getProductsByCategory(event.categoryId);
    emit(state.copyWith(products: products, loading: false));
  }
}
