# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

PROVIDERS = [
    ('google', 'Google (Gmail / Google Workspace)'),
    ('microsoft', 'Microsoft (Outlook / Hotmail / Office 365)'),
    ('apple', 'Apple iCloud (@icloud.com / @me.com)'),
    ('yahoo', 'Yahoo Mail (@yahoo.com)'),
    ('zoho', 'Zoho Mail'),
    ('custom', 'Custom Company Email (بريد خاص للشركة / cPanel / Webmail)'),
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
        'guide_ar': 'افتح حساب Google ⬅️ الأمان ⬅️ التحقق بخطوتين ⬅️ كلمات مرور التطبيقات (App Passwords) وأنشئ رمزاً من 16 حرفاً.',
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
        'guide_ar': 'افتح حساب Microsoft ⬅️ الأمان المتقدم ⬅️ كلمات مرور التطبيقات (App Passwords) وأنشئ كلمة مرور جديدة.',
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
        'guide_ar': 'افتح Apple ID ⬅️ تسجيل الدخول والأمان ⬅️ كلمات المرور الخاصة بالتطبيقات (App-Specific Passwords).',
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
        'guide_ar': 'افتح أمان حساب Yahoo ⬅️ إنشاء كلمة مرور التطبيق (Generate app password).',
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
        'guide_ar': 'افتح حساب Zoho ⬅️ الأمان ⬅️ كلمات مرور خاصة بالتطبيقات (Application-Specific Passwords).',
    },
    'custom': {
        'url': '',
        'smtp_host': '',
        'smtp_port': 587,
        'smtp_encryption': 'starttls',
        'imap_host': '',
        'imap_port': 993,
        'imap_ssl': True,
        'name_ar': 'بريد خاص بالشركة',
        'guide_ar': 'أدخل عنوان بريدك المؤسسي وكلمة المرور، وسيقوم النظام بضبط الإعدادات تلقائياً أو يمكنك تخصيصها.',
    },
}


class NexusUniversalMailWizard(models.TransientModel):
    _name = 'nexus.mail.wizard'
    _description = 'Universal Email Quick Setup Wizard'

    provider = fields.Selection(
        selection=PROVIDERS,
        string='Email Provider / مزود البريد',
        default='google',
        required=True,
    )
    email_address = fields.Char(
        string='Email Address / البريد الإلكتروني',
        required=True,
        placeholder='e.g. user@gmail.com, info@company.com',
    )
    app_password = fields.Char(
        string='App Password / كلمة مرور التطبيق',
        required=True,
        placeholder='16-character App Password (e.g. abcd efgh ijkl mnop)',
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
        string='Setup Outgoing Mail (إرسال الفواتير والإشعارات - SMTP)',
        default=True,
    )
    setup_incoming = fields.Boolean(
        string='Setup Incoming Mail (استقبال الردود والتذاكر - IMAP)',
        default=True,
    )
    send_test_email = fields.Boolean(
        string='Send Verification Test Email (إرسال بريد تجريبي للتأكيد)',
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
                    <strong>الخطوة 1:</strong> اضغط على زر 
                    <a href="{cfg['url']}" target="_blank" class="btn btn-sm btn-primary ms-2 me-2" style="font-weight: bold;">
                        🔗 فتح صفحة استخراج كلمة المرور ({cfg['name_ar']})
                    </a>
                    <br/>
                    <small class="text-muted">{cfg['guide_ar']}</small>
                </div>
                """
            else:
                record.guide_html = f"""
                <div class="alert alert-secondary py-2 px-3 my-1" style="border-radius: 8px;">
                    <strong>إعداد البريد المخصص:</strong> {cfg['guide_ar']}
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
            raise UserError(_('يرجى إدخال عنوان بريد إلكتروني صحيح.'))
        if not password:
            raise UserError(_('يرجى إدخال كلمة مرور التطبيق (App Password).'))

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
                results.append('✅ البريد الصادر (SMTP): تم الاتصال والتحقق بنجاح.')
            except Exception as e:
                raise UserError(_('فشل اختبار البريد الصادر (SMTP):\n%s') % str(e))

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
                results.append('✅ البريد الوارد (IMAP): تم التحقق والربط بنجاح.')
            except Exception as e:
                # We report as warning or message without breaking outgoing if outgoing worked
                results.append(f'⚠️ تنبيه في البريد الوارد: {str(e)}')

        # 3. Optional verification email
        if self.send_test_email and mail_server:
            recipient = (self.test_recipient or email).strip()
            try:
                test_mail = self.env['mail.mail'].create({
                    'subject': _('تأكيد ربط البريد بنجاح - Nexus Enterprise Engine'),
                    'body_html': f"""
                        <div style="font-family: Arial, sans-serif; padding: 20px; color: #2C3E50;">
                            <h2 style="color: #0B3D2E;">تهانينا! تم ربط البريد الإلكتروني بنجاح</h2>
                            <p>تم إعداد بريدك <b>{email}</b> بنجاح للعمل مع نظام <b>Nexus Enterprise Engine</b>.</p>
                            <p>المزود: <b>{dict(PROVIDERS).get(self.provider)}</b></p>
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
                results.append(f'📩 تم إرسال رسالة بريد تجريبية للتأكيد إلى: {recipient}')
            except Exception as e:
                results.append(f'⚠️ لم يتم إرسال الإيميل التجريبي: {str(e)}')

        summary = '\n'.join(results)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('نجح ربط البريد الإلكتروني!'),
                'message': summary,
                'type': 'success',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
