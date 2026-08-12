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
