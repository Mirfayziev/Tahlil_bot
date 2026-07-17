#!/bin/sh
# web uchun HTTP endpoint, botlar/notifier uchun esa mos jarayon ishlab
# turganini tekshiradi (ularda HTTP server yo'q).
if [ "${SERVICE_ROLE:-web}" = "web" ]; then
  curl -f http://localhost:8000/healthz || exit 1
else
  pgrep -f "bots/${SERVICE_ROLE}.py" > /dev/null || exit 1
fi
