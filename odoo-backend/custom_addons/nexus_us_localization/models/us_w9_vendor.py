# -*- coding: utf-8 -*-
"""Nexus US W-9 Vendor — استمارة W-9 للموردين.

Tracks W-9 collection status for US vendors. The IRS requires every
US business to obtain a W-9 from each vendor before issuing payments
that may be reported on 1099 forms.

Fields:
    * ``is_1099_vendor`` — flag the vendor for 1099 reporting
    * ``tin`` — Tax Identification Number (EIN or SSN)
    * ``tin_type`` — which type of TIN
    * ``w9_collected`` — whether the W-9 form has been received
    * ``w9_collected_date`` — date the form was received
    * ``backup_withholding`` — whether backup withholding applies
"""

from odoo import fields, models


class NexusUSW9Vendor(models.Model):
    """Adds 1099 / W-9 tracking fields directly on res.partner."""

    _inherit = "res.partner"

    is_1099_vendor = fields.Boolean(
        string="1099 Vendor",
        help="Vendor whose payments may be reported on Form 1099.",
    )
    tin = fields.Char(
        string="TIN / EIN / SSN",
        help="Tax Identification Number — 9 digits.",
    )
    tin_type = fields.Selection(
        [
            ("EIN", "EIN (Employer ID)"),
            ("SSN", "SSN (Social Security)"),
            ("ITIN", "ITIN (Individual Taxpayer ID)"),
        ],
        string="TIN Type",
        default="EIN",
    )
    w9_collected = fields.Boolean(
        string="W-9 Collected",
        help="Has the W-9 form been received from this vendor?",
    )
    w9_collected_date = fields.Date(
        string="W-9 Collection Date",
    )
    backup_withholding = fields.Boolean(
        string="Backup Withholding",
        help="Apply 24% backup withholding on payments.",
    )
    w9_notes = fields.Text(
        string="W-9 Notes",
    )
