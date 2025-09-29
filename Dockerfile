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

RUN mkdir -p /app/logs /app/staticfiles

EXPOSE $PORT

CMD python manage.py collectstatic --noinput && python manage.py migrate && python manage.py setup_cache_table && daphne base.asgi:application --bind 0.0.0.0 --port $PORT