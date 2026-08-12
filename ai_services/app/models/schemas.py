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
    modules: list[str] = []
    warehouses: list[str] = []
    product_categories: list[str] = []
    chart_of_accounts_summary: list[dict] = []
    pos_config: dict | None = None
    steps: list[str] = []
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
