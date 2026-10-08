# Service Request Management Platform

**Web platform + two Telegram bots + Claude AI** for handling citizen/employee service requests end to end — built for a government organization in Uzbekistan from its technical specification.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-black) ![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0) ![tests](https://img.shields.io/badge/tests-134-brightgreen)

## How it works

```
Customer ──► Telegram Bot #1 ──► Web platform (Flask) ──► AI module (Claude)
                                      │  categorises, prioritises, drafts reply
                                      ▼
                    Dispatcher assigns ──► Telegram Bot #2 ──► Executor
                                      │
                         notifier.py ─┴─► deadline / SLA alerts via Telegram
```

## Features

- **Two bots** — customers submit and track requests and rate the service; executors see only their own tasks, report progress and close them.
- **AI triage (Claude)** — auto category and priority, summary, draft reply, delay-risk estimate, management digest.
- **Dispatcher panel** — filters, search, assignment, comments, full status lifecycle (new → … → closed/rejected).
- **6 roles with RBAC** — super admin, administrator, dispatcher, department head, executor, observer; audit log.
- **SLA & alerts** — deadlines per category, overdue detection, Telegram reminders before and after deadline.
- **Analytics** — KPI cards and Chart.js dashboards (trend, top categories, SLA, departments); Excel/PDF export.
- **Production setup** — internal REST API secured with service token, Celery + Redis, Docker/docker-compose, Gunicorn, Prometheus metrics, rate limiting, Swagger docs, Railway config.

## Stack

Flask 3 · SQLAlchemy · PostgreSQL · aiogram 3 · Anthropic Claude · Celery · Redis · openpyxl / ReportLab · Docker · pytest (134 tests)

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # DB, bot tokens, ANTHROPIC_API_KEY
python scripts/seed.py      # creates the first admin
python run.py               # http://localhost:5000
python bots/customer_bot.py & python bots/executor_bot.py & python bots/notifier.py
```

---

*Batafsil o'zbekcha qo'llanma quyida.*

# Xizmat kўrsatish jarayonlarini boshqarish platformasi

Texnik topshiriq (TZ) asosida qurilgan to'liq tizim: veb-boshqaruv platformasi, ikkita Telegram bot
(mijozlar va ijrochilar uchun) va sun'iy intellekt integratsiyasi.

## 1. Arxitektura

```
Mijoz → Telegram Bot №1 → Web Platform (Flask) → AI moduli (Anthropic Claude)
                                   ↓
                          Telegram Bot №2 → Ijrochi
                                   ↓
                      Bildirishnoma workeri (notifier.py)
```

- **Web platforma** — Flask + SQLAlchemy + Flask-Login, admin/dispatcher panel, dashboard, hisobotlar.
- **Bot №1 (customer_bot.py)** — mijozlar murojaat qoldiradi, holatini kuzatadi, xizmatni baholaydi.
- **Bot №2 (executor_bot.py)** — ijrochilar topshiriqlarni qabul qiladi, bajaradi, hisobot beradi.
- **AI moduli (app/ai/service.py)** — matnni tahlil qilib kategoriya/ustuvorlikni aniqlaydi, xulosa va
  dastlabki javob tayyorlaydi, rahbar uchun umumiy tahlil yozadi.
- **notifier.py** — muddat va yangi hodisalar bo'yicha Telegram orqali avtomatik xabar yuboradi.
- Botlar va veb-platforma bir-biri bilan **ichki REST API** (`/api/...`) orqali, `X-Internal-Token` bilan
  himoyalangan holda gaplashadi — bu TZ'dagi arxitektura chizmasiga mos.

## 2. Loyihaning tuzilishi

```
service_platform/
├── app/
│   ├── models.py            — barcha ma'lumotlar bazasi modellari
│   ├── auth/                — kirish/chiqish
│   ├── admin/                — kategoriyalar, xodimlar, bo'limlar, audit
│   ├── dispatcher/           — murojaatlarni boshqarish (asosiy operator paneli)
│   ├── dashboard/            — KPI, grafiklar, AI xulosalari
│   ├── reports/              — Excel/PDF eksport
│   ├── api/                  — botlar uchun ichki REST API
│   ├── ai/service.py         — Claude (Anthropic) orqali AI tahlil
│   └── templates/, static/
├── bots/
│   ├── customer_bot.py       — Bot №1
│   ├── executor_bot.py       — Bot №2
│   ├── notifier.py           — bildirishnoma/eslatma workeri
│   └── api_client.py         — botlar uchun umumiy HTTP klient
├── scripts/seed.py           — boshlang'ich ma'lumotlar (super admin, kategoriyalar)
├── config.py, run.py, requirements.txt, Procfile, .env.example
```

## 3. O'rnatish (lokal)

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env faylini to'ldiring: FLASK_SECRET_KEY, DATABASE_URL, bot tokenlari, ANTHROPIC_API_KEY va h.k.

python scripts/seed.py             # bazani yaratadi + super admin (parol: ADMIN_PASSWORD yoki tasodifiy, konsolda chiqadi)
python run.py                      # veb-platforma http://localhost:5000 da ishga tushadi
```

Botlarni alohida terminal oynalarida ishga tushiring:

```bash
python bots/customer_bot.py
python bots/executor_bot.py
python bots/notifier.py
```

> **Muhim:** birinchi kirishdan so'ng super admin parolini albatta o'zgartiring
> (Xodimlar bo'limi orqali yangi parol bilan yangi super admin yarating yoki DB orqali yangilang).


## 4. TZ bandlari va tizimdagi joylashuvi

| TZ bandi | Amalga oshirilishi |
|---|---|
| 3.1 Avtorizatsiya | `app/auth` — login/parol, Flask-Login sessiyasi |
| 3.2 Rollar | `RoleEnum` (`super_admin`, `administrator`, `dispatcher`, `bolim_rahbari`, `ijrochi`, `kuzatuvchi`) |
| 3.3 Kategoriyalar | `app/admin/routes.py` — `categories()`, ota/bola kategoriya tuzilmasi |
| 4. Murojaat holatlari | `RequestStatus` enum — yangi → ... → yopildi/rad etildi |
| 5. Dispetcher paneli | `app/dispatcher/routes.py` — filtr, qidiruv, tayinlash, izoh |
| 6. Ijrochilar | `User` modeli (rol=ijrochi) + `workload`, `KPIRecord` |
| 7. Muddatlar | `ServiceRequest.deadline_at`, `is_overdue` property, SLA konfiguratsiyasi (`config.py`) |
| 8. Avtomatik ogohlantirish | `bots/notifier.py` — muddat oldidan/keyin, yangi murojaat, javob kelganda |
| 9. Hisobotlar | `app/reports` — Excel (openpyxl) va PDF (reportlab) eksport |
| 10. Dashboard | `app/dashboard` — KPI kartalar, Chart.js grafiklar (dinamika, TOP, SLA, bo'limlar) |
| 11-12. KPI/Analitika | `KPIRecord` modeli, `predict_delay_risk()` (app/ai/service.py) |
| 13. AI integratsiya | `app/ai/service.py` — Claude (Anthropic) orqali kategoriya/ustuvorlik/xulosa/javob |
| 14. Bot №1 | `bots/customer_bot.py` |
| 15. Bot №2 | `bots/executor_bot.py` (har ijrochi faqat o'ziga tegishli ishlarni ko'radi) |
| 16. Qo'shimcha | Audit log (`AuditLog`), Excel/PDF eksport, RBAC (`roles_required`), ko'p tillilik kategoriya darajasida |
| 17. Texnologiyalar | Flask (backend), PostgreSQL (SQLAlchemy), Redis (config tayyor), JWT o'rniga sessiya-asosli auth + ichki API token |

## 5. Kengaytirish bo'yicha tavsiyalar

- **OneID/LDAP integratsiyasi** — `app/auth/routes.py` ichida qo'shimcha auth provayder qo'shish mumkin.
- **GraphQL** — hozirgi REST API tuzilmasi ustiga Ariadne/Graphene bilan qo'shish mumkin.
- **MinIO/S3** — hozircha fayllar Telegram `file_id` sifatida saqlanadi; production'da ularni
  MinIO/S3'ga yuklab, `RequestAttachment.file_ref` ga public/signed URL yozish tavsiya etiladi.
- **ML-asosidagi kechikish prognozi** — `predict_delay_risk()` hozircha evristik; tarixiy ma'lumotlar
  to'planganidan so'ng scikit-learn asosidagi regressiya modeliga almashtiring.
- **OpenAI/Azure OpenAI** — `config.AI_PROVIDER` va `app/ai/service.py` orqali provayderni almashtirish
  uchun tayyor joy qoldirilgan (hozircha Anthropic Claude ishlatilgan).

## 6. Yangi qo'shilgan funksiyalar (2-versiya)

1. **Zudlik bilan Telegram bildirishnoma** — `app/notify.py` orqali har bir hodisada
   (yangi murojaat, tayinlash, holat o'zgarishi, muddat) tegishli odamga **darhol** xabar boradi,
   alohida `notifier.py` workerini kutish shart emas (u faqat muddat monitoring va zaxira
   qayta urinish uchun ishlaydi).
2. **To'liq dashboard grafiklar** — TOP xizmatlar, TOP ijrochilar, SLA holati, murojaatlar
   dinamikasi va endi **Bo'limlar kesimi** grafigi ham qo'shildi (`Boshqaruv paneli`).
3. **AI avtomatik yo'naltirish** — agar dispetcher `.env` dagi `AUTO_ASSIGN_AFTER_MINUTES`
   (standart: 15 daqiqa) ichida murojaatni qabul qilmasa, `app/ai/auto_assign.py` AI taklif
   qilgan (yoki asl) kategoriya bo'yicha tegishli **bo'limdagi** eng bo'sh ijrochiga avtomatik
   yuboradi. Buning ishlashi uchun Admin panelida **Kategoriyalar** bo'limida har bir kategoriyaga
   tegishli Bo'limni belgilab qo'ying.
4. **Tashkiliy manzil so'rash** — Bot №1 endi GPS-lokatsiya o'rniga: Departament tarkibidami yoki
   Mustaqil boshqarmami, Departament nomi (ro'yxatdan), Boshqarma nomi va Xona raqamini so'raydi.
5. **To'liq holat kuzatuvi va baholash** — Mijoz boti barcha holatlarni (Yangi, Qabul qilindi,
   Ijrochiga yuborildi, Jarayonda, Qo'shimcha ma'lumot kutilmoqda, Bajarildi, Yopildi, Rad etildi)
   aniq ko'rsatadi; bajarilgandan so'ng 5 yulduzgacha baholash + izoh + alohida
   "taklif-so'rov" savoli so'raladi.
6. **Dispetcher va hisobotlarda Bo'linma ustuni** — Murojatlar jadvalida "Raqam"dan keyin
   Departament/Boshqarma/Xona ma'lumoti (`Bo'linma`) ko'rinadi, xuddi shu ustun Excel va PDF
   eksportida ham mavjud.

> **Eslatma:** yangi `org_department`, `org_division`, `room_number` va kategoriya-bo'lim
> bog'lanishi maydonlari qo'shilgani sababli, eski `local.db` fayli bilan mos kelmasligi mumkin.
> Yangilashdan so'ng `local.db` faylini o'chirib, `python scripts/seed.py` ni qayta ishga tushiring.
