"""AI assistant endpoints for ERP operations and setup guidance."""
import json
import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    BankReconciliationRequest,
    BankReconciliationResponse,
    BusinessSetupRequest,
    BusinessSetupResponse,
    CashRegisterRequest,
    CashRegisterResponse,
    InventorySalesRequest,
    InventorySalesResponse,
    ReportSuggestionRequest,
    ReportSuggestionResponse,
)
from app.services.llm_factory import LLMError, generate_json

logger = logging.getLogger(__name__)
router = APIRouter()


def _safe_dump(data: dict | list | None) -> str:
    if data is None:
        return "[]"
    return json.dumps(data, ensure_ascii=False, default=str)


@router.post("/wizard/business-setup", response_model=BusinessSetupResponse)
def business_setup(request: BusinessSetupRequest) -> BusinessSetupResponse:
    """Generate a tailored business setup plan for a new Odoo instance."""
    prompt = f"""You are an ERP implementation consultant helping configure a new company in Odoo.
The user provided the following information:
- business_type: {request.business_type}
- industry: {request.industry}
- company_size: {request.size}
- country: {request.country}
- language: {request.language}

Return a JSON object with these keys:
- modules: list of plain Odoo technical module name strings that should be installed (e.g., ["stock", "sale_management", "purchase", "point_of_sale", "account_accountant", "project", "mrp"]).
- warehouses: list of plain warehouse name strings (e.g., ["Main Warehouse", "Riyadh Store"]).
- product_categories: list of plain product category name strings (e.g., ["Electronics", "Mobile Accessories", "Laptops"]).
- chart_of_accounts_summary: list of objects with name and code, e.g., {{"name": "Revenues", "code": "4000"}}.
- pos_config: an object with `name` and `product_categories` for a POS if applicable, otherwise null.
- steps: list of setup steps in Arabic.
- summary_ar: short Arabic summary.
- summary_en: short English summary.

Return only valid JSON.
"""
    try:
        result = generate_json(prompt)
        if isinstance(result, list):
            result = {"result": result}
        return BusinessSetupResponse(**result)
    except LLMError as exc:
        logger.error("business-setup LLM error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/monitor/inventory-sales", response_model=InventorySalesResponse)
def monitor_inventory_sales(request: InventorySalesRequest) -> InventorySalesResponse:
    """Analyze inventory and sales data and return alerts/suggestions."""
    prompt = f"""You are an ERP operations analyst. Analyze the following inventory and sales data.
Inventory data: {_safe_dump(request.inventory)}
Sales data: {_safe_dump(request.sales)}
Language: {request.language}

Return a JSON object with:
- alerts: list of alerts, each with "severity" (low|medium|high) and "message_ar" in Arabic.
- suggestions: list of action suggestions in Arabic.
- summary_ar: short Arabic summary.

Return only valid JSON.
"""
    try:
        result = generate_json(prompt)
        if isinstance(result, list):
            result = {"alerts": [], "suggestions": [], "summary_ar": str(result)}
        return InventorySalesResponse(**result)
    except LLMError as exc:
        logger.error("inventory-sales LLM error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/monitor/cash-register", response_model=CashRegisterResponse)
def monitor_cash_register(request: CashRegisterRequest) -> CashRegisterResponse:
    """Check POS / cash register sessions and warn about non-closed or unusual sessions."""
    prompt = f"""You are a cash control assistant. Review the following POS / cash register sessions.
Sessions data: {_safe_dump(request.sessions)}
Language: {request.language}

Return a JSON object with:
- status: one of "ok", "warning", or "critical".
- open_sessions: list of names/IDs of sessions that are still open.
- alerts: list of Arabic alerts with "severity" and "message_ar".
- summary_ar: short Arabic summary.

Return only valid JSON.
"""
    try:
        result = generate_json(prompt)
        if isinstance(result, list):
            result = {"status": "ok", "open_sessions": [], "alerts": [], "summary_ar": str(result)}
        return CashRegisterResponse(**result)
    except LLMError as exc:
        logger.error("cash-register LLM error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/monitor/bank-reconciliation", response_model=BankReconciliationResponse)
def monitor_bank_reconciliation(request: BankReconciliationRequest) -> BankReconciliationResponse:
    """Match bank statement lines with internal transactions and find discrepancies."""
    prompt = f"""You are an accounting assistant performing bank reconciliation.
Bank statement lines: {_safe_dump(request.bank_lines)}
Internal transactions: {_safe_dump(request.transactions)}
Language: {request.language}

Return a JSON object with:
- matches: list of matched pairs, each with "bank_line" and "transaction" identifiers and "confidence" (0-1).
- unmatched_bank: list of unmatched bank statement line identifiers.
- unmatched_transactions: list of unmatched internal transaction identifiers.
- suggestions: list of Arabic suggestions for resolving discrepancies.
- summary_ar: short Arabic summary.

Return only valid JSON.
"""
    try:
        result = generate_json(prompt)
        if isinstance(result, list):
            result = {"matches": [], "unmatched_bank": [], "unmatched_transactions": [], "suggestions": [], "summary_ar": str(result)}
        return BankReconciliationResponse(**result)
    except LLMError as exc:
        logger.error("bank-reconciliation LLM error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/reports/suggest", response_model=ReportSuggestionResponse)
def suggest_reports(request: ReportSuggestionRequest) -> ReportSuggestionResponse:
    """Suggest useful reports for a given role and industry."""
    prompt = f"""You are a BI and ERP reporting consultant. Suggest useful reports for the following user.
Role: {request.role}
Industry: {request.industry}
Company size: {request.size}
Language: {request.language}

Return a JSON object with:
- reports: list of reports, each with "title_ar", "title_en", "type" (list|pivot|graph|dashboard), "frequency" (daily|weekly|monthly|quarterly|yearly|ad-hoc), and "description_ar".
- summary_ar: short Arabic summary.

Return only valid JSON.
"""
    try:
        result = generate_json(prompt)
        if isinstance(result, list):
            result = {"reports": result, "summary_ar": ""}
        return ReportSuggestionResponse(**result)
    except LLMError as exc:
        logger.error("reports/suggest LLM error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
