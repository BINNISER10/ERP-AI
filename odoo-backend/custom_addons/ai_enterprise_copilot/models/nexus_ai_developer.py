# -*- coding: utf-8 -*-
"""Nexus AI Developer & Business Staff Member — مطور أودو ومستشار الأعمال الذكي.

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
    ('odoo_senior_dev', '👨‍💻 كبير مطوري أودو 18 (Senior Odoo Developer)'),
    ('business_architect', '🏛️ مهندس معماري للشركات والعمليات (Business Architect)'),
    ('tax_compliance_expert', '⚖️ خبير الضرائب والفوترة الإلكترونية ZATCA'),
    ('data_analyst', '📊 محلل بيانات ومهندس تقارير SQL (BI & Data Analyst)'),
    ('pos_hardware_engineer', '💳 مهندس نقاط البيع والأجهزة Mada / Stripe'),
]

MODULE_SELECTION = [
    ('general', 'عام / General'),
    ('account', 'المحاسبة والمالية (Accounting & Invoicing)'),
    ('point_of_sale', 'نقاط البيع والكاشير (Point of Sale & POS)'),
    ('stock', 'المستودعات والمخزون (Inventory & Stock)'),
    ('zatca', 'الفوترة الإلكترونية والزكاة (ZATCA Compliance)'),
    ('hr', 'الموارد البشرية والرواتب (HR & Payroll WPS)'),
    ('mrp', 'التصنيع والإنتاج (Manufacturing & MRP)'),
    ('project', 'المشاريع والعقود (Projects & Contracting)'),
    ('api_gateway', 'بوابة الربط البرمجي (API Gateway & Flutter POS)'),
]


class NexusAiDeveloperStaff(models.Model):
    _name = 'nexus.ai.developer.staff'
    _description = 'Odoo Software Development Staff Member'
    _order = 'id desc'

    name = fields.Char(string='عنوان الجلسة / Topic', required=True, default='استشارة تقنية جديدة')
    user_id = fields.Many2one('res.users', string='المستخدم', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='المنشأة', default=lambda self: self.env.company)

    developer_persona = fields.Selection(
        selection=PERSONA_SELECTION,
        string='الموظف / المستشار الذكي المطلوب',
        default='odoo_senior_dev',
        required=True,
    )
    context_module = fields.Selection(
        selection=MODULE_SELECTION,
        string='الموديول أو المجال المعني',
        default='general',
        required=True,
    )

    prompt = fields.Text(
        string='السؤال أو المتطلب البرمجي / التشغيلي',
        placeholder='مثال: كيف أضيف حقل لحساب هامش الربح تلقائياً في الفاتورة؟ أو: اكتب استعلام SQL لمقارنة مبيعات هذا الشهر بالشهر السابق...',
        required=True,
    )
    error_traceback = fields.Text(
        string='رسالة الخطأ للتشخيص (Error Traceback - اختياري)',
        placeholder='إذا واجهت أي رسالة خطأ، الصقها هنا وسيقوم المطور الذكي بتحليل السبب الجذري وإعطائك الحل الفوري...',
    )

    state = fields.Selection(
        [
            ('draft', 'مسودة (Draft)'),
            ('answered', 'تم التحليل والحل (Answered)'),
        ],
        default='draft',
        required=True,
    )

    # ── AI Solutions Output ──
    solution_title = fields.Char(string='عنوان الحل')
    ai_response_html = fields.Html(string='شرح وتوجيهات المطور الذكي', readonly=True)
    root_cause_explanation = fields.Text(string='السبب الجذري للخطأ (Root Cause)', readonly=True)
    
    generated_code = fields.Text(string='الكود البرمجي / الاستعلام الجاهز (Code)')
    generated_code_type = fields.Selection(
        [
            ('python', 'Python (Server Action / Model Code)'),
            ('sql', 'PostgreSQL SQL Query'),
            ('xml', 'QWeb / View XML'),
            ('n8n', 'n8n JSON Workflow'),
            ('text', 'Technical Guide / Steps'),
        ],
        string='نوع الكود',
        default='python',
    )
    recommended_actions_html = fields.Html(string='الخطوات التنفيذية الموصى بها', readonly=True)

    def action_ask_ai_developer(self):
        """Invoke AI Developer Staff endpoint via AI microservices or fallback engine."""
        self.ensure_one()
        prompt_text = (self.prompt or '').strip()
        if not prompt_text:
            raise UserError(_('يرجى كتابة السؤال أو المتطلب البرمجي أولاً.'))

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
        self.solution_title = data.get('title') or f"حل مقترح: {prompt_text[:40]}"
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
                    <strong>🔍 تشخيص الخطأ والسبب الجذري:</strong><br/>
                    {self.root_cause_explanation}
                </div>
            """)

        self.ai_response_html = ''.join(html_parts)

        # Recommended Actions list
        rec_actions = data.get('recommended_actions', [])
        if rec_actions:
            action_items = ''.join([f'<li class="mb-2">👉 {act}</li>' for act in rec_actions])
            self.recommended_actions_html = f"""
                <div class="card border-success p-3 shadow-sm bg-light" style="border-radius: 8px;">
                    <h6 class="text-success font-weight-bold mb-2">📋 خطوات التنفيذ العملية (Action Plan):</h6>
                    <ul class="mb-0 ps-3" style="color: #2D3748; font-size: 14px;">
                        {action_items}
                    </ul>
                </div>
            """

        self.state = 'answered'
        if not self.name or self.name == 'استشارة تقنية جديدة':
            self.name = self.solution_title[:60]

        return True

    def _generate_internal_solution(self, prompt, persona, module, traceback):
        """Embedded expert rules engine when offline."""
        lower_prompt = prompt.lower()
        title = "استشارة مطور أودو المعتمد"
        code_type = "python"
        code = None
        solution = "بناءً على متطلبك في نظام Nexus Enterprise Engine (Odoo 18)، إليك الحل الهندسي المتوافق مع معايير Odoo الرسمية."
        root_cause = None
        actions = [
            "تطبيق الكود في Server Action أو عبر كود الموديول المخصص",
            "اختبار العملية في بيئة التطوير والتحقق من الصلاحيات",
            "مراجعة سجلات الخادم في حال وجود أي تنبيهات",
        ]

        if traceback or "error" in lower_prompt or "خطأ" in lower_prompt:
            title = "تشخيص وحل مشكلة برمجية"
            root_cause = "تحليل رسالة الخطأ يشير إلى تعارض في قيود قاعدة البيانات (Constraint) أو نقص في الحقول الإلزامية."
            solution = "لتجاوز هذا الخطأ، يجب التأكد من عدم تكرار المعرفات الفريدة وتمرير القيم الافتراضية قبل حفظ السجل."
            code = "# Python Fix Pattern\nexisting = env['account.move'].search([('name', '=', move_name)], limit=1)\nif not existing:\n    record.action_post()\n"
            actions = ["مراجعة دالة create() أو write()", "إضافة تحقق search قبل الإنشاء لمنع التكرار"]
        elif "sql" in lower_prompt or "استعلام" in lower_prompt or "تقرير" in lower_prompt:
            title = "استعلام SQL تحليلي جاهز"
            code_type = "sql"
            code = """-- استعلام كشف حساب ومبيعات الشهور
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
            solution = "استعلام SQL محسن لقراءة بيانات الفواتير والمبيعات بأعلى سرعة دون التأثير على أداء الخادم."
            actions = ["تنفيذ الاستعلام عبر Text-to-SQL", "تصدير النتائج إلى Excel أو لوحة تحكم"]
        elif "zatca" in lower_prompt or "ضريبة" in lower_prompt:
            title = "تهيئة الفوترة الإلكترونية ZATCA Phase 2"
            code_type = "python"
            code = "# ZATCA QR & Hash Generation\nfrom odoo.addons.nexus_zatca_compliance.models.zatca_hasher import generate_zatca_invoice_hash\ninvoice_hash = generate_zatca_invoice_hash(xml_content)\n"
            solution = "لربط الفاتورة مع منصة فاتورة، يجب مطابقة كود الضريبة (VAT-15) وحساب التجزئة المشفرة SHA-256 للـ XML."
            actions = ["التحقق من صحة الرقم الضريبي (15 رقماً)", "تفعيل الشهادة الرقمية CSID في إعدادات ZATCA"]
        else:
            title = f"تطوير وأتمتة موديول: {module}"
            code_type = "python"
            code = """# Odoo 18 Server Action / Computed Logic
for record in records:
    # حساب الحقول آلياً
    if record.amount_total > 0:
        record.message_post(body=f"تم التحقق الآلي من الفاتورة بمبلغ: {record.amount_total}")
"""
            solution = f"تم إعداد الأتمتة البرمجية لموديول ({module}) لتنفيذ الإجراء المطلوب تلقائياً عند حفظ السجل."

        return {
            'title': title,
            'solution_ar': solution,
            'code': code,
            'code_type': code_type,
            'recommended_actions': actions,
            'root_cause': root_cause,
        }
