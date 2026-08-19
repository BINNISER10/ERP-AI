{
    "name": "Nexus Saudi Localization / تخصيص السوق السعودي",
    "version": "18.0.1.0.0",
    "category": "Nexus/Localization",
    "summary": "Comprehensive Saudi Arabia localization: ZATCA Phase 2 e-invoicing, VAT 15%, Arabic RTL, Saudization (Nitaqat), MOL compliance, and Saudi chart of accounts templates.",
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
        "nexus_zatca_compliance",
        "nexus_base_security",
        "ai_enterprise_copilot"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/saudi_localization_menu.xml",
        "data/saudi_cron.xml",
        "views/saudi_company_settings_view.xml",
        "views/saudi_qr_invoice_view.xml",
        "views/saudi_vat_report_view.xml",
        "views/saudization_dashboard_view.xml"
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook"
}
