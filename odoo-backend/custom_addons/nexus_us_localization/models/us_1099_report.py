# -*- coding: utf-8 -*-
"""Nexus US 1099 Report — تقرير 1099 للسنة الضريبية.

Generates the 1099-NEC and 1099-MISC summary that US businesses
must file with the IRS each year. The report lists every vendor
who:
    * Has ``is_1099_vendor`` flag set, AND
    * Has accumulated ``$form_1099_threshold`` or more in payments
      during the calendar year.

The output is a CSV file in the IRS-required format plus an
HTML preview.
"""

import base64
import csv
import io
import logging
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NexusUS1099Report(models.TransientModel):
    """1099-NEC / MISC report wizard."""

    _name = "nexus.us.1099.report"
    _description = "Nexus US 1099 Report"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    tax_year = fields.Integer(
        string="Tax Year",
        required=True,
        default=lambda self: date.today().year - 1,
    )
    form_type = fields.Selection(
        [
            ("1099-NEC", "1099-NEC (Nonemployee Compensation)"),
            ("1099-MISC", "1099-MISC (Miscellaneous Income)"),
        ],
        string="Form Type",
        default="1099-NEC",
    )
    threshold = fields.Float(
        string="Reporting Threshold ($)",
        default=600.0,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("computed", "Computed"), ("exported", "Exported")],
        default="draft",
    )

    line_ids = fields.One2many(
        "nexus.us.1099.report.line",
        "report_id",
        string="Vendors to Report",
    )
    total_amount = fields.Float(string="Total Payments", readonly=True)
    total_vendor_count = fields.Integer(string="Vendor Count", readonly=True)

    # ─────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────
    def action_compute(self):
        self.ensure_one()
        settings = self.env["nexus.us.company.settings"].get_for_company(
            self.company_id
        )
        threshold = self.threshold or settings.form_1099_threshold

        year_start = date(self.tax_year, 1, 1)
        year_end = date(self.tax_year, 12, 31)

        # Clear previous lines
        self.line_ids.unlink()

        lines = []
        total = 0.0
        vendor_count = 0

        vendors = self.env["res.partner"].search([
            ("company_id", "=", self.company_id.id),
            ("is_1099_vendor", "=", True),
            ("country_id.code", "=", "US"),
        ])
        for vendor in vendors:
            payments_total = self._vendor_payments(
                vendor, self.company_id, year_start, year_end
            )
            if payments_total >= threshold:
                lines.append({
                    "report_id": self.id,
                    "partner_id": vendor.id,
                    "tin": vendor.vat or "",
                    "tin_type": (
                        "EIN" if (vendor.vat or "").isdigit()
                        and len(vendor.vat or "") == 9
                        else "SSN"
                    ),
                    "total_payments": payments_total,
                    "address": self._format_address(vendor),
                })
                total += payments_total
                vendor_count += 1

        self.env["nexus.us.1099.report.line"].create(lines)
        self.write({
            "state": "computed",
            "total_amount": round(total, 2),
            "total_vendor_count": vendor_count,
        })
        return self._reopen()

    # ─────────────────────────────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────────────────────────────
    def action_export_csv(self):
        self.ensure_one()
        if self.state != "computed":
            raise UserError(_("احسب التقرير أولاً."))

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "TIN",
            "TIN_Type",
            "Name",
            "Address",
            "Total Payments",
            "Form Type",
            "Tax Year",
        ])
        for line in self.line_ids:
            writer.writerow([
                line.tin,
                line.tin_type,
                line.partner_id.display_name,
                line.address,
                "%0.2f" % line.total_payments,
                self.form_type,
                self.tax_year,
            ])
        content = buf.getvalue().encode("utf-8")
        filename = "1099_%s_%d.csv" % (self.form_type, self.tax_year)

        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "datas": base64.b64encode(content),
            "res_model": self._name,
            "res_id": self.id,
            "type": "binary",
        })
        self.write({"state": "exported"})
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%d?download=true" % attachment.id,
            "target": "self",
        }

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────
    def _vendor_payments(self, vendor, company, year_start, year_end):
        """Sum vendor bills posted in the calendar year."""
        bills = self.env["account.move"].search([
            ("company_id", "=", company.id),
            ("partner_id", "=", vendor.id),
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", year_start),
            ("invoice_date", "<=", year_end),
        ])
        return sum(bills.mapped("amount_total"))

    def _format_address(self, partner):
        bits = [
            partner.street or "",
            partner.street2 or "",
            partner.city or "",
            partner.state_id.name if partner.state_id else "",
            partner.zip or "",
        ]
        return ", ".join(b for b in bits if b)

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }


class NexusUS1099ReportLine(models.TransientModel):
    """Vendor line in a 1099 report."""

    _name = "nexus.us.1099.report.line"
    _description = "Nexus US 1099 Report Line"

    report_id = fields.Many2one(
        "nexus.us.1099.report",
        string="Report",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
    )
    tin = fields.Char(string="TIN / EIN / SSN")
    tin_type = fields.Selection(
        [("SSN", "SSN"), ("EIN", "EIN"), ("ITIN", "ITIN")],
        string="TIN Type",
    )
    total_payments = fields.Float(string="Total Payments", digits=(12, 2))
    address = fields.Char(string="Address")
