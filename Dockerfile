# Multi-stage Dockerfile for production Django application
# Stage 1: Build dependencies and collect static files
FROM python:3.11-slim as builder

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system django && adduser --system --ingroup django django

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project files
COPY . .

# Change ownership to django user
RUN chown -R django:django /app

# Switch to django user
USER django

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Stage 2: Production runtime
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=base.settings \
    PORT=8000

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN addgroup --system django && adduser --system --ingroup django django

# Create necessary directories
RUN mkdir -p /app /app/staticfiles /app/mediafiles /app/logs \
    && chown -R django:django /app

# Set work directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code and collected static files
COPY --from=builder --chown=django:django /app .

# Switch to django user
USER django

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

# Expose port
EXPOSE ${PORT}

# Create entrypoint script
USER root
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "Starting Django application..."\n\
\n\
# Wait for database\n\
echo "Waiting for database..."\n\
python manage.py wait_for_db\n\
\n\
# Run migrations\n\
echo "Running database migrations..."\n\
python manage.py migrate --noinput\n\
\n\
# Create superuser if specified\n\
if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ]; then\n\
    echo "Creating superuser..."\n\
    python manage.py shell -c "\n\
from django.contrib.auth import get_user_model;\n\
User = get_user_model();\n\
if not User.objects.filter(username='"'"'$DJANGO_SUPERUSER_USERNAME'"'"').exists():\n\
    User.objects.create_superuser('"'"'$DJANGO_SUPERUSER_USERNAME'"'"', '"'"'$DJANGO_SUPERUSER_EMAIL'"'"', '"'"'$DJANGO_SUPERUSER_PASSWORD'"'"')\n\
    "\n\
fi\n\
\n\
# Start application\n\
if [ "$1" = "web" ]; then\n\
    echo "Starting Gunicorn web server..."\n\
    exec gunicorn base.wsgi:application \\\n\
        --bind 0.0.0.0:${PORT} \\\n\
        --workers ${GUNICORN_WORKERS:-3} \\\n\
        --worker-class gevent \\\n\
        --worker-connections ${GUNICORN_WORKER_CONNECTIONS:-1000} \\\n\
        --max-requests ${GUNICORN_MAX_REQUESTS:-1000} \\\n\
        --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100} \\\n\
        --preload \\\n\
        --access-logfile - \\\n\
        --error-logfile - \\\n\
        --log-level ${GUNICORN_LOG_LEVEL:-info} \\\n\
        --timeout ${GUNICORN_TIMEOUT:-30}\n\
elif [ "$1" = "worker" ]; then\n\
    echo "Starting Celery worker..."\n\
    exec celery -A base worker \\\n\
        --loglevel=${CELERY_LOG_LEVEL:-info} \\\n\
        --concurrency=${CELERY_CONCURRENCY:-2} \\\n\
        --max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD:-100}\n\
elif [ "$1" = "beat" ]; then\n\
    echo "Starting Celery beat scheduler..."\n\
    exec celery -A base beat \\\n\
        --loglevel=${CELERY_LOG_LEVEL:-info} \\\n\
        --scheduler django_celery_beat.schedulers:DatabaseScheduler\n\
elif [ "$1" = "flower" ]; then\n\
    echo "Starting Celery Flower monitoring..."\n\
    exec celery -A base flower \\\n\
        --port=${FLOWER_PORT:-5555} \\\n\
        --basic_auth=${FLOWER_USER:-admin}:${FLOWER_PASSWORD:-admin123}\n\
else\n\
    echo "Available commands: web, worker, beat, flower"\n\
    exec "$@"\n\
fi' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

USER django

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["web"]
