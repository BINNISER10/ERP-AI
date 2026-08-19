# -*- coding: utf-8 -*-
{
    "name": "Nexus Core Financial Synchronization / محرك المزامنة المحاسبية الفوري",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "summary": "Real-time financial synchronization and dual-ledger bridge for the Nexus Enterprise Engine.",
    "author": "Nexus Enterprise Architecture",
    "website": "https://nexus-engine.app",
    "license": "LGPL-3",
    "depends": ["base", "account", "mail", "nexus_base_security"],
    "data": [
        "security/ir.model.access.csv",
        "views/settings_view.xml",
        "views/nexus_sync_queue_views.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
