/** @odoo-module **/

/**
 * Nexus Pure Branding — lightweight runtime title and brand sanitizer.
 */

const BRAND_TITLE = "Nexus Enterprise Engine";

function sanitizeTitle() {
    try {
        const current = document.title || "";
        if (/Odoo|ERPNext|Frappe/i.test(current)) {
            const cleaned = current
                .replace(/Odoo|ERPNext|Frappe/gi, BRAND_TITLE)
                .replace(/\s*[-–—|]\s*$/g, "");
            document.title = cleaned || BRAND_TITLE;
        } else if (!document.title || document.title.trim() === "") {
            document.title = BRAND_TITLE;
        }
    } catch (e) {
        // Safe fail
    }
}

function patchFavicon() {
    try {
        const favicon = "/nexus_pure_branding/static/src/img/nexus_favicon.svg";
        const links = document.querySelectorAll('link[rel*="icon"]');
        links.forEach((link) => {
            const href = link.getAttribute("href") || "";
            if (/web\/static|odoo|erpnext|frappe/i.test(href)) {
                link.setAttribute("href", favicon);
            }
        });
        if (!document.querySelector('link[rel*="icon"][href*="nexus_pure_branding"]')) {
            const link = document.createElement("link");
            link.rel = "icon";
            link.type = "image/svg+xml";
            link.href = favicon;
            document.head.appendChild(link);
        }
    } catch (e) {
        // Safe fail
    }
}

export function startSanitizer() {
    // Initial sanitize on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            sanitizeTitle();
            patchFavicon();
        });
    } else {
        sanitizeTitle();
        patchFavicon();
    }

    // Periodic lightweight check (every 3 seconds) instead of heavy mutation observer
    setInterval(() => {
        sanitizeTitle();
    }, 3000);
}

startSanitizer();
