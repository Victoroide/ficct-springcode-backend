FROM python:3.11-slim-bullseye

# Open http ports
EXPOSE 8000
EXPOSE 8001

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Installing build tools
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev libffi-dev

# Install pip and necessary packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install daphne==4.0.0 gunicorn channels channels-redis

# Install requirements
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

# Moving application files
WORKDIR /app
COPY . /app

# Create logs directory
RUN mkdir -p /app/logs

# Default command (will be overridden by docker-compose)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "base.wsgi:application"]