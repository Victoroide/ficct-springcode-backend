FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DJANGO_SETTINGS_MODULE=base.settings

# Install system dependencies including OCR libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for OCR libraries
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/staticfiles /app/static

EXPOSE $PORT

CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && python manage.py createcachetable django_cache_table && daphne base.asgi:application --bind 0.0.0.0 --port $PORT"]