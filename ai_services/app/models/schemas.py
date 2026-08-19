from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class SqlQueryRequest(BaseModel):
    question: str
    schema_filter: list[str] | None = None


class SqlQueryResponse(BaseModel):
    sql: str
    result: list[dict] | None = None
    columns: list[str] | None = None
    row_count: int = 0
    truncated: bool = False


class OcrRequest(BaseModel):
    vendor_id: int | None = None
    company_id: int | None = None


class InvoiceLine(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float


class OcrResponse(BaseModel):
    vendor: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    total_amount: float | None = None
    tax_amount: float | None = None
    currency: str | None = None
    confidence: float
    lines: list[InvoiceLine] | None = None
    raw_text: str


# --- AI Assistant schemas ---

class BusinessSetupRequest(BaseModel):
    business_type: str = "retail"
    industry: str = "general"
    size: str = "small"
    country: str = "SA"
    language: str = "ar"


class BusinessSetupResponse(BaseModel):
    modules: list[str | dict] = []
    warehouses: list[str | dict] = []
    product_categories: list[str | dict] = []
    chart_of_accounts_summary: list[dict] = []
    pos_config: dict | None = None
    steps: list[str | dict] = []
    summary_ar: str = ""
    summary_en: str = ""


class InventorySalesRequest(BaseModel):
    inventory: list[dict] | None = None
    sales: list[dict] | None = None
    language: str = "ar"


class InventorySalesAlert(BaseModel):
    severity: str = "low"
    message_ar: str = ""


class InventorySalesResponse(BaseModel):
    alerts: list[InventorySalesAlert] = []
    suggestions: list[str] = []
    summary_ar: str = ""


class CashRegisterRequest(BaseModel):
    sessions: list[dict] | None = None
    language: str = "ar"


class CashRegisterResponse(BaseModel):
    status: str = "ok"
    open_sessions: list[str] = []
    alerts: list[InventorySalesAlert] = []
    summary_ar: str = ""


class BankReconciliationRequest(BaseModel):
    bank_lines: list[dict] | None = None
    transactions: list[dict] | None = None
    language: str = "ar"


class BankMatch(BaseModel):
    bank_line: str = ""
    transaction: str = ""
    confidence: float = 0.0


class BankReconciliationResponse(BaseModel):
    matches: list[BankMatch] = []
    unmatched_bank: list[str] = []
    unmatched_transactions: list[str] = []
    suggestions: list[str] = []
    summary_ar: str = ""


class ReportSuggestionRequest(BaseModel):
    role: str = "manager"
    industry: str = "general"
    size: str = "small"
    language: str = "ar"


class ReportSuggestion(BaseModel):
    title_ar: str = ""
    title_en: str = ""
    type: str = "list"
    frequency: str = "monthly"
    description_ar: str = ""


class ReportSuggestionResponse(BaseModel):
    reports: list[ReportSuggestion] = []
    summary_ar: str = ""


# --- Document Hunter Schemas ---

class DocumentHunterResponse(BaseModel):
    document_type: str = "unknown"  # cr, vat, gosi, national_address, unknown
    document_title_ar: str = ""
    cr_number: str | None = None
    vat_number: str | None = None
    gosi_number: str | None = None
    company_name_ar: str | None = None
    company_name_en: str | None = None
    activity_description: str | None = None
    industry_sector: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    capital: float | None = None
    employee_count: int | None = None
    saudization_rate: float | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    building_no: str | None = None
    postal_code: str | None = None
    confidence: float = 0.0
    raw_text: str = ""
    ai_questions: list[dict] = []
    suggested_modules: list[str] = []


# --- AI Developer Staff Schemas ---

class DeveloperConsultRequest(BaseModel):
    prompt: str
    persona: str = "odoo_senior_dev"  # odoo_senior_dev, business_architect, tax_compliance_expert, data_analyst, pos_hardware_engineer
    context_module: str = "general"
    error_traceback: str | None = None
    language: str = "ar"


class DeveloperConsultResponse(BaseModel):
    title: str = ""
    solution_ar: str = ""
    code: str | None = None
    code_type: str = "python"  # python, sql, xml, n8n, text
    recommended_actions: list[str] = []
    root_cause: str | None = None


# --- Smart Chart-of-Accounts Import Schemas ---

class CoaAccountRow(BaseModel):
    code: str = ""
    name: str = ""
    raw_type_hint: str | None = None
    parent_code: str | None = None


class CoaMappingRequest(BaseModel):
    accounts: list[CoaAccountRow] = []
    country: str = "SA"
    language: str = "ar"


class CoaAccountMapping(BaseModel):
    code: str = ""
    name: str = ""
    account_type: str = "asset_current"
    is_group: bool = False
    reconcile: bool = False
    suggested_parent_code: str | None = None
    confidence: float = 0.5
    reasoning_ar: str = ""


class CoaMappingResponse(BaseModel):
    mappings: list[CoaAccountMapping] = []
    warnings_ar: list[str] = []
    summary_ar: str = ""


# --- Smart Manufacturing BOM Advisor Schemas ---

class BomAdvisorRequest(BaseModel):
    product_name: str
    product_category: str | None = None
    description: str | None = None
    destination_type: str | None = None  # e.g. hospital, warehouse, residential, retail
    country: str = "SA"
    language: str = "ar"


class BomComponentSuggestion(BaseModel):
    name: str = ""
    quantity: float = 1.0
    uom: str = "Units"
    is_critical: bool = False
    reasoning_ar: str = ""


class ComplianceSuggestion(BaseModel):
    requirement_ar: str = ""
    reason_ar: str = ""
    severity: str = "recommended"  # recommended, required


class BomAdvisorResponse(BaseModel):
    components: list[BomComponentSuggestion] = []
    compliance_suggestions: list[ComplianceSuggestion] = []
    manufacturing_notes_ar: list[str] = []
    summary_ar: str = ""
