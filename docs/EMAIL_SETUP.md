# Nexus Universal Email Setup — معالج ربط البريد الشامل

نظام متكامل ومدمج في Odoo لربط أي بريد إلكتروني بخطوة واحدة عبر **كلمات مرور التطبيقات (App Passwords)** دون الحاجة إلى حجز دومين أو إعدادات OAuth معقدة.

---

## 🚀 كيفية استخدام المعالج المدمج داخل Odoo

1. افتح نظام Odoo: `http://148.116.78.77:8069`
2. اذهب إلى **الإعدادات (Settings) ⬅️ Nexus Mail ⬅️ فتح معالج إعداد البريد الشامل**
   *(أو من القائمة: Settings ⬅️ Technical ⬅️ Universal Mail Setup)*
3. اختر **مزود البريد** الخاص بك.
4. اضغط على زر **🔗 فتح صفحة استخراج كلمة المرور** لاستخراج رمز الـ 16 حرفاً بضغطة واحدة.
5. ضع بريدك والرمز واضغط **⚡ حفظ واختبار وتفعيل البريد الآن**.

---

## 📋 الروابط المباشرة والإعدادات المسبقة لجميع المنصات

### 1. Google (Gmail / Google Workspace)
- **الرابط المباشر لاستخراج كلمة المرور:** [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- **البريد الصادر (SMTP):** `smtp.gmail.com` | المنفذ: `587` | التشفير: `STARTTLS`
- **البريد الوارد (IMAP):** `imap.gmail.com` | المنفذ: `993` | التشفير: `SSL/TLS`

---

### 2. Microsoft (Outlook / Hotmail / Live / Office 365)
- **الرابط المباشر لاستخراج كلمة المرور:** [https://account.live.com/proofs/AppPassword](https://account.live.com/proofs/AppPassword)
  *(أو لحسابات المؤسسات Office 365: [https://mysignins.microsoft.com/security-info](https://mysignins.microsoft.com/security-info))*
- **البريد الصادر (SMTP):** `smtp.office365.com` | المنفذ: `587` | التشفير: `STARTTLS`
- **البريد الوارد (IMAP):** `outlook.office365.com` | المنفذ: `993` | التشفير: `SSL/TLS`

---

### 3. Apple iCloud (@icloud.com / @me.com)
- **الرابط المباشر لاستخراج كلمة المرور:** [https://appleid.apple.com/account/manage/section/security](https://appleid.apple.com/account/manage/section/security)
- **البريد الصادر (SMTP):** `smtp.mail.me.com` | المنفذ: `587` | التشفير: `STARTTLS`
- **البريد الوارد (IMAP):** `imap.mail.me.com` | المنفذ: `993` | التشفير: `SSL/TLS`

---

### 4. Yahoo Mail (@yahoo.com)
- **الرابط المباشر لاستخراج كلمة المرور:** [https://login.yahoo.com/account/security](https://login.yahoo.com/account/security)
- **البريد الصادر (SMTP):** `smtp.mail.yahoo.com` | المنفذ: `587` | التشفير: `STARTTLS`
- **البريد الوارد (IMAP):** `imap.mail.yahoo.com` | المنفذ: `993` | التشفير: `SSL/TLS`

---

### 5. Zoho Mail
- **الرابط المباشر لاستخراج كلمة المرور:** [https://accounts.zoho.com/home#security/app_passwords](https://accounts.zoho.com/home#security/app_passwords)
- **البريد الصادر (SMTP):** `smtppro.zoho.com` | المنفذ: `587` | التشفير: `STARTTLS`
- **البريد الوارد (IMAP):** `imappro.zoho.com` | المنفذ: `993` | التشفير: `SSL/TLS`

---

### 6. بريد خاص للشركات (Custom Domain / cPanel / Webmail / Private Server)
- يدعم المعالج التعرف التلقائي على خوادم النطاق بمجرد إدخال بريدك (مثل `info@company.com` ⬅️ يتعرف تلقائياً على `mail.company.com`).
- **المنافذ القياسية المدعومة:**
  - SMTP: `587` (STARTTLS) أو `465` (SSL)
  - IMAP: `993` (SSL)

---

## 🛠️ الموديول البرمجي المخصص: `nexus_universal_mail`
تم إنشاء وتثبيت موديول `nexus_universal_mail` على السيرفر ويشمل:
1. `models/universal_mail_wizard.py`: معالج تفاعلي لاختبار وتهيئة `ir.mail_server` و `fetchmail.server` وإرسال إيميل تأكيد فوري.
2. `views/universal_mail_wizard_views.xml`: واجهة رسومية سلسة وزر لفتح رابط مزود البريد في نافذة جديدة.
3. `views/res_config_settings_views.xml`: زر وصول سريع في الإعدادات العامة لـ Odoo.
