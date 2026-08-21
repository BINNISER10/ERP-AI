# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

PROVIDERS = [
    ('google', 'Google (Gmail / Google Workspace)'),
    ('microsoft', 'Microsoft (Outlook / Hotmail / Office 365)'),
    ('apple', 'Apple iCloud (@icloud.com / @me.com)'),
    ('yahoo', 'Yahoo Mail (@yahoo.com)'),
    ('zoho', 'Zoho Mail'),
    ('custom', 'Custom Company Email (Ø¨Ø±ÙŠØ¯ Ø®Ø§Øµ Ù„Ù„Ø´Ø±ÙƒØ© / cPanel / Webmail)'),
]

PROVIDER_CONFIGS = {
    'google': {
        'url': 'https://myaccount.google.com/apppasswords',
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': 587,
        'smtp_encryption': 'starttls',
        'imap_host': 'imap.gmail.com',
        'imap_port': 993,
        'imap_ssl': True,
        'name_ar': 'Google Gmail / Workspace',
        'guide_ar': 'Ø§ÙØªØ­ Ø­Ø³Ø§Ø¨ Google â¬…ï¸ Ø§Ù„Ø£Ù…Ø§Ù† â¬…ï¸ Ø§Ù„ØªØ­Ù‚Ù‚ Ø¨Ø®Ø·ÙˆØªÙŠÙ† â¬…ï¸ ÙƒÙ„Ù…Ø§Øª Ù…Ø±ÙˆØ± Ø§Ù„ØªØ·Ø¨ÙŠÙ‚Ø§Øª (App Passwords) ÙˆØ£Ù†Ø´Ø¦ Ø±Ù…Ø²Ø§Ù‹ Ù…Ù† 16 Ø­Ø±ÙØ§Ù‹.',
    },
    'microsoft': {
        'url': 'https://account.live.com/proofs/AppPassword',
        'smtp_host': 'smtp.office365.com',
        'smtp_port': 587,
        'smtp_encryption': 'starttls',
        'imap_host': 'outlook.office365.com',
        'imap_port': 993,
        'imap_ssl': True,
        'name_ar': 'Microsoft Outlook / Hotmail / Office 365',
        'guide_ar': 'Ø§ÙØªØ­ Ø­Ø³Ø§Ø¨ Microsoft â¬…ï¸ Ø§Ù„Ø£Ù…Ø§Ù† Ø§Ù„Ù…ØªÙ‚Ø¯Ù… â¬…ï¸ ÙƒÙ„Ù…Ø§Øª Ù…Ø±ÙˆØ± Ø§Ù„ØªØ·Ø¨ÙŠÙ‚Ø§Øª (App Passwords) ÙˆØ£Ù†Ø´Ø¦ ÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ± Ø¬Ø¯ÙŠØ¯Ø©.',
    },
    'apple': {
        'url': 'https://appleid.apple.com/account/manage/section/security',
        'smtp_host': 'smtp.mail.me.com',
        'smtp_port': 587,
        'smtp_encryption': 'starttls',
        'imap_host': 'imap.mail.me.com',
        'imap_port': 993,
        'imap_ssl': True,
        'name_ar': 'Apple iCloud',
        'guide_ar': 'Ø§ÙØªØ­ Apple ID â¬…ï¸ ØªØ³Ø¬ÙŠÙ„ Ø§Ù„Ø¯Ø®ÙˆÙ„ ÙˆØ§Ù„Ø£Ù…Ø§Ù† â¬…ï¸ ÙƒÙ„Ù…Ø§Øª Ø§Ù„Ù…Ø±ÙˆØ± Ø§Ù„Ø®Ø§ØµØ© Ø¨Ø§Ù„ØªØ·Ø¨ÙŠÙ‚Ø§Øª (App-Specific Passwords).',
    },
    'yahoo': {
        'url': 'https://login.yahoo.com/account/security',
        'smtp_host': 'smtp.mail.yahoo.com',
        'smtp_port': 587,
        'smtp_encryption': 'starttls',
        'imap_host': 'imap.mail.yahoo.com',
        'imap_port': 993,
        'imap_ssl': True,
        'name_ar': 'Yahoo Mail',
        'guide_ar': 'Ø§ÙØªØ­ Ø£Ù…Ø§Ù† Ø­Ø³Ø§Ø¨ Yahoo â¬…ï¸ Ø¥Ù†Ø´Ø§Ø¡ ÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ± Ø§Ù„ØªØ·Ø¨ÙŠÙ‚ (Generate app password).',
    },
    'zoho': {
        'url': 'https://accounts.zoho.com/home#security/app_passwords',
        'smtp_host': 'smtppro.zoho.com',
        'smtp_port': 587,
        'smtp_encryption': 'starttls',
        'imap_host': 'imappro.zoho.com',
        'imap_port': 993,
        'imap_ssl': True,
        'name_ar': 'Zoho Mail',
        'guide_ar': 'Ø§ÙØªØ­ Ø­Ø³Ø§Ø¨ Zoho â¬…ï¸ Ø§Ù„Ø£Ù…Ø§Ù† â¬…ï¸ ÙƒÙ„Ù…Ø§Øª Ù…Ø±ÙˆØ± Ø®Ø§ØµØ© Ø¨Ø§Ù„ØªØ·Ø¨ÙŠÙ‚Ø§Øª (Application-Specific Passwords).',
    },
    'custom': {
        'url': '',
        'smtp_host': '',
        'smtp_port': 587,
        'smtp_encryption': 'starttls',
        'imap_host': '',
        'imap_port': 993,
        'imap_ssl': True,
        'name_ar': 'Ø¨Ø±ÙŠØ¯ Ø®Ø§Øµ Ø¨Ø§Ù„Ø´Ø±ÙƒØ©',
        'guide_ar': 'Ø£Ø¯Ø®Ù„ Ø¹Ù†ÙˆØ§Ù† Ø¨Ø±ÙŠØ¯Ùƒ Ø§Ù„Ù…Ø¤Ø³Ø³ÙŠ ÙˆÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ±ØŒ ÙˆØ³ÙŠÙ‚ÙˆÙ… Ø§Ù„Ù†Ø¸Ø§Ù… Ø¨Ø¶Ø¨Ø· Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹ Ø£Ùˆ ÙŠÙ…ÙƒÙ†Ùƒ ØªØ®ØµÙŠØµÙ‡Ø§.',
    },
}


class NexusUniversalMailWizard(models.TransientModel):
    _name = 'nexus.mail.wizard'
    _description = 'Universal Email Quick Setup Wizard'

    provider = fields.Selection(
        selection=PROVIDERS,
        string='Email Provider / Ù…Ø²ÙˆØ¯ Ø§Ù„Ø¨Ø±ÙŠØ¯',
        default='google',
        required=True,
    )
    email_address = fields.Char(
        string='Email Address / Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠ',
        required=True,
        placeholder='e.g. user@gmail.com, info@company.com',
    )
    app_password = fields.Char(
        string='App Password / ÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ± Ø§Ù„ØªØ·Ø¨ÙŠÙ‚',
        required=True,
    )
    app_password_url = fields.Char(
        string='App Password Link',
        compute='_compute_provider_details',
    )
    guide_html = fields.Html(
        string='Setup Guide',
        compute='_compute_provider_details',
    )

    # Technical overrides (shown if custom or expandable)
    smtp_host = fields.Char(string='SMTP Server (Host)', compute='_compute_provider_details', store=True, readonly=False)
    smtp_port = fields.Integer(string='SMTP Port', default=587)
    smtp_encryption = fields.Selection(
        selection=[
            ('none', 'None'),
            ('starttls', 'TLS (STARTTLS)'),
            ('ssl', 'SSL/TLS'),
        ],
        string='SMTP Security',
        default='starttls',
    )
    
    imap_host = fields.Char(string='IMAP Server (Host)', compute='_compute_provider_details', store=True, readonly=False)
    imap_port = fields.Integer(string='IMAP Port', default=993)
    imap_ssl = fields.Boolean(string='IMAP SSL/TLS', default=True)

    setup_outgoing = fields.Boolean(
        string='Setup Outgoing Mail (Ø¥Ø±Ø³Ø§Ù„ Ø§Ù„ÙÙˆØ§ØªÙŠØ± ÙˆØ§Ù„Ø¥Ø´Ø¹Ø§Ø±Ø§Øª - SMTP)',
        default=True,
    )
    setup_incoming = fields.Boolean(
        string='Setup Incoming Mail (Ø§Ø³ØªÙ‚Ø¨Ø§Ù„ Ø§Ù„Ø±Ø¯ÙˆØ¯ ÙˆØ§Ù„ØªØ°Ø§ÙƒØ± - IMAP)',
        default=True,
    )
    send_test_email = fields.Boolean(
        string='Send Verification Test Email (Ø¥Ø±Ø³Ø§Ù„ Ø¨Ø±ÙŠØ¯ ØªØ¬Ø±ÙŠØ¨ÙŠ Ù„Ù„ØªØ£ÙƒÙŠØ¯)',
        default=True,
    )
    test_recipient = fields.Char(
        string='Test Email Recipient',
        help='Recipient for verification test email. Defaults to the configured email.',
    )

    @api.depends('provider', 'email_address')
    def _compute_provider_details(self):
        for record in self:
            cfg = PROVIDER_CONFIGS.get(record.provider, PROVIDER_CONFIGS['custom'])
            record.app_password_url = cfg['url']
            
            # If custom and domain entered, try deriving hosts
            if record.provider == 'custom':
                domain = ''
                if record.email_address and '@' in record.email_address:
                    domain = record.email_address.split('@')[-1].strip()
                record.smtp_host = f"mail.{domain}" if domain else (record.smtp_host or '')
                record.imap_host = f"mail.{domain}" if domain else (record.imap_host or '')
            else:
                record.smtp_host = cfg['smtp_host']
                record.imap_host = cfg['imap_host']
                record.smtp_port = cfg['smtp_port']
                record.smtp_encryption = cfg['smtp_encryption']
                record.imap_port = cfg['imap_port']
                record.imap_ssl = cfg['imap_ssl']

            # Build rich HTML Guide
            if cfg['url']:
                record.guide_html = f"""
                <div class="alert alert-info py-2 px-3 my-1" style="border-radius: 8px;">
                    <strong>Ø§Ù„Ø®Ø·ÙˆØ© 1:</strong> Ø§Ø¶ØºØ· Ø¹Ù„Ù‰ Ø²Ø± 
                    <a href="{cfg['url']}" target="_blank" class="btn btn-sm btn-primary ms-2 me-2" style="font-weight: bold;">
                        ðŸ”— ÙØªØ­ ØµÙØ­Ø© Ø§Ø³ØªØ®Ø±Ø§Ø¬ ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ± ({cfg['name_ar']})
                    </a>
                    <br/>
                    <small class="text-muted">{cfg['guide_ar']}</small>
                </div>
                """
            else:
                record.guide_html = f"""
                <div class="alert alert-secondary py-2 px-3 my-1" style="border-radius: 8px;">
                    <strong>Ø¥Ø¹Ø¯Ø§Ø¯ Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„Ù…Ø®ØµØµ:</strong> {cfg['guide_ar']}
                </div>
                """

    def action_open_app_password_url(self):
        self.ensure_one()
        url = self.app_password_url
        if not url:
            cfg = PROVIDER_CONFIGS.get(self.provider, {})
            url = cfg.get('url')
        if not url:
            raise UserError(_('No direct App Password link available for custom provider. Please check your webmail/cPanel settings.'))
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_test_and_apply(self):
        self.ensure_one()
        email = (self.email_address or '').strip()
        raw_pass = (self.app_password or '').strip()
        # Remove spaces in app passwords (e.g. Google's "abcd efgh ijkl mnop" -> "abcdefghijklmnop")
        password = raw_pass.replace(' ', '').replace('\t', '')

        if not email or '@' not in email:
            raise UserError(_('ÙŠØ±Ø¬Ù‰ Ø¥Ø¯Ø®Ø§Ù„ Ø¹Ù†ÙˆØ§Ù† Ø¨Ø±ÙŠØ¯ Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠ ØµØ­ÙŠØ­.'))
        if not password:
            raise UserError(_('ÙŠØ±Ø¬Ù‰ Ø¥Ø¯Ø®Ø§Ù„ ÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ± Ø§Ù„ØªØ·Ø¨ÙŠÙ‚ (App Password).'))

        smtp_server_obj = self.env['ir.mail_server']
        fetchmail_server_obj = self.env['fetchmail.server']

        mail_server = False
        fetchmail_server = False
        results = []

        # 1. Outgoing SMTP
        if self.setup_outgoing:
            existing = smtp_server_obj.search([('smtp_user', '=', email)], limit=1)
            vals = {
                'name': f"{self.provider.capitalize()} - {email}",
                'smtp_host': self.smtp_host,
                'smtp_port': self.smtp_port,
                'smtp_encryption': self.smtp_encryption,
                'smtp_user': email,
                'smtp_pass': password,
                'smtp_authentication': 'login',
                'sequence': 10,
                'active': True,
            }
            if existing:
                existing.write(vals)
                mail_server = existing
            else:
                mail_server = smtp_server_obj.create(vals)

            # Test Outgoing
            try:
                mail_server.test_smtp_connection()
                results.append('âœ… Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„ØµØ§Ø¯Ø± (SMTP): ØªÙ… Ø§Ù„Ø§ØªØµØ§Ù„ ÙˆØ§Ù„ØªØ­Ù‚Ù‚ Ø¨Ù†Ø¬Ø§Ø­.')
            except Exception as e:
                raise UserError(_('ÙØ´Ù„ Ø§Ø®ØªØ¨Ø§Ø± Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„ØµØ§Ø¯Ø± (SMTP):\n%s') % str(e))

            # Set default from parameter
            self.env['ir.config_parameter'].sudo().set_param('mail.default.from', email)

        # 2. Incoming IMAP
        if self.setup_incoming:
            existing_imap = fetchmail_server_obj.search([('user', '=', email)], limit=1)
            imap_vals = {
                'name': f"{self.provider.capitalize()} Incoming - {email}",
                'server_type': 'imap',
                'server': self.imap_host,
                'port': self.imap_port,
                'is_ssl': self.imap_ssl,
                'user': email,
                'password': password,
                'active': True,
            }
            if existing_imap:
                existing_imap.write(imap_vals)
                fetchmail_server = existing_imap
            else:
                fetchmail_server = fetchmail_server_obj.create(imap_vals)

            # Test Incoming
            try:
                fetchmail_server.button_confirm_login()
                results.append('âœ… Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„ÙˆØ§Ø±Ø¯ (IMAP): ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ ÙˆØ§Ù„Ø±Ø¨Ø· Ø¨Ù†Ø¬Ø§Ø­.')
            except Exception as e:
                # We report as warning or message without breaking outgoing if outgoing worked
                results.append(f'âš ï¸ ØªÙ†Ø¨ÙŠÙ‡ ÙÙŠ Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„ÙˆØ§Ø±Ø¯: {str(e)}')

        # 3. Optional verification email
        if self.send_test_email and mail_server:
            recipient = (self.test_recipient or email).strip()
            try:
                test_mail = self.env['mail.mail'].create({
                    'subject': _('ØªØ£ÙƒÙŠØ¯ Ø±Ø¨Ø· Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø¨Ù†Ø¬Ø§Ø­ - Nexus Enterprise Engine'),
                    'body_html': f"""
                        <div style="font-family: Arial, sans-serif; padding: 20px; color: #2C3E50;">
                            <h2 style="color: #0B3D2E;">ØªÙ‡Ø§Ù†ÙŠÙ†Ø§! ØªÙ… Ø±Ø¨Ø· Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠ Ø¨Ù†Ø¬Ø§Ø­</h2>
                            <p>ØªÙ… Ø¥Ø¹Ø¯Ø§Ø¯ Ø¨Ø±ÙŠØ¯Ùƒ <b>{email}</b> Ø¨Ù†Ø¬Ø§Ø­ Ù„Ù„Ø¹Ù…Ù„ Ù…Ø¹ Ù†Ø¸Ø§Ù… <b>Nexus Enterprise Engine</b>.</p>
                            <p>Ø§Ù„Ù…Ø²ÙˆØ¯: <b>{dict(PROVIDERS).get(self.provider)}</b></p>
                            <hr style="border: 0; border-top: 1px solid #E2E8F0;"/>
                            <small style="color: #718096;">Nexus Enterprise Engine Automated Mailer</small>
                        </div>
                    """,
                    'email_to': recipient,
                    'email_from': email,
                    'mail_server_id': mail_server.id,
                    'auto_delete': False,
                })
                test_mail.send()
                results.append(f'ðŸ“© ØªÙ… Ø¥Ø±Ø³Ø§Ù„ Ø±Ø³Ø§Ù„Ø© Ø¨Ø±ÙŠØ¯ ØªØ¬Ø±ÙŠØ¨ÙŠØ© Ù„Ù„ØªØ£ÙƒÙŠØ¯ Ø¥Ù„Ù‰: {recipient}')
            except Exception as e:
                results.append(f'âš ï¸ Ù„Ù… ÙŠØªÙ… Ø¥Ø±Ø³Ø§Ù„ Ø§Ù„Ø¥ÙŠÙ…ÙŠÙ„ Ø§Ù„ØªØ¬Ø±ÙŠØ¨ÙŠ: {str(e)}')

        summary = '\n'.join(results)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ù†Ø¬Ø­ Ø±Ø¨Ø· Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠ!'),
                'message': summary,
                'type': 'success',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
