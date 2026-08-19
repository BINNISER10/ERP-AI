"""AI assistant endpoints for ERP operations and setup guidance."""
import json
import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    BankReconciliationRequest,
    BankReconciliationResponse,
    BomAdvisorRequest,
    BomAdvisorResponse,
    BusinessSetupRequest,
    BusinessSetupResponse,
    CashRegisterRequest,
    CashRegisterResponse,
    CoaMappingRequest,
    CoaMappingResponse,
    DeveloperConsultRequest,
    DeveloperConsultResponse,
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
        if not isinstance(result, dict):
            raise LLMError("AI returned an unexpected response shape for business setup.")
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
        if not isinstance(result, dict):
            raise LLMError("AI returned an unexpected response shape for inventory analysis.")
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
        if not isinstance(result, dict):
            raise LLMError("AI returned an unexpected response shape for cash register analysis.")
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
        if not isinstance(result, dict):
            raise LLMError("AI returned an unexpected response shape for bank reconciliation.")
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
        if not isinstance(result, dict):
            raise LLMError("AI returned an unexpected response shape for report suggestions.")
        return ReportSuggestionResponse(**result)
    except LLMError as exc:
        logger.error("reports/suggest LLM error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/developer/consult", response_model=DeveloperConsultResponse)
def developer_consult(request: DeveloperConsultRequest) -> DeveloperConsultResponse:
    """Odoo Software Development & Business Consultant Staff Member endpoint."""
    persona_descriptions = {
        "odoo_senior_dev": "You are a World-Class Principal Odoo 18 Developer & Architect. You write clean, performant, idiomatic Odoo Python, XML, and SQL code.",
        "business_architect": "You are an Enterprise ERP Business Architect. You advise on accounting, supply chain, multi-company setups, and business process automation.",
        "tax_compliance_expert": "You are a Saudi Tax & ZATCA Phase 2 E-Invoicing Expert. You specialize in XML C14N, digital signatures, VAT regulations, and compliance.",
        "data_analyst": "You are a Senior SQL & Business Intelligence Analyst for PostgreSQL and Odoo ERP data models.",
        "pos_hardware_engineer": "You are an IoT, POS, and Hardware Integration Specialist for Flutter, Mada POS, ESC/POS, and Stripe Terminal.",
    }

    system_persona = persona_descriptions.get(request.persona, persona_descriptions["odoo_senior_dev"])

    error_section = ""
    if request.error_traceback:
        error_section = f"""
ERROR TRACEBACK TO DIAGNOSE AND FIX:
{request.error_traceback}
"""

    prompt = f"""{system_persona}

You are acting as an internal staff member for the company using Nexus Enterprise Engine (Odoo 18).
User Question / Requirement: {request.prompt}
Context Module: {request.context_module}
{error_section}
Language: {request.language} (Provide explanations in Arabic, and code/syntax in proper technical format).

Return a JSON object with:
- title: Short informative title of the solution in Arabic.
- solution_ar: Comprehensive step-by-step explanation and practical guidance in Arabic.
- root_cause: If an error traceback was provided, explain the root cause clearly in Arabic, else null.
- code: Practical ready-to-run code (Python, Server Action, SQL query, XML view, or n8n JSON) if applicable, else null.
- code_type: One of "python", "sql", "xml", "n8n", or "text".
- recommended_actions: List of 3-5 concrete action bullet points in Arabic.

Return only valid JSON.
"""
    try:
        result = generate_json(prompt)
        if not isinstance(result, dict):
            raise LLMError("AI returned an unexpected response shape for developer consultation.")
        return DeveloperConsultResponse(**result)
    except LLMError as exc:
        logger.error("developer/consult LLM error: %s", exc)
        # Fallback expert response if LLM is offline
        return DeveloperConsultResponse(
            title=f"استشارة تقنية: {request.prompt[:50]}",
            solution_ar=f"تم استلام طلبك لفريق مطوري Nexus بنجاح. لتحقيق هذا المتطلب في موديول ({request.context_module})، يوصى بإنشاء Server Action أو Automated Action لربط الحقول وتشغيل الأتمتة.",
            code="# Server Action / Automated Action Example\n# record: active record in the Nexus Enterprise Engine\nfor rec in records:\n    if not rec.ref:\n        rec.ref = f'NEXUS-{rec.id:06d}'\n",
            code_type="python",
            recommended_actions=[
                "مراجعة إعدادات الموديول في Technical > Automated Actions",
                "التحقق من صحة أسماء الحقول في قاعدة البيانات",
                "اختبار العملية في بيئة التطوير قبل التطبيق النهائي",
            ],
            root_cause="تحليل أولي تلقائي من مطور النظام الذكي (Offline Fallback Mode)" if request.error_traceback else None,
        )


@router.post("/wizard/coa-mapping", response_model=CoaMappingResponse)
def coa_mapping(request: CoaMappingRequest) -> CoaMappingResponse:
    """Analyze a client's legacy chart of accounts and suggest a harmonious
    mapping onto Odoo's standard account_type taxonomy.

    Used when a client already has their own chart of accounts (built over
    years, sometimes with a non-standard numbering scheme) and wants to
    migrate it into the ERP without losing its structure.
    """
    if not request.accounts:
        return CoaMappingResponse(summary_ar="لا توجد حسابات لتحليلها.")

    accounts_payload = [a.model_dump() for a in request.accounts]
    prompt = f"""You are a senior chartered accountant specializing in migrating legacy,
company-specific charts of accounts into a standard ERP (Odoo) without losing the
client's original structure or numbering logic.

Country: {request.country}
Language: {request.language}

The client's raw chart-of-accounts rows (code, name, optional raw_type_hint, optional parent_code):
{_safe_dump(accounts_payload)}

For EACH row, decide the best-fit Odoo `account_type` from this exact list:
asset_receivable, asset_cash, asset_current, asset_non_current, asset_prepayments,
asset_fixed, liability_payable, liability_credit_card, liability_current,
liability_non_current, equity, equity_unaffected, income, income_other, expense,
expense_depreciation, expense_direct_cost, off_balance.

Preserve the client's existing hierarchy: if a row looks like a parent/heading account
(no transactions expected, used only to group children), mark is_group=true and account_type
should reflect the group's overall nature. Infer suggested_parent_code from code prefixes,
name patterns, or the given parent_code, when possible.

Return a JSON object with:
- mappings: list of objects, one per input row, each with:
  "code", "name", "account_type", "is_group" (bool), "reconcile" (bool - true only for
  receivable/payable control accounts), "suggested_parent_code" (or null),
  "confidence" (0-1), "reasoning_ar" (short Arabic justification).
- warnings_ar: list of Arabic warnings about ambiguous/conflicting/duplicate codes found.
- summary_ar: short Arabic summary of the overall mapping strategy used.

Return only valid JSON.
"""
    try:
        result = generate_json(prompt)
        if not isinstance(result, dict):
            raise LLMError("AI returned an unexpected response shape for CoA mapping.")
        return CoaMappingResponse(**result)
    except LLMError as exc:
        logger.error("coa-mapping LLM error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/wizard/bom-advisor", response_model=BomAdvisorResponse)
def bom_advisor(request: BomAdvisorRequest) -> BomAdvisorResponse:
    """Suggest a Bill of Materials and destination-aware compliance
    requirements for a manufactured product (e.g. a wood door destined for
    a hospital should be flagged for fire-rating certification).
    """
    prompt = f"""You are a world-class manufacturing engineer and BOM (Bill of Materials)
consultant with deep knowledge of building products, hardware components, and
industry/regulatory compliance requirements (fire rating, accessibility, hygiene,
electrical safety, etc.) across different installation destinations.

Product name: {request.product_name}
Product category: {request.product_category or "unspecified"}
Description: {request.description or "none"}
Installation destination: {request.destination_type or "unspecified"}
Country: {request.country}
Language: {request.language}

Think step by step about what this product is physically made of (raw materials,
hardware, fasteners, finishes), and whether the destination implies any special
regulatory or safety requirements (e.g. a door installed in a hospital or public
building may require fire-rating, an accessible/ADA-compliant design, or specific
hardware certifications; a warehouse door may require impact-resistance; a
residential product usually has no special requirements).

Return a JSON object with:
- components: list of BOM component suggestions, each with "name", "quantity",
  "uom", "is_critical" (bool - true if the product cannot function/be certified
  without it), "reasoning_ar" (short Arabic justification).
- compliance_suggestions: list of objects, each with "requirement_ar" (the
  suggested certification/spec, e.g. "تصنيف مقاوم للحريق 90 دقيقة"), "reason_ar"
  (why it applies given the destination), "severity" ("required" if the
  destination legally/practically mandates it, otherwise "recommended").
- manufacturing_notes_ar: list of additional Arabic notes/tips that a
  fast-production factory would care about (e.g. batching, tolerances, finishing).
- summary_ar: short Arabic summary.

Return only valid JSON.
"""
    try:
        result = generate_json(prompt)
        if not isinstance(result, dict):
            raise LLMError("AI returned an unexpected response shape for BOM advisor.")
        return BomAdvisorResponse(**result)
    except LLMError as exc:
        logger.error("bom-advisor LLM error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
