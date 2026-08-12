import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/database/app_database.dart';
import '../../../core/models/order_payload.dart';
import '../../../core/network/odoo_jsonrpc.dart';
import '../../../core/repository/pos_repository.dart';
import '../../../services/printing/thermal_printer_service.dart';
import '../../../services/stripe/stripe_terminal_service.dart';
import 'checkout_event.dart';
import 'checkout_state.dart';

class CheckoutBloc extends Bloc<CheckoutEvent, CheckoutState> {
  final OdooJsonRpcClient client;
  final AppDatabase database;
  final ThermalPrinterService printer;
  final StripeTerminalService stripeTerminal;
  late final PosRepository _repository;

  CheckoutBloc({
    required this.client,
    required this.database,
    required this.printer,
    required this.stripeTerminal,
  }) : super(const CheckoutState()) {
    _repository = PosRepository(database);

    on<BuildOrder>(_onBuildOrder);
    on<SetTip>(_onSetTip);
    on<SetSplitPayments>(_onSetSplitPayments);
    on<SetPaymentMethod>(_onSetPaymentMethod);
    on<ProcessPayment>(_onProcessPayment);
    on<SaveOrder>(_onSaveOrder);
  }

  Future<void> _onBuildOrder(BuildOrder event, Emitter<CheckoutState> emit) async {
    emit(state.copyWith(processing: true, error: null));
    try {
      final payload = await _repository.buildOrder(
        stateCode: event.stateCode,
        zipCode: event.zipCode,
        tipAmount: state.tipAmount,
        splitBill: state.splitPayments != null && state.splitPayments!.isNotEmpty,
        splitPayments: state.splitPayments,
        paymentMethod: state.paymentMethod,
      );
      emit(state.copyWith(payload: payload, processing: false));
    } catch (e) {
      emit(state.copyWith(processing: false, error: e.toString()));
    }
  }

  Future<void> _onSetTip(SetTip event, Emitter<CheckoutState> emit) async {
    emit(state.copyWith(tipAmount: event.tipAmount));
    if (state.payload != null) {
      final payload = await _repository.buildOrder(
        stateCode: state.payload!.stateCode,
        zipCode: state.payload!.zipCode,
        tipAmount: event.tipAmount,
        splitBill: state.payload!.splitBill,
        splitPayments: state.splitPayments,
        paymentMethod: state.paymentMethod,
      );
      emit(state.copyWith(payload: payload));
    }
  }

  Future<void> _onSetSplitPayments(SetSplitPayments event, Emitter<CheckoutState> emit) async {
    emit(state.copyWith(splitPayments: event.splitPayments));
    if (state.payload != null) {
      final payload = await _repository.buildOrder(
        stateCode: state.payload!.stateCode,
        zipCode: state.payload!.zipCode,
        tipAmount: state.tipAmount,
        splitBill: event.splitPayments.isNotEmpty,
        splitPayments: event.splitPayments,
        paymentMethod: state.paymentMethod,
      );
      emit(state.copyWith(payload: payload));
    }
  }

  Future<void> _onSetPaymentMethod(SetPaymentMethod event, Emitter<CheckoutState> emit) async {
    emit(state.copyWith(paymentMethod: event.paymentMethod));
  }

  Future<void> _onProcessPayment(ProcessPayment event, Emitter<CheckoutState> emit) async {
    emit(state.copyWith(processing: true, error: null));
    try {
      final payload = state.payload;
      if (payload == null) {
        throw Exception('No order payload. Build order first.');
      }

      if (state.paymentMethod == 'card') {
        final amount = payload.splitBill
            ? state.splitPayments?.firstOrNull?.amount ?? payload.amountTotal
            : payload.amountTotal;
        final success = await stripeTerminal.collectPayment(amount);
        if (!success) {
          throw Exception('Card payment failed or was cancelled.');
        }
      }

      await _repository.storeOrder(payload);
      await printer.printReceipt(payload);

      emit(state.copyWith(processing: false, paid: true));
    } catch (e) {
      emit(state.copyWith(processing: false, error: e.toString()));
    }
  }

  Future<void> _onSaveOrder(SaveOrder event, Emitter<CheckoutState> emit) async {
    try {
      await _repository.storeOrder(event.payload);
      emit(state.copyWith(payload: event.payload, paid: false));
    } catch (e) {
      emit(state.copyWith(error: e.toString()));
    }
  }
}
