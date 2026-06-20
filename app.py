from __future__ import annotations

import calendar
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from flask import Flask, g, jsonify, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "stock_tracker.sqlite3"
INVENTORY_UNITS = ("KG", "Litres", "Bottles")

app = Flask(__name__)
app.config["SECRET_KEY"] = "stock-tracker-local-dev"


def cleanup_old_visits(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM stock_visits WHERE datetime(created_at) < datetime('now', '-7 days')")


def cleanup_old_inventory_history(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM inventory_history WHERE datetime(created_at) < datetime('now', '-7 days')")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        g.db = connection
    return g.db


def init_db() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                city TEXT,
                city_id INTEGER
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS skus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name TEXT NOT NULL,
                employee_name TEXT NOT NULL,
                sku TEXT NOT NULL,
                shelf_count INTEGER NOT NULL CHECK (shelf_count >= 0),
                expiring_count INTEGER NOT NULL CHECK (expiring_count >= 0),
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS store_skus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id INTEGER NOT NULL,
                sku_id INTEGER NOT NULL,
                recommended_count INTEGER NOT NULL DEFAULT 10 CHECK (recommended_count > 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(store_id, sku_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS monthly_store_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id INTEGER,
                store_name TEXT NOT NULL,
                employee_name TEXT NOT NULL,
                visit_date TEXT NOT NULL,
                month_key TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(store_name, visit_date)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
                unit TEXT NOT NULL DEFAULT 'Bottles',
                emergency_minimum INTEGER NOT NULL DEFAULT 5 CHECK (emergency_minimum >= 0),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                item_name TEXT NOT NULL,
                change_type TEXT NOT NULL,
                quantity_before INTEGER,
                quantity_after INTEGER,
                emergency_minimum_before INTEGER,
                emergency_minimum_after INTEGER,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        inventory_item_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(inventory_items)").fetchall()
        }
        if "emergency_minimum" not in inventory_item_columns:
            connection.execute(
                "ALTER TABLE inventory_items ADD COLUMN emergency_minimum INTEGER NOT NULL DEFAULT 5 CHECK (emergency_minimum >= 0)"
            )
        if "unit" not in inventory_item_columns:
            connection.execute("ALTER TABLE inventory_items ADD COLUMN unit TEXT NOT NULL DEFAULT 'Bottles'")
        store_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(stores)").fetchall()
        }
        if "city" not in store_columns:
            connection.execute("ALTER TABLE stores ADD COLUMN city TEXT")
        if "city_id" not in store_columns:
            connection.execute("ALTER TABLE stores ADD COLUMN city_id INTEGER")
        connection.execute(
            """
            INSERT OR IGNORE INTO cities (name)
            SELECT DISTINCT TRIM(city)
            FROM stores
            WHERE city IS NOT NULL AND TRIM(city) != ''
            """
        )
        connection.execute(
            """
            UPDATE stores
            SET city_id = (
                SELECT cities.id
                FROM cities
                WHERE cities.name = TRIM(stores.city)
            )
            WHERE city_id IS NULL AND city IS NOT NULL AND TRIM(city) != ''
            """
        )
        store_sku_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(store_skus)").fetchall()
        }
        if "recommended_count" not in store_sku_columns:
            connection.execute(
                "ALTER TABLE store_skus ADD COLUMN recommended_count INTEGER NOT NULL DEFAULT 10 CHECK (recommended_count > 0)"
            )
        if "created_at" not in store_sku_columns:
            connection.execute("ALTER TABLE store_skus ADD COLUMN created_at TEXT")
            connection.execute("UPDATE store_skus SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        coverage_count = connection.execute("SELECT COUNT(*) FROM monthly_store_visits").fetchone()[0]
        if coverage_count == 0:
            connection.execute(
                """
                INSERT OR IGNORE INTO monthly_store_visits (
                    store_id, store_name, employee_name, visit_date, month_key, created_at, updated_at
                )
                SELECT
                    stores.id,
                    stock_visits.store_name,
                    stock_visits.employee_name,
                    date(stock_visits.created_at),
                    strftime('%Y-%m', stock_visits.created_at),
                    MIN(stock_visits.created_at),
                    MAX(stock_visits.created_at)
                FROM stock_visits
                LEFT JOIN stores ON stores.name = stock_visits.store_name
                GROUP BY stock_visits.store_name, date(stock_visits.created_at)
                """
            )
        cleanup_old_visits(connection)
        cleanup_old_inventory_history(connection)
        connection.commit()
    finally:
        connection.close()


@app.teardown_appcontext
def close_db(_exc: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.template_filter("datetime_display")
def datetime_display(value: str) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return str(value)
    return parsed.strftime("%b %d, %Y %I:%M %p")


def relative_time_display(value: str | None) -> str:
    if not value:
        return "No visit"
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return str(value)

    now = datetime.now(UTC).replace(tzinfo=None)
    delta = now - parsed
    if delta.total_seconds() < 0:
        return "Just now"

    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    if days:
        day_label = "day" if days == 1 else "days"
        if hours:
            hour_label = "hour" if hours == 1 else "hours"
            return f"{days} {day_label} {hours} {hour_label} ago"
        return f"{days} {day_label} ago"
    if hours:
        hour_label = "hour" if hours == 1 else "hours"
        return f"{hours} {hour_label} ago"
    if minutes:
        minute_label = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {minute_label} ago"
    return "Just now"


@app.template_filter("relative_time_display")
def relative_time_display_filter(value: str) -> str:
    return relative_time_display(value)


def is_visit_stale(last_visit: str | None) -> bool:
    return is_older_than_hours(last_visit, 72)


def is_visit_overdue(last_visit: str | None, mapping_created_at: str | None) -> bool:
    if last_visit:
        return is_older_than_hours(last_visit, 72)
    return is_older_than_hours(mapping_created_at, 72)


def is_older_than_hours(value: str | None, hours: int) -> bool:
    if not value:
        return True
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return True
    now = datetime.now(UTC).replace(tzinfo=None)
    return now - parsed > timedelta(hours=hours)


def get_status(
    shelf_count: int | None,
    expiring_count: int | None,
    recommended_count: int,
    last_visit: str | None,
    mapping_created_at: str | None,
) -> str:
    if not last_visit:
        if is_older_than_hours(mapping_created_at, 72):
            return "Critical"
        return "Unhealthy"

    if expiring_count is not None and expiring_count >= 1:
        return "Critical"

    if is_older_than_hours(last_visit, 72):
        return "Critical"
    if shelf_count is None or expiring_count is None:
        return "Unhealthy"
    if shelf_count < recommended_count * 0.2:
        return "Critical"
    if is_older_than_hours(last_visit, 48):
        return "Unhealthy"
    if shelf_count <= recommended_count * 0.5:
        return "Unhealthy"
    return "Healthy"


def record_monthly_store_visit(db: sqlite3.Connection, store_id: int, store_name: str, employee_name: str) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    visit_date = now.strftime("%Y-%m-%d")
    month_key = now.strftime("%Y-%m")
    db.execute(
        """
        INSERT INTO monthly_store_visits (
            store_id, store_name, employee_name, visit_date, month_key, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(store_name, visit_date) DO UPDATE SET
            store_id = excluded.store_id,
            employee_name = excluded.employee_name,
            updated_at = CURRENT_TIMESTAMP
        """,
        (store_id, store_name, employee_name, visit_date, month_key),
    )


def record_inventory_history(
    db: sqlite3.Connection,
    item_id: int | None,
    item_name: str,
    change_type: str,
    quantity_before: int | None,
    quantity_after: int | None,
    emergency_minimum_before: int | None,
    emergency_minimum_after: int | None,
    note: str = "",
) -> None:
    db.execute(
        """
        INSERT INTO inventory_history (
            item_id,
            item_name,
            change_type,
            quantity_before,
            quantity_after,
            emergency_minimum_before,
            emergency_minimum_after,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            item_name,
            change_type,
            quantity_before,
            quantity_after,
            emergency_minimum_before,
            emergency_minimum_after,
            note,
        ),
    )


def build_inventory_update_response(db: sqlite3.Connection, item_id: int):
    updated_row = db.execute(
        "SELECT id, quantity, unit, emergency_minimum, updated_at FROM inventory_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    rows = db.execute("SELECT quantity, emergency_minimum FROM inventory_items").fetchall()
    return jsonify(
        {
            "ok": True,
            "item": {
                "id": updated_row["id"],
                "quantity": updated_row["quantity"],
                "unit": updated_row["unit"],
                "emergency_minimum": updated_row["emergency_minimum"],
                "updated_at": updated_row["updated_at"],
                "updated_display": relative_time_display(updated_row["updated_at"]),
                "is_low_stock": (updated_row["quantity"] or 0) <= (updated_row["emergency_minimum"] or 0),
            },
            "summary": {
                "total_units": sum(row["quantity"] or 0 for row in rows),
                "low_stock_count": sum(
                    1 for row in rows if (row["quantity"] or 0) <= (row["emergency_minimum"] or 0)
                ),
            },
        }
    )


def get_monthly_visit_performance() -> dict:
    db = get_db()
    now = datetime.now(UTC).replace(tzinfo=None)
    month_key = now.strftime("%Y-%m")
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    expected_by_today_per_store = max(1, ((now.day - 1) // 3) + 1)
    expected_full_month_per_store = (days_in_month + 2) // 3
    stores = db.execute("SELECT id, name FROM stores ORDER BY name COLLATE NOCASE").fetchall()
    visit_rows = db.execute(
        """
        SELECT store_name, COUNT(*) AS visit_count
        FROM monthly_store_visits
        WHERE month_key = ?
        GROUP BY store_name
        """,
        (month_key,),
    ).fetchall()
    visits_by_store = {row["store_name"]: row["visit_count"] for row in visit_rows}
    store_rows = []
    for store in stores:
        visits_made = visits_by_store.get(store["name"], 0)
        completion_percent = round((visits_made / expected_by_today_per_store) * 100)
        remaining_to_pace = max(expected_by_today_per_store - visits_made, 0)
        store_rows.append(
            {
                "store_id": store["id"],
                "store_name": store["name"],
                "visits_made": visits_made,
                "expected_by_today": expected_by_today_per_store,
                "expected_full_month": expected_full_month_per_store,
                "completion_percent": completion_percent,
                "remaining_to_pace": remaining_to_pace,
                "status": "On track" if remaining_to_pace == 0 else "Behind plan",
            }
        )
    store_rows.sort(key=lambda row: (row["remaining_to_pace"] == 0, row["store_name"].lower()))
    employee_rows = db.execute(
        """
        SELECT employee_name, COUNT(*) AS visit_count
        FROM monthly_store_visits
        WHERE month_key = ?
        GROUP BY employee_name
        ORDER BY visit_count DESC, employee_name COLLATE NOCASE
        """,
        (month_key,),
    ).fetchall()
    return {
        "month_label": now.strftime("%B %Y"),
        "store_count": len(stores),
        "store_rows": store_rows,
        "employee_rows": employee_rows,
    }


def build_critical_report(rows: list[dict], visit_performance: dict | None = None) -> tuple[str, str]:
    generated_at = datetime.now().strftime("%b %d, %Y %I:%M %p")
    if visit_performance is None:
        visit_performance = get_monthly_visit_performance()
    expiring_rows = [row for row in rows if (row["expiring_count"] or 0) >= 1]
    stale_store_rows = {}
    for row in rows:
        if not row["is_stale"]:
            continue
        current_row = stale_store_rows.get(row["store_id"])
        if current_row is None or str(row["last_visit"] or "") > str(current_row["last_visit"] or ""):
            stale_store_rows[row["store_id"]] = row

    subject = f"Daily Stock Action Report - {datetime.now().strftime('%d %b %Y')}"
    lines = [
        "Daily Stock Action Report",
        f"Generated: {generated_at}",
        "",
        "1. Expiring items",
    ]

    if expiring_rows:
        lines.append(f"{len(expiring_rows)} item(s) need expiry action:")
        lines.append("")
        for index, row in enumerate(expiring_rows, start=1):
            lines.extend(
                [
                    f"{index}. {row['store_name']} - {row['sku_name']}",
                    f"   Expiring: {row['expiring_count']}",
                    f"   Current shelf count: {row['shelf_count'] if row['shelf_count'] is not None else 0}",
                    f"   Last visit: {row['last_visit_display']}",
                    f"   Last visit made by: {row['employee_name'] or 'No visit'}",
                    "   Action: Remove or replace expiring items",
                    "",
                ]
            )
    else:
        lines.append("No expiring items currently.")
        lines.append("")

    lines.append("2. Stores not visited in 72 hours")
    stale_rows = sorted(stale_store_rows.values(), key=lambda row: row["store_name"].lower())
    if stale_rows:
        lines.append(f"{len(stale_rows)} store(s) need a visit:")
        lines.append("")
        for index, row in enumerate(stale_rows, start=1):
            lines.extend(
                [
                    f"{index}. {row['store_name']}",
                    f"   Last visit: {row['last_visit_display']}",
                    f"   Last visit made by: {row['employee_name'] or 'No visit'}",
                    "   Action: Visit store and update shelf count",
                    "",
                ]
            )
    else:
        lines.append("All stores have been visited within the last 72 hours.")
        lines.append("")

    lines.extend(
        [
            "3. Monthly visit deadline performance by store",
            f"Month: {visit_performance['month_label']}",
            f"Stores tracked: {visit_performance['store_count']}",
            "",
        ]
    )
    if visit_performance["store_rows"]:
        for row in visit_performance["store_rows"]:
            lines.extend(
                [
                    f"- {row['store_name']}: {row['visits_made']}/{row['expected_by_today']} visits by today ({row['completion_percent']}%) - {row['status']}",
                    f"  Full month target: {row['expected_full_month']} visits",
                ]
            )
            if row["remaining_to_pace"]:
                lines.append(f"  Action: Complete {row['remaining_to_pace']} more visit(s) for this store to catch up.")
            else:
                lines.append("  Action: Maintain current visit pace.")
    else:
        lines.append("No active stores configured.")
    lines.append("")

    lines.append("4. Employee visit contribution this month")
    if visit_performance["employee_rows"]:
        for row in visit_performance["employee_rows"]:
            lines.append(f"- {row['employee_name']}: {row['visit_count']} store visit(s)")
    else:
        lines.append("No monthly store visits recorded yet.")
    lines.append("")

    return subject, "\n".join(lines)


def build_dashboard_store_overview(rows: list[dict], visit_performance: dict) -> dict:
    groups: dict[int, dict] = {}
    status_rank = {"Critical": 3, "Unhealthy": 2, "Healthy": 1}
    monthly_by_store = {row["store_id"]: row for row in visit_performance["store_rows"]}

    for row in rows:
        group = groups.get(row["store_id"])
        if group is None:
            group = {
                "store_id": row["store_id"],
                "store_name": row["store_name"],
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "sku_count": 0,
                "critical_skus": 0,
                "unhealthy_skus": 0,
                "expiring_skus": 0,
                "expiring_total": 0,
                "is_overdue": False,
                "last_visit": None,
                "last_visit_display": "No visit",
                "last_visit_employee": "No visit",
                "status": "Healthy",
            }
            groups[row["store_id"]] = group

        group["sku_count"] += 1
        if row["status"] == "Critical":
            group["critical_skus"] += 1
        elif row["status"] == "Unhealthy":
            group["unhealthy_skus"] += 1
        if (row["expiring_count"] or 0) >= 1:
            group["expiring_skus"] += 1
            group["expiring_total"] += row["expiring_count"] or 0
        if row["is_stale"]:
            group["is_overdue"] = True
        if status_rank[row["status"]] > status_rank[group["status"]]:
            group["status"] = row["status"]
        if row["last_visit"] and (group["last_visit"] is None or row["last_visit"] > group["last_visit"]):
            group["last_visit"] = row["last_visit"]
            group["last_visit_display"] = row["last_visit_display"]
            group["last_visit_employee"] = row["employee_name"] or "No visit"

    overview_rows = []
    counts = {"Healthy": 0, "Unhealthy": 0, "Critical": 0}
    for group in groups.values():
        monthly = monthly_by_store.get(
            group["store_id"],
            {
                "visits_made": 0,
                "expected_by_today": 0,
                "completion_percent": 0,
                "remaining_to_pace": 0,
                "status": "Behind plan",
            },
        )
        counts[group["status"]] += 1
        action_parts = []
        if group["expiring_skus"]:
            action_parts.append("expiry action")
        if group["is_overdue"]:
            action_parts.append("visit overdue")
        if monthly["remaining_to_pace"]:
            action_parts.append("monthly visits behind")
        if not action_parts:
            action_parts.append("maintain pace")

        overview_rows.append(
            {
                **group,
                "status_lower": group["status"].lower(),
                "monthly_visits_made": monthly["visits_made"],
                "monthly_expected_by_today": monthly["expected_by_today"],
                "monthly_completion_percent": monthly["completion_percent"],
                "monthly_remaining_to_pace": monthly["remaining_to_pace"],
                "monthly_status": monthly["status"],
                "action": ", ".join(action_parts),
            }
        )

    overview_rows.sort(
        key=lambda row: (
            -status_rank[row["status"]],
            -row["expiring_skus"],
            -row["monthly_remaining_to_pace"],
            row["store_name"].lower(),
        )
    )

    total = len(overview_rows)
    if total:
        critical_degrees = counts["Critical"] / total * 360
        unhealthy_degrees = critical_degrees + counts["Unhealthy"] / total * 360
        donut_style = (
            "background: conic-gradient("
            f"#f6c7c1 0deg {critical_degrees:.1f}deg, "
            f"#fce7b7 {critical_degrees:.1f}deg {unhealthy_degrees:.1f}deg, "
            f"#dcefdc {unhealthy_degrees:.1f}deg 360deg);"
        )
    else:
        donut_style = "background: #f3dede;"

    return {
        "rows": overview_rows,
        "counts": counts,
        "total": total,
        "critical_stores": counts["Critical"],
        "unhealthy_stores": counts["Unhealthy"],
        "healthy_stores": counts["Healthy"],
        "overdue_stores": sum(1 for row in overview_rows if row["is_overdue"]),
        "expiring_skus": sum(row["expiring_skus"] for row in overview_rows),
        "donut_style": donut_style,
    }


def build_mailto_url(subject: str, body: str) -> str:
    recipient = os.environ.get("CRITICAL_REPORT_TO_EMAIL", "").strip()
    return f"mailto:{quote(recipient)}?subject={quote(subject)}&body={quote(body)}"


def fetch_current_status_rows(
    search: str = "",
    store_id: int | None = None,
    city_id: int | None = None,
) -> list[sqlite3.Row]:
    query = """
        WITH latest_visits AS (
            SELECT
                store_name,
                sku,
                employee_name,
                shelf_count,
                expiring_count,
                created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY store_name, sku
                    ORDER BY datetime(created_at) DESC, id DESC
                ) AS row_number
            FROM stock_visits
        )
        SELECT
            stores.id AS store_id,
            stores.name AS store_name,
            cities.id AS city_id,
            cities.name AS city_name,
            skus.id AS sku_id,
            skus.name AS sku_name,
            store_skus.recommended_count,
            store_skus.created_at AS mapping_created_at,
            latest_visits.employee_name,
            latest_visits.shelf_count,
            latest_visits.expiring_count,
            latest_visits.created_at
        FROM store_skus
        JOIN stores ON stores.id = store_skus.store_id
        LEFT JOIN cities ON cities.id = stores.city_id
        JOIN skus ON skus.id = store_skus.sku_id
        LEFT JOIN latest_visits
            ON latest_visits.row_number = 1
            AND latest_visits.store_name = stores.name
            AND latest_visits.sku = skus.name
    """
    params: list[str] = []
    where_clauses: list[str] = []
    if search:
        where_clauses.append("(stores.name LIKE ? OR cities.name LIKE ? OR skus.name LIKE ? OR latest_visits.employee_name LIKE ?)")
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term, like_term])
    if store_id is not None:
        where_clauses.append("stores.id = ?")
        params.append(str(store_id))
    if city_id is not None:
        where_clauses.append("stores.city_id = ?")
        params.append(str(city_id))
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY stores.name COLLATE NOCASE, skus.name COLLATE NOCASE"

    rows = get_db().execute(query, params).fetchall()
    current_status_rows: list[sqlite3.Row] = []
    for row in rows:
        stale_visit = is_visit_overdue(row["created_at"], row["mapping_created_at"])
        status = get_status(
            row["shelf_count"],
            row["expiring_count"],
            row["recommended_count"],
            row["created_at"],
            row["mapping_created_at"],
        )
        current_status_rows.append(
            {
                "store_id": row["store_id"],
                "store_name": row["store_name"],
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "sku_id": row["sku_id"],
                "sku_name": row["sku_name"],
                "recommended_count": row["recommended_count"],
                "mapping_created_at": row["mapping_created_at"],
                "employee_name": row["employee_name"],
                "shelf_count": row["shelf_count"],
                "expiring_count": row["expiring_count"],
                "last_visit": row["created_at"],
                "last_visit_display": relative_time_display(row["created_at"]),
                "is_stale": stale_visit,
                "status": status,
            }
        )
    return current_status_rows


@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard", methods=["GET"])
def dashboard():
    db = get_db()
    cleanup_old_visits(db)
    db.commit()
    search = request.args.get("search", "").strip()
    selected_store_id = request.args.get("store_id", "").strip()
    selected_city_id = request.args.get("city_id", "").strip()
    selected_store_id_value: int | None = None
    selected_city_id_value: int | None = None
    if selected_store_id:
        try:
            selected_store_id_value = int(selected_store_id)
        except ValueError:
            selected_store_id_value = None
    if selected_city_id:
        try:
            selected_city_id_value = int(selected_city_id)
        except ValueError:
            selected_city_id_value = None
    current_status_rows = fetch_current_status_rows(search, selected_store_id_value, selected_city_id_value)
    dashboard_status_groups = []
    dashboard_groups_by_store: dict[int, dict] = {}
    for row in current_status_rows:
        group = dashboard_groups_by_store.get(row["store_id"])
        if group is None:
            group = {
                "store_id": row["store_id"],
                "store_name": row["store_name"],
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "rows": [],
            }
            dashboard_groups_by_store[row["store_id"]] = group
            dashboard_status_groups.append(group)
        group["rows"].append(row)
    recent_visits = db.execute(
        """
        SELECT id, store_name, employee_name, sku, shelf_count, expiring_count, notes, created_at
        FROM stock_visits
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 10
        """
    ).fetchall()
    stores = db.execute("SELECT id, name FROM stores ORDER BY name COLLATE NOCASE").fetchall()
    cities = db.execute("SELECT id, name FROM cities ORDER BY name COLLATE NOCASE").fetchall()
    skus = db.execute("SELECT id, name FROM skus ORDER BY name COLLATE NOCASE").fetchall()
    employees = db.execute("SELECT id, name FROM employees ORDER BY name COLLATE NOCASE").fetchall()

    summary = {
        "stores": db.execute("SELECT COUNT(*) FROM stores").fetchone()[0],
        "shelf_total": sum((row["shelf_count"] or 0) for row in current_status_rows),
        "expiring_total": sum((row["expiring_count"] or 0) for row in current_status_rows),
        "stores_active": len(stores),
        "skus_active": len(skus),
        "mapped_skus": db.execute("SELECT COUNT(*) FROM store_skus").fetchone()[0],
    }
    visit_performance = get_monthly_visit_performance()
    store_overview = build_dashboard_store_overview(current_status_rows, visit_performance)
    critical_report_subject, critical_report_body = build_critical_report(current_status_rows, visit_performance)

    return render_template(
        "index.html",
        current_status_rows=current_status_rows,
        dashboard_status_groups=dashboard_status_groups,
        store_overview=store_overview,
        recent_visits=recent_visits,
        summary=summary,
        critical_report_mailto=build_mailto_url(critical_report_subject, critical_report_body),
        search=search,
        stores=stores,
        cities=cities,
        skus=skus,
        employees=employees,
        selected_store_id=selected_store_id,
        selected_city_id=selected_city_id,
    )


@app.route("/api/stores/<int:store_id>/skus", methods=["GET"])
def store_skus_api(store_id: int):
    rows = get_db().execute(
        """
        SELECT skus.id, skus.name
        FROM store_skus
        JOIN skus ON skus.id = store_skus.sku_id
        WHERE store_skus.store_id = ?
        ORDER BY skus.name COLLATE NOCASE
        """,
        (store_id,),
    ).fetchall()
    return jsonify([{"id": row["id"], "name": row["name"]} for row in rows])


@app.route("/inventory", methods=["GET"])
def inventory():
    db = get_db()
    cleanup_old_inventory_history(db)
    db.commit()
    rows = db.execute(
        """
        SELECT
            id,
            name,
            quantity,
            unit,
            emergency_minimum,
            updated_at
        FROM inventory_items
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()
    total_units = sum(row["quantity"] or 0 for row in rows)
    low_stock_count = sum(1 for row in rows if (row["quantity"] or 0) <= (row["emergency_minimum"] or 0))
    history_rows = db.execute(
        """
        SELECT item_name, change_type, quantity_before, quantity_after, emergency_minimum_before,
               emergency_minimum_after, note, created_at
        FROM inventory_history
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 20
        """
    ).fetchall()
    return render_template(
        "inventory.html",
        inventory_rows=rows,
        history_rows=history_rows,
        total_units=total_units,
        low_stock_count=low_stock_count,
        inventory_units=INVENTORY_UNITS,
    )


@app.route("/inventory/items", methods=["POST"])
def add_inventory_item():
    name = request.form.get("name", "").strip()
    quantity = request.form.get("quantity", "").strip()
    unit = request.form.get("unit", "").strip()
    emergency_minimum = request.form.get("emergency_minimum", "").strip()
    if not name or unit not in INVENTORY_UNITS:
        return redirect(url_for("inventory"))
    try:
        quantity_value = int(quantity or 0)
        emergency_minimum_value = int(emergency_minimum or 0)
    except ValueError:
        return redirect(url_for("inventory"))
    if quantity_value < 0 or emergency_minimum_value < 0:
        return redirect(url_for("inventory"))

    db = get_db()
    existing_row = db.execute(
        "SELECT id, quantity, unit, emergency_minimum FROM inventory_items WHERE name = ?",
        (name,),
    ).fetchone()
    db.execute(
        """
        INSERT INTO inventory_items (name, quantity, unit, emergency_minimum, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(name) DO UPDATE SET
            quantity = inventory_items.quantity + excluded.quantity,
            updated_at = CURRENT_TIMESTAMP
        """,
        (name, quantity_value, unit, emergency_minimum_value),
    )
    item_row = db.execute(
        "SELECT id, quantity, unit, emergency_minimum FROM inventory_items WHERE name = ?",
        (name,),
    ).fetchone()
    record_inventory_history(
        db,
        item_row["id"],
        name,
        "Added item" if existing_row is None else "Added stock",
        existing_row["quantity"] if existing_row else None,
        item_row["quantity"],
        existing_row["emergency_minimum"] if existing_row else None,
        item_row["emergency_minimum"],
        f"Inventory item saved in {item_row['unit']}",
    )
    db.commit()
    cleanup_old_inventory_history(db)
    db.commit()
    return redirect(url_for("inventory"))


@app.route("/manage", methods=["GET"])
def manage():
    selected_store_id = request.args.get("store_id", "").strip()
    selected_store_id_value: int | None = None
    if selected_store_id:
        try:
            selected_store_id_value = int(selected_store_id)
        except ValueError:
            selected_store_id_value = None

    stores = get_db().execute(
        """
        SELECT stores.id, stores.name, stores.city_id, COALESCE(cities.name, stores.city) AS city_name
        FROM stores
        LEFT JOIN cities ON cities.id = stores.city_id
        ORDER BY stores.name COLLATE NOCASE
        """
    ).fetchall()
    cities = get_db().execute("SELECT id, name FROM cities ORDER BY name COLLATE NOCASE").fetchall()
    skus = get_db().execute("SELECT id, name FROM skus ORDER BY name COLLATE NOCASE").fetchall()
    employees = get_db().execute("SELECT id, name FROM employees ORDER BY name COLLATE NOCASE").fetchall()
    store_sku_rows = get_db().execute(
        """
        SELECT
            store_skus.id,
            store_skus.store_id,
            store_skus.sku_id,
            stores.name AS store_name,
            skus.name AS sku_name,
            store_skus.recommended_count
        FROM store_skus
        JOIN stores ON stores.id = store_skus.store_id
        JOIN skus ON skus.id = store_skus.sku_id
        ORDER BY stores.name COLLATE NOCASE, skus.name COLLATE NOCASE
        """
    ).fetchall()

    assignments_by_store: dict[int, list[sqlite3.Row]] = {}
    for row in store_sku_rows:
        assignments_by_store.setdefault(row["store_id"], []).append(row)

    assigned_sku_ids_by_store = {
        str(store_id): [row["sku_id"] for row in rows]
        for store_id, rows in assignments_by_store.items()
    }

    assignment_groups = []
    for store in stores:
        if selected_store_id_value is not None and store["id"] != selected_store_id_value:
            continue
        assignment_groups.append(
            {
                "store": store,
                "assignments": assignments_by_store.get(store["id"], []),
            }
        )

    return render_template(
        "manage.html",
        stores=stores,
        cities=cities,
        skus=skus,
        employees=employees,
        assignment_groups=assignment_groups,
        assigned_sku_ids_by_store=assigned_sku_ids_by_store,
        selected_store_id=selected_store_id,
    )


@app.route("/stores", methods=["POST"])
def add_store():
    name = request.form.get("name", "").strip()
    city_id = request.form.get("city_id", "").strip()
    if not name or not city_id:
        return redirect(url_for("manage"))
    try:
        city_id_value = int(city_id)
    except ValueError:
        return redirect(url_for("manage"))
    db = get_db()
    city_exists = db.execute("SELECT 1 FROM cities WHERE id = ?", (city_id_value,)).fetchone()
    if city_exists is None:
        return redirect(url_for("manage"))
    db.execute("INSERT OR IGNORE INTO stores (name, city_id) VALUES (?, ?)", (name, city_id_value))
    db.commit()
    return redirect(url_for("manage"))


@app.route("/stores/<int:store_id>/city", methods=["POST"])
def update_store_city(store_id: int):
    city_id = request.form.get("city_id", "").strip()
    try:
        city_id_value = int(city_id) if city_id else None
    except ValueError:
        return redirect(url_for("manage"))
    db = get_db()
    db.execute("UPDATE stores SET city_id = ? WHERE id = ?", (city_id_value, store_id))
    db.commit()
    return redirect(url_for("manage"))


@app.route("/cities", methods=["POST"])
def add_city():
    name = request.form.get("name", "").strip()
    if name:
        db = get_db()
        db.execute("INSERT OR IGNORE INTO cities (name) VALUES (?)", (name,))
        db.commit()
    return redirect(url_for("manage"))


@app.route("/cities/<int:city_id>/delete", methods=["POST"])
def delete_city(city_id: int):
    db = get_db()
    db.execute("UPDATE stores SET city_id = NULL WHERE city_id = ?", (city_id,))
    db.execute("DELETE FROM cities WHERE id = ?", (city_id,))
    db.commit()
    return redirect(url_for("manage"))


@app.route("/stores/<int:store_id>/delete", methods=["POST"])
def delete_store(store_id: int):
    db = get_db()
    db.execute("DELETE FROM store_skus WHERE store_id = ?", (store_id,))
    db.execute("DELETE FROM stores WHERE id = ?", (store_id,))
    db.commit()
    return redirect(url_for("manage"))


@app.route("/skus", methods=["POST"])
def add_sku():
    name = request.form.get("name", "").strip()
    if name:
        db = get_db()
        db.execute("INSERT OR IGNORE INTO skus (name) VALUES (?)", (name,))
        db.commit()
    return redirect(url_for("manage"))


@app.route("/skus/<int:sku_id>/delete", methods=["POST"])
def delete_sku(sku_id: int):
    db = get_db()
    db.execute("DELETE FROM store_skus WHERE sku_id = ?", (sku_id,))
    db.execute("DELETE FROM skus WHERE id = ?", (sku_id,))
    db.commit()
    return redirect(url_for("manage"))


@app.route("/inventory/<int:item_id>/set", methods=["POST"])
def set_inventory_item(item_id: int):
    quantity = request.form.get("quantity", "").strip()
    try:
        quantity_value = int(quantity or 0)
    except ValueError:
        return redirect(url_for("inventory"))
    if quantity_value < 0:
        return redirect(url_for("inventory"))

    db = get_db()
    item_row = db.execute(
        "SELECT id, name, quantity, emergency_minimum FROM inventory_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if item_row is None:
        return redirect(url_for("inventory"))
    db.execute(
        """
        UPDATE inventory_items
        SET quantity = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (quantity_value, item_id),
    )
    record_inventory_history(
        db,
        item_id,
        item_row["name"],
        "Set quantity",
        item_row["quantity"],
        quantity_value,
        item_row["emergency_minimum"],
        item_row["emergency_minimum"],
        "Exact quantity saved",
    )
    db.commit()
    cleanup_old_inventory_history(db)
    db.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return build_inventory_update_response(db, item_id)
    return redirect(url_for("inventory"))


@app.route("/inventory/<int:item_id>/adjust", methods=["POST"])
def adjust_inventory_item(item_id: int):
    adjustment = request.form.get("adjustment", "").strip()
    try:
        adjustment_value = int(adjustment)
    except ValueError:
        return redirect(url_for("inventory"))

    db = get_db()
    current_row = db.execute(
        "SELECT name, quantity, unit, emergency_minimum FROM inventory_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if current_row is None:
        return redirect(url_for("inventory"))
    current_quantity = current_row["quantity"] if current_row else 0
    new_quantity = max(current_quantity + adjustment_value, 0)
    db.execute(
        "UPDATE inventory_items SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_quantity, item_id),
    )
    record_inventory_history(
        db,
        item_id,
        current_row["name"],
        "Adjusted quantity",
        current_quantity,
        new_quantity,
        current_row["emergency_minimum"],
        current_row["emergency_minimum"],
        f"Adjustment {adjustment_value:+d}",
    )
    db.commit()
    cleanup_old_inventory_history(db)
    db.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return build_inventory_update_response(db, item_id)
    return redirect(url_for("inventory"))


@app.route("/inventory/<int:item_id>/delete", methods=["POST"])
def delete_inventory_item(item_id: int):
    db = get_db()
    item_row = db.execute(
        "SELECT name, quantity, emergency_minimum FROM inventory_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if item_row is not None:
        record_inventory_history(
            db,
            item_id,
            item_row["name"],
            "Deleted item",
            item_row["quantity"],
            None,
            item_row["emergency_minimum"],
            None,
            "Inventory item deleted",
        )
    db.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
    db.commit()
    cleanup_old_inventory_history(db)
    db.commit()
    return redirect(url_for("inventory"))


@app.route("/employees", methods=["POST"])
def add_employee():
    name = request.form.get("name", "").strip()
    if name:
        db = get_db()
        db.execute("INSERT OR IGNORE INTO employees (name) VALUES (?)", (name,))
        db.commit()
    return redirect(url_for("manage", _anchor="employees"))


@app.route("/employees/<int:employee_id>/delete", methods=["POST"])
def delete_employee(employee_id: int):
    db = get_db()
    db.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    db.commit()
    return redirect(url_for("manage", _anchor="employees"))


@app.route("/store-skus", methods=["POST"])
def add_store_sku():
    store_id = request.form.get("store_id", "").strip()
    sku_id = request.form.get("sku_id", "").strip()
    recommended_count = request.form.get("recommended_count", "").strip()
    if store_id and sku_id and recommended_count:
        try:
            recommended_count_value = int(recommended_count)
        except ValueError:
            return redirect(url_for("manage", _anchor="assignments"))
        if recommended_count_value <= 0:
            return redirect(url_for("manage", _anchor="assignments"))

        db = get_db()
        db.execute(
            """
            INSERT INTO store_skus (store_id, sku_id, recommended_count)
            VALUES (?, ?, ?)
            ON CONFLICT(store_id, sku_id) DO UPDATE SET recommended_count = excluded.recommended_count
            """,
            (int(store_id), int(sku_id), recommended_count_value),
        )
        db.commit()
    return redirect(url_for("manage", _anchor="assignments"))


@app.route("/store-skus/<int:assignment_id>/delete", methods=["POST"])
def delete_store_sku(assignment_id: int):
    db = get_db()
    db.execute("DELETE FROM store_skus WHERE id = ?", (assignment_id,))
    db.commit()
    return redirect(url_for("manage", _anchor="assignments"))


@app.route("/store-skus/<int:assignment_id>/recommended-count", methods=["POST"])
def update_store_sku_recommended_count(assignment_id: int):
    recommended_count = request.form.get("recommended_count", "").strip()
    try:
        recommended_count_value = int(recommended_count)
    except ValueError:
        return redirect(url_for("manage", _anchor="assignments"))
    if recommended_count_value <= 0:
        return redirect(url_for("manage", _anchor="assignments"))

    db = get_db()
    db.execute(
        "UPDATE store_skus SET recommended_count = ? WHERE id = ?",
        (recommended_count_value, assignment_id),
    )
    db.commit()
    return redirect(url_for("manage", _anchor="assignments"))


@app.route("/record", methods=["POST"])
def record_visit():
    form = request.form
    store_id = form.get("store_id", "").strip()
    employee_id = form.get("employee_id", "").strip()
    employee_name = form.get("employee_name", "").strip()
    sku_id = form.get("sku_id", "").strip()
    shelf_count = form.get("shelf_count", "").strip()
    expiring_count = form.get("expiring_count", "").strip()
    notes = form.get("notes", "").strip()

    if not store_id or not sku_id:
        return redirect(url_for("dashboard"))

    db = get_db()
    store_row = db.execute("SELECT id, name FROM stores WHERE id = ?", (int(store_id),)).fetchone()
    sku_row = db.execute("SELECT id, name FROM skus WHERE id = ?", (int(sku_id),)).fetchone()
    if store_row is None or sku_row is None:
        return redirect(url_for("dashboard"))

    if employee_id:
        try:
            employee_id_value = int(employee_id)
        except ValueError:
            return redirect(url_for("dashboard"))
        employee_row = db.execute("SELECT id, name FROM employees WHERE id = ?", (employee_id_value,)).fetchone()
        if employee_row is None:
            return redirect(url_for("dashboard"))
        employee_name = employee_row["name"]
    if not employee_name:
        return redirect(url_for("dashboard"))

    mapping_exists = db.execute(
        "SELECT 1 FROM store_skus WHERE store_id = ? AND sku_id = ?",
        (store_row["id"], sku_row["id"]),
    ).fetchone()
    if mapping_exists is None:
        return redirect(url_for("dashboard"))

    try:
        shelf_count_value = int(shelf_count or 0)
        expiring_count_value = int(expiring_count or 0)
    except ValueError:
        return redirect(url_for("dashboard"))

    if shelf_count_value < 0 or expiring_count_value < 0:
        return redirect(url_for("dashboard"))

    db.execute(
        """
        INSERT INTO stock_visits (store_name, employee_name, sku, shelf_count, expiring_count, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (store_row["name"], employee_name, sku_row["name"], shelf_count_value, expiring_count_value, notes),
    )
    record_monthly_store_visit(db, store_row["id"], store_row["name"], employee_name)
    cleanup_old_visits(db)
    db.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        current_status_rows = fetch_current_status_rows()
        updated_row = next(
            (
                row for row in current_status_rows if row["store_id"] == store_row["id"] and row["sku_id"] == sku_row["id"]
            ),
            None,
        )
        summary = {
            "stores": get_db().execute("SELECT COUNT(*) FROM stores").fetchone()[0],
            "shelf_total": sum((row["shelf_count"] or 0) for row in current_status_rows),
            "expiring_total": sum((row["expiring_count"] or 0) for row in current_status_rows),
            "stores_active": get_db().execute("SELECT COUNT(*) FROM stores").fetchone()[0],
            "skus_active": get_db().execute("SELECT COUNT(*) FROM skus").fetchone()[0],
            "mapped_skus": get_db().execute("SELECT COUNT(*) FROM store_skus").fetchone()[0],
        }
        visit_performance = get_monthly_visit_performance()
        store_overview = build_dashboard_store_overview(current_status_rows, visit_performance)
        critical_report_subject, critical_report_body = build_critical_report(current_status_rows, visit_performance)
        return jsonify(
            {
                "ok": True,
                "row": updated_row,
                "summary": summary,
                "store_overview": store_overview,
                "critical_report_mailto": build_mailto_url(critical_report_subject, critical_report_body),
            }
        )
    return redirect(url_for("dashboard"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "8001")))
