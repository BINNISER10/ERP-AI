"""ERPNext-style Cost Center doctype.

A parent-child tree of cost centers used to allocate expenses and revenue
for Profit & Loss reporting by department/branch/project.
"""

from odoo import api, fields, models, _


class NexusCostCenter(models.Model):
    _name = "nexus.cost.center"
    _description = "Nexus Financial Cost Center"
    _rec_name = "cost_center_name"
    _order = "name"

    cost_center_name = fields.Char(string="Cost Center Name", required=True)
    name = fields.Char(compute="_compute_name", store=True)
    parent_id = fields.Many2one(
        "nexus.cost.center",
        string="Parent Cost Center",
        index=True,
        ondelete="cascade",
    )
    child_ids = fields.One2many("nexus.cost.center", "parent_id")
    is_group = fields.Boolean(string="Is Group", default=False)
    disabled = fields.Boolean(string="Disabled", default=False)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    full_name = fields.Char(
        compute="_compute_full_name",
        store=True,
    )

    _sql_constraints = [
        (
            "name_parent_uniq",
            "unique(cost_center_name, parent_id, company_id)",
            "A cost center with this name already exists under the same parent.",
        ),
    ]

    @api.constrains("is_group", "child_ids")
    def _check_group_leaf(self):
        for record in self:
            if not record.is_group and record.child_ids:
                raise models.ValidationError(
                    _("Cost center '%s' has children, so it must be marked as a Group.")
                    % record.cost_center_name
                )

    @api.depends("cost_center_name")
    def _compute_name(self):
        for record in self:
            record.name = record.cost_center_name

    @api.depends("parent_id", "cost_center_name")
    def _compute_full_name(self):
        for record in self:
            parts = []
            parent = record.parent_id
            while parent:
                parts.append(parent.cost_center_name)
                parent = parent.parent_id
            parts.append(record.cost_center_name)
            record.full_name = " / ".join(parts)
