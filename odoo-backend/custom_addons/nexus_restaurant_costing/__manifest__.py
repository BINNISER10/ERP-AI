{
    "name": "Nexus Restaurant Costing",
    "version": "18.0.1.0.0",
    "category": "Nexus/MRP",
    "summary": "Recipe BOM, inventory consumption and dynamic COGS/profit margins for hospitality.",
    "author": "Nexus Systems",
    "website": "https://nexus.example.com",
    "license": "LGPL-3",
    "depends": ["base", "stock", "mrp", "sale", "nexus_api_gateway"],
    "data": [
        "security/ir.model.access.csv",
        "views/recipe_bom_views.xml",
        "views/menu_item_views.xml",
        "data/ir_sequence.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
