{
    "name": "Nexus SaaS Billing / الفوترة والاشتراكات",
    "version": "18.0.1.0.0",
    "category": "Nexus/SaaS",
    "summary": "Stripe billing and subscription management for Nexus SaaS tenants.",
    "author": "Nexus Engine",
    "website": "https://nexus-engine.app",
    "license": "LGPL-3",
    "depends": [
        "base",
        "account",
        "nexus_saas_tenant",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/res_config_settings_views.xml",
        "views/subscription_views.xml",
        "views/billing_invoice_views.xml",
        "views/saas_billing_menus.xml",
    ],
    "external_dependencies": {
        "python": ["stripe"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
