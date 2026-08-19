{
    "name": "Nexus Pure Branding",
    "version": "18.0.1.0.0",
    "category": "Nexus/Branding",
    "summary": "White-label layer — strips all Odoo / ERPNext upstream branding, enterprise upgrade prompts, upsell modals and external support links across the whole backend.",
    "author": "Nexus Engine",
    "website": "https://nexus-engine.app",
    "license": "LGPL-3",
    "depends": [
        "base",
        "base_setup",
        "web",
        "mail",
        "portal",
        "website",
    ],
    "data": [
        "data/email_templates.xml",
        "views/web_template_overrides.xml",
        "views/portal_template_overrides.xml",
        "views/res_config_settings_overrides.xml",
        "views/website_template_overrides.xml",
    ],
    "assets": {
        "web._assets_backend_helpers": [
            "nexus_pure_branding/static/src/scss/pure_branding.scss",
        ],
        "web.assets_backend": [
            "nexus_pure_branding/static/src/js/upgrade_fields.js",
            "nexus_pure_branding/static/src/js/branding_sanitizer.js",
        ],
        "web.assets_frontend": [
            "nexus_pure_branding/static/src/js/branding_sanitizer.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
