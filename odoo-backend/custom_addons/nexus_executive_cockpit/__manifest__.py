{
    "name": "Nexus Executive AI Cockpit / لوحة القيادة الاستراتيجية",
    "version": "18.0.1.0.0",
    "category": "Nexus/Reporting",
    "summary": (
        "Customizable, prescriptive executive dashboard: liquidity, "
        "daily sales, gross margin, per-branch P&L, 90-day cash flow "
        "forecast, and anomaly/waste alerts."
    ),
    "author": "Nexus Engine",
    "website": "https://nexus-engine.app",
    "license": "LGPL-3",
    "depends": ["base", "account"],
    "data": [
        "security/ir.model.access.csv",
        "security/cockpit_rules.xml",
        "views/cockpit_templates.xml",
        "views/cockpit_menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
