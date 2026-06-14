# Stock Tracker

Small Flask + SQLite app for tracking store-level SKU shelf counts and expiry checks.

## Features

- View the latest status for every active store/SKU assignment
- Set a recommended shelf count for each store/SKU assignment
- Edit recommended shelf counts directly from the assignment list
- Update shelf count and expiring count inline from the dashboard
- Filter the dashboard by store, SKU, or employee
- See summary totals and the latest visit history
- Add or remove stores, SKUs, and store/SKU assignments
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

## How it works

The app has two main pages:

- `/dashboard` shows the current shelf and expiry status for each configured store/SKU pair.
- `/manage` lets you maintain the active store list, SKU list, and which SKUs each store carries.

Dashboard updates create new records in `stock_visits`. The current status table is calculated from the latest visit for each store/SKU pair, so visit history is retained over time.

Status rules:

- `Healthy`: current shelf count is above 50% of the recommended count and no items are expiring
- `Unhealthy`: current shelf count is 20-50% of the recommended count and no items are expiring
- `Critical`: at least one item is expiring, current shelf count is below 20% of the recommended count, no count has been recorded yet, or the last visit is older than 72 hours

## Data

The SQLite database is stored at `instance/stock_tracker.sqlite3`.

Main tables:

- `stores`: active stores available for assignment
- `skus`: active SKU names
- `store_skus`: active store-to-SKU assignments with recommended shelf counts
- `stock_visits`: historical shelf count and expiry count records
