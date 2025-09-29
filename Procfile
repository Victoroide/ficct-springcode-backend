web: python manage.py collectstatic --noinput && python manage.py migrate && gunicorn base.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
