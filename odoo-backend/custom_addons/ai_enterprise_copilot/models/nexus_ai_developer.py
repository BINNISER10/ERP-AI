# -*- coding: utf-8 -*-
"""Nexus AI Developer & Business Staff Member â€” Ù…Ø·ÙˆØ± Ø£ÙˆØ¯Ùˆ ÙˆÙ…Ø³ØªØ´Ø§Ø± Ø§Ù„Ø£Ø¹Ù…Ø§Ù„ Ø§Ù„Ø°ÙƒÙŠ.

An embedded AI technical team member inside Odoo that assists business administrators
and developers with custom business logic, automated actions, SQL queries, ZATCA
compliance, Flutter POS hardware integration, and error diagnostics.
"""

import json
import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PERSONA_SELECTION = [
    ('odoo_senior_dev', 'ðŸ‘¨â€ðŸ’» ÙƒØ¨ÙŠØ± Ù…Ø·ÙˆØ±ÙŠ Ø£ÙˆØ¯Ùˆ 18 (Senior Odoo Developer)'),
    ('business_architect', 'ðŸ›ï¸ Ù…Ù‡Ù†Ø¯Ø³ Ù…Ø¹Ù…Ø§Ø±ÙŠ Ù„Ù„Ø´Ø±ÙƒØ§Øª ÙˆØ§Ù„Ø¹Ù…Ù„ÙŠØ§Øª (Business Architect)'),
    ('tax_compliance_expert', 'âš–ï¸ Ø®Ø¨ÙŠØ± Ø§Ù„Ø¶Ø±Ø§Ø¦Ø¨ ÙˆØ§Ù„ÙÙˆØªØ±Ø© Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠØ© ZATCA'),
    ('data_analyst', 'ðŸ“Š Ù…Ø­Ù„Ù„ Ø¨ÙŠØ§Ù†Ø§Øª ÙˆÙ…Ù‡Ù†Ø¯Ø³ ØªÙ‚Ø§Ø±ÙŠØ± SQL (BI & Data Analyst)'),
    ('pos_hardware_engineer', 'ðŸ’³ Ù…Ù‡Ù†Ø¯Ø³ Ù†Ù‚Ø§Ø· Ø§Ù„Ø¨ÙŠØ¹ ÙˆØ§Ù„Ø£Ø¬Ù‡Ø²Ø© Mada / Stripe'),
]

MODULE_SELECTION = [
    ('general', 'Ø¹Ø§Ù… / General'),
    ('account', 'Ø§Ù„Ù…Ø­Ø§Ø³Ø¨Ø© ÙˆØ§Ù„Ù…Ø§Ù„ÙŠØ© (Accounting & Invoicing)'),
    ('point_of_sale', 'Ù†Ù‚Ø§Ø· Ø§Ù„Ø¨ÙŠØ¹ ÙˆØ§Ù„ÙƒØ§Ø´ÙŠØ± (Point of Sale & POS)'),
    ('stock', 'Ø§Ù„Ù…Ø³ØªÙˆØ¯Ø¹Ø§Øª ÙˆØ§Ù„Ù…Ø®Ø²ÙˆÙ† (Inventory & Stock)'),
    ('zatca', 'Ø§Ù„ÙÙˆØªØ±Ø© Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠØ© ÙˆØ§Ù„Ø²ÙƒØ§Ø© (ZATCA Compliance)'),
    ('hr', 'Ø§Ù„Ù…ÙˆØ§Ø±Ø¯ Ø§Ù„Ø¨Ø´Ø±ÙŠØ© ÙˆØ§Ù„Ø±ÙˆØ§ØªØ¨ (HR & Payroll WPS)'),
    ('mrp', 'Ø§Ù„ØªØµÙ†ÙŠØ¹ ÙˆØ§Ù„Ø¥Ù†ØªØ§Ø¬ (Manufacturing & MRP)'),
    ('project', 'Ø§Ù„Ù…Ø´Ø§Ø±ÙŠØ¹ ÙˆØ§Ù„Ø¹Ù‚ÙˆØ¯ (Projects & Contracting)'),
    ('api_gateway', 'Ø¨ÙˆØ§Ø¨Ø© Ø§Ù„Ø±Ø¨Ø· Ø§Ù„Ø¨Ø±Ù…Ø¬ÙŠ (API Gateway & Flutter POS)'),
]


class NexusAiDeveloperStaff(models.Model):
    _name = 'nexus.ai.developer.staff'
    _description = 'Odoo Software Development Staff Member'
    _order = 'id desc'

    name = fields.Char(string='Ø¹Ù†ÙˆØ§Ù† Ø§Ù„Ø¬Ù„Ø³Ø© / Topic', required=True, default='Ø§Ø³ØªØ´Ø§Ø±Ø© ØªÙ‚Ù†ÙŠØ© Ø¬Ø¯ÙŠØ¯Ø©')
    user_id = fields.Many2one('res.users', string='Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù…', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Ø§Ù„Ù…Ù†Ø´Ø£Ø©', default=lambda self: self.env.company)

    developer_persona = fields.Selection(
        selection=PERSONA_SELECTION,
        string='Ø§Ù„Ù…ÙˆØ¸Ù / Ø§Ù„Ù…Ø³ØªØ´Ø§Ø± Ø§Ù„Ø°ÙƒÙŠ Ø§Ù„Ù…Ø·Ù„ÙˆØ¨',
        default='odoo_senior_dev',
        required=True,
    )
    context_module = fields.Selection(
        selection=MODULE_SELECTION,
        string='Ø§Ù„Ù…ÙˆØ¯ÙŠÙˆÙ„ Ø£Ùˆ Ø§Ù„Ù…Ø¬Ø§Ù„ Ø§Ù„Ù…Ø¹Ù†ÙŠ',
        default='general',
        required=True,
    )

    prompt = fields.Text(
        string='Ø§Ù„Ø³Ø¤Ø§Ù„ Ø£Ùˆ Ø§Ù„Ù…ØªØ·Ù„Ø¨ Ø§Ù„Ø¨Ø±Ù…Ø¬ÙŠ / Ø§Ù„ØªØ´ØºÙŠÙ„ÙŠ',
        required=True,
    )
    error_traceback = fields.Text(
        string='Ø±Ø³Ø§Ù„Ø© Ø§Ù„Ø®Ø·Ø£ Ù„Ù„ØªØ´Ø®ÙŠØµ (Error Traceback - Ø§Ø®ØªÙŠØ§Ø±ÙŠ)',
    )

    state = fields.Selection(
        [
            ('draft', 'Ù…Ø³ÙˆØ¯Ø© (Draft)'),
            ('answered', 'ØªÙ… Ø§Ù„ØªØ­Ù„ÙŠÙ„ ÙˆØ§Ù„Ø­Ù„ (Answered)'),
        ],
        default='draft',
        required=True,
    )

    # â”€â”€ AI Solutions Output â”€â”€
    solution_title = fields.Char(string='Ø¹Ù†ÙˆØ§Ù† Ø§Ù„Ø­Ù„')
    ai_response_html = fields.Html(string='Ø´Ø±Ø­ ÙˆØªÙˆØ¬ÙŠÙ‡Ø§Øª Ø§Ù„Ù…Ø·ÙˆØ± Ø§Ù„Ø°ÙƒÙŠ', readonly=True)
    root_cause_explanation = fields.Text(string='Ø§Ù„Ø³Ø¨Ø¨ Ø§Ù„Ø¬Ø°Ø±ÙŠ Ù„Ù„Ø®Ø·Ø£ (Root Cause)', readonly=True)
    
    generated_code = fields.Text(string='Ø§Ù„ÙƒÙˆØ¯ Ø§Ù„Ø¨Ø±Ù…Ø¬ÙŠ / Ø§Ù„Ø§Ø³ØªØ¹Ù„Ø§Ù… Ø§Ù„Ø¬Ø§Ù‡Ø² (Code)')
    generated_code_type = fields.Selection(
        [
            ('python', 'Python (Server Action / Model Code)'),
            ('sql', 'PostgreSQL SQL Query'),
            ('xml', 'QWeb / View XML'),
            ('n8n', 'n8n JSON Workflow'),
            ('text', 'Technical Guide / Steps'),
        ],
        string='Ù†ÙˆØ¹ Ø§Ù„ÙƒÙˆØ¯',
        default='python',
    )
    recommended_actions_html = fields.Html(string='Ø§Ù„Ø®Ø·ÙˆØ§Øª Ø§Ù„ØªÙ†ÙÙŠØ°ÙŠØ© Ø§Ù„Ù…ÙˆØµÙ‰ Ø¨Ù‡Ø§', readonly=True)

    def action_ask_ai_developer(self):
        """Invoke AI Developer Staff endpoint via AI microservices or fallback engine."""
        self.ensure_one()
        prompt_text = (self.prompt or '').strip()
        if not prompt_text:
            raise UserError(_('ÙŠØ±Ø¬Ù‰ ÙƒØªØ§Ø¨Ø© Ø§Ù„Ø³Ø¤Ø§Ù„ Ø£Ùˆ Ø§Ù„Ù…ØªØ·Ù„Ø¨ Ø§Ù„Ø¨Ø±Ù…Ø¬ÙŠ Ø£ÙˆÙ„Ø§Ù‹.'))

        payload = {
            'prompt': prompt_text,
            'persona': self.developer_persona,
            'context_module': self.context_module,
            'error_traceback': (self.error_traceback or '').strip() or None,
            'language': 'ar',
        }

        data = None
        # Try calling AI microservices container
        try:
            url = 'http://nexus_ai:8000/api/v1/ai/developer/consult'
            resp = requests.post(url, json=payload, timeout=8)
            if resp.ok:
                data = resp.json()
        except Exception as e:
            _logger.info('Could not reach ai_services container directly: %s. Using internal solver.', e)

        if not data:
            # Smart internal developer engine fallback
            data = self._generate_internal_solution(prompt_text, self.developer_persona, self.context_module, self.error_traceback)

        # Update record with AI solution
        self.solution_title = data.get('title') or f"Ø­Ù„ Ù…Ù‚ØªØ±Ø­: {prompt_text[:40]}"
        self.root_cause_explanation = data.get('root_cause') or ''
        self.generated_code = data.get('code') or ''
        self.generated_code_type = data.get('code_type') or 'python'

        # Build Rich HTML Solution View
        solution_body = data.get('solution_ar', '')
        persona_label = dict(PERSONA_SELECTION).get(self.developer_persona, '')
        
        html_parts = [
            f"""
            <div class="card border-0 shadow-sm p-3 mb-3" style="border-radius: 10px; background-color: #F8FAFC; border-left: 5px solid #0B3D2E !important;">
                <div class="d-flex align-items-center mb-2">
                    <span class="badge bg-primary me-2" style="font-size: 13px;">{persona_label}</span>
                    <strong class="text-dark" style="font-size: 16px;">{self.solution_title}</strong>
                </div>
                <div class="mt-2 text-dark" style="font-size: 15px; line-height: 1.8;">
                    {solution_body.replace('\n', '<br/>')}
                </div>
            </div>
            """
        ]

        if self.root_cause_explanation:
            html_parts.append(f"""
                <div class="alert alert-warning border-0 shadow-sm p-3 mb-3" style="border-radius: 8px;">
                    <strong>ðŸ” ØªØ´Ø®ÙŠØµ Ø§Ù„Ø®Ø·Ø£ ÙˆØ§Ù„Ø³Ø¨Ø¨ Ø§Ù„Ø¬Ø°Ø±ÙŠ:</strong><br/>
                    {self.root_cause_explanation}
                </div>
            """)

        self.ai_response_html = ''.join(html_parts)

        # Recommended Actions list
        rec_actions = data.get('recommended_actions', [])
        if rec_actions:
            action_items = ''.join([f'<li class="mb-2">ðŸ‘‰ {act}</li>' for act in rec_actions])
            self.recommended_actions_html = f"""
                <div class="card border-success p-3 shadow-sm bg-light" style="border-radius: 8px;">
                    <h6 class="text-success font-weight-bold mb-2">ðŸ“‹ Ø®Ø·ÙˆØ§Øª Ø§Ù„ØªÙ†ÙÙŠØ° Ø§Ù„Ø¹Ù…Ù„ÙŠØ© (Action Plan):</h6>
                    <ul class="mb-0 ps-3" style="color: #2D3748; font-size: 14px;">
                        {action_items}
                    </ul>
                </div>
            """

        self.state = 'answered'
        if not self.name or self.name == 'Ø§Ø³ØªØ´Ø§Ø±Ø© ØªÙ‚Ù†ÙŠØ© Ø¬Ø¯ÙŠØ¯Ø©':
            self.name = self.solution_title[:60]

        return True

    def _generate_internal_solution(self, prompt, persona, module, traceback):
        """Embedded expert rules engine when offline."""
        lower_prompt = prompt.lower()
        title = "Ø§Ø³ØªØ´Ø§Ø±Ø© Ù…Ø·ÙˆØ± Ø£ÙˆØ¯Ùˆ Ø§Ù„Ù…Ø¹ØªÙ…Ø¯"
        code_type = "python"
        code = None
        solution = "Ø¨Ù†Ø§Ø¡Ù‹ Ø¹Ù„Ù‰ Ù…ØªØ·Ù„Ø¨Ùƒ ÙÙŠ Ù†Ø¸Ø§Ù… Nexus Enterprise Engine (Odoo 18)ØŒ Ø¥Ù„ÙŠÙƒ Ø§Ù„Ø­Ù„ Ø§Ù„Ù‡Ù†Ø¯Ø³ÙŠ Ø§Ù„Ù…ØªÙˆØ§ÙÙ‚ Ù…Ø¹ Ù…Ø¹Ø§ÙŠÙŠØ± Odoo Ø§Ù„Ø±Ø³Ù…ÙŠØ©."
        root_cause = None
        actions = [
            "ØªØ·Ø¨ÙŠÙ‚ Ø§Ù„ÙƒÙˆØ¯ ÙÙŠ Server Action Ø£Ùˆ Ø¹Ø¨Ø± ÙƒÙˆØ¯ Ø§Ù„Ù…ÙˆØ¯ÙŠÙˆÙ„ Ø§Ù„Ù…Ø®ØµØµ",
            "Ø§Ø®ØªØ¨Ø§Ø± Ø§Ù„Ø¹Ù…Ù„ÙŠØ© ÙÙŠ Ø¨ÙŠØ¦Ø© Ø§Ù„ØªØ·ÙˆÙŠØ± ÙˆØ§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ§Øª",
            "Ù…Ø±Ø§Ø¬Ø¹Ø© Ø³Ø¬Ù„Ø§Øª Ø§Ù„Ø®Ø§Ø¯Ù… ÙÙŠ Ø­Ø§Ù„ ÙˆØ¬ÙˆØ¯ Ø£ÙŠ ØªÙ†Ø¨ÙŠÙ‡Ø§Øª",
        ]

        if traceback or "error" in lower_prompt or "Ø®Ø·Ø£" in lower_prompt:
            title = "ØªØ´Ø®ÙŠØµ ÙˆØ­Ù„ Ù…Ø´ÙƒÙ„Ø© Ø¨Ø±Ù…Ø¬ÙŠØ©"
            root_cause = "ØªØ­Ù„ÙŠÙ„ Ø±Ø³Ø§Ù„Ø© Ø§Ù„Ø®Ø·Ø£ ÙŠØ´ÙŠØ± Ø¥Ù„Ù‰ ØªØ¹Ø§Ø±Ø¶ ÙÙŠ Ù‚ÙŠÙˆØ¯ Ù‚Ø§Ø¹Ø¯Ø© Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª (Constraint) Ø£Ùˆ Ù†Ù‚Øµ ÙÙŠ Ø§Ù„Ø­Ù‚ÙˆÙ„ Ø§Ù„Ø¥Ù„Ø²Ø§Ù…ÙŠØ©."
            solution = "Ù„ØªØ¬Ø§ÙˆØ² Ù‡Ø°Ø§ Ø§Ù„Ø®Ø·Ø£ØŒ ÙŠØ¬Ø¨ Ø§Ù„ØªØ£ÙƒØ¯ Ù…Ù† Ø¹Ø¯Ù… ØªÙƒØ±Ø§Ø± Ø§Ù„Ù…Ø¹Ø±ÙØ§Øª Ø§Ù„ÙØ±ÙŠØ¯Ø© ÙˆØªÙ…Ø±ÙŠØ± Ø§Ù„Ù‚ÙŠÙ… Ø§Ù„Ø§ÙØªØ±Ø§Ø¶ÙŠØ© Ù‚Ø¨Ù„ Ø­ÙØ¸ Ø§Ù„Ø³Ø¬Ù„."
            code = "# Python Fix Pattern\nexisting = env['account.move'].search([('name', '=', move_name)], limit=1)\nif not existing:\n    record.action_post()\n"
            actions = ["Ù…Ø±Ø§Ø¬Ø¹Ø© Ø¯Ø§Ù„Ø© create() Ø£Ùˆ write()", "Ø¥Ø¶Ø§ÙØ© ØªØ­Ù‚Ù‚ search Ù‚Ø¨Ù„ Ø§Ù„Ø¥Ù†Ø´Ø§Ø¡ Ù„Ù…Ù†Ø¹ Ø§Ù„ØªÙƒØ±Ø§Ø±"]
        elif "sql" in lower_prompt or "Ø§Ø³ØªØ¹Ù„Ø§Ù…" in lower_prompt or "ØªÙ‚Ø±ÙŠØ±" in lower_prompt:
            title = "Ø§Ø³ØªØ¹Ù„Ø§Ù… SQL ØªØ­Ù„ÙŠÙ„ÙŠ Ø¬Ø§Ù‡Ø²"
            code_type = "sql"
            code = """-- Ø§Ø³ØªØ¹Ù„Ø§Ù… ÙƒØ´Ù Ø­Ø³Ø§Ø¨ ÙˆÙ…Ø¨ÙŠØ¹Ø§Øª Ø§Ù„Ø´Ù‡ÙˆØ±
SELECT 
    partner.name AS customer_name,
    COUNT(move.id) AS invoice_count,
    SUM(move.amount_total) AS total_revenue
FROM account_move move
JOIN res_partner partner ON partner.id = move.partner_id
WHERE move.move_type = 'out_invoice' 
  AND move.state = 'posted'
GROUP BY partner.name
ORDER BY total_revenue DESC
LIMIT 10;"""
            solution = "Ø§Ø³ØªØ¹Ù„Ø§Ù… SQL Ù…Ø­Ø³Ù† Ù„Ù‚Ø±Ø§Ø¡Ø© Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„ÙÙˆØ§ØªÙŠØ± ÙˆØ§Ù„Ù…Ø¨ÙŠØ¹Ø§Øª Ø¨Ø£Ø¹Ù„Ù‰ Ø³Ø±Ø¹Ø© Ø¯ÙˆÙ† Ø§Ù„ØªØ£Ø«ÙŠØ± Ø¹Ù„Ù‰ Ø£Ø¯Ø§Ø¡ Ø§Ù„Ø®Ø§Ø¯Ù…."
            actions = ["ØªÙ†ÙÙŠØ° Ø§Ù„Ø§Ø³ØªØ¹Ù„Ø§Ù… Ø¹Ø¨Ø± Text-to-SQL", "ØªØµØ¯ÙŠØ± Ø§Ù„Ù†ØªØ§Ø¦Ø¬ Ø¥Ù„Ù‰ Excel Ø£Ùˆ Ù„ÙˆØ­Ø© ØªØ­ÙƒÙ…"]
        elif "zatca" in lower_prompt or "Ø¶Ø±ÙŠØ¨Ø©" in lower_prompt:
            title = "ØªÙ‡ÙŠØ¦Ø© Ø§Ù„ÙÙˆØªØ±Ø© Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠØ© ZATCA Phase 2"
            code_type = "python"
            code = "# ZATCA QR & Hash Generation\nfrom odoo.addons.nexus_zatca_compliance.models.zatca_hasher import generate_zatca_invoice_hash\ninvoice_hash = generate_zatca_invoice_hash(xml_content)\n"
            solution = "Ù„Ø±Ø¨Ø· Ø§Ù„ÙØ§ØªÙˆØ±Ø© Ù…Ø¹ Ù…Ù†ØµØ© ÙØ§ØªÙˆØ±Ø©ØŒ ÙŠØ¬Ø¨ Ù…Ø·Ø§Ø¨Ù‚Ø© ÙƒÙˆØ¯ Ø§Ù„Ø¶Ø±ÙŠØ¨Ø© (VAT-15) ÙˆØ­Ø³Ø§Ø¨ Ø§Ù„ØªØ¬Ø²Ø¦Ø© Ø§Ù„Ù…Ø´ÙØ±Ø© SHA-256 Ù„Ù„Ù€ XML."
            actions = ["Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† ØµØ­Ø© Ø§Ù„Ø±Ù‚Ù… Ø§Ù„Ø¶Ø±ÙŠØ¨ÙŠ (15 Ø±Ù‚Ù…Ø§Ù‹)", "ØªÙØ¹ÙŠÙ„ Ø§Ù„Ø´Ù‡Ø§Ø¯Ø© Ø§Ù„Ø±Ù‚Ù…ÙŠØ© CSID ÙÙŠ Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª ZATCA"]
        else:
            title = f"ØªØ·ÙˆÙŠØ± ÙˆØ£ØªÙ…ØªØ© Ù…ÙˆØ¯ÙŠÙˆÙ„: {module}"
            code_type = "python"
            code = """# Odoo 18 Server Action / Computed Logic
for record in records:
    # Ø­Ø³Ø§Ø¨ Ø§Ù„Ø­Ù‚ÙˆÙ„ Ø¢Ù„ÙŠØ§Ù‹
    if record.amount_total > 0:
        record.message_post(body=f"ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ø§Ù„Ø¢Ù„ÙŠ Ù…Ù† Ø§Ù„ÙØ§ØªÙˆØ±Ø© Ø¨Ù…Ø¨Ù„Øº: {record.amount_total}")
"""
            solution = f"ØªÙ… Ø¥Ø¹Ø¯Ø§Ø¯ Ø§Ù„Ø£ØªÙ…ØªØ© Ø§Ù„Ø¨Ø±Ù…Ø¬ÙŠØ© Ù„Ù…ÙˆØ¯ÙŠÙˆÙ„ ({module}) Ù„ØªÙ†ÙÙŠØ° Ø§Ù„Ø¥Ø¬Ø±Ø§Ø¡ Ø§Ù„Ù…Ø·Ù„ÙˆØ¨ ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹ Ø¹Ù†Ø¯ Ø­ÙØ¸ Ø§Ù„Ø³Ø¬Ù„."

        return {
            'title': title,
            'solution_ar': solution,
            'code': code,
            'code_type': code_type,
            'recommended_actions': actions,
            'root_cause': root_cause,
        }
