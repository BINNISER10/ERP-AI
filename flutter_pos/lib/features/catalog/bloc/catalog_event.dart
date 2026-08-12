import 'package:equatable/equatable.dart';

abstract class CatalogEvent extends Equatable {
  const CatalogEvent();

  @override
  List<Object?> get props => [];
}

class LoadCatalog extends CatalogEvent {}

class SyncCatalog extends CatalogEvent {}

class SelectCategory extends CatalogEvent {
  final String? categoryId;

  const SelectCategory(this.categoryId);

  @override
  List<Object?> get props => [categoryId];
}
