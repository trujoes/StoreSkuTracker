# Stock Tracker

Small Flask + SQLite app for tracking store-level SKU shelf counts and expiry checks.

## Features

- View the latest status for every active store/SKU assignment
- Set a recommended shelf count for each store/SKU assignment
- Edit recommended shelf counts directly from the assignment list
- Update shelf count and expiring count inline from the dashboard
- Treat blank shelf/expiring count inputs as `0`
- Filter the dashboard by store, SKU, or employee
- Filter the dashboard by store using a dropdown
- Show relative last-visit timing in the live status table
- Open a prefilled action report email draft for expiring items and overdue store visits
- Track monthly visit completion per store against a 3-day minimum visit interval
- See summary totals and the latest visit history
- Keep activity history for the last 7 days only
- Add or remove stores, SKUs, and store/SKU assignments
- View store/SKU assignments grouped by store, with a store-level filter
- Preserve historical visit records even when catalog items are removed
- Uses SQLite for local storage

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:8001` in your browser.

Set `PORT` if you want to run it somewhere else.

Optional: set `CRITICAL_REPORT_TO_EMAIL` to prefill the recipient for the dashboard action report email draft.

## How it works

The app has two main pages:

- `/dashboard` shows the current shelf and expiry status for each configured store/SKU pair.
- `/manage` lets you maintain the active store list, SKU list, and which SKUs each store carries.

Dashboard updates create new records in `stock_visits`. The current status table is calculated from the latest retained visit for each store/SKU pair.

The live status table shows last visit as relative time, such as `2 days 3 hours`. The recent visits history still shows the full date and time.

Detailed activity history is retained for 7 days. Older `stock_visits` records are removed automatically during app startup, dashboard loads, and new dashboard saves. Monthly store visit coverage is retained separately so the action report can show each store's visits made versus expected visits for the current month.

Status rules:

- `Healthy`: current shelf count is above 50% of the recommended count, no items are expiring, and the latest visit is within 48 hours
- `Unhealthy`: early warning status when shelf count is 20-50%, the latest visit is 48-72 hours old, or a new store/SKU mapping has not been visited yet
- `Critical`: immediate action status when at least one item is expiring, shelf count is below 20%, or the store/SKU has not been visited for more than 72 hours

## Data

The SQLite database is stored at `instance/stock_tracker.sqlite3`.

Main tables:

- `stores`: active stores available for assignment
- `skus`: active SKU names
- `employees`: active employees available in the dashboard save dropdown
- `store_skus`: active store-to-SKU assignments with recommended shelf counts and mapping creation time
- `stock_visits`: historical shelf count and expiry count records
- `monthly_store_visits`: one monthly coverage row per store per day for visit deadline reporting

## Important behavior notes

- The app does not repopulate active stores/SKUs from old `stock_visits` on startup. This prevents deleted catalog items from reappearing after reload.
- Historical visit records are preserved even when stores, SKUs, or assignments are removed from the active catalog.
- Visit records are retained for 7 days only; older activity is automatically pruned.
- Monthly store visit coverage is stored separately from detailed visit records so per-store monthly performance reporting continues after old activity rows are pruned.
- Existing store/SKU mappings received a default recommended count of `10` when recommended counts were added.
- Adding the same store/SKU assignment again from `/manage` updates its recommended count instead of creating a duplicate.
- Inline dashboard saves create a new `stock_visits` row. The dashboard calculates current status from the latest visit for each store/SKU pair.
- Blank shelf count or expiring count inputs are saved as `0`.

## Key files

- `app.py`: Flask routes, SQLite schema setup/migrations, and status rules
- `templates/index.html`: dashboard UI, inline update form, and manager status note
- `templates/manage.html`: store/SKU management and recommended count editing
- `static/app.js`: inline dashboard AJAX saves and client-side filtering
- `static/styles.css`: desktop, mobile, status, and card/table styling
- `instance/stock_tracker.sqlite3`: local SQLite database

## PythonAnywhere deployment

The app is currently deployed on PythonAnywhere Free.

Production URL:

```text
https://trujoescoffee.pythonanywhere.com
```

Production paths:

```text
Application code: /home/trujoescoffee/StoreSkuTracker
SQLite database: /home/trujoescoffee/StoreSkuTracker/instance/stock_tracker.sqlite3
Static files: /home/trujoescoffee/StoreSkuTracker/static
Templates: /home/trujoescoffee/StoreSkuTracker/templates
Virtualenv: /home/trujoescoffee/.virtualenvs/storesku
```

PythonAnywhere static files mapping:

```text
URL: /static/
Directory: /home/trujoescoffee/StoreSkuTracker/static
```

PythonAnywhere WSGI configuration:

```python
import sys

path = '/home/trujoescoffee/StoreSkuTracker'
if path not in sys.path:
    sys.path.insert(0, path)

from app import app as application
```

Deployment steps used:

1. Upload project ZIP to PythonAnywhere.
2. Extract it into `/home/trujoescoffee/StoreSkuTracker`.
3. Create a virtualenv named `storesku`.
4. Install dependencies with `pip install -r requirements.txt`.
5. Create a manual Flask web app from the PythonAnywhere Web tab.
6. Set the virtualenv path to `/home/trujoescoffee/.virtualenvs/storesku`.
7. Update the WSGI file with the configuration above.
8. Add the `/static/` static files mapping.
9. Click **Reload** in the PythonAnywhere Web tab.

## Updating PythonAnywhere from GitHub

Use this flow after the PythonAnywhere folder has been switched to a GitHub clone.

Before every update, back up the live SQLite database:

```bash
cd ~/StoreSkuTracker
cp instance/stock_tracker.sqlite3 ~/stock_tracker_backup_$(date +%Y%m%d_%H%M%S).sqlite3
```

To deploy changes that have already been merged into `main`:

```bash
cd ~/StoreSkuTracker
git checkout main
git pull origin main
workon storesku
pip install -r requirements.txt
```

Then go to the PythonAnywhere **Web** tab and click **Reload**.

To test a feature branch on PythonAnywhere before merging:

```bash
cd ~/StoreSkuTracker
cp instance/stock_tracker.sqlite3 ~/stock_tracker_backup_$(date +%Y%m%d_%H%M%S).sqlite3
git fetch origin
git checkout BRANCH_NAME
git pull origin BRANCH_NAME
workon storesku
pip install -r requirements.txt
```

Then click **Reload** in the PythonAnywhere **Web** tab.

To return PythonAnywhere to production `main` after branch testing:

```bash
cd ~/StoreSkuTracker
git checkout main
git pull origin main
```

Then click **Reload** again.

Important: do not overwrite the live production database from GitHub. The file `instance/stock_tracker.sqlite3` should stay ignored by Git and should be backed up separately.

## Backup

Because the free deployment uses SQLite, back up the database file periodically.

Manual backup command on PythonAnywhere:

```bash
cp ~/StoreSkuTracker/instance/stock_tracker.sqlite3 ~/stock_tracker_backup.sqlite3
```

## Recommended next improvements

- Add login/password protection before sharing the URL widely. Currently, anyone with the URL can edit data.
- Move `SECRET_KEY` to an environment variable instead of keeping it hardcoded.
- Add user roles later if managers and employees need different permissions.
- Add automated database backups if this becomes business-critical.
- If usage grows or many users update at the same time, consider moving from SQLite to MySQL/Postgres.
- Clean up local-only files before long-term GitHub maintenance, especially `.venv`, `__pycache__`, and generated database copies.

## Handoff PDF

A developer handoff PDF is included in this repo:

```text
StoreSkuTracker_Developer_Handoff.pdf
```
