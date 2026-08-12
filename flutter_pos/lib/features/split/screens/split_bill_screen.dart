import 'package:flutter/material.dart';

import '../../../core/models/order_payload.dart';

class SplitBillScreen extends StatefulWidget {
  const SplitBillScreen({super.key});

  @override
  State<SplitBillScreen> createState() => _SplitBillScreenState();
}

class _SplitBillScreenState extends State<SplitBillScreen> {
  int _splits = 2;
  double _total = 0.0;
  final _customAmounts = <TextEditingController>[];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // In a real app, the total would come from an inherited order model.
    _total = 100.0;
    _updateControllers();
  }

  void _updateControllers() {
    final equal = _total / _splits;
    _customAmounts
      ..forEach((c) => c.dispose())
      ..clear();
    for (var i = 0; i < _splits; i++) {
      _customAmounts.add(TextEditingController(text: equal.toStringAsFixed(2)));
    }
  }

  @override
  void dispose() {
    for (final c in _customAmounts) {
      c.dispose();
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
                            _updateControllers();
                          })
                      : null,
                ),
                Text('$_splits ways'),
                IconButton(
                  icon: const Icon(Icons.add),
                  onPressed: () => setState(() {
                    _splits++;
                    _updateControllers();
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
