# معمارية المحاسبة الهجينة (Odoo ↔ ERPNext) — Nexus Engine

> هذا المستند يوثّق النموذج المعماري **الموجود فعلاً** في الكود (وليس اقتراحاً جديداً).
> الهدف: توضيح كيف يُستخدم ERPNext كمحرك محاسبي أساسي وغني، بينما يبقى Odoo هو
> الواجهة التشغيلية (POS، المبيعات، المخزون، الموارد البشرية) — مع خارطة طريق
> للأخطاء المعروفة وحالة الإصلاح الحالية.

---

## 1. الفكرة الأساسية: Dual-Ledger مع مطابقة (Reconciliation)

المشروع **لا** يستبدل محاسبة Odoo بمحاسبة ERPNext، بل يبنيهما معاً كدفترين
متوازيين مع آلية مطابقة (drift detection):

```
┌─────────────────────────┐        push (async, idempotent)        ┌──────────────────────────┐
│           Odoo           │ ────────────────────────────────────▶ │   ERPNext (Nexus Core)    │
│  الواجهة التشغيلية        │        nexus.sync.queue                │  المحرك المحاسبي الغني     │
│  - POS / المبيعات        │ ◀──────────────────────────────────── │  - دليل حسابات عميق       │
│  - المخزون / HR          │        pull (reports, on-demand)       │  - مراكز تكلفة            │
│  - فوترة أولية + ترحيل   │                                         │  - أصول ثابتة             │
│    محلي (account.move)  │        reconciliation (nightly cron)   │  - تقارير مالية شاملة      │
└─────────────────────────┘ ◀────────────────────────────────────▶ └──────────────────────────┘
```

**لماذا Odoo يحتاج دليل حسابات محلي حقيقي رغم وجود ERPNext؟**
لأن Odoo لا يستطيع ترحيل فاتورة (`account.move`) بدون حسابات حقيقية
(`account.account`) في قاعدة بياناته. الحل ليس حذف محاسبة Odoo، بل إبقاءها
**بسيطة وكافية فقط للترحيل المحلي**، بينما التقارير المالية العميقة (الميزانية،
قائمة الدخل، التدفقات) تُسحب من ERPNext.

---

## 2. الوحدات (Modules) ومسؤولية كل واحدة

| الوحدة | الدور |
|--------|-------|
| `odoo_erpnext_hybrid_sync` | الأساس: `hybrid.config` (بيانات الاتصال بـ ERPNext)، `nexus.sync.queue` (طابور دفع غير متزامن مع إعادة محاولة exponential backoff)، حقول `erpnext_synced` / `erpnext_docname` على `account.move` |
| `nexus_advanced_accounting` | يُرحّل الفواتير محلياً في Odoo (`_post()`) ثم يستدعي `nexus.sync.queue.enqueue()` لدفعها لـ ERPNext؛ يبني حمولات (payloads) الفواتير، الدفعات، الأصول، مراكز التكلفة، مطالبات المصاريف، وقوالب الضرائب |
| `ai_enterprise_copilot/erpnext_bridge*.py` | طبقة HTTP مباشرة مع ERPNext (SSRF-safe): `push_account_move`, `push_partner`, `push_payment`, إلخ. تُستخدم كمسار "دفع فوري" بديل عن الطابور، مع تراجع تلقائي (`_safe_push`) إلى `nexus.sync.queue` عند الفشل |
| `ai_enterprise_copilot/erpnext_reconciliation.py` | Cron ليلي يقارن الأرصدة/الذمم بين Odoo و ERPNext، ويفتح حادثة (`copilot.support.incident`) عند وجود انحراف |
| `ai_enterprise_copilot/nexus_finance_report.py` | معالج التقارير المالية: **يُفضّل ERPNext أولاً** (`bridge.run_finance_report`)، ويتراجع لمحرك محلي (`nexus.finance.report.renderer`) فقط عند تعذّر الاتصال |
| `nexus_saudi_localization` / `nexus_us_localization` | إضافات محلية (COA بسيط + ضرائب) تُنشأ الآن عبر `post_init_hook` (`hooks.py`) بدل قوالب `account.account.template`/`account.tax.template` المحذوفة في Odoo 17+ |

---

## 3. تدفق البيانات (مثال: فاتورة مبيعات)

1. المستخدم يُرحّل فاتورة في Odoo → `account.move._post()`
2. `nexus_advanced_accounting` يتحقق: هل الفاتورة مُزامنة سابقاً؟ إن لم تكن، يستدعي `_enqueue_invoice_sync()`
3. `nexus.sync.queue.enqueue(operation="invoice.create", ...)` يُنشئ سجل طابور (idempotent عبر `transaction_id` فريد)
4. Cron (`_cron_drain`) يسحب السجلات المعلّقة، يبني الحمولة (`_build_invoice_payload`)، ويرسلها لـ ERPNext عبر `/api/resource/Sales Invoice`
5. عند النجاح: `account.move.erpnext_synced = True`, `erpnext_docname = <اسم المستند في ERPNext>`
6. عند الفشل: إعادة محاولة بـ backoff تصاعدي (حتى 5 مرات)، ثم `state = "failed"` مع سبب الخطأ
7. الـ Cron الليلي للمطابقة (`nexus.erpnext.reconciliation`) يتحقق لاحقاً أن الأرصدة متطابقة

---

## 4. حالة الإصلاح الحالية (كما تم في هذه الجلسة)

### ✅ تم إصلاحه
- `ensure_one()` على AbstractModel فارغة (renderer, cache, excel_export) — كانت تفشل دائماً
- `nexus.sync.queue.enqueue()` يُستدعى بمعامل خاطئ (`resource=` بدل `endpoint=`) وبدون `company` المطلوب — في `erpnext_bridge.py` و `erpnext_bridge_extensions.py`
- استخدام حقل `nexus_erpnext_id` غير المعرّف على `account.move`/`account.account`/`res.partner`
- **دالة `push_account_move` كانت غير موجودة** على `nexus.erpnext.bridge.extensions` رغم استدعائها من `erpnext_bridge_listeners.py` (AttributeError عند كل ترحيل فاتورة)
- **دالة `_x()` غير معرّفة** في `erpnext_bridge.py._render_erpnext_payload` (AttributeError عند كل تقرير من ERPNext)
- XML ID مكرر (`access_nexus_finance_report_user`) بين CSV و XML يكسر تثبيت الموديول
- `dict(wizard.report_type)` بدل `dict(wizard._fields["report_type"].selection)`
- استيرادات ناقصة (`api`, `base64`) ومكسرة (`ValueError` بدل `ValidationError`)
- **`account.account.template` / `account.tax.template` محذوفة في Odoo 17+/18** — أُعيدت كتابتها كـ `post_init_hook` (`hooks.py`) يُنشئ `account.account`/`account.tax` حقيقية لكل شركة
- **`nexus_saudi_localization` و `nexus_us_localization` بلا `__init__.py` جذري إطلاقاً** — الموديولان لم يكونا قابلين للتحميل نهائياً قبل هذا الإصلاح

### ✅ تم إصلاحه (جلسة المراجعة الثانية)
- `nexus.erpnext.reconciliation._erpnext_period_totals` / `_erpnext_partner_totals` كانتا تستدعيان endpoints مخترعة (`nexus_core.finance.get_period_totals`, `get_open_balances`) **غير موجودة في أي ERPNext حقيقي** — كل فحص كان يفشل بصمت ويُبلّغ "مطابق تماماً" دائماً. استُبدلت بموارد ERPNext القياسية (`GL Entry`, `Account`, `Sales/Purchase Invoice`)
- أُضيف **إصلاح ذاتي (self-healing)** لـ `nexus.erpnext.reconciliation`: عند اكتشاف انحراف في رصيد عميل/مورد، تتم إعادة الدفع (`push_partner`) تلقائياً، وتُعلّم `drift_line` كـ `resolved=True` عند النجاح. إذا فشلت إعادة المزامنة أو تكرر نفس الانحراف (`drift_key`) لـ 3 دورات متتالية، يُفتح `copilot.support.incident` بدل التكرار الصامت إلى الأبد

### ⚠️ قرار معماري واعٍ: لن يتم توحيد VAT السعودي مع الجسر حالياً
راجعت هذا الخيار بعمق ووجدت أنه **خطر أكبر من فائدته حالياً**: لا يوجد أي نموذج "ربط حسابات" (Account Mapping) بين حسابات ضريبة القيمة المضافة في Odoo وحساباتها المقابلة في ERPNext (بعكس `nexus.tax.mapping` الموجود فعلياً للضرائب و`nexus.cost.center.mapping` لمراكز التكلفة). أي محاولة لجلب أرقام VAT من ERPNext ستعتمد على **تخمين أسماء حسابات** غير مضمونة الصحة — وهذا غير مقبول لتقرير له أثر قانوني مباشر (ZATCA). البديل المسؤول: إبقاء حساب VAT محلياً في Odoo كما هو (مصدر دقيق ومباشر من فواتير Odoo نفسها الخاضعة للفوترة الإلكترونية)، مع توثيق هذا القرار صراحة بدل فرض توحيد قسري.

**للتوحيد الآمن مستقبلاً**: يجب أولاً بناء نموذج `nexus.account.mapping` (شبيه بـ `nexus.tax.mapping`) يربط كل حساب Odoo بمعرّف حساب ERPNext الحقيقي، قبل محاولة جلب أرقام VAT من الجسر.

### ⚠️ لا يزال معروفاً وينتظر تنفيذاً
- لم يتم التحقق الشامل من أن كل مسارات `push_*` (دفعات، أصول، مراكز تكلفة) تصل فعلياً وبدون أخطاء صامتة لـ ERPNext (راجع نمط `except Exception: pass` المنتشر في `_safe_push`) — تمت مراجعة التوقيعات فقط (`enqueue()` صحيح الآن)، وليس التنفيذ الفعلي على بيئة حية
- لم يتم اختبار أي من هذا على نسخة Odoo 18 / ERPNext v15 حيّة فعلياً (لا تتوفر بيئة تشغيل مباشرة في هذه الجلسات)

---

## 5. التوصية المعمارية للمستقبل

1. **إبقاء Odoo "خفيفاً" محاسبياً**: لا تُضف تقارير مالية عميقة جديدة في Odoo؛ وجّه أي تقرير جديد ليمر عبر `nexus.erpnext.bridge` أولاً بنفس نمط `nexus_finance_report.py`
2. **توحيد نمط push**: يُفضّل الاعتماد على `nexus.sync.queue` (الطابور) كمسار وحيد للدفع بدل ازدواجية `erpnext_bridge_extensions._safe_push` (دفع فوري + طابور احتياطي)، لتفادي حالات السباق (race conditions) بين المسارين
3. **تسجيل صريح للفشل الصامت**: أي `except Exception: pass` في مسارات مالية يجب أن يسجّل (`_logger.error`) على الأقل، حتى لو لم يوقف المعاملة
4. **اختبار حقيقي أولوية قصوى**: قبل الإنتاج، يجب تشغيل دورة كاملة (فاتورة → دفع → مطابقة) على بيئة Odoo 18 + ERPNext v15 فعلية للتحقق من صحة كل الإصلاحات أعلاه
