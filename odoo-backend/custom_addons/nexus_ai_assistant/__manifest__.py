{
    "name": "Nexus AI Assistant",
    "version": "18.0.1.0.0",
    "category": "Nexus/AI",
    "summary": "Gemini-powered AI assistant for ERP setup, monitoring and reporting",
    "description": """
        Adds a Gemini-powered AI assistant inside Odoo for:
        - Business entity setup wizard (retail, factory, etc.)
        - Inventory and sales monitoring
        - Cash register daily close alerts
        - Bank reconciliation and matching
        - AI report suggestions
    """,
    "author": "Nexus Enterprise",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/ai_config_data.xml",
        "views/ai_config_views.xml",
        "views/business_setup_wizard_views.xml",
        "views/ai_monitor_wizard_views.xml",
        "views/ai_assistant_menus.xml",
    ],
    "application": True,
    "installable": True,
    "license": "LGPL-3",
}
