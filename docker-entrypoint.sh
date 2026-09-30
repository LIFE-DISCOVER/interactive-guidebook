#!/bin/sh
set -e

python manage.py migrate --noinput

# Countries, guidebook steps and services come from the files in data/ (managed on
# GitHub). If they cannot be loaded, keep serving the previous content; the deploy
# script checks for "Content synced" and reports the failure.
python manage.py sync_content || echo "WARNING: content sync failed; serving the previous content."

# First launch: create the administrator from DJANGO_SUPERUSER_EMAIL and
# DJANGO_SUPERUSER_PASSWORD if both are set, which skips the setup page.
python manage.py ensure_admin

# If there is still no user, print the code needed on the setup page.
python manage.py setup_code

exec "$@"
