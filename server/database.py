"""
Database module for Lab #26 MCP Server.
Uses SQLite for portability — no external DB setup required.
"""

import sqlite3
import os
from pathlib import Path

# Default DB path, overridable via env var
DB_PATH = Path(os.getenv("DB_PATH", "./data/lab26.db"))


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force: bool = False) -> None:
    """
    Initialize the database schema and seed sample data.

    Args:
        force: If True, drops existing tables and recreates them.
    """
    conn = get_connection()
    cursor = conn.cursor()

    if force:
        cursor.executescript("""
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS products;
            DROP TABLE IF EXISTS customers;
        """)

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            category    TEXT    NOT NULL,
            price       REAL    NOT NULL CHECK(price >= 0),
            stock       INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS customers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            email       TEXT    UNIQUE NOT NULL,
            region      TEXT    NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id  INTEGER NOT NULL REFERENCES customers(id),
            product_id   INTEGER NOT NULL REFERENCES products(id),
            quantity     INTEGER NOT NULL CHECK(quantity > 0),
            total_price  REAL    NOT NULL CHECK(total_price >= 0),
            quarter      TEXT    NOT NULL,
            status       TEXT    NOT NULL DEFAULT 'completed'
                         CHECK(status IN ('completed', 'pending', 'cancelled')),
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_orders_quarter     ON orders(quarter);
        CREATE INDEX IF NOT EXISTS idx_orders_status      ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_products_category  ON products(category);
        CREATE INDEX IF NOT EXISTS idx_customers_region   ON customers(region);
    """)

    # Seed data only if tables are empty
    product_count = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if product_count == 0:
        _seed_data(cursor)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH.resolve()}")


def _seed_data(cursor: sqlite3.Cursor) -> None:
    """Insert realistic Vietnamese sales sample data."""
    cursor.executemany(
        "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        [
            ("Laptop Pro 15",        "Electronics",  25_000_000, 50),
            ("Smartphone X12",       "Electronics",  15_000_000, 120),
            ("Wireless Headphones",  "Electronics",   3_000_000, 200),
            ("Mechanical Keyboard",  "Electronics",   1_500_000,  80),
            ("4K Monitor 27\"",      "Electronics",   8_000_000,  40),
            ("Office Chair Ergon",   "Furniture",     5_000_000,  30),
            ("Standing Desk Pro",    "Furniture",     8_000_000,  20),
            ("Bookshelf Oak",        "Furniture",     3_500_000,  25),
            ("Notebook Set A4",      "Stationery",      150_000, 500),
            ("Premium Pen Set",      "Stationery",      200_000,1000),
            ("Coffee Maker Deluxe",  "Appliances",    2_500_000,  75),
            ("Air Purifier Pro",     "Appliances",    4_000_000,  45),
        ],
    )

    cursor.executemany(
        "INSERT INTO customers (name, email, region) VALUES (?, ?, ?)",
        [
            ("Nguyễn Văn An",    "nva@example.com",   "Hanoi"),
            ("Trần Thị Bình",    "ttb@example.com",   "HCMC"),
            ("Lê Văn Cường",     "lvc@example.com",   "Da Nang"),
            ("Phạm Thị Dung",    "ptd@example.com",   "Hanoi"),
            ("Hoàng Văn Em",     "hve@example.com",   "HCMC"),
            ("Vũ Thị Phương",    "vtp@example.com",   "Da Nang"),
            ("Đặng Minh Quân",   "dmq@example.com",   "Hanoi"),
            ("Bùi Thị Hoa",      "bth@example.com",   "HCMC"),
        ],
    )

    orders_data = [
        # Q1-2025
        (1, 1, 2, 50_000_000, "Q1-2025", "completed"),
        (2, 2, 1, 15_000_000, "Q1-2025", "completed"),
        (3, 3, 3,  9_000_000, "Q1-2025", "completed"),
        (4, 9, 10, 1_500_000, "Q1-2025", "completed"),
        # Q2-2025
        (5, 4, 1,  5_000_000, "Q2-2025", "completed"),
        (6, 5, 2, 16_000_000, "Q2-2025", "completed"),
        (7, 6, 1,  2_500_000, "Q2-2025", "completed"),
        (1, 7, 1,  8_000_000, "Q2-2025", "pending"),
        # Q3-2025
        (2, 1, 1, 25_000_000, "Q3-2025", "completed"),
        (3, 2, 2, 30_000_000, "Q3-2025", "completed"),
        (4, 8, 1,  3_500_000, "Q3-2025", "completed"),
        (5, 9, 5,    750_000, "Q3-2025", "completed"),
        (6, 10,10, 2_000_000, "Q3-2025", "completed"),
        # Q4-2025
        (7, 11, 1, 2_500_000, "Q4-2025", "completed"),
        (8, 12, 1, 4_000_000, "Q4-2025", "completed"),
        (1, 5,  2, 16_000_000,"Q4-2025", "completed"),
        (2, 4,  3,  4_500_000,"Q4-2025", "pending"),
    ]

    cursor.executemany(
        """INSERT INTO orders
           (customer_id, product_id, quantity, total_price, quarter, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        orders_data,
    )


def get_schema_ddl() -> str:
    """Return CREATE TABLE DDL for all tables."""
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    conn.close()
    return "\n\n".join(row[0] for row in rows if row[0])
