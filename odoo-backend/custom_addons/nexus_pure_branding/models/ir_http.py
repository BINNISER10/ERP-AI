# -*- coding: utf-8 -*-
"""Rebrand the session info payload so the web client never renders the
upstream "Odoo" name, version, or "Community Edition" suffix anywhere in
the backend UI (e.g. browser dev tools, the debug menu, JS console)."""
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Return a session info that reports a private Nexus build."""
        res = super().session_info()
        res["server_version"] = "Nexus Enterprise Engine"
        info = res.get("server_version_info") or [18, 0, 0, "final", 0, ""]
        if isinstance(info, (list, tuple)) and len(info) >= 6:
            info = list(info)
            # Report as an "enterprise" build so the web client does not
            # append a visible "Community Edition" suffix anywhere.
            info[5] = "e"
            if len(info) >= 7:
                info[6] = "nexus"
            else:
                info.append("nexus")
        res["server_version_info"] = info
        return res
