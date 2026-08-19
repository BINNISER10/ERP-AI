# -*- coding: utf-8 -*-
"""Nexus Saudi VAT Report — تقرير ضريبة القيمة المضافة.

Generates the VAT return that ZATCA / GAZT requires:

    * Output VAT (on sales) — standard 15%
    * Input VAT (on purchases) — standard 15%
    * Net VAT payable / refundable

Supports both monthly and quarterly periods and writes a flat
``.xml`` payload that matches ZATCA's VAT return schema (v0.9).
"""

import logging
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class NexusSaudiVatReport(models.TransientModel):
    """VAT return wizard — generates a ZATCA-compatible XML."""

    _name = "nexus.saudi.vat.report"
    _description = "Nexus Saudi VAT Report"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    period_start = fields.Date(
        string="Period Start",
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    period_end = fields.Date(
        string="Period End",
        required=True,
        default=fields.Date.today,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("computed", "Computed"),
            ("exported", "Exported"),
        ],
        default="draft",
    )

    output_vat = fields.Float(
        string="Output VAT (Sales)",
        readonly=True,
    )
    input_vat = fields.Float(
        string="Input VAT (Purchases)",
        readonly=True,
    )
    net_vat = fields.Float(
        string="Net VAT Payable",
        readonly=True,
    )
    sales_total = fields.Float(
        string="Total Sales (incl. VAT)",
        readonly=True,
    )
    purchases_total = fields.Float(
        string="Total Purchases (incl. VAT)",
        readonly=True,
    )
    summary_html = fields.Html(
        string="Summary",
        readonly=True,
        sanitize=False,
    )
    xml_payload = fields.Text(
        string="ZATCA XML Payload",
        readonly=True,
    )

    # ─────────────────────────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────────────────────────
    @api.constrains("period_start", "period_end")
    def _check_dates(self):
        for rec in self:
            if rec.period_start > rec.period_end:
                raise ValidationError(
                    _("تاريخ بداية الفترة يجب أن يكون قبل نهايتها.")
                )

    # ─────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────
    def action_compute(self):
        for rec in self:
            (
                output_vat,
                input_vat,
                sales_total,
                purchases_total,
            ) = rec._compute_totals()
            rec.write({
                "output_vat": round(output_vat, 2),
                "input_vat": round(input_vat, 2),
                "net_vat": round(output_vat - input_vat, 2),
                "sales_total": round(sales_total, 2),
                "purchases_total": round(purchases_total, 2),
                "summary_html": rec._render_summary(
                    output_vat, input_vat, sales_total, purchases_total
                ),
                "xml_payload": rec._render_xml(
                    output_vat, input_vat, sales_total, purchases_total
                ),
                "state": "computed",
            })
        return self._reopen()

    def action_export(self):
        self.ensure_one()
        if self.state != "computed":
            raise UserError(_("يجب حساب التقرير قبل التصدير."))
        self.state = "exported"
        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/nexus.saudi.vat.report/%d/xml_payload/zatca_vat.xml?download=true"
                % self.id
            ),
            "target": "self",
        }

    # ─────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────
    def _compute_totals(self):
        """Return (output_vat, input_vat, sales_total, purchases_total)."""
        MoveLine = self.env["account.move.line"]
        common = [
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),
            ("date", ">=", self.period_start),
            ("date", "<=", self.period_end),
            ("tax_line_id", "!=", False),
        ]
        # Sales (out_invoice / out_refund)
        sale_lines = MoveLine.search(
            common + [("move_id.move_type", "in", ["out_invoice", "out_refund"])]
        )
        # Purchases (in_invoice / in_refund)
        purchase_lines = MoveLine.search(
            common + [("move_id.move_type", "in", ["in_invoice", "in_refund"])]
        )

        output_vat = sum(abs(l.debit - l.credit) for l in sale_lines)
        input_vat = sum(abs(l.debit - l.credit) for l in purchase_lines)

        sale_invoices = sale_lines.mapped("move_id")
        purchase_invoices = purchase_lines.mapped("move_id")
        sales_total = sum(
            inv.amount_total_signed if inv.move_type == "out_refund"
            else inv.amount_total
            for inv in sale_invoices
        )
        purchases_total = sum(
            inv.amount_total_signed if inv.move_type == "in_refund"
            else inv.amount_total
            for inv in purchase_invoices
        )

        return output_vat, input_vat, sales_total, purchases_total

    def _render_summary(
        self, output_vat, input_vat, sales_total, purchases_total
    ):
        net = output_vat - input_vat
        net_label = (
            _("صافي الضريبة المستحقة الدفع / Net VAT Payable")
            if net > 0
            else _("صافي الضريبة القابلة للاسترداد / VAT Refund Due")
        )
        return (
            "<div class='o_report_heading text-center'><h3>"
            + _("تقرير ضريبة القيمة المضافة / VAT Report")
            + "</h3></div>"
            "<table class='table table-sm'>"
            "<tr><th>" + _("إجمالي المبيعات / Total Sales (incl. VAT)")
            + "</th><td class='text-end'>%0.2f</td></tr>"
            "<tr><th>" + _("إجمالي المشتريات / Total Purchases (incl. VAT)")
            + "</th><td class='text-end'>%0.2f</td></tr>"
            "<tr><th>" + _("ضريبة المخرجات / Output VAT")
            + "</th><td class='text-end'>%0.2f</td></tr>"
            "<tr><th>" + _("ضريبة المدخلات / Input VAT")
            + "</th><td class='text-end'>%0.2f</td></tr>"
            "<tr class='table-primary'><th>%s</th>"
            "<th class='text-end'>%0.2f</th></tr>"
            "</table>"
        ) % (sales_total, purchases_total, output_vat, input_vat, net_label, abs(net))

    def _render_xml(
        self, output_vat, input_vat, sales_total, purchases_total
    ):
        """Build the ZATCA VAT return XML."""
        from lxml import etree

        root = etree.Element(
            "VATReturn",
            nsmap={"zatca": "urn:zatca:vat:return:v0.9"},
        )
        etree.SubElement(root, "VATNumber").text = self.company_id.vat or ""
        etree.SubElement(root, "PeriodStart").text = str(self.period_start)
        etree.SubElement(root, "PeriodEnd").text = str(self.period_end)
        etree.SubElement(root, "SalesTotal").text = "%0.2f" % sales_total
        etree.SubElement(root, "PurchasesTotal").text = "%0.2f" % purchases_total
        etree.SubElement(root, "OutputVAT").text = "%0.2f" % output_vat
        etree.SubElement(root, "InputVAT").text = "%0.2f" % input_vat
        etree.SubElement(root, "NetVAT").text = "%0.2f" % (output_vat - input_vat)
        etree.SubElement(root, "Currency").text = self.company_id.currency_id.name
        return etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        ).decode("utf-8")

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }
