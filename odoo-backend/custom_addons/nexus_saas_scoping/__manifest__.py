{
    "name": "Nexus SaaS Scoping & Checkout / التسعير والتهيئة الذاتية",
    "version": "18.0.1.0.0",
    "category": "Nexus/SaaS",
    "summary": (
        "Zero-touch sales funnel: business-profiling wizard, rule-based "
        "module/resource-tier recommendation, dynamic pricing, and "
        "Stripe checkout -> automated tenant provisioning."
    ),
    "author": "Nexus Engine",
    "website": "https://nexus-engine.app",
    "license": "LGPL-3",
    "depends": [
        "base",
        "nexus_saas_tenant",
        "nexus_saas_billing",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sector_data.xml",
        "views/scoping_request_views.xml",
        "views/sector_views.xml",
        "views/saas_scoping_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
