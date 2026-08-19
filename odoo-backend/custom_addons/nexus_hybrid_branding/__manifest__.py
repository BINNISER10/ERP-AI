{
    "name": "Nexus Hybrid Branding (superseded)",
    "version": "18.0.1.0.0",
    "category": "Hidden",
    "summary": (
        "DEPRECATED — fully superseded by nexus_pure_branding, which covers "
        "every override here plus enterprise-upgrade/upsell removal and "
        "mail footer branding. Kept installable=False to prevent the "
        "conflicting duplicate view inheritance (both modules replace the "
        "same web.login_layout / web.brand_promotion xpaths)."
    ),
    "author": "Nexus Engine",
    "website": "https://nexus-engine.app",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "mail",
        "portal",
        "website",
    ],
    "data": [
        "views/rebrand_views.xml",
    ],
    "installable": False,
    "application": False,
    "auto_install": False,
}
