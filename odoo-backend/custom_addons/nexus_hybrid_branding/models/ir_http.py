"""Override session info to rebrand server version and hide Community edition."""
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Return a session info that reports a private Hybrid build."""
        res = super().session_info()
        res["server_version"] = "Nexus Hybrid"
        # Add the enterprise suffix so the web client does not append "Community Edition".
        info = res.get("server_version_info") or [18, 0, 0, "final", 0, ""]
        if isinstance(info, (list, tuple)) and len(info) >= 6:
            info = list(info)
            info[5] = "e"
            if len(info) >= 7:
                info[6] = "nexus-hybrid"
            else:
                info.append("nexus-hybrid")
        res["server_version_info"] = info
        return res
