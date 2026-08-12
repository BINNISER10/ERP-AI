from app.services.ocr_engine import OcrEngine


class TestOcrEngine:
    def test_parse_text_simple_invoice(self):
        engine = OcrEngine()
        text = """Acme Supplies
Invoice #: INV-1234
Date: 12/04/2025
Total: $250.00
Tax: $20.00
Widget x 2 @ $100.00"""
        result = engine._parse_text(text)
        assert result["vendor"] == "Acme Supplies"
        assert result["invoice_number"] == "INV-1234"
        assert result["invoice_date"] == "12/04/2025"
        assert result["total_amount"] == 250.0
        assert result["tax_amount"] == 20.0
        assert result["currency"] == "USD"
        assert len(result["lines"]) == 1
        assert result["lines"][0]["quantity"] == 2.0
