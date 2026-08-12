{
    "name": "Nexus Real Estate",
    "version": "18.0.1.0.0",
    "category": "Nexus/Real Estate",
    "summary": "Property units and lease contract management.",
    "author": "Nexus Systems",
    "website": "https://nexus.example.com",
    "license": "LGPL-3",
    "depends": ["base", "account", "nexus_base_security"],
    "data": [
        "security/ir.model.access.csv",
        "views/property_unit_views.xml",
        "views/lease_contract_views.xml",
        "data/ir_sequence.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
