# Lab #26 — MCP Server (VinUniversity AICB-P2T3)

> **Mục tiêu:** Build custom MCP server + test cross-client compatibility  
> **Chương 6 — Chuẩn hóa Tool Integration** · Tuần 6 · Phase 2 · Track 3

---

## Tổng quan

MCP server này expose một **sales database** (SQLite) thông qua 3 tools, 2 resources, và 1 prompt template — tuân theo kiến trúc FastMCP từ slide bài giảng.

```
lab26-sales-db
 ├── Tools      → search_records, insert_record, aggregate_data
 ├── Resources  → db://schema, db://stats
 └── Prompts    → analyze-sales
```

---

## Cấu trúc project

```
lab26-mcp-server/
├── server/
│   ├── main.py          ← FastMCP STDIO server (main deliverable)
│   ├── http_server.py   ← [BONUS] HTTP server + Bearer auth + rate limiting
│   └── database.py      ← SQLite wrapper, schema, seed data
│
├── scripts/
│   ├── init_db.py       ← Khởi tạo / reset database
│   └── test_client.py   ← Smoke-test tất cả tools (không cần Inspector/LLM)
│
├── tests/
│   └── test_tools.py    ← Pytest suite đầy đủ (30+ test cases)
│
├── config/
│   └── claude_desktop_config.json   ← Cấu hình Claude Desktop ready-to-use
│
├── docs/
│   ├── inspector_guide.md  ← Hướng dẫn kiểm thử với MCP Inspector
│   └── architecture.md     ← Sơ đồ kiến trúc + security model
│
├── .env.example         ← Template environment variables
├── requirements.txt
└── pyproject.toml
```

---

## Yêu cầu

- Python **3.11+**
- Node.js 18+ (cho MCP Inspector + GitHub MCP server)
- pip

---

## Cài đặt

```bash
# 1. Clone repo
git clone <your-repo-url>
cd lab26-mcp-server

# 2. Tạo virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Copy env template
cp .env.example .env
# (Chỉnh sửa .env nếu cần)

# 5. Khởi tạo database
python scripts/init_db.py
```

---

## Chạy server

### STDIO (mặc định — cho Claude Desktop & Inspector)

```bash
python server/main.py
```

### HTTP + Auth (BONUS)

```bash
# Tạo token
TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Token: $TOKEN"

# Chạy HTTP server
MCP_AUTH_TOKEN=$TOKEN python server/http_server.py
```

Server sẽ chạy tại: `http://localhost:8000`

---

## Tools

### 1. `search_records`

Tìm kiếm records trong database. Hỗ trợ filter theo bất kỳ column nào (LIKE matching), sắp xếp, và phân trang bằng `limit`/`offset`.

```python
# Tìm tất cả sản phẩm Electronics
search_records("products", {"category": "Electronics"})

# Sắp xếp theo giá giảm dần và lấy trang thứ 2
search_records("products", limit=5, offset=5, order_by="price", order_dir="desc")

# Tìm khách hàng ở Hanoi
search_records("customers", {"region": "Hanoi"})

# Tìm đơn hàng Q3-2025 đã hoàn thành
search_records("orders", {"quarter": "Q3-2025", "status": "completed"})
```

**Input schema:**

| Field     | Type   | Required | Default | Description                              |
|-----------|--------|----------|---------|------------------------------------------|
| `table`   | string | ✓        | —       | `products` / `customers` / `orders`      |
| `filters` | dict   | ✗        | null    | `{column: value}` — dùng LIKE matching   |
| `limit`   | int    | ✗        | 10      | Số rows tối đa (1–100)                   |
| `offset`  | int    | ✗        | 0       | Số rows bỏ qua để phân trang             |
| `order_by`| string | ✗        | id      | Column hợp lệ để sắp xếp                 |
| `order_dir`| string| ✗        | asc     | `asc` hoặc `desc`                        |

---

### 2. `insert_record`

Thêm record mới vào database.

```python
# Thêm sản phẩm mới
insert_record("products", {
    "name": "Gaming Headset", "category": "Electronics",
    "price": 2500000, "stock": 50
})

# Thêm khách hàng
insert_record("customers", {
    "name": "Nguyễn Thị F", "email": "ntf@example.com", "region": "Da Nang"
})

# Thêm đơn hàng
insert_record("orders", {
    "customer_id": 1, "product_id": 3,
    "quantity": 2, "total_price": 6000000,
    "quarter": "Q1-2026"
})
```

**Required fields per table:**

| Table       | Required Fields                                                          |
|-------------|--------------------------------------------------------------------------|
| `products`  | `name`, `category`, `price`, `stock`                                     |
| `customers` | `name`, `email`, `region`                                                |
| `orders`    | `customer_id`, `product_id`, `quantity`, `total_price`, `quarter`        |

Kết quả insert trả về cả `id` và payload `record` vừa được ghi vào database.

---

### 3. `aggregate_data`

Business intelligence aggregations — tool chính cho phân tích dữ liệu.

```python
aggregate_data("revenue_by_quarter")
aggregate_data("top_products", quarter_filter="Q3-2025")
aggregate_data("revenue_by_region", region_filter="Hanoi")
aggregate_data("inventory_summary")
```

**Available metrics:**

| Metric                  | Mô tả                                        |
|-------------------------|----------------------------------------------|
| `revenue_by_quarter`    | Doanh thu, số đơn, avg order value theo quý  |
| `revenue_by_region`     | Doanh thu và số khách theo vùng              |
| `revenue_by_category`   | Doanh thu và units sold theo category         |
| `top_products`          | Top 10 sản phẩm theo doanh thu               |
| `order_count_by_status` | Số đơn và tổng giá trị theo trạng thái       |
| `customer_summary`      | Số khách và tổng chi tiêu theo vùng          |
| `inventory_summary`     | Tồn kho, giá min/max theo category           |

---

## Resources

### `db://schema`
Full database schema với DDL, mô tả columns, và ví dụ queries.
Đọc resource này trước khi query để hiểu cấu trúc dữ liệu.

### `db://stats`
Live statistics: row counts, tổng doanh thu, số đơn pending.

---

## Prompts

### `analyze-sales`
Template phân tích doanh số — agent tự động chạy đầy đủ workflow phân tích.

```
Arguments:
  quarter: "Q3-2025"   (default)
  region:  "all"       (hoặc "Hanoi", "HCMC", "Da Nang")
```

---

## Kiểm thử

### 1. Smoke-test (không cần MCP client)

```bash
python scripts/test_client.py
```

Chạy tất cả tools, in kết quả màu sắc, báo pass/fail.

### 2. Pytest suite đầy đủ

```bash
# Cài dev dependencies
pip install pytest pytest-asyncio

# Chạy tất cả tests
pytest tests/ -v

# Với coverage
pytest tests/ -v --tb=short
```

**30+ test cases** bao gồm:
- Tất cả 7 aggregate metrics
- Edge cases: invalid table, invalid column, missing fields, duplicate email
- Error handling: structured error responses (không raise exceptions)
- Insert → search roundtrip
- Rate limiting (HTTP)

### 3. MCP Inspector

```bash
# Cài Inspector (một lần)
npm install -g @modelcontextprotocol/inspector

# Chạy Inspector với server
npx @modelcontextprotocol/inspector python server/main.py
```

Mở: **http://localhost:5173**

Xem hướng dẫn chi tiết: [docs/inspector_guide.md](docs/inspector_guide.md)

---

## Claude Desktop Integration

### Bước 1: Copy config

Mở file: `config/claude_desktop_config.json`

Sao chép nội dung vào Claude Desktop config:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Bước 2: Cập nhật đường dẫn

Trong config, thay `"args": ["-m", "server.main"]` bằng đường dẫn tuyệt đối nếu cần:

```json
{
  "mcpServers": {
    "lab26-sales-db": {
      "command": "python",
      "args": ["-m", "server.main"],
      "cwd": "/absolute/path/to/lab26-mcp-server",
      "env": {
        "DB_PATH": "/absolute/path/to/lab26-mcp-server/data/lab26.db"
      }
    }
  }
}
```

### Bước 3: Khởi động lại Claude Desktop

Vào **Settings → Developer → MCP Servers** để verify server đã kết nối.

### Bước 4: Test E2E

Thử trong Claude Desktop:

```
"Phân tích doanh số Q3-2025 và tạo báo cáo"
"Tìm tất cả sản phẩm Electronics dưới 5 triệu"
"Thêm sản phẩm mới: Webcam 4K, Electronics, 1.200.000 VND, 30 chiếc"
"So sánh doanh thu theo vùng trong Q4-2025"
```

---

## Multi-Tool Demo (Claude Desktop + GitHub MCP)

Theo demo trong slide, bạn có thể kết hợp lab26-sales-db với GitHub MCP:

1. Thêm `GITHUB_PERSONAL_ACCESS_TOKEN` vào config
2. Thử prompt:
   > "Query doanh số Q3-2025, phân tích top products, rồi tạo GitHub issue với báo cáo phân tích"

Claude sẽ tự động:
- Route `aggregate_data` → `lab26-sales-db`
- Route `create_issue` → `github-mcp`

---

## [BONUS] HTTP Server với Bearer Auth

### Kiến trúc bảo mật (4 tầng theo slide)

```
Layer 1 — Transport:    Bearer token + HTTPS
Layer 2 — Validation:   Column names validated via PRAGMA, values parameterized
Layer 3 — Permissions:  Read-only tools không expose raw schema manipulation
Layer 4 — Audit:        Mọi request được log với token hash + request count
```

### Tính năng

- **Bearer token auth** — token được hash (SHA-256) trong memory
- **Rate limiting** — sliding window, 60 req/min per token (configurable)
- **Request logging** — log level INFO, token suffix, path, scope
- **Security headers** — WWW-Authenticate, Retry-After, X-Request-Count
- **One-time dev token** — nếu không set `MCP_AUTH_TOKEN`, tự generate và in ra console
- **Health endpoint** — `/health` không cần auth (cho load balancer)

### Chạy và test

```bash
# Start
MCP_AUTH_TOKEN=mysecrettoken python server/http_server.py

# Test health (no auth)
curl http://localhost:8000/health

# Test auth OK
curl -H "Authorization: Bearer mysecrettoken" http://localhost:8000/mcp

# Test auth fail (401)
curl http://localhost:8000/mcp

# Test wrong token (401)
curl -H "Authorization: Bearer wrongtoken" http://localhost:8000/mcp

# Inspect via MCP Inspector
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
# Thêm header: Authorization: Bearer mysecrettoken
```

---

## Database Schema

```sql
CREATE TABLE products (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    category   TEXT    NOT NULL,        -- Electronics/Furniture/Stationery/Appliances
    price      REAL    NOT NULL CHECK(price >= 0),
    stock      INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    email      TEXT    UNIQUE NOT NULL,
    region     TEXT    NOT NULL,        -- Hanoi/HCMC/Da Nang
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    product_id   INTEGER NOT NULL REFERENCES products(id),
    quantity     INTEGER NOT NULL CHECK(quantity > 0),
    total_price  REAL    NOT NULL,
    quarter      TEXT    NOT NULL,     -- Q1-2025, Q2-2025, ...
    status       TEXT    NOT NULL DEFAULT 'completed'
                 CHECK(status IN ('completed', 'pending', 'cancelled')),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Key Takeaways (từ slide)

1. **MCP chuẩn hóa tool integration** — build MCP server một lần, dùng được với Claude, Cursor, Gemini, VS Code...
2. **Tool description là quan trọng nhất** — LLM chọn tool 100% dựa trên name + description (docstring)
3. **Resources & Prompts underutilized** — dùng `db://schema` cho dynamic context injection thay vì hardcode
4. **Inspector trước Claude Desktop** — verify schemas + error handling trước khi integrate với LLM
5. **Security không optional** — HTTP transport bắt buộc có auth; đừng expose MCP server không có token

---

## Liên hệ

AICB-P2T3 · VinUniversity · Phase 2 · Track 3 · Tuần 6  
GitHub: `github.com/vinuni-aicb`  
Email: `instructor@vinuni.edu.vn`
