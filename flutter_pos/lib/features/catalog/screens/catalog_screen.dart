import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/database/app_database.dart';
import '../../../core/models/modifier.dart';
import '../../pos/bloc/pos_bloc.dart';
import '../../pos/bloc/pos_event.dart';
import '../../pos/bloc/pos_state.dart';
import '../bloc/catalog_bloc.dart';
import '../bloc/catalog_event.dart';
import '../bloc/catalog_state.dart';
import '../widgets/product_card.dart';
import '../widgets/modifier_dialog.dart';
import '../../checkout/screens/checkout_screen.dart';

class CatalogScreen extends StatefulWidget {
  const CatalogScreen({super.key});

  @override
  State<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends State<CatalogScreen> {
  @override
  void initState() {
    super.initState();
    context.read<CatalogBloc>().add(const LoadCatalog());
    context.read<PosBloc>().add(const LoadCart());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Nexus Catalog'),
        actions: [
          IconButton(
            icon: const Icon(Icons.sync),
            onPressed: () => context.read<CatalogBloc>().add(const SyncCatalog()),
          ),
          BlocBuilder<PosBloc, PosState>(
            builder: (context, state) {
              final count = state.cart.length;
              return Badge(
                label: Text('$count'),
                isLabelVisible: count > 0,
                child: IconButton(
                  icon: const Icon(Icons.shopping_cart),
                  onPressed: () => _goToCheckout(context),
                ),
              );
            },
          ),
        ],
      ),
      body: Row(
        children: [
          SizedBox(
            width: 120,
            child: BlocBuilder<CatalogBloc, CatalogState>(
              builder: (context, state) {
                return ListView(
                  children: [
                    ListTile(
                      title: const Text('All'),
                      selected: state.selectedCategoryId == null,
                      onTap: () => context.read<CatalogBloc>().add(const SelectCategory(null)),
                    ),
                    ...state.categories.map(
                      (c) => ListTile(
                        title: Text(c.name, overflow: TextOverflow.ellipsis),
                        selected: state.selectedCategoryId == c.serverId,
                        onTap: () => context.read<CatalogBloc>().add(SelectCategory(c.serverId)),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
          const VerticalDivider(),
          Expanded(
            child: BlocBuilder<CatalogBloc, CatalogState>(
              builder: (context, state) {
                if (state.loading || state.syncing) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (state.error != null) {
                  return Center(child: Text(state.error!));
                }
                return GridView.builder(
                  padding: const EdgeInsets.all(8),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    childAspectRatio: 0.8,
                  ),
                  itemCount: state.products.length,
                  itemBuilder: (context, index) {
                    final product = state.products[index];
                    return ProductCard(
                      product: product,
                      onTap: () => _onProductTap(context, product),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _onProductTap(BuildContext context, ProductRow product) async {
    Modifier? modifier;
    if (product.modifierSchema != null && product.modifierSchema!.isNotEmpty) {
      modifier = await showDialog<Modifier>(
        context: context,
        builder: (_) => ModifierDialog(product: product),
      );
    }
    if (!context.mounted) return;
    context.read<PosBloc>().add(
          AddToCart(
            product: product,
            quantity: 1.0,
            price: product.listPrice,
            taxIds: _parseTaxIds(product.taxesIdJson),
            modifiers: modifier ?? const Modifier(),
          ),
        );
  }

  void _goToCheckout(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CheckoutScreen()));
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
