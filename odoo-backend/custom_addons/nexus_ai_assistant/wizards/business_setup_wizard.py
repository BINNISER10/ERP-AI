import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AiBusinessSetupWizard(models.TransientModel):
    _name = "nexus.ai.business.setup.wizard"
    _description = "AI Business Setup Wizard"

    business_type = fields.Selection(
        [
            ("retail", "Retail"),
            ("factory", "Factory / Manufacturing"),
            ("restaurant", "Restaurant"),
            ("real_estate", "Real Estate"),
            ("fuel_station", "Fuel Station"),
            ("services", "Services"),
            ("other", "Other"),
        ],
        default="retail",
        required=True,
    )
    industry = fields.Char(default="general", required=True)
    size = fields.Selection(
        [
            ("micro", "Micro"),
            ("small", "Small"),
            ("medium", "Medium"),
            ("large", "Large"),
        ],
        default="small",
        required=True,
    )
    country_code = fields.Char(default="SA", required=True)
    language = fields.Char(default="ar", required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)

    state = fields.Selection(
        [("input", "Input"), ("result", "Result")],
        default="input",
    )
    result_json = fields.Text(readonly=True)
    summary_ar = fields.Text(readonly=True)
    summary_en = fields.Text(readonly=True)
    modules_text = fields.Text(compute="_compute_result_texts", readonly=True)
    product_categories_text = fields.Text(compute="_compute_result_texts", readonly=True)
    warehouses_text = fields.Text(compute="_compute_result_texts", readonly=True)
    steps_text = fields.Text(compute="_compute_result_texts", readonly=True)

    @api.depends("result_json")
    def _compute_result_texts(self):
        for rec in self:
            if not rec.result_json:
                rec.modules_text = ""
                rec.product_categories_text = ""
                rec.warehouses_text = ""
                rec.steps_text = ""
                continue
            try:
                data = json.loads(rec.result_json)
            except json.JSONDecodeError:
                rec.modules_text = ""
                rec.product_categories_text = ""
                rec.warehouses_text = ""
                rec.steps_text = ""
                continue
            rec.modules_text = "\n".join(data.get("modules", []))
            rec.product_categories_text = "\n".join(data.get("product_categories", []))
            rec.warehouses_text = "\n".join(data.get("warehouses", []))
            rec.steps_text = "\n".join(f"- {s}" for s in data.get("steps", []))

    def _prepare_payload(self):
        return {
            "business_type": self.business_type,
            "industry": self.industry,
            "size": self.size,
            "country": self.country_code,
            "language": self.language,
        }

    def _stringify_name(self, item):
        """Return a clean string from either a plain name or a {'name': ...} object."""
        if isinstance(item, dict):
            return item.get("name") or item.get("Name") or str(item)
        return str(item)

    def _normalize_result(self, result):
        """Ensure list-of-name fields are plain strings, even if the AI returns objects."""
        for key in ("modules", "warehouses", "product_categories", "steps"):
            if key in result and isinstance(result[key], list):
                result[key] = [self._stringify_name(it) for it in result[key]]

    def action_generate(self):
        self.ensure_one()
        config = self.env["nexus.ai.config"].get_config()
        payload = self._prepare_payload()
        if config.ai_provider and config.ai_provider != "auto":
            # The ai_service itself decides the provider via AI_PROVIDER env,
            # but we can pass it in future versions if the endpoint supports it.
            pass
        result = config._call_ai_service("api/v1/ai/wizard/business-setup", payload)
        self._normalize_result(result)
        self.result_json = json.dumps(result, ensure_ascii=False)
        self.summary_ar = result.get("summary_ar", "")
        self.summary_en = result.get("summary_en", "")
        self.state = "result"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _ensure_unique_warehouse_code(self, base_code):
        """Return a unique warehouse code based on the given base."""
        code = base_code[:5].upper() if base_code else "WH"
        wh_model = self.env.get("stock.warehouse")
        if not wh_model:
            return code
        existing = wh_model.search_count([("code", "=", code), ("company_id", "=", self.company_id.id)])
        if existing:
            counter = 1
            while wh_model.search_count([("code", "=", f"{code}{counter}"), ("company_id", "=", self.company_id.id)]):
                counter += 1
            return f"{code}{counter}"
        return code

    def action_apply(self):
        self.ensure_one()
        if not self.result_json:
            raise UserError(_("Generate the setup plan first."))
        try:
            data = json.loads(self.result_json)
        except json.JSONDecodeError as exc:
            raise UserError(_("The AI result is not valid JSON.")) from exc

        created = []

        # Product categories
        product_category = self.env.get("product.category")
        if product_category:
            for name in data.get("product_categories", []):
                if not product_category.search([("name", "=", name)], limit=1):
                    product_category.create({"name": name})
                    created.append(f"Product category: {name}")

        # Warehouses
        wh_model = self.env.get("stock.warehouse")
        if wh_model:
            for wh_name in data.get("warehouses", []):
                code = self._ensure_unique_warehouse_code(wh_name[:3] if wh_name else "WH")
                wh_model.create({
                    "name": wh_name,
                    "code": code,
                    "company_id": self.company_id.id,
                })
                created.append(f"Warehouse: {wh_name} ({code})")

        if not created:
            raise UserError(_("No records could be created. Make sure Stock and Product modules are installed."))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Setup Applied"),
                "message": _("Created records:") + "\n" + "\n".join(created),
                "type": "success",
                "sticky": False,
            },
        }
