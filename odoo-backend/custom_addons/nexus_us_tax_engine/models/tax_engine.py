from odoo import models, api
from odoo.exceptions import UserError


class UsTaxEngine(models.AbstractModel):
    _name = "us.tax.engine"
    _description = "US Sales Tax Engine"

    @api.model
    def calculate_tax(self, amount, state_code, zip_code=None, county=None, city=None, product_category=None):
        """Calculate multi-jurisdiction US sales tax.

        Returns a dict with:
            - total_tax: total tax amount
            - tax_lines: list of breakdowns per jurisdiction
            - taxable_amount: input amount
        """
        if amount < 0:
            raise UserError("Taxable amount cannot be negative.")

        # Fetch all active rates for the requested state and refine in Python.
        rates = self.env["us.tax.rate"].search(
            [
                ("state_code", "=", state_code.upper()),
                ("active", "=", True),
            ]
        )

        if not rates:
            return {
                "total_tax": 0.0,
                "tax_lines": [],
                "taxable_amount": amount,
            }

        tax_lines = []
        total_tax = 0.0
        applied_rate_ids = set()

        for rate in rates:
            # Skip local-only records that do not match the provided county/city.
            if rate.county and county and rate.county.lower() != county.lower():
                continue
            if rate.city and city and rate.city.lower() != city.lower():
                continue

            # Validate zip code range when the record specifies one.
            if rate.zip_start and zip_code and zip_code < rate.zip_start:
                continue
            if rate.zip_end and zip_code and zip_code > rate.zip_end:
                continue

            if rate.id in applied_rate_ids:
                continue

            tax = round(amount * rate.rate, 2)
            tax_lines.append(
                {
                    "name": rate.name,
                    "jurisdiction": rate.tax_type,
                    "rate": rate.rate,
                    "tax": tax,
                    "state": rate.state_code,
                    "county": rate.county,
                    "city": rate.city,
                }
            )
            total_tax += tax
            applied_rate_ids.add(rate.id)

        return {
            "total_tax": round(total_tax, 2),
            "tax_lines": tax_lines,
            "taxable_amount": amount,
        }
