# Deploy Local Data to Main Server (Al Najah)

**Server:** `root@37.27.16.210`  
**App path:** `/var/www/alnajahfireerp`  
**Git repo:** https://github.com/gearupae/alnajanew.git

For **full production deploy** (code, no `.env` overwrite, optional DB), use from repo root:

- `docs/DEPLOY_HETZNER.md`
- `scripts/deploy_production.sh`

To replace the main server database with your local data:

## Option 1: SQLite (default)

1. **On your local machine**, the database is at:
   ```
   erp_project/db.sqlite3
   ```

2. **Copy to server**:
   ```bash
   scp erp_project/db.sqlite3 root@37.27.16.210:/var/www/alnajahfireerp/erp_project/
   ```

3. **On the server**, run migrations and restart:
   ```bash
   cd /var/www/alnajahfireerp/erp_project
   source ../venv/bin/activate
   python manage.py migrate --no-input
   systemctl restart gunicorn
   ```

## Option 2: PostgreSQL

Use your normal PostgreSQL backup/restore process for the production database configured in `erp_project/.env` on the server.
