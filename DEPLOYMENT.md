# Al Najah ERP — Git & production server

| Item | Value |
|------|--------|
| **Production site** | https://alnajah.telldb.com/ |
| **Hetzner SSH** | `ssh root@37.27.16.210` |
| **App directory** | `/var/www/alnajahfireerp` |
| **Git repository** | https://github.com/gearupae/alnajanew.git |
| **Default branch** | `main` |

## Deploy from your machine (recommended)

From the repo root:

```bash
export DEPLOY_HOST=root@37.27.16.210
export DEPLOY_PATH=/var/www/alnajahfireerp
./scripts/deploy_production.sh
```

See [docs/DEPLOY_HETZNER.md](docs/DEPLOY_HETZNER.md) for `--with-db`, pip, and server `git pull` options.

## Local development

```bash
git clone https://github.com/gearupae/alnajanew.git
cd alnajanew
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd erp_project && cp ../.env.example .env
python manage.py migrate
python manage.py runserver 0.0.0.0:3000
```
