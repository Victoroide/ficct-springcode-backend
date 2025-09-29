FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV DJANGO_SETTINGS_MODULE base.settings

RUN apt-get update && \
    apt-get install -y build-essential libpq-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs && \
    python manage.py collectstatic --noinput

EXPOSE $PORT

CMD python manage.py migrate && gunicorn base.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --log-level info