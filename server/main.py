"""
Lab #26 — MCP Server (STDIO transport)
======================================
FastMCP server exposing:
  Tools:     search_records, insert_record, aggregate_data
  Resources: db://schema, db://stats
  Prompts:   analyze-sales

Run:
    python -m server.main
    # or
    python server/main.py
"""

import sys
import os

# Allow running as `python server/main.py` from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from server.database import get_connection, init_db, get_schema_ddl

# ─────────────────────────────────────────────
# Server instantiation
# ─────────────────────────────────────────────
mcp = FastMCP(
    name="lab26-sales-db",
    instructions="""
Sales Database MCP Server — Lab #26 (VinUniversity AICB).

Use this server when the user asks about:
  • Sales data, revenue, product performance, customer info
  • Inserting new products, customers, or orders
  • Aggregating/summarizing business metrics

Workflow recommendation:
  1. Read db://schema to understand available tables/columns
  2. Use search_records() to find specific records
  3. Use aggregate_data() for business intelligence summaries
  4. Use insert_record() to add new data

Available aggregate metrics:
  revenue_by_quarter, revenue_by_region, revenue_by_category,
  top_products, order_count_by_status, customer_summary, inventory_summary
""",
)


# ─────────────────────────────────────────────
# TOOL 1: search_records
# ─────────────────────────────────────────────
@mcp.tool()
async def search_records(
    table: str,
    filters: dict | None = None,
    limit: int = 10,
) -> dict:
    """
    Search and retrieve records from the sales database.

    Use this tool when you need to find specific rows in any table.
    Supports partial-match filtering on any column.

    Args:
        table:   Table to query. Must be one of: 'products', 'customers', 'orders'
        filters: Optional {column: value} dict for WHERE conditions (LIKE matching).
                 Example: {"category": "Electronics"} or {"region": "Hanoi"}
        limit:   Max rows to return (1–100, default 10)

    Returns:
        {table, records: [...], returned: int, total: int}

    Examples:
        search_records("products", {"category": "Electronics"})
        search_records("customers", {"region": "Hanoi"})
        search_records("orders", {"quarter": "Q3-2025", "status": "completed"})
        search_records("products")  # returns first 10 products
    """
    VALID_TABLES = {"products", "customers", "orders"}
    if table not in VALID_TABLES:
        return {"error": f"Invalid table '{table}'. Choose from: {sorted(VALID_TABLES)}"}

    limit = max(1, min(limit, 100))

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Build WHERE clause safely (column names validated below)
        where_clause = ""
        params: list = []

        if filters:
            # Get actual column names to prevent injection via column names
            pragma_rows = cursor.execute(f"PRAGMA table_info({table})").fetchall()
            valid_cols = {row["name"] for row in pragma_rows}

            conditions = []
            for col, val in filters.items():
                if col not in valid_cols:
                    conn.close()
                    return {"error": f"Column '{col}' does not exist in table '{table}'"}
                conditions.append(f"{col} LIKE ?")
                params.append(f"%{val}%")

            where_clause = "WHERE " + " AND ".join(conditions)

        rows = cursor.execute(
            f"SELECT * FROM {table} {where_clause} LIMIT ?",
            params + [limit],
        ).fetchall()

        total = cursor.execute(
            f"SELECT COUNT(*) FROM {table} {where_clause}", params
        ).fetchone()[0]

        conn.close()
        return {
            "table":    table,
            "records":  [dict(r) for r in rows],
            "returned": len(rows),
            "total":    total,
        }

    except Exception as exc:
        return {"error": str(exc), "table": table}


# ─────────────────────────────────────────────
# TOOL 2: insert_record
# ─────────────────────────────────────────────
@mcp.tool()
async def insert_record(table: str, data: dict) -> dict:
    """
    Insert a new record into the sales database.

    Use this tool when the user wants to add new products, customers, or orders.
    Always validate required fields before calling.

    Args:
        table: Target table. Must be one of: 'products', 'customers', 'orders'
        data:  Dict of column->value pairs for the new record.

    Required fields per table:
        products:  name (str), category (str), price (float), stock (int)
        customers: name (str), email (str), region (str)
        orders:    customer_id (int), product_id (int), quantity (int),
                   total_price (float), quarter (str, e.g. 'Q1-2025')

    Returns:
        {success: bool, id: int, message: str}

    Examples:
        insert_record("products", {
            "name": "Gaming Chair", "category": "Furniture",
            "price": 6500000, "stock": 15
        })
        insert_record("customers", {
            "name": "Test User", "email": "test@example.com", "region": "Hanoi"
        })
        insert_record("orders", {
            "customer_id": 1, "product_id": 2,
            "quantity": 1, "total_price": 15000000,
            "quarter": "Q1-2026"
        })
    """
    VALID_TABLES = {"products", "customers", "orders"}
    if table not in VALID_TABLES:
        return {"success": False, "error": f"Invalid table '{table}'. Choose from: {sorted(VALID_TABLES)}"}

    if not data:
        return {"success": False, "error": "No data provided."}

    REQUIRED_FIELDS: dict[str, list[str]] = {
        "products":  ["name", "category", "price", "stock"],
        "customers": ["name", "email", "region"],
        "orders":    ["customer_id", "product_id", "quantity", "total_price", "quarter"],
    }

    missing = [f for f in REQUIRED_FIELDS[table] if f not in data]
    if missing:
        return {
            "success": False,
            "error": f"Missing required fields for '{table}': {missing}",
            "required": REQUIRED_FIELDS[table],
        }

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Validate column names against actual schema
        pragma_rows = cursor.execute(f"PRAGMA table_info({table})").fetchall()
        valid_cols = {row["name"] for row in pragma_rows} - {"id", "created_at"}

        safe_data = {k: v for k, v in data.items() if k in valid_cols}
        unknown = set(data.keys()) - valid_cols - {"id", "created_at"}
        if unknown:
            conn.close()
            return {"success": False, "error": f"Unknown columns: {list(unknown)}"}

        cols = ", ".join(safe_data.keys())
        placeholders = ", ".join("?" for _ in safe_data)
        cursor.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(safe_data.values()),
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()

        return {
            "success": True,
            "id":      new_id,
            "message": f"Record inserted into '{table}' with id={new_id}",
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ─────────────────────────────────────────────
# TOOL 3: aggregate_data
# ─────────────────────────────────────────────
@mcp.tool()
async def aggregate_data(
    metric: str,
    quarter_filter: str | None = None,
    region_filter: str | None = None,
) -> dict:
    """
    Aggregate and summarize sales data for business intelligence.

    Use this as the PRIMARY tool for analysis, reporting, and KPI queries.
    Do NOT use search_records for aggregation — use this instead.

    Args:
        metric: The aggregation to perform. Must be one of:
            'revenue_by_quarter'     — Total revenue, orders, avg value per quarter
            'revenue_by_region'      — Revenue and customer count per region
            'revenue_by_category'    — Revenue and units sold per product category
            'top_products'           — Top 10 products ranked by total revenue
            'order_count_by_status'  — Count and value of orders by status
            'customer_summary'       — Customer count and spend per region
            'inventory_summary'      — Stock levels, price range per category

        quarter_filter: Optional quarter to filter results (e.g. 'Q3-2025').
                        Applies to metrics that join with orders.
        region_filter:  Optional region to filter (e.g. 'Hanoi', 'HCMC').
                        Applies to metrics that join with customers.

    Returns:
        {metric, results: [...], row_count: int, summary: str, filters_applied: dict}

    Examples:
        aggregate_data("revenue_by_quarter")
        aggregate_data("top_products", quarter_filter="Q3-2025")
        aggregate_data("revenue_by_region", region_filter="Hanoi")
        aggregate_data("inventory_summary")
    """
    METRICS: dict[str, str] = {
        "revenue_by_quarter": """
            SELECT
                o.quarter,
                SUM(o.total_price)  AS total_revenue,
                COUNT(o.id)         AS order_count,
                ROUND(AVG(o.total_price), 0) AS avg_order_value,
                SUM(o.quantity)     AS units_sold
            FROM orders o
            {where}
            GROUP BY o.quarter
            ORDER BY o.quarter
        """,
        "revenue_by_region": """
            SELECT
                c.region,
                SUM(o.total_price)          AS total_revenue,
                COUNT(o.id)                 AS order_count,
                COUNT(DISTINCT o.customer_id) AS unique_customers,
                SUM(o.quantity)             AS units_sold
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            {where}
            GROUP BY c.region
            ORDER BY total_revenue DESC
        """,
        "revenue_by_category": """
            SELECT
                p.category,
                SUM(o.total_price)  AS total_revenue,
                COUNT(o.id)         AS order_count,
                SUM(o.quantity)     AS units_sold,
                COUNT(DISTINCT p.id) AS product_count
            FROM orders o
            JOIN products p ON o.product_id = p.id
            {where}
            GROUP BY p.category
            ORDER BY total_revenue DESC
        """,
        "top_products": """
            SELECT
                p.name,
                p.category,
                p.price,
                SUM(o.total_price)  AS total_revenue,
                SUM(o.quantity)     AS units_sold,
                COUNT(o.id)         AS order_count
            FROM orders o
            JOIN products p ON o.product_id = p.id
            {where}
            GROUP BY p.id, p.name, p.category, p.price
            ORDER BY total_revenue DESC
            LIMIT 10
        """,
        "order_count_by_status": """
            SELECT
                o.status,
                COUNT(o.id)        AS order_count,
                SUM(o.total_price) AS total_value,
                SUM(o.quantity)    AS units
            FROM orders o
            {where}
            GROUP BY o.status
            ORDER BY order_count DESC
        """,
        "customer_summary": """
            SELECT
                c.region,
                COUNT(DISTINCT c.id)        AS customer_count,
                COUNT(o.id)                 AS total_orders,
                COALESCE(SUM(o.total_price), 0) AS total_spend
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.id
            {where_customers}
            GROUP BY c.region
            ORDER BY total_spend DESC
        """,
        "inventory_summary": """
            SELECT
                category,
                COUNT(*)            AS product_count,
                SUM(stock)          AS total_stock,
                ROUND(AVG(price),0) AS avg_price,
                MIN(price)          AS min_price,
                MAX(price)          AS max_price
            FROM products
            GROUP BY category
            ORDER BY total_stock DESC
        """,
    }

    if metric not in METRICS:
        return {
            "error":            f"Unknown metric '{metric}'.",
            "available_metrics": sorted(METRICS.keys()),
        }

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Build WHERE conditions
        conditions: list[str] = []
        params: list = []
        filters_applied: dict = {}

        if quarter_filter and metric not in ("inventory_summary", "customer_summary"):
            conditions.append("o.quarter = ?")
            params.append(quarter_filter)
            filters_applied["quarter"] = quarter_filter

        if region_filter and metric in ("revenue_by_region", "top_products",
                                        "revenue_by_quarter", "revenue_by_category",
                                        "order_count_by_status"):
            conditions.append("c.region = ?")
            params.append(region_filter)
            filters_applied["region"] = region_filter

        # Special handling for customer_summary (no orders join in base)
        where_customers = ""
        if region_filter and metric == "customer_summary":
            where_customers = "WHERE c.region = ?"
            params.append(region_filter)
            filters_applied["region"] = region_filter

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        sql = METRICS[metric].format(where=where, where_customers=where_customers)
        rows = cursor.execute(sql, params).fetchall()
        results = [dict(r) for r in rows]
        conn.close()

        # Build summary string
        summary = f"{len(results)} group(s) returned for '{metric}'"
        if results and "total_revenue" in (results[0] if results else {}):
            grand = sum(r.get("total_revenue", 0) or 0 for r in results)
            summary += f" | Grand total revenue: {grand:,.0f} VND"
        if filters_applied:
            summary += f" | Filters: {filters_applied}"

        return {
            "metric":          metric,
            "results":         results,
            "row_count":       len(results),
            "summary":         summary,
            "filters_applied": filters_applied,
        }

    except Exception as exc:
        return {"error": str(exc), "metric": metric}


# ─────────────────────────────────────────────
# RESOURCE 1: Database Schema
# ─────────────────────────────────────────────
@mcp.resource("db://schema")
async def get_schema() -> str:
    """
    Full database schema — tables, columns, types, constraints.
    Read this FIRST before querying to understand available data.
    """
    return f"""# Lab26 Sales Database Schema

## DDL (raw SQL)
```sql
{get_schema_ddl()}
```

---

## Table Reference

### products
| Column      | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| id          | INTEGER | PK, auto-increment                             |
| name        | TEXT    | Product name                                   |
| category    | TEXT    | Electronics / Furniture / Stationery / Appliances |
| price       | REAL    | Price in VND                                   |
| stock       | INTEGER | Current stock quantity                         |
| created_at  | TS      | Auto-set on insert                             |

### customers
| Column      | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| id          | INTEGER | PK, auto-increment                             |
| name        | TEXT    | Full name                                      |
| email       | TEXT    | Unique                                         |
| region      | TEXT    | Hanoi / HCMC / Da Nang                         |
| created_at  | TS      | Auto-set on insert                             |

### orders
| Column       | Type    | Notes                                         |
|--------------|---------|-----------------------------------------------|
| id           | INTEGER | PK, auto-increment                            |
| customer_id  | INTEGER | FK → customers.id                             |
| product_id   | INTEGER | FK → products.id                              |
| quantity     | INTEGER | Units ordered (> 0)                           |
| total_price  | REAL    | Total value in VND                            |
| quarter      | TEXT    | e.g. Q1-2025, Q2-2025, Q3-2025, Q4-2025      |
| status       | TEXT    | completed / pending / cancelled               |
| created_at   | TS      | Auto-set on insert                            |

---

## Quick Examples
```
# Search
search_records("products", {{"category": "Electronics"}})
search_records("orders", {{"quarter": "Q3-2025", "status": "completed"}})

# Insert
insert_record("products", {{"name": "New Item", "category": "Electronics", "price": 5000000, "stock": 10}})

# Aggregate
aggregate_data("revenue_by_quarter")
aggregate_data("top_products", quarter_filter="Q3-2025")
aggregate_data("revenue_by_region", region_filter="Hanoi")
```
"""


# ─────────────────────────────────────────────
# RESOURCE 2: Live DB Statistics
# ─────────────────────────────────────────────
@mcp.resource("db://stats")
async def get_stats() -> str:
    """
    Live database statistics — row counts, revenue totals, latest activity.
    Use this for a quick health-check before running deeper queries.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()

        products_count  = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        customers_count = cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        orders_count    = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        total_revenue   = cur.execute(
            "SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='completed'"
        ).fetchone()[0]
        pending_orders  = cur.execute(
            "SELECT COUNT(*) FROM orders WHERE status='pending'"
        ).fetchone()[0]
        latest_quarter  = cur.execute(
            "SELECT quarter FROM orders ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        conn.close()

        return f"""# Database Statistics (Live)

| Metric               | Value                          |
|----------------------|-------------------------------|
| Products             | {products_count}               |
| Customers            | {customers_count}              |
| Total Orders         | {orders_count}                 |
| Pending Orders       | {pending_orders}               |
| Completed Revenue    | {total_revenue:,.0f} VND       |
| Latest Quarter       | {latest_quarter[0] if latest_quarter else 'N/A'} |

*Snapshot taken at query time from {str(conn)}*
"""
    except Exception as exc:
        return f"Error fetching stats: {exc}"


# ─────────────────────────────────────────────
# RESOURCE 3: Per-Table Schema (dynamic template)
# ─────────────────────────────────────────────
@mcp.resource("db://table/{table_name}")
async def get_table_schema(table_name: str) -> str:
    """
    Schema for a single table — DDL, columns with types and constraints, sample query.

    Dynamic template: replace {table_name} with 'products', 'customers', or 'orders'.
    Examples:
        db://table/products   — products table schema
        db://table/customers  — customers table schema
        db://table/orders     — orders table schema

    Use this when you only need details about one specific table, not the entire database.
    Prefer db://schema if you need an overview of all tables at once.
    """
    VALID_TABLES = {"products", "customers", "orders"}

    if table_name not in VALID_TABLES:
        return (
            f"# Unknown table: '{table_name}'\n\n"
            f"Valid tables: {', '.join(sorted(VALID_TABLES))}\n\n"
            f"Example URIs:\n"
            + "\n".join(f"  db://table/{t}" for t in sorted(VALID_TABLES))
        )

    try:
        conn = get_connection()
        cur = conn.cursor()

        # DDL
        ddl_row = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        ddl = ddl_row[0] if ddl_row else "-- DDL not found"

        # Column info via PRAGMA
        pragma_rows = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
        row_count = cur.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        conn.close()

        # Build column table
        col_lines = ["| # | Column | Type | NotNull | Default | PK |",
                     "|---|--------|------|---------|---------|-----|"]
        for r in pragma_rows:
            col_lines.append(
                f"| {r['cid']} | `{r['name']}` | {r['type']} "
                f"| {'✓' if r['notnull'] else ''} "
                f"| {r['dflt_value'] or ''} "
                f"| {'✓' if r['pk'] else ''} |"
            )

        # Table-specific hints
        hints = {
            "products": (
                "**Filter by:** `category` (Electronics, Furniture, Stationery, Appliances), `name`\n"
                "**Aggregate:** `inventory_summary` metric groups by category"
            ),
            "customers": (
                "**Filter by:** `region` (Hanoi, HCMC, Da Nang), `name`, `email`\n"
                "**Aggregate:** `customer_summary` metric groups spend by region"
            ),
            "orders": (
                "**Filter by:** `quarter` (Q1-2025…Q4-2025), `status` (completed/pending/cancelled)\n"
                "**Aggregate:** `revenue_by_quarter`, `revenue_by_region`, `top_products`"
            ),
        }

        return f"""# Table schema: `{table_name}`

## DDL
```sql
{ddl}
```

## Columns ({len(pragma_rows)} total)
{chr(10).join(col_lines)}

## Live stats
- **Row count:** {row_count:,}

## Usage hints
{hints[table_name]}

## Example tool calls
```python
# Search
search_records("{table_name}", {{"<column>": "<value>"}})

# Insert
insert_record("{table_name}", {{<required fields>}})
```

_Read `db://schema` for the full multi-table overview._
"""
    except Exception as exc:
        return f"Error reading schema for '{table_name}': {exc}"


# ─────────────────────────────────────────────
# PROMPT: analyze-sales
# ─────────────────────────────────────────────
@mcp.prompt()
def analyze_sales(quarter: str = "Q3-2025", region: str = "all") -> str:
    """
    Reusable sales analysis prompt template.
    Select this prompt when asked to produce a sales report or analysis.

    Args:
        quarter: Quarter to focus on (default: Q3-2025)
        region:  Region filter — 'Hanoi', 'HCMC', 'Da Nang', or 'all'
    """
    region_note = f"Focus specifically on region: **{region}**\n" if region != "all" else ""

    return f"""You are a business analyst. Produce a sales performance report for **{quarter}**.
{region_note}
Follow these steps in order:

1. **Schema check** — read resource `db://schema` to understand the data model.
2. **Quick stats** — read resource `db://stats` for overall counts.
3. **Revenue by quarter** — call `aggregate_data("revenue_by_quarter")` to see trends.
4. **Regional breakdown** — call `aggregate_data("revenue_by_region"{', region_filter="' + region + '"' if region != 'all' else ''})`.
5. **Category analysis** — call `aggregate_data("revenue_by_category", quarter_filter="{quarter}")`.
6. **Top products** — call `aggregate_data("top_products", quarter_filter="{quarter}")`.
7. **Compile report** with the structure below.

---

## Report Structure

### Executive Summary
(2–3 sentence overview of {quarter} performance)

### Key Metrics
| Metric | Value |
|--------|-------|
| Total Revenue | |
| Total Orders  | |
| Top Region    | |
| Top Category  | |

### Top Products (by Revenue)
(Table: Rank | Product | Category | Revenue | Units Sold)

### Regional Performance
(Table: Region | Revenue | Orders | Customers)

### Insights & Recommendations
(3 bullet points based on the data)
"""


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("[MCP] Starting lab26-sales-db server (stdio)...", flush=True)
    mcp.run()
