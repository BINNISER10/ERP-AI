# -*- coding: utf-8 -*-
{
    'name': 'Nexus Universal Mail Setup / معالج ربط البريد الشامل',
    'version': '18.0.1.0.0',
    'category': 'Productivity/Mail',
    'summary': 'Quick 1-Click App Password Email Integration for Google, Microsoft, Apple, Yahoo, Zoho & Custom Domains',
    'description': """
Nexus Universal Email Setup
===========================
Provides a fast, unified wizard with direct App-Password links for all major email platforms:
- Google / Gmail / Workspace (https://myaccount.google.com/apppasswords)
- Microsoft Outlook / Hotmail / Office 365 (https://account.live.com/proofs/AppPassword)
- Apple iCloud (https://appleid.apple.com/account/manage/section/security)
- Yahoo Mail (https://login.yahoo.com/account/security)
- Zoho Mail (https://accounts.zoho.com/home#security/app_passwords)
- Custom Company / cPanel / Webmail / Private SMTP
    """,
    'author': 'Nexus Enterprise Architecture',
    'website': 'https://nexus-engine.local',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'base_setup',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/universal_mail_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/mail_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
