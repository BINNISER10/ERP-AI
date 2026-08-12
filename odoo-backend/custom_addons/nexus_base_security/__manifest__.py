{
    "name": "Nexus Base Security",
    "version": "18.0.1.0.0",
    "category": "Nexus/Enterprise",
    "summary": "Base security and shared utilities for the Nexus Enterprise Engine.",
    "author": "Nexus Systems",
    "website": "https://nexus.example.com",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/nexus_groups.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
