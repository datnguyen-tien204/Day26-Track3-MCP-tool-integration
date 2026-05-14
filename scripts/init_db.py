#!/usr/bin/env python3
"""
scripts/init_db.py
==================
Initialize (or reset) the Lab #26 SQLite database with sample data.

Usage:
    python scripts/init_db.py          # init only if empty
    python scripts/init_db.py --reset  # drop & recreate all tables
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import init_db, get_connection, DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize Lab #26 database")
    parser.add_argument(
        "--reset", action="store_true",
        help="Drop all tables and recreate with fresh sample data"
    )
    args = parser.parse_args()

    print(f"DB path: {DB_PATH.resolve()}")

    if args.reset:
        print("WARNING: Resetting database (all existing data will be lost)...")

    init_db(force=args.reset)

    # Print summary
    conn = get_connection()
    cur = conn.cursor()
    for table in ("products", "customers", "orders"):
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  OK {table}: {count} rows")
    conn.close()

    print("\nDatabase ready. Run the MCP server:")
    print("  python server/main.py")


if __name__ == "__main__":
    main()
