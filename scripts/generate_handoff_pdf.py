from __future__ import annotations

from datetime import date
from pathlib import Path
import textwrap


OUTPUT_PATH = Path("StoreSkuTracker_Developer_Handoff.pdf")


def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap(text: str, width: int = 92) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [""]


sections = [
    {
        "title": "Project Overview",
        "body": [
            "StoreSkuTracker is a small Flask + SQLite web app used to track store-level SKU shelf counts, expiring items, and current stock health.",
            "The app has two main pages: /dashboard for live stock updates and /manage for managing stores, SKUs, and store-to-SKU assignments.",
            "The current production deployment is on PythonAnywhere Free under the account/site: https://trujoescoffee.pythonanywhere.com",
        ],
    },
    {
        "title": "Current Tech Stack",
        "bullets": [
            "Backend: Flask in app.py",
            "Database: SQLite at instance/stock_tracker.sqlite3",
            "Frontend: Jinja templates in templates/, JavaScript in static/app.js, CSS in static/styles.css",
            "Deployment target: PythonAnywhere Free plan",
            "PythonAnywhere project path: /home/trujoescoffee/StoreSkuTracker",
            "PythonAnywhere virtualenv: /home/trujoescoffee/.virtualenvs/storesku",
        ],
    },
    {
        "title": "Main Features Implemented",
        "bullets": [
            "Dashboard shows current stock status for each active store/SKU assignment.",
            "Employees can update shelf count and expiring count inline from the dashboard.",
            "Manage page can add/delete stores and SKU names.",
            "Manage page can assign SKUs to stores.",
            "Each store/SKU assignment has a recommended shelf count.",
            "Recommended shelf count can be edited directly from the assignment list.",
            "Dashboard includes a manager-friendly note explaining all status and color conditions.",
            "Dashboard and recent visits are mobile-friendly: on phones, tables become stacked cards.",
            "Historical visit records are preserved even when stores/SKUs are removed from the active catalog.",
        ],
    },
    {
        "title": "Status and Color Rules",
        "bullets": [
            "Healthy: current shelf count is above 50% of the recommended count and no items are expiring.",
            "Unhealthy: current shelf count is 20% to 50% of the recommended count and no items are expiring.",
            "Critical: at least 1 item is expiring, shelf count is below 20%, no count exists, or last visit is older than 72 hours.",
            "Rows with visits older than 72 hours are tinted red and marked Critical.",
        ],
    },
    {
        "title": "Database Tables",
        "bullets": [
            "stores: active store list.",
            "skus: active SKU list.",
            "store_skus: active store-to-SKU mappings, including recommended_count.",
            "stock_visits: historical visit/update records. This table stores store and SKU names as text so history remains readable after catalog changes.",
        ],
    },
    {
        "title": "Important Behavior Notes",
        "bullets": [
            "The app no longer repopulates active stores/SKUs from stock_visits on startup. This was fixed because deleted stores were reappearing after reload.",
            "Existing store/SKU mappings received a default recommended_count of 10 when the migration was added.",
            "Adding the same store/SKU mapping again from /manage updates its recommended count instead of creating a duplicate.",
            "Inline dashboard saves create a new stock_visits row. The dashboard then calculates current status from the latest visit per store/SKU pair.",
        ],
    },
    {
        "title": "Local Development Commands",
        "bullets": [
            "Create virtualenv: python3 -m venv .venv",
            "Activate virtualenv: source .venv/bin/activate",
            "Install dependencies: pip install -r requirements.txt",
            "Run locally: python app.py",
            "Local URL: http://127.0.0.1:8001",
            "Syntax check used during development: .venv/bin/python -m py_compile app.py",
        ],
    },
    {
        "title": "PythonAnywhere Deployment Steps Completed",
        "bullets": [
            "Code was uploaded to PythonAnywhere via ZIP.",
            "ZIP was extracted into /home/trujoescoffee/StoreSkuTracker.",
            "Virtualenv storesku was created.",
            "Dependencies were installed from requirements.txt.",
            "A manual Flask web app was configured from the PythonAnywhere Web tab.",
            "WSGI path was configured to import app from /home/trujoescoffee/StoreSkuTracker.",
            "Static files mapping was configured: URL /static/ -> /home/trujoescoffee/StoreSkuTracker/static.",
            "The app was reloaded and confirmed running at https://trujoescoffee.pythonanywhere.com.",
        ],
    },
    {
        "title": "PythonAnywhere WSGI Configuration",
        "code": [
            "import sys",
            "",
            "path = '/home/trujoescoffee/StoreSkuTracker'",
            "if path not in sys.path:",
            "    sys.path.insert(0, path)",
            "",
            "from app import app as application",
        ],
    },
    {
        "title": "Current Production Paths",
        "bullets": [
            "Application code: /home/trujoescoffee/StoreSkuTracker",
            "SQLite database: /home/trujoescoffee/StoreSkuTracker/instance/stock_tracker.sqlite3",
            "Static files: /home/trujoescoffee/StoreSkuTracker/static",
            "Templates: /home/trujoescoffee/StoreSkuTracker/templates",
            "Virtualenv: /home/trujoescoffee/.virtualenvs/storesku",
        ],
    },
    {
        "title": "Backup Guidance",
        "body": [
            "Because the app uses SQLite on the PythonAnywhere Free plan, the database file should be backed up periodically. A simple manual backup command is:",
        ],
        "code": [
            "cp ~/StoreSkuTracker/instance/stock_tracker.sqlite3 ~/stock_tracker_backup.sqlite3",
        ],
    },
    {
        "title": "Recommended Next Improvements",
        "bullets": [
            "Add login/password protection before wider employee rollout. Currently anyone with the URL can edit data.",
            "Move SECRET_KEY to an environment variable instead of hardcoding it.",
            "Add user roles later if managers and employees should have different permissions.",
            "For more users or heavier simultaneous updates, consider moving from SQLite to MySQL/Postgres.",
            "Add automated database backups if this becomes business-critical.",
            "Clean up committed local-only files such as .venv, __pycache__, and generated database copies before maintaining the GitHub repo.",
        ],
    },
    {
        "title": "Files Future Developer Should Review First",
        "bullets": [
            "app.py: Flask routes, SQLite schema, migrations, and status rules.",
            "templates/index.html: dashboard UI and manager status note.",
            "templates/manage.html: store/SKU management and recommended count editing.",
            "static/app.js: inline dashboard AJAX save and client-side filtering.",
            "static/styles.css: desktop, mobile, status, and card/table styling.",
            "README.md: run instructions and project summary.",
        ],
    },
]


def build_pages() -> list[list[tuple[str, int, str]]]:
    pages: list[list[tuple[str, int, str]]] = []
    current: list[tuple[str, int, str]] = []
    line_count = 0
    max_lines = 46

    def add_line(text: str, size: int = 10, kind: str = "body") -> None:
        nonlocal current, line_count
        if line_count >= max_lines:
            pages.append(current)
            current = []
            line_count = 0
        current.append((text, size, kind))
        line_count += 1

    add_line("StoreSkuTracker Developer Handoff", 20, "title")
    add_line(f"Prepared on {date.today().isoformat()}", 10, "muted")
    add_line("", 10)
    for section in sections:
        if line_count > max_lines - 8:
            pages.append(current)
            current = []
            line_count = 0
        add_line(section["title"], 14, "heading")
        for paragraph in section.get("body", []):
            for line in wrap(paragraph):
                add_line(line)
            add_line("")
        for bullet in section.get("bullets", []):
            wrapped = wrap(bullet, width=88)
            add_line(f"- {wrapped[0]}")
            for continuation in wrapped[1:]:
                add_line(f"  {continuation}")
        if "bullets" in section:
            add_line("")
        for code_line in section.get("code", []):
            add_line(code_line, 9, "code")
        if "code" in section:
            add_line("")

    if current:
        pages.append(current)
    return pages


def make_stream(lines: list[tuple[str, int, str]], page_num: int, total_pages: int) -> bytes:
    y = 760
    parts = ["BT"]
    for text, size, kind in lines:
        if kind == "title":
            font = "F2"
            color = "0.10 0.16 0.28"
            leading = 24
        elif kind == "heading":
            font = "F2"
            color = "0.18 0.45 0.70"
            leading = 19
        elif kind == "muted":
            font = "F1"
            color = "0.38 0.38 0.38"
            leading = 15
        elif kind == "code":
            font = "F3"
            color = "0.12 0.12 0.12"
            leading = 13
        else:
            font = "F1"
            color = "0.08 0.08 0.08"
            leading = 14

        if text:
            parts.append(f"/{font} {size} Tf {color} rg 1 0 0 1 72 {y} Tm ({pdf_escape(text)}) Tj")
        y -= leading
    parts.append(f"/F1 8 Tf 0.45 0.45 0.45 rg 1 0 0 1 72 42 Tm (Page {page_num} of {total_pages}) Tj")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1")


def write_pdf() -> None:
    pages = build_pages()
    objects: list[bytes] = []

    def add_object(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    catalog_id = add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object(b"")
    font_regular_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    font_mono_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_ids: list[int] = []
    for index, page_lines in enumerate(pages, start=1):
        stream = make_stream(page_lines, index, len(pages))
        stream_id = add_object(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        page = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
            + f"/Contents {stream_id} 0 R >>".encode()
        )
        page_ids.append(add_object(page))

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids).encode()
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_ids)).encode() + b" >>"

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj_id, data in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{obj_id} 0 obj\n".encode())
        output.extend(data)
        output.extend(b"\nendobj\n")
    xref_pos = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    OUTPUT_PATH.write_bytes(output)


if __name__ == "__main__":
    write_pdf()
    print(OUTPUT_PATH)
