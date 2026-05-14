# Lab #26 — Architecture Overview

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         HOST LAYER                              │
│  Claude Desktop / Cursor / MCP Inspector                        │
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐                         │
│  │   Client 1   │     │   Client 2   │                         │
│  │  (lab26-db)  │     │  (github)    │                         │
│  └──────┬───────┘     └──────┬───────┘                         │
└─────────│──────────────────── │───────────────────────────────┘
          │ JSON-RPC 2.0        │ JSON-RPC 2.0
          │ (STDIO)             │ (STDIO)
          ▼                     ▼
┌─────────────────┐    ┌─────────────────────┐
│  lab26-sales-db │    │   GitHub MCP Server │
│  (server/main)  │    │  (@mcp/server-github)│
│                 │    └─────────────────────┘
│  Tools:         │
│  ┌───────────┐  │           ┌──────────────────────────────┐
│  │search_    │  │           │  BONUS: HTTP Transport       │
│  │records    │  │           │  server/http_server.py       │
│  ├───────────┤  │           │                              │
│  │insert_    │  │           │  ┌────────────────────────┐  │
│  │record     │  │           │  │ BearerAuthMiddleware   │  │
│  ├───────────┤  │           │  ├────────────────────────┤  │
│  │aggregate_ │  │           │  │ TokenStore + RateLimit │  │
│  │data       │  │           │  ├────────────────────────┤  │
│  └───────────┘  │           │  │ Starlette ASGI App     │  │
│                 │           │  ├────────────────────────┤  │
│  Resources:     │           │  │ FastMCP (HTTP mode)    │  │
│  ┌───────────┐  │           │  └────────────────────────┘  │
│  │db://schema│  │           └──────────────────────────────┘
│  ├───────────┤  │
│  │db://stats │  │           Transport comparison:
│  └───────────┘  │           ┌─────────────┬─────────────────┐
│                 │           │ STDIO       │ HTTP (Bonus)    │
│  Prompts:       │           ├─────────────┼─────────────────┤
│  ┌───────────┐  │           │ Local only  │ Remote capable  │
│  │analyze-   │  │           │ No auth     │ Bearer token    │
│  │sales      │  │           │ Low latency │ Scalable        │
│  └───────────┘  │           │ Dev/local   │ Production      │
│                 │           └─────────────┴─────────────────┘
│        ▼        │
│  server/        │
│  database.py    │
│  (SQLite)       │
└─────────────────┘
```

## MCP Protocol Flow

```
Claude Desktop                   lab26-sales-db
     │                                │
     │── initialize ──────────────────▶
     │◀─ capabilities, tools/list ─────
     │                                │
     │── tools/list ──────────────────▶
     │◀─ [search_records,              │
     │    insert_record,               │
     │    aggregate_data] ─────────────
     │                                │
     │── resources/list ──────────────▶
     │◀─ [db://schema, db://stats] ────
     │                                │
     │── prompts/list ────────────────▶
     │◀─ [analyze-sales] ──────────────
     │                                │
     │  [User: "phân tích doanh số Q3"]
     │                                │
     │── tools/call: aggregate_data ──▶
     │   {"metric": "revenue_by_quarter"}
     │◀─ {results: [...]} ─────────────
     │                                │
     │── tools/call: aggregate_data ──▶
     │   {"metric": "top_products",   │
     │    "quarter_filter": "Q3-2025"}│
     │◀─ {results: [...]} ─────────────
     │                                │
     │  [Claude compiles report]      │
```

## Security Model (4 Layers — từ slides)

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Transport Security                    │
│  • STDIO: process isolation (local only)         │
│  • HTTP: Bearer token + TLS                      │
├─────────────────────────────────────────────────┤
│  Layer 2: Input Validation                      │
│  • Table names validated against whitelist       │
│  • Column names validated via PRAGMA table_info  │
│  • Values parameterized (no SQL injection)       │
├─────────────────────────────────────────────────┤
│  Layer 3: Permission Scope                      │
│  • search: READ only                             │
│  • insert: WRITE to specific tables              │
│  • aggregate: READ aggregated (no raw PII dump)  │
├─────────────────────────────────────────────────┤
│  Layer 4: Audit Logging                         │
│  • HTTP server logs every tool call              │
│  • Token usage tracked (request_count)           │
│  • Rate limiting: 60 req/min per token           │
└─────────────────────────────────────────────────┘
```

## File Structure

```
lab26-mcp-server/
├── server/
│   ├── __init__.py
│   ├── main.py          ← FastMCP server (STDIO) — 3 tools + 2 resources + 1 prompt
│   ├── http_server.py   ← [BONUS] HTTP server + Bearer auth + rate limiting
│   └── database.py      ← SQLite wrapper + schema + seed data
│
├── scripts/
│   ├── init_db.py       ← Initialize/reset the database
│   └── test_client.py   ← Smoke-test all tools without Inspector
│
├── tests/
│   └── test_tools.py    ← Full pytest suite (30+ test cases)
│
├── config/
│   └── claude_desktop_config.json   ← Ready-to-use Claude Desktop config
│
├── docs/
│   ├── inspector_guide.md  ← Step-by-step Inspector testing guide
│   └── architecture.md     ← This file
│
├── data/                   ← SQLite DB (auto-created, git-ignored)
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```
