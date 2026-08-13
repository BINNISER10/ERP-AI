{
    "name": "Odoo / ERPNext Hybrid Sync Foundation",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "summary": "Shared foundation for Odoo 18 + ERPNext 15 hybrid sync and AI copilot.",
    "author": "Nexus Engine",
    "website": "https://nexus-engine.app",
    "license": "LGPL-3",
    "depends": ["base", "account", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/settings_view.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
