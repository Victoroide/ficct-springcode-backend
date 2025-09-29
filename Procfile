web: python manage.py migrate && python manage.py setup_cache_table && python manage.py collectstatic --noinput && daphne base.asgi:application --bind 0.0.0.0 --port $PORT
