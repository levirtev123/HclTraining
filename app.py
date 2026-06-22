from __future__ import annotations

import json
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DB_PATH = ROOT / "sales_demo.db"


SCHEMA = {
    "customers": ["id", "name", "region", "segment", "joined_on"],
    "products": ["id", "name", "category", "price"],
    "orders": ["id", "customer_id", "product_id", "quantity", "order_date", "status"],
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                region TEXT NOT NULL,
                segment TEXT NOT NULL,
                joined_on TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            """
        )

        has_data = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if has_data:
            return

        conn.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
            [
                (1, "Apex Labs", "North", "Enterprise", "2024-01-15"),
                (2, "Bright Retail", "West", "SMB", "2024-03-09"),
                (3, "Cobalt Health", "South", "Enterprise", "2023-11-21"),
                (4, "Delta Foods", "East", "Mid-Market", "2025-02-01"),
                (5, "Evergreen Studio", "West", "SMB", "2025-05-17"),
                (6, "Forge Systems", "North", "Mid-Market", "2024-09-10"),
            ],
        )
        conn.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?)",
            [
                (1, "Analytics Pro", "Software", 249.0),
                (2, "Data Sync", "Software", 149.0),
                (3, "Support Plus", "Services", 99.0),
                (4, "Onboarding Sprint", "Services", 799.0),
                (5, "Secure Gateway", "Hardware", 399.0),
            ],
        )
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 1, 5, "2026-01-08", "Paid"),
                (2, 1, 3, 12, "2026-02-14", "Paid"),
                (3, 2, 2, 3, "2026-03-02", "Pending"),
                (4, 3, 4, 1, "2026-03-21", "Paid"),
                (5, 4, 5, 2, "2026-04-11", "Paid"),
                (6, 5, 3, 8, "2026-05-03", "Cancelled"),
                (7, 6, 1, 2, "2026-05-18", "Paid"),
                (8, 2, 5, 1, "2026-06-01", "Pending"),
                (9, 3, 2, 9, "2026-06-07", "Paid"),
                (10, 4, 1, 1, "2026-06-14", "Paid"),
            ],
        )


def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def detect_limit(text: str) -> int:
    match = re.search(r"\b(?:top|first|limit)\s+(\d{1,3})\b", text)
    if match:
        return min(max(int(match.group(1)), 1), 100)
    return 50


def build_filters(text: str) -> list[str]:
    filters: list[str] = []
    region_map = {
        "north": "North",
        "south": "South",
        "east": "East",
        "west": "West",
    }
    status_map = {
        "paid": "Paid",
        "pending": "Pending",
        "cancelled": "Cancelled",
        "canceled": "Cancelled",
    }
    segment_map = {
        "enterprise": "Enterprise",
        "smb": "SMB",
        "small business": "SMB",
        "mid market": "Mid-Market",
        "mid-market": "Mid-Market",
    }

    for token, value in region_map.items():
        if re.search(rf"\b{re.escape(token)}\b", text):
            filters.append(f"c.region = {quote(value)}")

    for token, value in status_map.items():
        if re.search(rf"\b{re.escape(token)}\b", text):
            filters.append(f"o.status = {quote(value)}")

    for token, value in segment_map.items():
        if re.search(rf"\b{re.escape(token)}\b", text):
            filters.append(f"c.segment = {quote(value)}")

    category_match = re.search(r"\b(software|services|hardware)\b", text)
    if category_match:
        filters.append(f"p.category = {quote(category_match.group(1).title())}")

    after_match = re.search(r"\b(?:after|since)\s+(\d{4}-\d{2}-\d{2})\b", text)
    before_match = re.search(r"\bbefore\s+(\d{4}-\d{2}-\d{2})\b", text)
    if after_match:
        filters.append(f"o.order_date >= {quote(after_match.group(1))}")
    if before_match:
        filters.append(f"o.order_date < {quote(before_match.group(1))}")

    return filters


def translate_to_sql(prompt: str) -> str:
    text = prompt.lower().strip()
    limit = detect_limit(text)
    filters = build_filters(text)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    if any(word in text for word in ["product", "products", "item", "items"]) and any(
        word in text for word in ["revenue", "sales", "sold", "units"]
    ):
        return f"""
            SELECT p.name AS product, p.category, p.price, COALESCE(SUM(o.quantity), 0) AS units_sold,
                   ROUND(COALESCE(SUM(o.quantity * p.price), 0), 2) AS revenue
            FROM products p
            LEFT JOIN orders o ON o.product_id = p.id
            LEFT JOIN customers c ON c.id = o.customer_id
            {where_clause}
            GROUP BY p.id
            ORDER BY revenue DESC, units_sold DESC
            LIMIT {limit}
        """

    if any(word in text for word in ["revenue", "sales", "total amount", "amount"]):
        if "by region" in text or "per region" in text:
            return f"""
                SELECT c.region, ROUND(SUM(o.quantity * p.price), 2) AS revenue
                FROM orders o
                JOIN customers c ON c.id = o.customer_id
                JOIN products p ON p.id = o.product_id
                {where_clause}
                GROUP BY c.region
                ORDER BY revenue DESC
                LIMIT {limit}
            """
        if "by product" in text or "per product" in text:
            return f"""
                SELECT p.name AS product, p.category, ROUND(SUM(o.quantity * p.price), 2) AS revenue
                FROM orders o
                JOIN products p ON p.id = o.product_id
                JOIN customers c ON c.id = o.customer_id
                {where_clause}
                GROUP BY p.id, p.name, p.category
                ORDER BY revenue DESC
                LIMIT {limit}
            """
        return f"""
            SELECT ROUND(SUM(o.quantity * p.price), 2) AS revenue
            FROM orders o
            JOIN products p ON p.id = o.product_id
            JOIN customers c ON c.id = o.customer_id
            {where_clause}
        """

    if any(word in text for word in ["customer", "customers", "account", "accounts"]):
        if "count" in text or "how many" in text:
            return f"""
                SELECT c.region, COUNT(DISTINCT c.id) AS customers
                FROM customers c
                LEFT JOIN orders o ON o.customer_id = c.id
                LEFT JOIN products p ON p.id = o.product_id
                {where_clause}
                GROUP BY c.region
                ORDER BY customers DESC
                LIMIT {limit}
            """
        return f"""
            SELECT c.name, c.region, c.segment, c.joined_on
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.id
            LEFT JOIN products p ON p.id = o.product_id
            {where_clause}
            GROUP BY c.id
            ORDER BY c.joined_on DESC
            LIMIT {limit}
        """

    if any(word in text for word in ["product", "products", "item", "items"]):
        return f"""
            SELECT p.name, p.category, p.price, COALESCE(SUM(o.quantity), 0) AS units_sold
            FROM products p
            LEFT JOIN orders o ON o.product_id = p.id
            LEFT JOIN customers c ON c.id = o.customer_id
            {where_clause}
            GROUP BY p.id
            ORDER BY units_sold DESC, p.name ASC
            LIMIT {limit}
        """

    return f"""
        SELECT o.id AS order_id, c.name AS customer, c.region, p.name AS product,
               o.quantity, ROUND(o.quantity * p.price, 2) AS amount, o.order_date, o.status
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        JOIN products p ON p.id = o.product_id
        {where_clause}
        ORDER BY o.order_date DESC
        LIMIT {limit}
    """


def normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def run_query(prompt: str) -> dict:
    sql = normalize_sql(translate_to_sql(prompt))
    if not sql.lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    with connect() as conn:
        rows = conn.execute(sql).fetchall()
        return {
            "sql": sql,
            "columns": rows[0].keys() if rows else [],
            "rows": [dict(row) for row in rows],
            "schema": SCHEMA,
        }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            path = "/index.html"

        file_path = STATIC / path.lstrip("/")
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return

        content_type = "text/html" if file_path.suffix == ".html" else "text/css"
        if file_path.suffix == ".js":
            content_type = "application/javascript"

        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/query":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length))
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                raise ValueError("Enter a question before running a query.")
            self.send_json(200, run_query(prompt))
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})


def main() -> None:
    initialize_database()
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("NL-to-SQL UI running at http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()
