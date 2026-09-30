FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    DJANGO_SERVE_STATIC=1 \
    DJANGO_DB_PATH=/data/db.sqlite3

WORKDIR /app

# gettext compiles the translation files (locale/*/LC_MESSAGES/django.po).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Build-time commands need some secret key; the real one comes from .env at runtime.
RUN export DJANGO_SECRET_KEY=build-only-not-secret \
    && python manage.py compilemessages \
    && python manage.py collectstatic --noinput \
    && useradd --system --home /app guidebook \
    && mkdir /data && chown guidebook:guidebook /data

USER guidebook
VOLUME /data
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "guidebook.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
