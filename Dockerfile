FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg2 (Postgres) uchun build kutubxonalari; procps — healthcheck'da bot
# jarayonini pgrep bilan tekshirish uchun
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/instance \
    && chmod +x /app/docker-entrypoint.sh /app/docker-healthcheck.sh

# Root bo'lmagan foydalanuvchi ostida ishga tushirish (xavfsizlik)
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/app/docker-healthcheck.sh"]

# Bitta image — web va Telegram botlar (Railway'da alohida xizmat sifatida)
# SERVICE_ROLE muhit o'zgaruvchisi orqali qaysi jarayon ishga tushishini tanlaydi
# (qarang: docker-entrypoint.sh). scripts/seed.py idempotent: jadvallar mavjud
# bo'lmasa yaratadi, shuning uchun migratsiya bosqichisiz muhitlarda ham xavfsiz.
ENV SERVICE_ROLE=web
CMD ["/app/docker-entrypoint.sh"]
