# إعداد SaaS — Nexus Tenant & Billing

## نظرة عامة

هذا الدليل يشرح كيفية تشغيل طبقة الـ SaaS بعد تثبيت موديولات `nexus_saas_tenant` و `nexus_saas_billing`.

## الموديولات الجديدة

| الموديول | الوظيفة |
|---|---|
| `nexus_saas_tenant` | إنشاء المستأجرين (tenants)، الخطط (plans)، الاشتراكات، استهلاك الموارد، عزل البيانات |
| `nexus_saas_billing` | ربط Stripe: checkout، subscriptions، webhooks، فواتير داخلية |

## خطوات التفعيل

### 1. تثبيت الموديولات

```bash
# داخل حاوية Odoo
odoo -d nexus -u nexus_saas_tenant,nexus_saas_billing --stop-after-init
```

### 2. إنشاء الخطط

انتقل إلى **SaaS Platform → Plans** وأنشئ خططك أو استخدم الخطط الافتراضية (Free, Basic, Professional, Enterprise).

### 3. إعداد Cloudflare DNS

انتقل إلى **Settings → General Settings → Nexus SaaS** وأدخل:
- `Cloudflare API Token`
- `Cloudflare Zone ID` (اختياري — إذا تركته فارغاً يتم اكتشافه من Base Domain)
- `CNAME Target` (مثلاً `app.erp.example.com`)

عند إنشاء مستأجر جديد، سيتم إنشاء سجل CNAME تلقائياً:

```
acme.erp.example.com  CNAME  app.erp.example.com
```

### 4. إعداد Stripe

انتقل إلى **Settings → General Settings → Nexus SaaS Billing**:
- `Stripe Secret Key`
- `Stripe Publishable Key`
- `Stripe Webhook Secret`

### 5. إعداد Webhook في Stripe

أضف endpoint:

```
https://erp.example.com/saas/billing/stripe/webhook
```

Events to send:
- `checkout.session.completed`
- `invoice.paid`
- `invoice.payment_failed`
- `customer.subscription.past_due`
- `customer.subscription.deleted`

### 6. تفعيل التسجيل الذاتي

في **Settings → General Settings → Nexus SaaS**:
- فعّل **Self-Service Signup**.
- اكتب **SaaS Base Domain** (مثلاً `nexus-engine.app`).

### 7. اختبار التسجيل

```bash
curl -X POST https://erp.example.com/saas/signup \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme LLC",
    "code": "acme",
    "email": "admin@acme.com",
    "password": "StrongPass123",
    "plan_code": "basic"
  }'
```

## عزل المستأجرين

### على مستوى custom models

- `nexus.saas.tenant`
- `nexus.saas.subscription`
- `nexus.saas.usage.record`
- `nexus.saas.billing.invoice`

كلها محمية بـ `ir.rule` بحيث يستطيع المستخدم رؤية سجلات tenant الخاص به فقط، بينما `base.group_system` يرى الكل.

### على مستوى res.company / res.users

- كل شركة تنتمي إلى `saas_tenant_id`.
- كل مستخدم ينتمي إلى `saas_tenant_id`.
- `res_users.py` يمنع المستخدم من الانتماء لشركة خارج tenant الخاص به.

## الحصص (Quotas)

يتم التحقق من الحصص عبر:
- `tenant.check_user_quota()`
- `tenant.check_company_quota()`
- `tenant.check_product_quota()`
- `tenant.check_invoice_quota()`

## المزامنة مع Stripe

- cron يومي `SaaS Billing: sync Stripe subscriptions`
- webhooks فورية لـ paid/failed/cancelled

## ملاحظات أمنية

1. `saas_stripe_secret_key` و `saas_stripe_webhook_secret` مخزّنتان في `ir.config_parameter` مع `password=True`.
2. webhook controller يتحقق من توقيع Stripe قبل معالجة أي حدث.
3. لا تقم أبداً بتفعيل `self_service_signup` بدون reCAPTCHA أو rate limiting في nginx.
