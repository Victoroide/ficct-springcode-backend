FROM python:3.11-slim-bullseye

EXPOSE 8000
EXPOSE 8001

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN apt-get update && \
    apt-get install -y build-essential libpq-dev libffi-dev

RUN pip install --no-cache-dir --upgrade pip && \
    pip install daphne==4.0.0 gunicorn channels channels-redis

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

WORKDIR /app
COPY . /app

RUN mkdir -p /app/logs

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "base.wsgi:application"]