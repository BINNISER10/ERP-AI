# -*- coding: utf-8 -*-
"""Nexus Smart Manufacturing (BOM) Advisor — مستشار التصنيع الذكي.

Extends Odoo's native ``mrp.bom`` (no custom BOM model is reinvented here)
with an AI-assisted advisor: given the product being manufactured and its
installation destination (e.g. hospital, warehouse), it suggests the raw
material / hardware components that make up the product, and flags any
destination-driven compliance requirements (e.g. a wood door destined for
a hospital should be fire-rated).

Suggested components are added as regular, editable ``mrp.bom.line``
records — nothing is force-applied. The user reviews/adjusts them like any
other BOM line before confirming.
"""
import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DESTINATION_TYPES = [
    ("hospital", "مستشفى / منشأة صحية (Hospital / Healthcare)"),
    ("warehouse", "مستودع / منشأة صناعية (Warehouse / Industrial)"),
    ("residential", "سكني (Residential)"),
    ("retail", "تجاري / بيع بالتجزئة (Retail / Commercial)"),
    ("educational", "تعليمي (Educational)"),
    ("other", "أخرى (Other)"),
]


class MrpBomAiAdvisor(models.Model):
    _inherit = "mrp.bom"

    ai_destination_type = fields.Selection(
        selection=DESTINATION_TYPES,
        string="وجهة التركيب (لاقتراح ذكي)",
        help="Where this product will be installed/used. Used by the AI "
        "advisor to suggest destination-specific compliance requirements.",
    )
    ai_compliance_html = fields.Html(
        string="متطلبات الامتثال المقترحة (AI)",
        readonly=True,
    )
    ai_manufacturing_notes_html = fields.Html(
        string="ملاحظات تصنيع ذكية (AI)",
        readonly=True,
    )

    def _nexus_ai_headers(self):
        """Build the X-API-Key header expected by the nexus_ai microservice."""
        config = self.env["copilot.config"].sudo().get_active_config(self.env.company)
        api_key = config.nexus_ai_api_key if config else False
        return {"X-API-Key": api_key} if api_key else {}

    def action_ai_suggest_bom(self):
        """Call the Nexus AI BOM Advisor and merge its suggestions into
        this BOM as new, editable lines + a compliance/notes summary.
        """
        self.ensure_one()
        if not self.product_tmpl_id:
            raise UserError(_("يرجى تحديد المنتج المُصنَّع أولاً."))

        destination_label = None
        if self.ai_destination_type:
            destination_label = dict(DESTINATION_TYPES).get(self.ai_destination_type)

        payload = {
            "product_name": self.product_tmpl_id.name,
            "product_category": self.product_tmpl_id.categ_id.name or None,
            "description": self.product_tmpl_id.description or None,
            "destination_type": destination_label,
            "country": self.env.company.country_id.code or "SA",
            "language": "ar",
        }

        data = None
        try:
            resp = requests.post(
                "http://nexus_ai:8000/api/v1/ai/wizard/bom-advisor",
                json=payload,
                headers=self._nexus_ai_headers(),
                timeout=45,
            )
            if resp.ok:
                data = resp.json()
            else:
                _logger.warning(
                    "Nexus AI bom-advisor returned HTTP %s: %s",
                    resp.status_code,
                    resp.text[:300],
                )
        except Exception as e:
            _logger.info("Nexus AI bom-advisor unreachable: %s", e)

        if not data:
            raise UserError(
                _(
                    "تعذر الاتصال بخدمة الذكاء الاصطناعي حالياً. "
                    "يرجى المحاولة لاحقاً أو إضافة المكونات يدوياً."
                )
            )

        self._apply_ai_component_suggestions(data.get("components", []))
        self._render_ai_compliance(data.get("compliance_suggestions", []))
        self._render_ai_manufacturing_notes(data.get("manufacturing_notes_ar", []))
        return True

    def _apply_ai_component_suggestions(self, components):
        Product = self.env["product.product"]
        Uom = self.env["uom.uom"]
        BomLine = self.env["mrp.bom.line"]
        existing_names = {
            (line.product_id.name or "").strip().lower() for line in self.bom_line_ids
        }

        for comp in components:
            name = (comp.get("name") or "").strip()
            if not name or name.lower() in existing_names:
                continue

            product = Product.search([("name", "=", name)], limit=1)
            if not product:
                prod_vals = {
                    "name": name,
                    "type": "consu",
                    "purchase_ok": True,
                    "sale_ok": False,
                }
                if "is_storable" in Product._fields:
                    prod_vals["is_storable"] = True
                product = Product.create(prod_vals)

            uom_name = (comp.get("uom") or "").strip()
            uom = Uom.search([("name", "=", uom_name)], limit=1) if uom_name else False
            uom = uom or product.uom_id

            BomLine.create(
                {
                    "bom_id": self.id,
                    "product_id": product.id,
                    "product_qty": comp.get("quantity") or 1.0,
                    "product_uom_id": uom.id,
                }
            )
            existing_names.add(name.lower())

    def _render_ai_compliance(self, compliance_suggestions):
        if not compliance_suggestions:
            self.ai_compliance_html = (
                "<p class='text-muted'>لا توجد متطلبات امتثال خاصة مقترحة لهذه الوجهة.</p>"
            )
            return

        items = []
        for c in compliance_suggestions:
            required = c.get("severity") == "required"
            badge_class = "badge bg-danger" if required else "badge bg-warning text-dark"
            badge_text = "إلزامي" if required else "موصى به"
            items.append(
                "<li class='mb-2'>"
                f"<span class='{badge_class} me-2'>{badge_text}</span>"
                f"<strong>{c.get('requirement_ar', '')}</strong><br/>"
                f"<small class='text-muted'>{c.get('reason_ar', '')}</small>"
                "</li>"
            )
        self.ai_compliance_html = f"<ul class='list-unstyled'>{''.join(items)}</ul>"

    def _render_ai_manufacturing_notes(self, notes):
        if not notes:
            self.ai_manufacturing_notes_html = ""
            return
        items = "".join(f"<li>{n}</li>" for n in notes)
        self.ai_manufacturing_notes_html = f"<ul>{items}</ul>"
