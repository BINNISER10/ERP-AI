/** @odoo-module **/

/**
 * Nexus Pure Branding — Enterprise upgrade field neutralization.
 *
 * In Odoo 17+ the only remaining "upgrade" widget is `upgrade_boolean`
 * (registered under the fields registry by the settings form view). It
 * renders an "Enterprise" badge next to the setting and opens the upgrade /
 * upsell dialog as soon as the user toggles the field.
 *
 * Here we re-register that name with { force: true } so settings views render
 * a plain, inert standard boolean instead.
 */

import { registry } from "@web/core/registry";
import { BooleanField } from "@web/views/fields/boolean/boolean_field";

const fieldRegistry = registry.category("fields");

class NexusUpgradeBooleanField extends BooleanField {}
fieldRegistry.add("upgrade_boolean", NexusUpgradeBooleanField, { force: true });
