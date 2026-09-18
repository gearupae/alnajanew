# Deploy to Hetzner (Al Najah ERP)

**Production URL:** https://alnajah.telldb.com/  
**Server:** `root@37.27.16.210`  
**Git repo:** https://github.com/gearupae/alnajanew.git  
**App path:** `/var/www/alnajahfireerp`

This is the recommended flow so you do **not** paste GitHub tokens on the server and you do **not** overwrite production `.env`.

## 1. Recommended: rsync + deploy script (from your Mac)

From the repo root:

```bash
export DEPLOY_HOST=root@37.27.16.210
export DEPLOY_PATH=/var/www/alnajahfireerp

# Code only (keeps server db and .env)
./scripts/deploy_production.sh

# Code + replace SQLite with your local DB (small / dev setups only)
./scripts/deploy_production.sh --with-db
```

What the script does:

- **Rsync** project files to `DEPLOY_PATH`, with `--delete` to remove stale files.
- **Never copies** `erp_project/.env` or root `.env` — the server keeps its secrets.
- **Skips** `venv`, `.git`, `media`, `staticfiles`, `backups` (and `db.sqlite3` unless `--with-db`).
- On the server: optional `pip install`, `migrate`, `collectstatic`, `systemctl restart gunicorn`.

Ensure on the server:

- App lives at `/var/www/alnajahfireerp` with `venv/` and `erp_project/`.
- `erp_project/.env` exists **once**, edited on the server (use `.env.example` as a template).
- `gunicorn` systemd unit points at `WorkingDirectory=/var/www/alnajahfireerp/erp_project` (or your layout).

## 2. Optional: `git pull` on the server (SSH deploy key)

Add a read-only deploy key in GitHub for **gearupae/alnajanew**, then on the server:

```bash
cd /var/www/alnajahfireerp
git remote set-url origin git@github.com:gearupae/alnajanew.git
git fetch origin
git checkout main
git reset --hard origin/main
source venv/bin/activate
cd erp_project
python manage.py migrate --no-input
python manage.py collectstatic --no-input
systemctl restart gunicorn
```

## Local development

```bash
cd erp_project
cp ../.env.example .env   # or edit .env for SQLite
python manage.py runserver 0.0.0.0:3000
```
