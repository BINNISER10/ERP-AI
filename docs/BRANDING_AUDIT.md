# تدقيق العلامة التجارية (White-Label Audit) — Nexus

## الوضع بعد هذه الجلسة

الموديول المعتمد الوحيد للعلامة التجارية الآن: **`nexus_pure_branding`**
(كان هناك موديولان متعارضان: `nexus_hybrid_branding` + `nexus_pure_branding`،
بالإضافة إلى ملف منفصل `ai_enterprise_copilot/views/hide_upgrade_buttons.xml`.
تم دمج كل شيء في `nexus_pure_branding` وتعطيل `nexus_hybrid_branding`
(`installable: False`) لمنع تعارض الـ xpath إذا ثُبّت الاثنان معاً.)

### ما يغطيه `nexus_pure_branding` الآن
- عنوان الصفحة + الأيقونة (favicon) + touch-icon + theme-color
- صفحة تسجيل الدخول (`web.login_layout`) — إزالة رابط odoo.com
- `web.brand_promotion` — إخفاء بالكامل
- بوابة العملاء (`portal.portal_record_sidebar`)
- كل بريد إلكتروني صادر (`mail.mail_notification_layout` / `_light`)
- إعدادات عامة: إزالة widget "Odoo Community/Enterprise Edition" وشارات المتجر
- تعطيل حقل `upgrade_boolean` (لا يفتح نافذة ترويج Enterprise)
- إزالة زر/رابط الترقية المدفوعة من بطاقة الموديول في `Settings > Apps`
- `session_info` — يُخفي رقم/اسم إصدار Odoo من استجابة الجلسة (كان يُنتج تناقض HTML رأيته وأصلحته)
- صفحة معلومات الموقع (`website.show_website_info` / `website_info` / `layout` meta generator) — تتطلب الآن تبعية `website`
- JS runtime sanitizer: يفحص كل 3 ثوانٍ عنوان الصفحة والأيقونة ويستبدل أي "Odoo/ERPNext/Frappe" تلقائياً (شبكة أمان أخيرة)

### تسريبات إضافية أُصلحت خارج موديولات العلامة التجارية
| الملف | كان | أصبح |
|-------|-----|------|
| `flutter_pos/.../checkout_screen.dart` | `'Pay & Post to Odoo'` | `'Pay & Complete Order'` |
| `flutter_pos/.../odoo_jsonrpc.dart` | `'Odoo error: ...'` | `'Server error: ...'` |
| `ai_services/.../ai_assistant.py` | رد احتياطي يذكر "Odoo Developer Staff" و"Odoo 18" | يذكر "فريق مطوري Nexus" و"Nexus Enterprise Engine" |

## قيود معروفة (لا يمكن حلها بالكامل ضمن هذا النطاق)
- **أسماء تطبيقات Odoo الجوهرية** في `Settings → Apps` (Point of Sale, Accounting, Sales...) هي تسميات النواة نفسها. تغييرها بالكامل يتطلب استبدال ملفات ترجمة `base`/`account`/... بأكملها — خارج نطاق "إخفاء علامة تجارية" وقد يخالف روح رخصة LGPL-3 (نسب العمل الأصلي).
- الأسماء التقنية الداخلية للحقول/الموديولات (`odoo_tax_id`, `OdooJsonRpcClient`, `odoo_erpnext_hybrid_sync`) غير مرئية للمستخدم العادي (بعضها يظهر فقط في Developer Mode) ولم تُغيَّر عمداً لتفادي مخاطر الترحيل (migration).
- لم يتم اختبار أي من overrides الـ QWeb الجديدة على نسخة Odoo 18 حية (لا تتوفر بيئة تشغيل هنا). يُنصح بتثبيت `nexus_pure_branding` على بيئة اختبار والتحقق يدوياً من: صفحة تسجيل الدخول، `Settings → General Settings`، بريد إلكتروني تجريبي، `Settings → Apps`.
