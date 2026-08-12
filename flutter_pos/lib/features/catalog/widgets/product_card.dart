import 'package:flutter/material.dart';

import '../../../core/database/app_database.dart';

class ProductCard extends StatelessWidget {
  final ProductRow product;
  final VoidCallback onTap;

  const ProductCard({super.key, required this.product, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(8.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Container(
                  alignment: Alignment.center,
                  color: Colors.grey.shade200,
                  child: const Icon(Icons.local_dining, size: 48),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                product.name,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleSmall,
              ),
              Text(
                '\$${product.listPrice.toStringAsFixed(2)}',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              if (product.isRecipeBom)
                const Chip(label: Text('Recipe'), visualDensity: VisualDensity.compact),
            ],
          ),
        ),
      ),
    );
  }
}
