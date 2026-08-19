# -*- coding: utf-8 -*-
from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_open_universal_mail_wizard(self):
        """Open the Universal Email Quick Setup Wizard."""
        return {
            'name': 'Universal Email Quick Setup / إعداد البريد الشامل',
            'type': 'ir.actions.act_window',
            'res_model': 'nexus.mail.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
