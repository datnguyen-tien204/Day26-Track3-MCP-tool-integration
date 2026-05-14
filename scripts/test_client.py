#!/usr/bin/env python3
"""
scripts/test_client.py
======================
Quick smoke-test script - verifies all 3 tools work correctly
WITHOUT needing an MCP client or Inspector.

Run from project root:
    python scripts/test_client.py
"""

import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import init_db
# Import tool functions directly for unit-style testing
from server.main import search_records, insert_record, aggregate_data, get_schema, get_stats

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = 0
failed = 0


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'-'*50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'-'*50}{RESET}")


def ok(label: str, detail: str = "") -> None:
    global passed
    passed += 1
    print(f"  {GREEN}PASS{RESET}  {label}" + (f"  ->  {detail}" if detail else ""))


def fail(label: str, detail: str = "") -> None:
    global failed
    failed += 1
    print(f"  {RED}FAIL{RESET}  {label}" + (f"  ->  {detail}" if detail else ""))


async def run_tests() -> None:
    # Setup
    section("Setup: Initialize DB")
    init_db()
    ok("DB initialized")

    # Tool 1: search_records
    section("Tool 1: search_records")

    # Valid table, no filter
    res = await search_records("products")
    if "records" in res and res["returned"] > 0:
        ok("search all products", f"{res['returned']} rows")
    else:
        fail("search all products", str(res))

    # Filter by category
    res = await search_records("products", {"category": "Electronics"})
    if "records" in res and all("Electronics" in r["category"] for r in res["records"]):
        ok("filter by category=Electronics", f"{res['returned']} rows")
    else:
        fail("filter by category=Electronics", str(res))

    # Filter customers by region
    res = await search_records("customers", {"region": "Hanoi"})
    if "records" in res and res["returned"] > 0:
        ok("filter customers by region=Hanoi", f"{res['returned']} rows")
    else:
        fail("filter customers by region=Hanoi", str(res))

    # Filter orders by quarter
    res = await search_records("orders", {"quarter": "Q3-2025"})
    if "records" in res:
        ok("filter orders by quarter=Q3-2025", f"{res['returned']} rows")
    else:
        fail("filter orders by quarter", str(res))

    # Invalid table should return error, not crash
    res = await search_records("nonexistent_table")
    if "error" in res:
        ok("invalid table returns error gracefully")
    else:
        fail("invalid table should return error", str(res))

    # Limit capping
    res = await search_records("products", limit=999)
    if res.get("returned", 0) <= 100:
        ok("limit capped at 100")
    else:
        fail("limit not capped", str(res.get("returned")))

    # Tool 2: insert_record
    section("Tool 2: insert_record")

    # Insert valid product
    res = await insert_record("products", {
        "name": "Test Laptop", "category": "Electronics",
        "price": 20_000_000, "stock": 5
    })
    if res.get("success") and res.get("id"):
        ok("insert valid product", f"id={res['id']}")
        inserted_product_id = res["id"]
    else:
        fail("insert valid product", str(res))
        inserted_product_id = 1

    # Insert valid customer
    res = await insert_record("customers", {
        "name": "Test User", "email": "test_unique_99@example.com", "region": "Da Nang"
    })
    if res.get("success") and res.get("id"):
        ok("insert valid customer", f"id={res['id']}")
        inserted_customer_id = res["id"]
    else:
        fail("insert valid customer", str(res))
        inserted_customer_id = 1

    # Insert valid order
    res = await insert_record("orders", {
        "customer_id": inserted_customer_id,
        "product_id":  inserted_product_id,
        "quantity":    2,
        "total_price": 40_000_000,
        "quarter":     "Q1-2026",
    })
    if res.get("success") and res.get("id"):
        ok("insert valid order", f"id={res['id']}")
    else:
        fail("insert valid order", str(res))

    # Missing required field
    res = await insert_record("products", {"name": "Incomplete"})
    if not res.get("success") and "error" in res:
        ok("missing fields returns error gracefully")
    else:
        fail("missing fields should return error", str(res))

    # Invalid table
    res = await insert_record("bad_table", {"x": 1})
    if not res.get("success"):
        ok("invalid table returns error gracefully")
    else:
        fail("invalid table should return error", str(res))

    # Tool 3: aggregate_data
    section("Tool 3: aggregate_data")

    metrics = [
        "revenue_by_quarter",
        "revenue_by_region",
        "revenue_by_category",
        "top_products",
        "order_count_by_status",
        "customer_summary",
        "inventory_summary",
    ]
    for metric in metrics:
        res = await aggregate_data(metric)
        if "results" in res and res["row_count"] >= 0:
            ok(f"metric: {metric}", f"{res['row_count']} groups")
        else:
            fail(f"metric: {metric}", str(res))

    # With quarter filter
    res = await aggregate_data("top_products", quarter_filter="Q3-2025")
    if "results" in res:
        ok("top_products with quarter_filter", f"{res['row_count']} products")
    else:
        fail("top_products with quarter_filter", str(res))

    # With region filter
    res = await aggregate_data("revenue_by_region", region_filter="Hanoi")
    if "results" in res:
        ok("revenue_by_region with region_filter", f"{res['row_count']} rows")
    else:
        fail("revenue_by_region with region_filter", str(res))

    # Invalid metric
    res = await aggregate_data("made_up_metric")
    if "error" in res:
        ok("invalid metric returns error gracefully")
    else:
        fail("invalid metric should return error", str(res))

    # Resources
    section("Resources")

    schema = await get_schema()
    if "products" in schema and "orders" in schema and "customers" in schema:
        ok("db://schema - contains all table names")
    else:
        fail("db://schema - missing table info")

    stats = await get_stats()
    if "Products" in stats and "VND" in stats:
        ok("db://stats - contains counts and revenue")
    else:
        fail("db://stats - missing expected fields", stats[:100])

    # Summary
    section("Results")
    total = passed + failed
    color = GREEN if failed == 0 else RED
    print(f"\n  {color}{BOLD}{passed}/{total} tests passed{RESET}")
    if failed > 0:
        print(f"  {RED}{failed} test(s) failed - check output above{RESET}")
    else:
        print(f"  {GREEN}All tests passed! Server is ready for Inspector & Claude Desktop.{RESET}")
    print()

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
