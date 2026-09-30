# Deployment

The production setup is one Linux server running Docker Compose (`compose.yaml`: the Django app
behind Caddy, which handles HTTPS). Every change merged into `main` is deployed automatically:

1. **CI** (`.github/workflows/ci.yml`) runs the checks, the tests, a content dry run and a Docker
   build for every pull request and every push to `main`.
2. **Deploy** (`.github/workflows/deploy.yml`) starts when CI succeeded on `main`. It connects to
   the server with a dedicated SSH key and passes the tested commit ID.
3. On the server, that key can only run **`deploy/deploy.sh`** (installed as
   `/usr/local/sbin/guidebook-deploy`). The script checks that the commit is on `main`, backs up
   the database, checks out the commit, rebuilds and restarts the containers, and reports the
   content sync (`python manage.py sync_content` runs on every start).

## One-time server setup

Assumes Docker and the app already run in `/opt/guidebook` with its `.env` there.

```bash
# 1. Turn /opt/guidebook into a clone of the repository (keeps .env and the database volume)
cd /opt/guidebook
git init -q && git remote add origin https://github.com/LIFE-DISCOVER/interactive-guidebook.git
git fetch -q origin main && git reset -q --hard origin/main   # .env is ignored by git and stays

# 2. Install the deploy script (re-copy it when deploy/deploy.sh changes)
install -m 755 deploy/deploy.sh /usr/local/sbin/guidebook-deploy

# 3. Create the deploy key and allow it to run only the deploy script
ssh-keygen -t ed25519 -N '' -C 'github-actions deploy' -f /root/guidebook-deploy-key
echo "command=\"/usr/local/sbin/guidebook-deploy\",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty $(cat /root/guidebook-deploy-key.pub)" >> /root/.ssh/authorized_keys

# 4. Print the values for GitHub, then delete the private key from the server
cat /root/guidebook-deploy-key          # -> secret DEPLOY_SSH_KEY
ssh-keyscan -t ed25519 localhost | sed "s/^localhost/<server-ip>/"   # -> secret DEPLOY_KNOWN_HOSTS
shred -u /root/guidebook-deploy-key
```

In `.env`, set `CONTENT_REPO_URL=https://github.com/LIFE-DISCOVER/interactive-guidebook/edit/main/data/` for the
"Edit on GitHub" links in the admin.

## GitHub settings

- **Environment `production`** (Settings → Environments): secrets `DEPLOY_SSH_KEY`,
  `DEPLOY_KNOWN_HOSTS`, `DEPLOY_HOST` (server IP or host name); variable `SITE_URL`
  (e.g. `https://guidebook.example.org`). Optionally restrict it to the `main` branch.
- **Branch protection for `main`**: require a pull request with 1 approval and the CI checks
  (`test`, `docker`) to pass; no force pushes.
- **CODEOWNERS** (`.github/CODEOWNERS`): maintainers and per-country reviewers.

## Operations

- Logs: `cd /opt/guidebook && docker compose logs -f`
- Backups: before every deploy (`/srv/guidebook/backups/pre-deploy-*`, kept 30 days) and nightly.
- Manual deploy of the current `main`:
  `cd /opt/guidebook && git fetch -q origin main && guidebook-deploy "$(git rev-parse origin/main)"`
- Roll back: revert the change on GitHub (a new commit) — the deploy runs automatically. To restore
  data, stop the app and copy a backup into the `guidebook_db` volume.
