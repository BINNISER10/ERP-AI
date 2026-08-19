"""Cloudflare DNS integration for automatic tenant subdomain provisioning.

Requires a Cloudflare API token with the following permissions:
    - Zone:Read
    - DNS:Edit
"""
import logging
import re

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"
_DNS_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")


class CloudflareDnsManager(models.AbstractModel):
    _name = "nexus.saas.cloudflare.dns"
    _description = "Cloudflare DNS Manager"

    @api.model
    def _get_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        return {
            "token": icp.get_param("nexus_saas.cloudflare_api_token", "").strip(),
            "zone_id": icp.get_param("nexus_saas.cloudflare_zone_id", "").strip(),
            "base_domain": icp.get_param("nexus_saas.base_domain", "").strip().lower(),
            "cname_target": icp.get_param("nexus_saas.cloudflare_cname_target", "").strip().lower(),
        }

    @api.model
    def _request(self, method, path, json_payload=None, params=None):
        config = self._get_config()
        token = config.get("token")
        if not token:
            raise UserError(_("Cloudflare API token is not configured."))

        url = f"{_CLOUDFLARE_API}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=json_payload,
                params=params,
                timeout=(5, 30),
            )
        except requests.RequestException as exc:
            _logger.exception("Cloudflare API request failed: %s %s", method, url)
            raise UserError(_("Cloudflare API request failed: %s") % exc) from exc

        try:
            data = response.json()
        except ValueError as exc:
            _logger.error("Cloudflare returned non-JSON response: %s", response.text[:500])
            raise UserError(_("Cloudflare returned an unexpected response.")) from exc

        if not data.get("success"):
            errors = data.get("errors", [])
            messages = [err.get("message", str(err)) for err in errors]
            _logger.error("Cloudflare API error: %s", messages)
            raise UserError(_("Cloudflare API error: %s") % "; ".join(messages) if messages else _("Unknown Cloudflare error"))

        return data.get("result", {})

    @api.model
    def _find_zone_id(self, domain):
        """Return the zone ID for the given domain, or the configured zone_id if set."""
        config = self._get_config()
        zone_id = config.get("zone_id")
        if zone_id:
            return zone_id

        # Cloudflare requires at least 3 characters for zone name search.
        root = domain.lower().strip()
        if not root or len(root) < 3:
            raise UserError(_("Cannot determine Cloudflare zone for domain '%s'.") % domain)

        result = self._request("GET", "/zones", params={"name": root})
        zones = result if isinstance(result, list) else [result]
        for zone in zones:
            if zone.get("name") == root:
                return zone.get("id")
        raise UserError(_("No Cloudflare zone found for domain '%s'.") % root)

    @api.model
    def _validate_name(self, name):
        if not _DNS_NAME_RE.match(name):
            raise UserError(_("'%s' is not a valid DNS record name.") % name)

    @api.model
    def create_or_update_record(self, record_name, record_type, content, ttl=1, proxied=False):
        """Create or update a DNS record in Cloudflare.

        :param record_name: full record name, e.g. 'acme.nexus-engine.app'
        :param record_type: 'CNAME', 'A', etc.
        :param content: target value
        :param ttl: 1 = automatic
        :param proxied: whether to proxy through Cloudflare
        :return: dict with id, name, type, content
        """
        self._validate_name(record_name)
        root_domain = self._get_config().get("base_domain")
        if not root_domain:
            raise UserError(_("SaaS base domain is not configured."))

        zone_id = self._find_zone_id(root_domain)

        # Search for existing record
        existing = self._request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"name": record_name, "type": record_type},
        )
        records = existing if isinstance(existing, list) else []

        payload = {
            "type": record_type,
            "name": record_name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied,
        }

        if records:
            record_id = records[0]["id"]
            result = self._request(
                "PUT",
                f"/zones/{zone_id}/dns_records/{record_id}",
                json_payload=payload,
            )
            _logger.info("Updated Cloudflare DNS record %s -> %s", record_name, content)
        else:
            result = self._request(
                "POST",
                f"/zones/{zone_id}/dns_records",
                json_payload=payload,
            )
            _logger.info("Created Cloudflare DNS record %s -> %s", record_name, content)

        return result

    @api.model
    def delete_record(self, record_name, record_type="CNAME"):
        """Delete a DNS record by name and type."""
        root_domain = self._get_config().get("base_domain")
        if not root_domain:
            return False
        zone_id = self._find_zone_id(root_domain)
        existing = self._request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"name": record_name, "type": record_type},
        )
        records = existing if isinstance(existing, list) else []
        for rec in records:
            self._request("DELETE", f"/zones/{zone_id}/dns_records/{rec['id']}")
            _logger.info("Deleted Cloudflare DNS record %s", record_name)
        return bool(records)

    @api.model
    def provision_tenant_subdomain(self, tenant_code):
        """Create/update the CNAME record for a tenant subdomain."""
        config = self._get_config()
        base_domain = config.get("base_domain")
        target = config.get("cname_target")
        if not base_domain or not target:
            _logger.warning(
                "Skipping Cloudflare provisioning: base_domain=%s cname_target=%s",
                base_domain,
                target,
            )
            return False

        record_name = f"{tenant_code}.{base_domain}"
        return self.create_or_update_record(record_name, "CNAME", target)

    @api.model
    def provision_tenant_custom_domain(self, custom_domain):
        """Create/update the CNAME record for a tenant custom domain."""
        config = self._get_config()
        target = config.get("cname_target")
        if not target or not custom_domain:
            return False
        return self.create_or_update_record(custom_domain, "CNAME", target)
