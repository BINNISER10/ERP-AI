import 'package:equatable/equatable.dart';

import '../../../core/database/app_database.dart';

class CatalogState extends Equatable {
  final List<ProductRow> products;
  final List<ProductCategoryRow> categories;
  final String? selectedCategoryId;
  final bool loading;
  final bool syncing;
  final String? error;

  const CatalogState({
    this.products = const [],
    this.categories = const [],
    this.selectedCategoryId,
    this.loading = false,
    this.syncing = false,
    this.error,
  });

  CatalogState copyWith({
    List<ProductRow>? products,
    List<ProductCategoryRow>? categories,
    String? selectedCategoryId,
    bool? loading,
    bool? syncing,
    String? error,
  }) {
    return CatalogState(
      products: products ?? this.products,
      categories: categories ?? this.categories,
      selectedCategoryId: selectedCategoryId ?? this.selectedCategoryId,
      loading: loading ?? this.loading,
      syncing: syncing ?? this.syncing,
      error: error ?? this.error,
    );
  }

  @override
  List<Object?> get props => [products, categories, selectedCategoryId, loading, syncing, error];
}
