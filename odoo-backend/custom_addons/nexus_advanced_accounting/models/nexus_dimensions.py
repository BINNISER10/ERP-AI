"""Pillar 1 — Dimensions & Cost Center Engine.

When a Branch (stock.warehouse), Department (hr.department), or Project
(project.project) is created in the Nexus Command Center, a Cost Center
is queued for synchronous creation in the Nexus Core.  All invoice
payloads then tag their lines with the correct cost center for deep
P&L reporting.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    nexus_cost_center_synced = fields.Boolean(
        string="Nexus Core Cost Center Synced",
        default=False,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        for wh in warehouses:
            wh._enqueue_cost_center()
        return warehouses

    def write(self, vals):
        res = super().write(vals)
        if "name" in vals or "active" in vals:
            for wh in self:
                wh._enqueue_cost_center()
        return res

    def _enqueue_cost_center(self):
        """Queue a Cost Center creation call for this branch in the Nexus Core."""
        if self.nexus_cost_center_synced:
            return
        tx_id = f"NX-CC-WH-{self.id}"
        self.env["nexus.sync.queue"].enqueue(
            operation="cost_center.create",
            payload={},
            endpoint="/api/resource/Cost Center",
            company=self.company_id,
            model_name=self._name,
            res_id=self.id,
            transaction_id=tx_id,
            priority=20,
        )
        _logger.info(
            "Nexus Core: queued Cost Center for Branch '%s' [%s]",
            self.name,
            tx_id[:12],
        )


class HrDepartment(models.Model):
    _inherit = "hr.department"

    nexus_cost_center_synced = fields.Boolean(
        string="Nexus Core Cost Center Synced",
        default=False,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        depts = super().create(vals_list)
        for dept in depts:
            dept._enqueue_cost_center()
        return depts

    def write(self, vals):
        res = super().write(vals)
        if "name" in vals or "active" in vals:
            for dept in self:
                dept._enqueue_cost_center()
        return res

    def _enqueue_cost_center(self):
        if self.nexus_cost_center_synced:
            return
        tx_id = f"NX-CC-DEPT-{self.id}"
        self.env["nexus.sync.queue"].enqueue(
            operation="cost_center.create",
            payload={},
            endpoint="/api/resource/Cost Center",
            company=self.company_id,
            model_name=self._name,
            res_id=self.id,
            transaction_id=tx_id,
            priority=20,
        )
        _logger.info(
            "Nexus Core: queued Cost Center for Department '%s' [%s]",
            self.name,
            tx_id[:12],
        )


class ProjectProject(models.Model):
    _inherit = "project.project"

    nexus_cost_center_synced = fields.Boolean(
        string="Nexus Core Cost Center Synced",
        default=False,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        for proj in projects:
            proj._enqueue_cost_center()
        return projects

    def write(self, vals):
        res = super().write(vals)
        if "name" in vals or "active" in vals:
            for proj in self:
                proj._enqueue_cost_center()
        return res

    def _enqueue_cost_center(self):
        if self.nexus_cost_center_synced:
            return
        tx_id = f"NX-CC-PROJ-{self.id}"
        self.env["nexus.sync.queue"].enqueue(
            operation="cost_center.create",
            payload={},
            endpoint="/api/resource/Cost Center",
            company=self.company_id,
            model_name=self._name,
            res_id=self.id,
            transaction_id=tx_id,
            priority=20,
        )
        _logger.info(
            "Nexus Core: queued Cost Center for Project '%s' [%s]",
            self.name,
            tx_id[:12],
        )


class NexusCostCenterMapping(models.Model):
    """Stores the mapping between Nexus Command Center dimensions and
    Nexus Core Cost Center records."""

    _name = "nexus.cost.center.mapping"
    _description = "Nexus Core Cost Center Mapping"
    _rec_name = "nexus_cost_center_name"
    _order = "model_name, res_id"

    model_name = fields.Char(
        string="Source Model",
        required=True,
        index=True,
    )
    res_id = fields.Integer(
        string="Source Record ID",
        required=True,
        index=True,
    )
    nexus_cost_center_name = fields.Char(
        string="Nexus Core Cost Center Name",
        required=True,
    )
    nexus_cost_center_id = fields.Char(
        string="Nexus Core Doc Name",
        help="The 'name' returned by the Nexus Core API on creation.",
    )
    synced = fields.Boolean(
        string="Synced to Nexus Core",
        default=False,
    )
    transaction_id = fields.Char(
        string="Nexus Transaction ID",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            "model_res_uniq",
            "unique(model_name, res_id)",
            "Nexus Core: duplicate cost center mapping.",
        ),
    ]

    def _mark_synced(self, model_name, res_id, docname):
        """Record that a specific Odoo record's cost center is now in Nexus Core."""
        mapping = self.sudo().search(
            [("model_name", "=", model_name), ("res_id", "=", res_id)], limit=1
        )
        if mapping:
            mapping.write(
                {
                    "synced": True,
                    "nexus_cost_center_id": docname,
                }
            )
        else:
            self.sudo().create(
                {
                    "model_name": model_name,
                    "res_id": res_id,
                    "nexus_cost_center_name": (
                        self.env[model_name]
                        .browse(res_id)
                        .sudo()
                        .display_name
                    ),
                    "nexus_cost_center_id": docname,
                    "synced": True,
                    "company_id": (
                        self.env[model_name]
                        .browse(res_id)
                        .sudo()
                        .company_id.id
                    ),
                }
            )

        # Mark the source record as synced
        source = self.env[model_name].browse(res_id).sudo()
        if source.exists() and hasattr(source, "nexus_cost_center_synced"):
            source.write({"nexus_cost_center_synced": True})


# ── Expense Claim sync (guarded — hr_expense module may not be installed) ──

class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    nexus_cost_center = fields.Char(
        string="Nexus Core Cost Center",
        copy=False,
    )

    def approve_expense_sheets(self):
        """After approval, queue the Expense Claim in the Nexus Core."""
        res = super().approve_expense_sheets()
        for sheet in self:
            if sheet.state == "approve":
                # Resolve cost center from employee department or company
                if not sheet.nexus_cost_center:
                    sheet.nexus_cost_center = (
                        sheet.employee_id.department_id.name
                        if sheet.employee_id and sheet.employee_id.department_id
                        else sheet.company_id.name
                    )
                sheet._enqueue_expense_claim()
        return res

    def _enqueue_expense_claim(self):
        """Queue an Expense Claim in the Nexus Core."""
        self.ensure_one()
        tx_id = f"NX-EXP-{self.id}"
        self.env["nexus.sync.queue"].enqueue(
            operation="expense_claim.create",
            payload={},
            endpoint="/api/resource/Expense Claim",
            company=self.company_id,
            model_name="hr.expense.sheet",
            res_id=self.id,
            transaction_id=tx_id,
            priority=18,
        )
        _logger.info(
            "Nexus Core: queued Expense Claim '%s' [%s]",
            self.name,
            tx_id[:12],
        )
