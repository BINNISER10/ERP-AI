{
    "name": "Nexus API Gateway",
    "version": "18.0.1.0.0",
    "category": "Nexus/POS",
    "summary": "JSON-RPC gateway for the Flutter POS authentication, catalog sync and offline order posting.",
    "author": "Nexus Systems",
    "website": "https://nexus.example.com",
    "license": "LGPL-3",
    "depends": ["base", "sale", "stock", "point_of_sale", "nexus_base_security"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
