"""Queue of physical database provisioning jobs for 'dedicated_db' tenants.

Architecture (control-plane / data-plane split):

* This Odoo database (wherever this module is installed) is the
  **control plane** — it owns tenant/plan/subscription/billing records
  regardless of isolation mode.
* A 'shared' tenant's actual business data (companies, invoices, POS...)
  lives right here, alongside the control-plane records (current /
  existing behaviour, unchanged — this is what Ocean Seven uses).
* A 'dedicated_db' tenant's business data lives in a **separate,
  completely independent Odoo database**, physically isolated at the
  Postgres level. This queue is how the control plane asks an external,
  privileged provisioner process (``saas-db-provisioner/``, outside
  this Odoo process — creating databases requires OS/Postgres-admin
  privileges Odoo application code should never hold) to create or drop
  that database, and how that provisioner reports back.

Nothing in this file touches Postgres directly. See
``saas-db-provisioner/`` for the privileged worker, and
``controllers/db_provisioner_gateway.py`` for the HTTP contract between
the two.
"""
import logging
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaaSDbProvisionRequest(models.Model):
    _name = "nexus.saas.db.provision.request"
    _description = "SaaS Dedicated Database Provisioning Request"
    _order = "id desc"

    tenant_id = fields.Many2one(
        "nexus.saas.tenant", string="Tenant", required=True, ondelete="cascade", index=True
    )
    request_type = fields.Selection(
        [("create", "Create Database"), ("drop", "Drop Database")],
        required=True,
        default="create",
    )
    target_db_name = fields.Char(string="Target Database Name", required=True, index=True)
    modules = fields.Char(
        string="Modules to Install",
        help="Comma-separated technical module names installed on the new DB.",
    )
    admin_name = fields.Char(string="Admin Name")
    admin_email = fields.Char(string="Admin Email")
    admin_password = fields.Char(
        string="Initial Admin Password",
        groups="base.group_system",
        help="One-time secret consumed by the provisioner to set the "
        "admin login on the newly created database. Cleared once done.",
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    error_message = fields.Text(string="Error Message")
    log = fields.Text(string="Provisioner Log")
    requested_at = fields.Datetime(default=fields.Datetime.now, required=True)
    started_at = fields.Datetime()
    completed_at = fields.Datetime()

    _sql_constraints = [
        (
            "target_db_pending_uniq",
            "unique(target_db_name, request_type, state)",
            "A request of this type is already pending/in-progress for this database.",
        ),
    ]

    @api.model
    def _generate_password(self):
        return secrets.token_urlsafe(24)

    def action_retry(self):
        for req in self:
            if req.state != "error":
                raise UserError(_("Only failed requests can be retried."))
            req.write({"state": "pending", "error_message": False})
