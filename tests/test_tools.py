"""
tests/test_tools.py
===================
Pytest test suite for Lab #26 MCP Server tools.

Run:
    pytest tests/ -v
    pytest tests/ -v --tb=short
"""

import pytest
import pytest_asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Use a fresh temporary database for every test."""
    db_file = tmp_path / "test_lab26.db"
    monkeypatch.setenv("DB_PATH", str(db_file))

    # Re-import with patched env
    import importlib
    import server.database as db_module
    importlib.reload(db_module)
    import server.main as main_module
    importlib.reload(main_module)

    db_module.init_db()
    yield


# ─── Tool 1: search_records ──────────────────────────────────────────────────

class TestSearchRecords:

    @pytest.mark.asyncio
    async def test_search_all_products(self):
        from server.main import search_records
        result = await search_records("products")
        assert "records" in result
        assert result["returned"] > 0
        assert result["total"] > 0

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self):
        from server.main import search_records
        result = await search_records("products", filters={"category": "Electronics"})
        assert "records" in result
        assert all("Electronics" in r["category"] for r in result["records"])

    @pytest.mark.asyncio
    async def test_search_customers_by_region(self):
        from server.main import search_records
        result = await search_records("customers", filters={"region": "Hanoi"})
        assert "records" in result
        assert result["returned"] > 0

    @pytest.mark.asyncio
    async def test_search_orders_by_quarter(self):
        from server.main import search_records
        result = await search_records("orders", filters={"quarter": "Q3-2025"})
        assert "records" in result

    @pytest.mark.asyncio
    async def test_invalid_table_returns_error(self):
        from server.main import search_records
        result = await search_records("nonexistent")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_limit_is_capped_at_100(self):
        from server.main import search_records
        result = await search_records("products", limit=999)
        assert result.get("returned", 0) <= 100

    @pytest.mark.asyncio
    async def test_invalid_column_returns_error(self):
        from server.main import search_records
        result = await search_records("products", filters={"nonexistent_col": "x"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_orders_table_searchable(self):
        from server.main import search_records
        result = await search_records("orders")
        assert "records" in result
        assert result["returned"] > 0

    @pytest.mark.asyncio
    async def test_search_supports_ordering(self):
        from server.main import search_records
        result = await search_records("products", limit=5, order_by="price", order_dir="desc")
        prices = [row["price"] for row in result["records"]]
        assert prices == sorted(prices, reverse=True)
        assert result["order_by"] == "price"
        assert result["order_dir"] == "desc"

    @pytest.mark.asyncio
    async def test_search_supports_offset_pagination(self):
        from server.main import search_records
        first_page = await search_records("products", limit=3, offset=0, order_by="id")
        second_page = await search_records("products", limit=3, offset=3, order_by="id")
        assert first_page["records"]
        assert second_page["records"]
        assert first_page["records"][0]["id"] != second_page["records"][0]["id"]
        assert second_page["offset"] == 3
        assert "has_more" in second_page

    @pytest.mark.asyncio
    async def test_invalid_order_by_returns_error(self):
        from server.main import search_records
        result = await search_records("products", order_by="not_a_column")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_order_dir_returns_error(self):
        from server.main import search_records
        result = await search_records("products", order_dir="sideways")
        assert "error" in result


# ─── Tool 2: insert_record ───────────────────────────────────────────────────

class TestInsertRecord:

    @pytest.mark.asyncio
    async def test_insert_valid_product(self):
        from server.main import insert_record
        result = await insert_record("products", {
            "name": "Test Product", "category": "Electronics",
            "price": 1_000_000, "stock": 10,
        })
        assert result["success"] is True
        assert "id" in result
        assert result["id"] > 0
        assert result["record"]["name"] == "Test Product"
        assert result["record"]["category"] == "Electronics"
        assert result["record"]["price"] == 1_000_000
        assert result["record"]["stock"] == 10

    @pytest.mark.asyncio
    async def test_insert_valid_customer(self):
        from server.main import insert_record
        result = await insert_record("customers", {
            "name": "Test User", "email": "testxyz@example.com", "region": "Hanoi",
        })
        assert result["success"] is True
        assert result["id"] > 0

    @pytest.mark.asyncio
    async def test_insert_valid_order(self):
        from server.main import insert_record
        # Insert prerequisites first
        p = await insert_record("products", {
            "name": "P", "category": "Electronics", "price": 100, "stock": 1
        })
        c = await insert_record("customers", {
            "name": "C", "email": "c@test.com", "region": "HCMC"
        })
        result = await insert_record("orders", {
            "customer_id": c["id"], "product_id": p["id"],
            "quantity": 1, "total_price": 100, "quarter": "Q1-2026",
        })
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_missing_required_field_returns_error(self):
        from server.main import insert_record
        result = await insert_record("products", {"name": "Incomplete"})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_table_returns_error(self):
        from server.main import insert_record
        result = await insert_record("bad_table", {"x": 1})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_error(self):
        from server.main import insert_record
        data = {"name": "User", "email": "dup@example.com", "region": "HCMC"}
        await insert_record("customers", data)
        result = await insert_record("customers", data)
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_inserted_record_is_searchable(self):
        from server.main import insert_record, search_records
        await insert_record("products", {
            "name": "SearchableItem", "category": "Stationery",
            "price": 50_000, "stock": 99,
        })
        found = await search_records("products", filters={"name": "SearchableItem"})
        assert found["returned"] == 1
        assert found["records"][0]["stock"] == 99


# ─── Tool 3: aggregate_data ──────────────────────────────────────────────────

class TestAggregateData:

    ALL_METRICS = [
        "revenue_by_quarter",
        "revenue_by_region",
        "revenue_by_category",
        "top_products",
        "order_count_by_status",
        "customer_summary",
        "inventory_summary",
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metric", ALL_METRICS)
    async def test_all_metrics_return_results(self, metric):
        from server.main import aggregate_data
        result = await aggregate_data(metric)
        assert "results" in result, f"Missing 'results' key for metric={metric}: {result}"
        assert "row_count" in result
        assert result["row_count"] >= 0

    @pytest.mark.asyncio
    async def test_invalid_metric_returns_error(self):
        from server.main import aggregate_data
        result = await aggregate_data("made_up_metric")
        assert "error" in result
        assert "available_metrics" in result

    @pytest.mark.asyncio
    async def test_revenue_by_quarter_has_expected_keys(self):
        from server.main import aggregate_data
        result = await aggregate_data("revenue_by_quarter")
        assert result["row_count"] > 0
        row = result["results"][0]
        assert "quarter" in row
        assert "total_revenue" in row
        assert "order_count" in row

    @pytest.mark.asyncio
    async def test_top_products_with_quarter_filter(self):
        from server.main import aggregate_data
        result = await aggregate_data("top_products", quarter_filter="Q3-2025")
        assert "results" in result
        assert result.get("filters_applied", {}).get("quarter") == "Q3-2025"

    @pytest.mark.asyncio
    async def test_revenue_by_region_with_filter(self):
        from server.main import aggregate_data
        result = await aggregate_data("revenue_by_region", region_filter="Hanoi")
        assert "results" in result

    @pytest.mark.asyncio
    async def test_inventory_summary_has_stock_column(self):
        from server.main import aggregate_data
        result = await aggregate_data("inventory_summary")
        if result["row_count"] > 0:
            assert "total_stock" in result["results"][0]
            assert "product_count" in result["results"][0]

    @pytest.mark.asyncio
    async def test_summary_string_is_present(self):
        from server.main import aggregate_data
        result = await aggregate_data("revenue_by_quarter")
        assert "summary" in result
        assert len(result["summary"]) > 0


# ─── Resources ───────────────────────────────────────────────────────────────

class TestResources:

    @pytest.mark.asyncio
    async def test_schema_contains_all_tables(self):
        from server.main import get_schema
        schema = await get_schema()
        for table in ("products", "customers", "orders"):
            assert table in schema

    @pytest.mark.asyncio
    async def test_schema_contains_column_names(self):
        from server.main import get_schema
        schema = await get_schema()
        for col in ("total_price", "quarter", "category", "region"):
            assert col in schema

    @pytest.mark.asyncio
    async def test_stats_contains_expected_fields(self):
        from server.main import get_stats
        stats = await get_stats()
        assert "Products" in stats
        assert "Orders" in stats
        assert "VND" in stats


# ─── Edge cases & error handling ─────────────────────────────────────────────

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_filters_dict(self):
        from server.main import search_records
        result = await search_records("products", filters={})
        # Empty filters should behave like no filter
        assert "records" in result

    @pytest.mark.asyncio
    async def test_search_returns_dict_not_list(self):
        from server.main import search_records
        result = await search_records("products")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_insert_returns_dict_not_raises(self):
        from server.main import insert_record
        result = await insert_record("products", {})
        assert isinstance(result, dict)
        # Should return error dict, not raise
        assert "error" in result or "success" in result

    @pytest.mark.asyncio
    async def test_aggregate_always_returns_dict(self):
        from server.main import aggregate_data
        for metric in ["revenue_by_quarter", "bad_metric", ""]:
            result = await aggregate_data(metric)
            assert isinstance(result, dict)


# ─── Resource 3: Dynamic per-table schema template ───────────────────────────

class TestTableSchemaResource:
    """Tests for db://table/{table_name} dynamic resource (Part 2 requirement)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("table", ["products", "customers", "orders"])
    async def test_valid_table_returns_ddl(self, table):
        from server.main import get_table_schema
        result = await get_table_schema(table)
        assert "CREATE TABLE" in result, f"Expected DDL for '{table}'"
        assert table in result

    @pytest.mark.asyncio
    async def test_products_schema_has_key_columns(self):
        from server.main import get_table_schema
        result = await get_table_schema("products")
        for col in ("name", "category", "price", "stock"):
            assert col in result

    @pytest.mark.asyncio
    async def test_customers_schema_has_key_columns(self):
        from server.main import get_table_schema
        result = await get_table_schema("customers")
        for col in ("name", "email", "region"):
            assert col in result

    @pytest.mark.asyncio
    async def test_orders_schema_has_key_columns(self):
        from server.main import get_table_schema
        result = await get_table_schema("orders")
        for col in ("customer_id", "product_id", "quarter", "status", "total_price"):
            assert col in result

    @pytest.mark.asyncio
    async def test_invalid_table_returns_error_message(self):
        from server.main import get_table_schema
        result = await get_table_schema("nonexistent_table")
        assert "Unknown table" in result or "Valid tables" in result

    @pytest.mark.asyncio
    async def test_schema_includes_row_count(self):
        from server.main import get_table_schema
        result = await get_table_schema("products")
        assert "Row count" in result or "row" in result.lower()

    @pytest.mark.asyncio
    async def test_schema_includes_column_count_info(self):
        from server.main import get_table_schema
        result = await get_table_schema("orders")
        # Should show column table
        assert "| #" in result or "Column" in result

    @pytest.mark.asyncio
    async def test_schema_includes_usage_hints(self):
        from server.main import get_table_schema
        result = await get_table_schema("orders")
        assert "quarter" in result.lower() or "status" in result.lower()

    @pytest.mark.asyncio
    async def test_sql_injection_attempt_rejected(self):
        from server.main import get_table_schema
        result = await get_table_schema("products; DROP TABLE products--")
        assert "Unknown table" in result or "Valid tables" in result


# ─── Bonus: HTTP Server auth middleware ──────────────────────────────────────

class TestHTTPServerAuth:
    """Smoke-tests for the Bearer token middleware in http_server.py (BONUS)."""

    def _make_app(self, token: str):
        """Build the Starlette app with a known test token."""
        import os, importlib
        os.environ["MCP_AUTH_TOKEN"] = token
        import server.http_server as hs
        importlib.reload(hs)
        return hs.create_app()

    def test_health_endpoint_no_auth_needed(self):
        """GET /health returns 200 without Authorization header."""
        from starlette.testclient import TestClient
        app = self._make_app("test-secret-token")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    def test_mcp_endpoint_without_token_returns_401(self):
        """POST /mcp without Authorization header → 401."""
        from starlette.testclient import TestClient
        app = self._make_app("test-secret-token")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/mcp", json={})
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

    def test_mcp_endpoint_wrong_token_returns_401(self):
        """POST /mcp with wrong token → 401."""
        from starlette.testclient import TestClient
        app = self._make_app("test-secret-token")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/mcp", json={}, headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401

    def test_mcp_endpoint_correct_token_passes_auth(self):
        """POST /mcp with correct Bearer token passes auth layer (may return 4xx from MCP itself)."""
        from starlette.testclient import TestClient
        app = self._make_app("test-secret-token")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05",
                             "capabilities": {},
                             "clientInfo": {"name": "test", "version": "0.1"}}},
            headers={"Authorization": "Bearer test-secret-token"},
        )
        # 401 means auth failed — any other code means auth passed
        assert resp.status_code != 401, f"Auth should pass but got 401: {resp.text}"

    def test_rate_limiter_blocks_after_limit(self):
        """Exceed rate limit → 429 Too Many Requests."""
        import importlib, os
        os.environ["MCP_AUTH_TOKEN"] = "rate-test-token"
        os.environ["RATE_LIMIT_RPM"] = "3"     # set very low limit for test
        import server.http_server as hs
        importlib.reload(hs)
        os.environ.pop("RATE_LIMIT_RPM", None)  # restore
        app = hs.create_app()
        from starlette.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        headers = {"Authorization": "Bearer rate-test-token"}
        statuses = []
        for _ in range(10):
            r = client.post("/mcp", json={}, headers=headers)
            statuses.append(r.status_code)
        assert 429 in statuses, f"Expected 429 after rate limit, got: {statuses}"
