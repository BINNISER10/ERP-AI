import 'package:flutter/material.dart';

import '../../../core/models/order_payload.dart';

class SplitBillScreen extends StatefulWidget {
  final double total;

  const SplitBillScreen({super.key, required this.total});

  @override
  State<SplitBillScreen> createState() => _SplitBillScreenState();
}

class _SplitBillScreenState extends State<SplitBillScreen> {
  int _splits = 2;
  late double _total;
  final _customAmounts = <TextEditingController>[];

  @override
  void initState() {
    super.initState();
    _total = widget.total;
    _syncControllers();
  }

  void _syncControllers() {
    if (_customAmounts.length == _splits) return;
    final equal = _splits == 0 ? 0.0 : _total / _splits;
    // Grow the list first; never dispose controllers still bound to the tree.
    while (_customAmounts.length < _splits) {
      _customAmounts.add(TextEditingController(text: equal.toStringAsFixed(2)));
    }
    // Shrink: drop surplus controllers after the current frame so any widget
    // still referencing them has unmounted first.
    if (_customAmounts.length > _splits) {
      final removed = _customAmounts.sublist(_splits);
      _customAmounts.removeRange(_splits, _customAmounts.length);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        for (final c in removed) {
          if (!c.isDisposed) c.dispose();
        }
      });
    }
  }

  @override
  void dispose() {
    for (final c in _customAmounts) {
      if (!c.isDisposed) c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Split Bill')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Text('Total: \$${_total.toStringAsFixed(2)}', style: Theme.of(context).textTheme.titleLarge),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  icon: const Icon(Icons.remove),
                  onPressed: _splits > 2
                      ? () => setState(() {
                            _splits--;
                            _syncControllers();
                          })
                      : null,
                ),
                Text('$_splits ways'),
                IconButton(
                  icon: const Icon(Icons.add),
                  onPressed: () => setState(() {
                    _splits++;
                    _syncControllers();
                  }),
                ),
              ],
            ),
            Expanded(
              child: ListView.builder(
                itemCount: _splits,
                itemBuilder: (context, index) {
                  return ListTile(
                    leading: Text('Guest ${index + 1}'),
                    title: TextField(
                      controller: _customAmounts[index],
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(prefixText: '\$'),
                    ),
                  );
                },
              ),
            ),
            FilledButton(
              onPressed: _onConfirm,
              child: const Text('Confirm Split'),
            ),
          ],
        ),
      ),
    );
  }

  void _onConfirm() {
    final payments = _customAmounts
        .asMap()
        .entries
        .map((e) => SplitPayment(
              amount: double.tryParse(e.value.text) ?? 0.0,
              method: 'cash',
            ))
        .toList();
    Navigator.of(context).pop(payments);
  }
}