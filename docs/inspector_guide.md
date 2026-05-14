# MCP Inspector Testing Guide — Lab #26

## What is MCP Inspector?

MCP Inspector is the official developer tool for testing MCP servers **without an LLM**.
It lets you:
- Browse all tools, resources, and prompts your server exposes
- Call tools manually with custom inputs
- Verify JSON schemas and output formats
- Check error handling before integrating with Claude Desktop

---

## Setup

### 1. Install MCP Inspector (one-time)

```bash
npm install -g @modelcontextprotocol/inspector
# or run directly with npx (no install needed)
```

### 2. Start your MCP server

```bash
# From project root
python scripts/init_db.py    # Initialize database first
python server/main.py        # Start STDIO server
```

### 3. Launch Inspector

```bash
# In a new terminal
npx @modelcontextprotocol/inspector python server/main.py
```

The Inspector UI opens at: **http://localhost:5173**

---

## Inspector Walkthrough

### Step 1 — Connect to Server

1. Open http://localhost:5173
2. Inspector auto-connects to your server via STDIO
3. You should see **"lab26-sales-db"** connected in the top bar

### Step 2 — Explore Tools

Click **"Tools"** in the left panel. You should see 3 tools:

| Tool Name       | Description                               |
|-----------------|-------------------------------------------|
| `search_records` | Search rows in products/customers/orders |
| `insert_record`  | Insert new records into any table        |
| `aggregate_data` | Business intelligence aggregations       |

**Check each tool's schema** — expand to see input types and descriptions.

### Step 3 — Test Tool Calls

#### Test `search_records`

```json
{
  "table": "products",
  "filters": {"category": "Electronics"},
  "limit": 5
}
```

Expected output:
```json
{
  "table": "products",
  "records": [...],
  "returned": 5,
  "total": 5
}
```

#### Test `insert_record`

```json
{
  "table": "products",
  "data": {
    "name": "Inspector Test Product",
    "category": "Electronics",
    "price": 5000000,
    "stock": 10
  }
}
```

Expected output:
```json
{
  "success": true,
  "id": 13,
  "message": "Record inserted into 'products' with id=13"
}
```

#### Test `aggregate_data`

```json
{
  "metric": "revenue_by_quarter"
}
```

Expected output:
```json
{
  "metric": "revenue_by_quarter",
  "results": [
    {"quarter": "Q1-2025", "total_revenue": 76000000, "order_count": 4, ...},
    {"quarter": "Q2-2025", "total_revenue": 31500000, "order_count": 4, ...},
    ...
  ],
  "row_count": 4,
  "summary": "4 group(s) returned..."
}
```

### Step 4 — Test Resources

Click **"Resources"** in the left panel.

| URI         | Description              |
|-------------|--------------------------|
| `db://schema` | Full database schema   |
| `db://stats`  | Live row counts + KPIs |

Click each URI to fetch and verify the content.

### Step 5 — Test Prompts

Click **"Prompts"** in the left panel.

- Select **`analyze-sales`**
- Set arguments: `quarter = "Q3-2025"`, `region = "Hanoi"`
- The rendered prompt template should appear

### Step 6 — Test Error Handling

Verify that errors return structured responses (not stack traces):

```json
// Invalid table
{ "table": "nonexistent", "limit": 10 }
// Expected: {"error": "Invalid table 'nonexistent'..."}

// Invalid metric
{ "metric": "made_up_metric" }
// Expected: {"error": "Unknown metric...", "available_metrics": [...]}

// Missing required fields
{ "table": "products", "data": {"name": "Incomplete"} }
// Expected: {"success": false, "error": "Missing required fields..."}
```

---

## Testing the HTTP Server (Bonus)

### Start HTTP server

```bash
# Generate a token
TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Token: $TOKEN"

# Start server
MCP_AUTH_TOKEN=$TOKEN python server/http_server.py
```

### Connect Inspector to HTTP

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

Set the Authorization header:
```
Authorization: Bearer <YOUR_TOKEN>
```

### Verify Auth

```bash
# Should work
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/health

# Should return 401
curl http://localhost:8000/mcp

# Should return 401
curl -H "Authorization: Bearer wrong_token" http://localhost:8000/mcp
```

---

## Screenshot Checklist for Deliverable

Take screenshots of:

- [ ] Inspector connected (server name visible)
- [ ] Tools list showing all 3 tools with descriptions
- [ ] `search_records` with filter — valid response
- [ ] `insert_record` — success response with `id`
- [ ] `aggregate_data("revenue_by_quarter")` — results table
- [ ] `db://schema` resource content
- [ ] Error handling — invalid table/metric returns structured error
- [ ] (Bonus) Inspector connected to HTTP server with auth header

---

## Troubleshooting

| Problem                          | Solution                                                   |
|----------------------------------|------------------------------------------------------------|
| "Module not found"               | Run from project root, not the server/ directory          |
| "DB not found"                   | Run `python scripts/init_db.py` first                     |
| Inspector blank/no tools         | Check server console for Python errors                     |
| "Connection refused" (HTTP)      | Make sure HTTP server is running on port 8000              |
| Auth 401 on HTTP                 | Check token matches `MCP_AUTH_TOKEN` env var               |
| Rate limit 429                   | Wait 60 seconds or increase `RATE_LIMIT_RPM` env var       |
