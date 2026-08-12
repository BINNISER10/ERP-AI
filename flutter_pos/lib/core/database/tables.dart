import 'package:drift/drift.dart';

part 'tables.g.dart';

@DataClassName('ProductRow')
class Products extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get serverId => text().withLength(min: 1, max: 64)();
  TextColumn get name => text().withLength(min: 1, max: 256)();
  TextColumn get defaultCode => text().nullable()();
  TextColumn get barcode => text().nullable()();
  RealColumn get listPrice => real().withDefault(const Constant(0.0))();
  RealColumn get standardPrice => real().withDefault(const Constant(0.0))();
  TextColumn get uomName => text().nullable()();
  TextColumn get categoryId => text().nullable()();
  TextColumn get taxesIdJson => text().nullable()();
  RealColumn get qtyAvailable => real().withDefault(const Constant(0.0))();
  TextColumn get image128 => text().nullable()();
  BoolColumn get isRecipeBom => boolean().withDefault(const Constant(false))();
  TextColumn get modifierSchema => text().nullable()();
  DateTimeColumn get lastSyncedAt => dateTime().nullable()();

  @override
  List<String> get customConstraints => ['UNIQUE(server_id)'];
}

@DataClassName('ProductCategoryRow')
class ProductCategories extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get serverId => text().withLength(min: 1, max: 64)();
  TextColumn get name => text().withLength(min: 1, max: 256)();
  TextColumn get parentId => text().nullable()();

  @override
  List<String> get customConstraints => ['UNIQUE(server_id)'];
}

@DataClassName('TaxRow')
class Taxes extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get serverId => text().withLength(min: 1, max: 64)();
  TextColumn get name => text().withLength(min: 1, max: 256)();
  RealColumn get amount => real().withDefault(const Constant(0.0))();
  TextColumn get amountType => text().withDefault(const Constant('percent'))();

  @override
  List<String> get customConstraints => ['UNIQUE(server_id)'];
}

@DataClassName('CartItemRow')
class CartItems extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get productServerId => text()();
  TextColumn get name => text().withLength(min: 1, max: 256)();
  RealColumn get quantity => real().withDefault(const Constant(1.0))();
  RealColumn get priceUnit => real().withDefault(const Constant(0.0))();
  RealColumn get discount => real().withDefault(const Constant(0.0))();
  TextColumn get taxIdsJson => text().nullable()();
  TextColumn get modifiersJson => text().nullable()();
  RealColumn get costOfGoodsSold => real().withDefault(const Constant(0.0))();
  RealColumn get subtotal => real().withDefault(const Constant(0.0))();
  RealColumn get taxAmount => real().withDefault(const Constant(0.0))();
  RealColumn get total => real().withDefault(const Constant(0.0))();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
}

@DataClassName('OrderRow')
class Orders extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get clientOrderRef => text().withLength(min: 1, max: 64)();
  TextColumn get odooOrderName => text().nullable()();
  TextColumn get status => text().withDefault(const Constant('draft'))();
  DateTimeColumn get orderDate => dateTime().withDefault(currentDateAndTime)();
  TextColumn get partnerId => text().nullable()();
  TextColumn get payloadJson => text()();
  RealColumn get amountTotal => real().withDefault(const Constant(0.0))();
  RealColumn get amountTax => real().withDefault(const Constant(0.0))();
  RealColumn get tipAmount => real().withDefault(const Constant(0.0))();
  BoolColumn get paid => boolean().withDefault(const Constant(false))();
  BoolColumn get synced => boolean().withDefault(const Constant(false))();
  BoolColumn get splitBill => boolean().withDefault(const Constant(false))();
  TextColumn get splitPaymentsJson => text().nullable()();
  TextColumn get paymentMethod => text().nullable()();
  TextColumn get stateCode => text().nullable()();
  TextColumn get zipCode => text().nullable()();
  DateTimeColumn get syncedAt => dateTime().nullable()();
  TextColumn get syncError => text().nullable()();
}

@DataClassName('SyncStateRow')
class SyncState extends Table {
  TextColumn get key => text().withLength(min: 1, max: 64)();
  TextColumn get value => text().nullable()();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {key};
}
