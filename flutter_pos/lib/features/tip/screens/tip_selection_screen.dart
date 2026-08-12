import 'package:flutter/material.dart';

class TipSelectionScreen extends StatelessWidget {
  const TipSelectionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add Tip')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _TipButton(percent: 0.0, label: 'No Tip', onTap: (v) => Navigator.of(context).pop(v)),
            _TipButton(percent: 0.10, label: '10%', onTap: (v) => Navigator.of(context).pop(v)),
            _TipButton(percent: 0.15, label: '15%', onTap: (v) => Navigator.of(context).pop(v)),
            _TipButton(percent: 0.18, label: '18%', onTap: (v) => Navigator.of(context).pop(v)),
            _TipButton(percent: 0.20, label: '20%', onTap: (v) => Navigator.of(context).pop(v)),
            const Spacer(),
            TextButton(
              onPressed: () => Navigator.of(context).pop(0.0),
              child: const Text('Skip'),
            ),
          ],
        ),
      ),
    );
  }
}

class _TipButton extends StatelessWidget {
  final double percent;
  final String label;
  final ValueSetter<double> onTap;

  const _TipButton({required this.percent, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: OutlinedButton(
        onPressed: () => onTap(percent),
        child: Text(label),
      ),
    );
  }
}
