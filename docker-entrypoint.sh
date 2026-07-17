#!/bin/sh
# Railway'da bitta Dockerfile'dan bir nechta xizmat (web + botlar) ishga tushirish uchun:
# har bir Railway xizmatida SERVICE_ROLE muhit o'zgaruvchisi mos qiymatga o'rnatiladi.
set -e

case "${SERVICE_ROLE:-web}" in
  web)
    python scripts/seed.py
    exec gunicorn -c gunicorn.conf.py run:app
    ;;
  customer_bot)
    exec python bots/customer_bot.py
    ;;
  executor_bot)
    exec python bots/executor_bot.py
    ;;
  notifier)
    exec python bots/notifier.py
    ;;
  *)
    echo "Noma'lum SERVICE_ROLE: ${SERVICE_ROLE}" >&2
    exit 1
    ;;
esac
