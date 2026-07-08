FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Systémové balíčky pro Pillow (JPEG/PNG/WEBP) a build závislostí.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        libwebp7 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Sběr statiky (Django admin + DRF) do STATIC_ROOT pro WhiteNoise.
# SECRET_KEY/DEBUG mají bezpečné defaulty, collectstatic nepotřebuje DB ani secrets.
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "salon_api.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
