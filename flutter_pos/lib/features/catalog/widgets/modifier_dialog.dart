import 'dart:convert';

import 'package:flutter/material.dart';

import '../../../core/database/app_database.dart';
import '../../../core/models/modifier.dart';

class ModifierDialog extends StatefulWidget {
  final ProductRow product;

  const ModifierDialog({super.key, required this.product});

  @override
  State<ModifierDialog> createState() => _ModifierDialogState();
}

class _ModifierDialogState extends State<ModifierDialog> {
  final List<String> _excluded = [];
  final Map<String, String> _substitutes = {};
  final Map<String, double> _surcharges = {};

  late final List<dynamic> _options;
  late final List<dynamic> _surchargeOptions;

  @override
  void initState() {
    super.initState();
    final Map<String, dynamic>? schema;
    try {
      schema = jsonDecode(widget.product.modifierSchema ?? '{}') as Map<String, dynamic>?;
    } catch (_) {
      schema = null;
    }
    final options = schema?['options'] as List<dynamic>? ?? [];
    final surcharges = schema?['surcharges'] as List<dynamic>? ?? [];
    _options = options.where((o) => (o['type'] as String? ?? 'toggle') != 'surcharge').toList();
    _surchargeOptions = surcharges.isEmpty
        ? options.where((o) => (o['type'] as String? ?? '') == 'surcharge').toList()
        : surcharges;
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Modifiers for ${widget.product.name}'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ..._options.map((opt) {
              final name = opt['name'] as String;
              final type = opt['type'] as String? ?? 'toggle';
              final choices = (opt['choices'] as List<dynamic>?)?.cast<String>() ?? [];

              if (type == 'exclude') {
                return CheckboxListTile(
                  title: Text('No $name'),
                  value: _excluded.contains(name),
                  onChanged: (v) => setState(() {
                    if (v == true) {
                      _excluded.add(name);
                    } else {
                      _excluded.remove(name);
                    }
                  }),
                );
              }

              return ListTile(
                title: Text(name),
                subtitle: DropdownButton<String>(
                  value: _substitutes[name],
                  isExpanded: true,
                  hint: const Text('Select option'),
                  items: choices
                      .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                      .toList(),
                  onChanged: (v) => setState(() => _substitutes[name] = v ?? ''),
                ),
              );
            }),
            ..._surchargeOptions.map((opt) {
              final name = opt['name'] as String;
              final price = (opt['price'] as num?)?.toDouble() ?? 0.0;
              return CheckboxListTile(
                title: Text('$name (+ \$${price.toStringAsFixed(2)})'),
                value: _surcharges.containsKey(name),
                onChanged: (v) => setState(() {
                  if (v == true) {
                    _surcharges[name] = price;
                  } else {
                    _surcharges.remove(name);
                  }
                }),
              );
            }),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            final modifier = Modifier(
              exclude: _excluded,
              substitute: _substitutes,
              surcharges: _surcharges,
            );
            Navigator.of(context).pop(modifier);
          },
          child: const Text('Add'),
        ),
      ],
    );
  }
}