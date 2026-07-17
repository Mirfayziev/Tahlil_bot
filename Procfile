web: python scripts/seed.py && gunicorn run:app --bind 0.0.0.0:$PORT --workers 3 --timeout 120
customer_bot: python bots/customer_bot.py
executor_bot: python bots/executor_bot.py
notifier: python bots/notifier.py
