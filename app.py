from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "stock_tracker.sqlite3"

app = Flask(__name__)
app.config["SECRET_KEY"] = "stock-tracker-local-dev"


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
                UNIQUE(store_id, sku_id)
            )
            """
        )
        store_sku_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(store_skus)").fetchall()
        }
        if "recommended_count" not in store_sku_columns:
            connection.execute(
                "ALTER TABLE store_skus ADD COLUMN recommended_count INTEGER NOT NULL DEFAULT 10 CHECK (recommended_count > 0)"
            )
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


def is_visit_stale(last_visit: str | None) -> bool:
    if not last_visit:
        return True
    try:
        parsed = datetime.fromisoformat(last_visit)
    except (TypeError, ValueError):
        return True
    now = datetime.now(UTC).replace(tzinfo=None)
    return now - parsed > timedelta(hours=72)


def get_status(
    shelf_count: int | None,
    expiring_count: int | None,
    recommended_count: int,
    last_visit: str | None,
) -> str:
    if shelf_count is None or expiring_count is None:
        return "Critical"
    if expiring_count >= 1:
        return "Critical"
    if is_visit_stale(last_visit):
        return "Critical"
    if shelf_count < recommended_count * 0.2:
        return "Critical"
    if shelf_count <= recommended_count * 0.5:
        return "Unhealthy"
    return "Healthy"


def fetch_current_status_rows(search: str = "") -> list[sqlite3.Row]:
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
            skus.id AS sku_id,
            skus.name AS sku_name,
            store_skus.recommended_count,
            latest_visits.employee_name,
            latest_visits.shelf_count,
            latest_visits.expiring_count,
            latest_visits.created_at
        FROM store_skus
        JOIN stores ON stores.id = store_skus.store_id
        JOIN skus ON skus.id = store_skus.sku_id
        LEFT JOIN latest_visits
            ON latest_visits.row_number = 1
            AND latest_visits.store_name = stores.name
            AND latest_visits.sku = skus.name
    """
    params: list[str] = []
    if search:
        query += " WHERE stores.name LIKE ? OR skus.name LIKE ? OR latest_visits.employee_name LIKE ?"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term])
    query += " ORDER BY stores.name COLLATE NOCASE, skus.name COLLATE NOCASE"

    rows = get_db().execute(query, params).fetchall()
    current_status_rows: list[sqlite3.Row] = []
    for row in rows:
        stale_visit = is_visit_stale(row["created_at"])
        status = get_status(
            row["shelf_count"],
            row["expiring_count"],
            row["recommended_count"],
            row["created_at"],
        )
        current_status_rows.append(
            {
                "store_id": row["store_id"],
                "store_name": row["store_name"],
                "sku_id": row["sku_id"],
                "sku_name": row["sku_name"],
                "recommended_count": row["recommended_count"],
                "employee_name": row["employee_name"],
                "shelf_count": row["shelf_count"],
                "expiring_count": row["expiring_count"],
                "last_visit": row["created_at"],
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
    search = request.args.get("search", "").strip()
    current_status_rows = fetch_current_status_rows(search)
    recent_visits = get_db().execute(
        """
        SELECT id, store_name, employee_name, sku, shelf_count, expiring_count, notes, created_at
        FROM stock_visits
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 10
        """
    ).fetchall()
    stores = get_db().execute("SELECT id, name FROM stores ORDER BY name COLLATE NOCASE").fetchall()
    skus = get_db().execute("SELECT id, name FROM skus ORDER BY name COLLATE NOCASE").fetchall()

    summary = {
        "stores": get_db().execute("SELECT COUNT(*) FROM stores").fetchone()[0],
        "records": get_db().execute("SELECT COUNT(*) FROM stock_visits").fetchone()[0],
        "shelf_total": sum((row["shelf_count"] or 0) for row in current_status_rows),
        "expiring_total": sum((row["expiring_count"] or 0) for row in current_status_rows),
        "stores_active": len(stores),
        "skus_active": len(skus),
        "mapped_skus": get_db().execute("SELECT COUNT(*) FROM store_skus").fetchone()[0],
    }

    return render_template(
        "index.html",
        current_status_rows=current_status_rows,
        recent_visits=recent_visits,
        summary=summary,
        search=search,
        stores=stores,
        skus=skus,
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


@app.route("/manage", methods=["GET"])
def manage():
    stores = get_db().execute("SELECT id, name FROM stores ORDER BY name COLLATE NOCASE").fetchall()
    skus = get_db().execute("SELECT id, name FROM skus ORDER BY name COLLATE NOCASE").fetchall()
    store_sku_rows = get_db().execute(
        """
        SELECT store_skus.id, stores.name AS store_name, skus.name AS sku_name, store_skus.recommended_count
        FROM store_skus
        JOIN stores ON stores.id = store_skus.store_id
        JOIN skus ON skus.id = store_skus.sku_id
        ORDER BY stores.name COLLATE NOCASE, skus.name COLLATE NOCASE
        """
    ).fetchall()
    return render_template("manage.html", stores=stores, skus=skus, store_sku_rows=store_sku_rows)


@app.route("/stores", methods=["POST"])
def add_store():
    name = request.form.get("name", "").strip()
    if name:
        db = get_db()
        db.execute("INSERT OR IGNORE INTO stores (name) VALUES (?)", (name,))
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


@app.route("/store-skus", methods=["POST"])
def add_store_sku():
    store_id = request.form.get("store_id", "").strip()
    sku_id = request.form.get("sku_id", "").strip()
    recommended_count = request.form.get("recommended_count", "").strip()
    if store_id and sku_id and recommended_count:
        try:
            recommended_count_value = int(recommended_count)
        except ValueError:
            return redirect(url_for("manage"))
        if recommended_count_value <= 0:
            return redirect(url_for("manage"))

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
    return redirect(url_for("manage"))


@app.route("/store-skus/<int:assignment_id>/delete", methods=["POST"])
def delete_store_sku(assignment_id: int):
    db = get_db()
    db.execute("DELETE FROM store_skus WHERE id = ?", (assignment_id,))
    db.commit()
    return redirect(url_for("manage"))


@app.route("/store-skus/<int:assignment_id>/recommended-count", methods=["POST"])
def update_store_sku_recommended_count(assignment_id: int):
    recommended_count = request.form.get("recommended_count", "").strip()
    try:
        recommended_count_value = int(recommended_count)
    except ValueError:
        return redirect(url_for("manage"))
    if recommended_count_value <= 0:
        return redirect(url_for("manage"))

    db = get_db()
    db.execute(
        "UPDATE store_skus SET recommended_count = ? WHERE id = ?",
        (recommended_count_value, assignment_id),
    )
    db.commit()
    return redirect(url_for("manage"))


@app.route("/record", methods=["POST"])
def record_visit():
    form = request.form
    store_id = form.get("store_id", "").strip()
    employee_name = form.get("employee_name", "").strip()
    sku_id = form.get("sku_id", "").strip()
    shelf_count = form.get("shelf_count", "").strip()
    expiring_count = form.get("expiring_count", "").strip()
    notes = form.get("notes", "").strip()

    if not store_id or not employee_name or not sku_id or not shelf_count or not expiring_count:
        return redirect(url_for("dashboard"))

    db = get_db()
    store_row = db.execute("SELECT id, name FROM stores WHERE id = ?", (int(store_id),)).fetchone()
    sku_row = db.execute("SELECT id, name FROM skus WHERE id = ?", (int(sku_id),)).fetchone()
    if store_row is None or sku_row is None:
        return redirect(url_for("dashboard"))

    mapping_exists = db.execute(
        "SELECT 1 FROM store_skus WHERE store_id = ? AND sku_id = ?",
        (store_row["id"], sku_row["id"]),
    ).fetchone()
    if mapping_exists is None:
        return redirect(url_for("dashboard"))

    try:
        shelf_count_value = int(shelf_count)
        expiring_count_value = int(expiring_count)
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
            "records": get_db().execute("SELECT COUNT(*) FROM stock_visits").fetchone()[0],
            "shelf_total": sum((row["shelf_count"] or 0) for row in current_status_rows),
            "expiring_total": sum((row["expiring_count"] or 0) for row in current_status_rows),
            "stores_active": get_db().execute("SELECT COUNT(*) FROM stores").fetchone()[0],
            "skus_active": get_db().execute("SELECT COUNT(*) FROM skus").fetchone()[0],
            "mapped_skus": get_db().execute("SELECT COUNT(*) FROM store_skus").fetchone()[0],
        }
        return jsonify(
            {
                "ok": True,
                "row": updated_row,
                "summary": summary,
            }
        )
    return redirect(url_for("dashboard"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "8001")))
