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

python scripts/seed.py             # bazani yaratadi + super admin (login: admin / parol: admin12345)
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

## 4. Render.com'ga joylashtirish

Loyiha `Procfile` bilan birga keladi — Render'da 4 ta process turi:

| Process       | Buyruq                                              |
|---------------|------------------------------------------------------|
| `web`         | `gunicorn run:app --bind 0.0.0.0:$PORT`              |
| `customer_bot`| `python bots/customer_bot.py`                        |
| `executor_bot`| `python bots/executor_bot.py`                        |
| `notifier`    | `python bots/notifier.py`                            |

Qadamlar:
1. Render'da yangi **PostgreSQL** database yarating, `DATABASE_URL` ni oling.
2. Yangi **Web Service** yarating, ushbu repo'ni ulang, `requirements.txt` avtomatik aniqlanadi.
3. Environment Variables bo'limida `.env.example` dagi barcha o'zgaruvchilarni kiriting.
4. `web` uchun start command: `gunicorn run:app --bind 0.0.0.0:$PORT`
5. Har bir bot uchun alohida **Background Worker** yarating (Render'da "Background Worker" turi),
   mos buyruqlarni bering (`python bots/customer_bot.py` va h.k.).
6. Deploy tugagach, bir martalik Shell orqali: `python scripts/seed.py`

## 5. TZ bandlari va tizimdagi joylashuvi

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

## 6. Kengaytirish bo'yicha tavsiyalar

- **OneID/LDAP integratsiyasi** — `app/auth/routes.py` ichida qo'shimcha auth provayder qo'shish mumkin.
- **GraphQL** — hozirgi REST API tuzilmasi ustiga Ariadne/Graphene bilan qo'shish mumkin.
- **MinIO/S3** — hozircha fayllar Telegram `file_id` sifatida saqlanadi; production'da ularni
  MinIO/S3'ga yuklab, `RequestAttachment.file_ref` ga public/signed URL yozish tavsiya etiladi.
- **ML-asosidagi kechikish prognozi** — `predict_delay_risk()` hozircha evristik; tarixiy ma'lumotlar
  to'planganidan so'ng scikit-learn asosidagi regressiya modeliga almashtiring.
- **OpenAI/Azure OpenAI** — `config.AI_PROVIDER` va `app/ai/service.py` orqali provayderni almashtirish
  uchun tayyor joy qoldirilgan (hozircha Anthropic Claude ishlatilgan).

## 7. Xavfsizlik eslatmalari

- Production'da `FLASK_SECRET_KEY` va `INTERNAL_API_TOKEN` ni albatta uzun, tasodifiy qiymatlarga almashtiring.
- `.env` faylini hech qachon repo'ga qo'shmang (`.gitignore` da allaqachon istisno qilingan).
- HTTPS orqali ishlating (Render avtomatik SSL beradi).

## 8. Yangi qo'shilgan funksiyalar (2-versiya)

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
