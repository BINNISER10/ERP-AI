{
    "name": "Nexus Contracting",
    "version": "18.0.1.0.0",
    "category": "Nexus/Construction",
    "summary": "Percentage-of-completion contract cost sheet management.",
    "author": "Nexus Systems",
    "website": "https://nexus.example.com",
    "license": "LGPL-3",
    "depends": ["base", "account", "project", "nexus_base_security"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/project_contract_views.xml",
        "views/cost_sheet_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
