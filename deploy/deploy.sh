#!/bin/sh
# Deploy script run on the server by the GitHub Actions deploy key (SSH forced command).
# The only input is the commit to deploy, which must be part of origin/main.
# Installed as /usr/local/sbin/guidebook-deploy — see docs/deployment.md.
set -eu

APP=/opt/guidebook
BACKUPS=/srv/guidebook/backups
COMMIT="${SSH_ORIGINAL_COMMAND:-${1:-}}"

case "$COMMIT" in
  *[!0-9a-f]*|'') echo "Usage: <40-character commit id>" >&2; exit 2 ;;
esac
[ "${#COMMIT}" -eq 40 ] || { echo "Usage: <40-character commit id>" >&2; exit 2; }

# One deploy at a time.
exec 9>/run/guidebook-deploy.lock
flock 9

cd "$APP"
git fetch --quiet origin main
if ! git merge-base --is-ancestor "$COMMIT" origin/main; then
  echo "Commit $COMMIT is not on main; refusing to deploy." >&2
  exit 1
fi

# Database backup before every deploy; keep 30 days.
mkdir -p "$BACKUPS"
DB="$(docker volume inspect -f '{{.Mountpoint}}' guidebook_db)/db.sqlite3"
python3 -c "import sqlite3,sys; sqlite3.connect(sys.argv[1]).backup(sqlite3.connect(sys.argv[2]))" \
  "$DB" "$BACKUPS/pre-deploy-$(date -u +%Y%m%d-%H%M%S)-${COMMIT%"${COMMIT#???????}"}.sqlite3"
find "$BACKUPS" -name 'pre-deploy-*.sqlite3' -mtime +30 -delete

git reset --hard --quiet "$COMMIT"
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker compose up -d --build --quiet-pull

# Wait for the app, then report the content sync.
i=0
until docker compose logs web --since "$STARTED" 2>&1 | grep -q 'Listening at'; do
  i=$((i + 1))
  [ "$i" -le 60 ] || { echo "The app did not start within 2 minutes." >&2; docker compose logs web --since "$STARTED" | tail -30; exit 1; }
  sleep 2
done
LOG="$(docker compose logs web --since "$STARTED" 2>&1)"
echo "$LOG" | grep -E 'Applying|Content synced|countries:|steps:|services:|WARNING|Warning' || true
echo "$LOG" | grep -q 'Content synced' || { echo "Content sync failed; the previous content is still served." >&2; exit 1; }
echo "Deployed $COMMIT"
