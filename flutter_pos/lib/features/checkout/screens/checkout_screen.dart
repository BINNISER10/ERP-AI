import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../pos/bloc/pos_bloc.dart';
import '../../pos/bloc/pos_event.dart';
import '../../pos/bloc/pos_state.dart';
import '../../tip/screens/tip_selection_screen.dart';
import '../../split/screens/split_bill_screen.dart';
import '../bloc/checkout_bloc.dart';
import '../bloc/checkout_event.dart';
import '../bloc/checkout_state.dart';

class CheckoutScreen extends StatelessWidget {
  const CheckoutScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: Column(
        children: [
          Expanded(
            child: BlocBuilder<PosBloc, PosState>(
              builder: (context, state) {
                if (state.cart.isEmpty) {
                  return const Center(child: Text('Cart is empty'));
                }
                return ListView.builder(
                  itemCount: state.cart.length,
                  itemBuilder: (context, index) {
                    final item = state.cart[index];
                    return ListTile(
                      title: Text(item.name),
                      subtitle: Text('Qty: ${item.quantity.toStringAsFixed(2)}'),
                      trailing: Text('\$${item.total.toStringAsFixed(2)}'),
                    );
                  },
                );
              },
            ),
          ),
          BlocBuilder<PosBloc, PosState>(
            builder: (context, state) {
              return Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text('Subtotal: \$${state.subtotal.toStringAsFixed(2)}'),
                    Text('Tax: \$${state.tax.toStringAsFixed(2)}'),
                    Text('Total: \$${state.total.toStringAsFixed(2)}', style: Theme.of(context).textTheme.titleLarge),
                  ],
                ),
              );
            },
          ),
          BlocBuilder<CheckoutBloc, CheckoutState>(
            builder: (context, state) {
              return Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (state.tipAmount > 0) Text('Tip: \$${state.tipAmount.toStringAsFixed(2)}'),
                    if (state.splitPayments != null && state.splitPayments!.isNotEmpty)
                      Text('Split into ${state.splitPayments!.length} payments'),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton(
                            onPressed: () => _onAddTip(context),
                            child: const Text('Add Tip'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton(
                            onPressed: () => _onSplitBill(context),
                            child: const Text('Split Bill'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    DropdownButton<String>(
                      value: state.paymentMethod,
                      isExpanded: true,
                      items: const [
                        DropdownMenuItem(value: 'cash', child: Text('Cash')),
                        DropdownMenuItem(value: 'card', child: Text('Card (Stripe Terminal)')),
                        DropdownMenuItem(value: 'mada', child: Text('Mada POS')),
                      ],
                      onChanged: (v) {
                        if (v != null) {
                          context.read<CheckoutBloc>().add(SetPaymentMethod(v));
                        }
                      },
                    ),
                    const SizedBox(height: 8),
                    FilledButton(
                      onPressed: state.processing
                          ? null
                          : () => _onCheckout(context),
                      child: state.processing
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Pay & Post to Odoo'),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Future<void> _onAddTip(BuildContext context) async {
    final tip = await Navigator.of(context).push<double>(
      MaterialPageRoute(builder: (_) => const TipSelectionScreen()),
    );
    if (tip != null && context.mounted) {
      context.read<CheckoutBloc>().add(SetTip(tip));
    }
  }

  Future<void> _onSplitBill(BuildContext context) async {
    final payments = await Navigator.of(context).push<List<dynamic>>(
      MaterialPageRoute(builder: (_) => const SplitBillScreen()),
    );
    if (payments != null && context.mounted) {
      // Simplified: the split bill screen is expected to update the CheckoutBloc
      // via inherited state or returning data. Real implementation maps list to
      // SplitPayment objects.
    }
  }

  Future<void> _onCheckout(BuildContext context) async {
    // US retail path: prompt for state/zip.
    final result = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => const _UsAddressDialog(),
    );
    if (!context.mounted) return;

    context.read<CheckoutBloc>().add(
          BuildOrder(
            stateCode: result?['state']?.toUpperCase(),
            zipCode: result?['zip'],
          ),
        );

    // Wait for BuildOrder to finish.
    await for (final state in context.read<CheckoutBloc>().stream) {
      if (!state.processing) break;
    }

    if (!context.mounted) return;
    context.read<CheckoutBloc>().add(const ProcessPayment());

    // After payment, clear cart.
    await for (final state in context.read<CheckoutBloc>().stream) {
      if (state.paid) break;
      if (state.error != null) break;
    }

    if (!context.mounted) return;
    final state = context.read<CheckoutBloc>().state;
    if (state.paid) {
      context.read<PosBloc>().add(const ClearCart());
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Order posted and payment complete')),
      );
    } else if (state.error != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: ${state.error}')),
      );
    }
  }
}

class _UsAddressDialog extends StatefulWidget {
  const _UsAddressDialog();

  @override
  State<_UsAddressDialog> createState() => _UsAddressDialogState();
}

class _UsAddressDialogState extends State<_UsAddressDialog> {
  final _stateController = TextEditingController();
  final _zipController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('US Sales Tax'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _stateController,
            decoration: const InputDecoration(labelText: 'State (e.g. CA)'),
            maxLength: 2,
          ),
          TextField(
            controller: _zipController,
            decoration: const InputDecoration(labelText: 'ZIP Code'),
            keyboardType: TextInputType.number,
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Skip'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop({
            'state': _stateController.text,
            'zip': _zipController.text,
          }),
          child: const Text('Continue'),
        ),
      ],
    );
  }
}
