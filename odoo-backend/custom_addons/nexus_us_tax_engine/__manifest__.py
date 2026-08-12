{
    "name": "Nexus US Tax Engine",
    "version": "18.0.1.0.0",
    "category": "Nexus/Accounting",
    "summary": "Multi-jurisdiction US sales and use tax calculations.",
    "author": "Nexus Systems",
    "website": "https://nexus.example.com",
    "license": "LGPL-3",
    "depends": ["base", "account", "nexus_base_security"],
    "data": [
        "security/ir.model.access.csv",
        "data/tax_rates.xml",
        "views/us_tax_rate_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
