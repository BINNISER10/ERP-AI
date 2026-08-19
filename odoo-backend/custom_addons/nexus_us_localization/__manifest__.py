{
    "name": "Nexus US Localization / تخصيص السوق الأمريكي",
    "version": "18.0.1.0.0",
    "category": "Nexus/Localization",
    "summary": "Comprehensive United States localization: GAAP-compliant chart of accounts, multi-state sales tax, 1099-NEC/MISC reporting, W-9 vendor forms, ACH payment processing, and US tax templates.",
    "author": "Nexus Engine",
    "website": "https://nexus-engine.app",
    "license": "LGPL-3",
    "depends": [
        "base",
        "account",
        "sale",
        "purchase",
        "stock",
        "hr",
        "point_of_sale",
        "nexus_us_tax_engine",
        "nexus_base_security",
        "ai_enterprise_copilot"
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/us_ach_rules.xml",
        "data/us_localization_menu.xml",
        "data/us_cron.xml",
        "views/us_company_settings_view.xml",
        "views/us_1099_report_view.xml",
        "views/us_multi_state_tax_view.xml"
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook"
}
