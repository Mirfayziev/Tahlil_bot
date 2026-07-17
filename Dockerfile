FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg2 (Postgres) uchun build kutubxonalari
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/instance

# Root bo'lmagan foydalanuvchi ostida ishga tushirish (xavfsizlik)
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# scripts/seed.py idempotent: jadvallar mavjud bo'lmasa yaratadi (db.create_all()) va
# faqat super admin/bo'lim/kategoriya bo'lmasa qo'shadi — shu sabab har bir deploy'da
# (Railway kabi migratsiya bosqichi bo'lmagan muhitlarda ham) xavfsiz ishga tushiriladi.
CMD ["sh", "-c", "python scripts/seed.py && gunicorn -c gunicorn.conf.py run:app"]
