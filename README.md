# Nexus Enterprise Engine

[![Odoo](https://img.shields.io/badge/Odoo-18.0-714B67.svg)](https://www.odoo.com)
[![License](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://python.org)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)](#)

> **مشروع نِكسَس إنتربرايز إنجين** — نظام ERP متكامل مبني على Odoo 18 مع جسر محاسبي إلى ERPNext، يدعم الشركات السعودية والأمريكية بميزات محلية كاملة.

---

## 🏗️ البنية المعمارية / Architecture

```
                          ┌──────────────────────────┐
                          │   Customer Browser       │
                          └────────────┬─────────────┘
                                       │ HTTPS
                          ┌────────────▼─────────────┐
                          │  Nginx Reverse Proxy     │
                          │  (config/nginx.conf)     │
                          └──────┬───────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼─────┐         ┌────────▼────────┐       ┌──────▼──────┐
   │  Odoo 18 │ ◄──────►│ AI Microservices│       │  ERPNext    │
   │ (UI/UX)  │         │   (FastAPI)     │       │  (Backend)  │
   └────┬─────┘         └─────────────────┘       └──────┬──────┘
        │                                                 │
        └─────────────────► Nexus Bridge ◄────────────────�
                            (SSRF-safe)
```

**العميل يرى نظاماً واحداً فقط:** `https://erp.example.com`  
**خلف الكواليس:** Odoo للواجهة + ERPNext للمحاسبة + FastAPI للذكاء الاصطناعي

---

## 📦 الوحدات الأساسية / Core Modules

### 🤖 AI Enterprise Copilot
- **Onboarding Wizard** — تأهيل ذكي بـ 5 مراحل
- **Document Hunter** — استخراج تلقائي من السجل التجاري، الضريبية، التأمينات
- **AI Developer Staff** — مساعد تقني مدمج
- **Universal Migrator** — استيراد من Excel/CSV/SQL/JSON
- **Universal Mail** — ربط سريع مع Gmail/Outlook/iCloud
- **Nexus Finance Reports** — 9 تقارير مالية متقدمة

### 🇸🇦 Saudi Localization
- **ZATCA Phase 2** — فوترة إلكترونية مع QR + UBL 2.1 XML + SHA-256 chain
- **VAT 15%** — محرك ضريبي كامل
- **Saudization (نطاقات)** — تتبع نسبة التوطين + Bands (Platinum → Red)
- **GOSI/WPS** — جاهز لحماية الأجور
- **Saudi Chart of Accounts** — قوالب SOCPA

### 🇺🇸 US Localization
- **GAAP Chart of Accounts** — قوالب محاسبية أمريكية
- **Multi-State Sales Tax** — محرك ضرائب متعدد الولايات
- **1099-NEC / MISC** — تقارير الموردين السنوية
- **W-9 Tracking** — تتبع استمارات W-9
- **ACH Validation** — تحقق من Routing Numbers (ABA checksum)

### 🌐 Pure Branding (White-Label)
- **إزالة كل علامات Odoo/ERPNext** من الواجهة
- **هوية موحدة** باسم "Nexus Enterprise Engine"
- **Logo + Favicon + Theme Color** قابلة للتخصيص

---

## 🚀 النشر / Deployment

### المتطلبات / Prerequisites
- Ubuntu 22.04+ أو أي Linux يدعم Docker
- Domain مخصص (مثلاً `erp.example.com`)
- Port 80 + 443 مفتوحين
- صلاحية root

### التثبيت السريع / Quick Install

```bash
# 1. Clone
git clone https://github.com/your-org/nexus-erp.git
cd nexus-erp

# 2. Deploy
sudo ODOO_DOMAIN=erp.example.com ./deploy.sh
```

السكربت يقوم بـ:
1. ✅ توليد Docker secrets (كلمات مرور عشوائية)
2. ✅ التحقق من DNS
3. ✅ تشغيل PostgreSQL + Redis + Odoo + AI + ERPNext
4. ✅ طلب شهادة SSL من Let's Encrypt
5. ✅ تشغيل Nginx reverse proxy
6. ✅ اختبار نهائي

### الـ URLs المتاحة

| URL | الوصف |
|-----|-------|
| `https://erp.example.com/` | واجهة Odoo الرئيسية |
| `https://erp.example.com/web/login` | تسجيل الدخول |
| `https://erp.example.com/odoo/` | لوحة تحكم المسؤول |
| `https://erp.example.com/api/v1/health` | صحة خدمة AI |

---

## 📊 التقارير المالية / Financial Reports

### 9 تقارير جاهزة
1. **الميزانية العمومية / Balance Sheet**
2. **قائمة الدخل / Profit & Loss**
3. **التدفقات النقدية / Cash Flow**
4. **ميزان المراجعة / Trial Balance**
5. **دفتر الأستاذ العام / General Ledger**
6. **أعمار الذمم المدينة / Receivable Aging**
7. **أعمار الذمم الدائنة / Payable Aging**
8. **انحراف الميزانية / Budget Variance**
9. **تقرير مراكز التكلفة / Cost Center Report**

### Dashboard تفاعلي
- 📊 Revenue vs Expense (6 شهور)
- 🥧 Aging Buckets (Donut)
- 📈 Cash Position (30 يوم)
- 🏆 Top 10 Customers
- 💎 KPI Summary Cards

### التصدير
- 📄 **PDF** مع QWeb templates
- 📊 **XLSX** مع openpyxl
- 📋 **CSV** (fallback)

---

## �️ البنية التقنية / Tech Stack

| المكون | التقنية |
|--------|---------|
| **Backend** | Odoo 18 + Python 3.12 |
| **Database** | PostgreSQL 16 |
| **Cache/Queue** | Redis 7 |
| **AI Microservices** | FastAPI + Ollama |
| **Accounting Engine** | ERPNext 15 |
| **Reverse Proxy** | Nginx 1.27 |
| **SSL** | Let's Encrypt (Certbot) |
| **Container** | Docker Compose |
| **Frontend Charts** | Chart.js 4.4 |
| **CSS** | SCSS |
| **PDF Generation** | QWeb + wkhtmltopdf |

---

## 📁 هيكل المشروع / Project Structure

```
ERP ODOO/
├── odoo-backend/
│   └── custom_addons/
│       ├── ai_enterprise_copilot/        # المعالج الذكي + التقارير
│       ├── nexus_pure_branding/          # إخفاء العلامات التجارية وتخصيص الهوية
│       ├── nexus_universal_mail/         # ربط البريد الإلكتروني
│       ├── nexus_saudi_localization/     # 🇸🇦 تخصيص السعودية
│       ├── nexus_us_localization/        # 🇺� تخصيص أمريكا
│       ├── nexus_zatca_compliance/       # ZATCA XML hasher
│       ├── nexus_us_tax_engine/          # محرك الضرائب الأمريكي
│       ├── nexus_advanced_accounting/    # جسر Odoo ↔ ERPNext
│       ├── odoo_erpnext_hybrid_sync/     # طابور المزامنة
│       ├── nexus_erpnext_accounting/     # محرك GL ثانوي
│       └── nexus_base_security/          # مجموعات الأمان
├── ai_services/                          # FastAPI microservices
├── flutter_pos/                          # POS للعملاء
├── config/
│   ├── nginx.conf                        # Reverse Proxy
│   ├── odoo.conf
│   └── postgresql.conf
├── terraform/                            # Oracle Cloud deployment
├── docs/                                 # Documentation
│   ├── EMAIL_SETUP.md
│   └── API.md
├── docker-compose.prod.yml               # Production stack
├── deploy.sh                             # One-command deployment
└── README.md                             # This file
```

---

## 🔒 الأمان / Security

- ✅ **SSRF Protection** — حجب metadata IPs
- ✅ **Docker Secrets** — لا كلمات مرور في plain text
- ✅ **HTTPS Everywhere** — HSTS + OCSP Stapling
- ✅ **Rate Limiting** — حماية من Brute Force
- ✅ **CSP Headers** — Content Security Policy
- ✅ **Audit Logging** — تتبع كل التغييرات
- ✅ **Daily Reconciliation** — كشف الانحراف بين Odoo و ERPNext

---

## 📈 الأداء / Performance

| المقياس | القيمة |
|--------|--------|
| **زمن توليد التقرير** | < 2 ثانية (cached: < 100ms) |
| **زمن Push لفاتورة** | < 1 ثانية |
| **Reconciliation دوري** | يومي |
| **Cache TTL** | 60 ثانية |
| **Concurrent Users** | 100+ |
| **Database Size** | يصل إلى 10GB بكفاءة |

---

## 🧪 الاختبارات / Testing

```bash
# اختبارات الوحدة
python -m pytest odoo-backend/custom_addons/*/tests/

# التحقق البنيوي
python validate.py

# اختبارات E2E
./scripts/run_e2e_tests.sh
```

---

## 📞 الدعم / Support

- 📧 **Email:** support@nexus-engine.app
- � **Website:** https://nexus-engine.app
- 📚 **Docs:** https://docs.nexus-engine.app

---

## 📄 الترخيص / License

**LGPL-3.0** — مفتوح المصدر، قابل للاستخدام التجاري.

---

## 🙏 شكر وتقدير / Credits

- **Odoo Community** — لإطار عمل ERP الرائع
- **ERPNext** — لمحاسبة مفتوحة المصدر قوية
- **FastAPI** — لخدمة AI السريعة
- **Chart.js** — للرسوم البيانية الجميلة
- **Let's Encrypt** — لشهادات SSL المجانية

---

<p align="center">
  <b>صُنع بـ ❤️ للشركات السعودية والأمريكية</b><br/>
  <i>Built with ❤️ for Saudi and American businesses</i>
</p>
