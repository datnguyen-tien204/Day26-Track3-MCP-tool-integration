# Báo Cáo Chạy Lab 26 - MCP Server

Mã sinh viên: 2A202600217  
Họ tên: Nguyễn Tiến Đạt  
Ngày thực hiện: 14/05/2026  
Thư mục project: `E:\Working\VinUni-FinalProj\Assignment\assignments\Day26-Track03-MCP_and_A2A_Infrastructure`

## 1. Mục Tiêu

Lab này xây dựng một MCP server cho cơ sở dữ liệu bán hàng SQLite. Server cung cấp tools, resources và HTTP transport có xác thực Bearer token để kiểm thử với MCP Inspector và VS Code Copilot.

Các thành phần chính:

- STDIO MCP server: `server/main.py`
- HTTP MCP server bonus: `server/http_server.py`
- Database SQLite: `data/lab26.db`
- Script khởi tạo database: `scripts/init_db.py`
- Bộ test tự động: `tests/test_tools.py`
- Cấu hình MCP cho VS Code Copilot: `.vscode/mcp.json`

## 2. Các Bước Đã Thực Hiện

### 2.1. Cài đặt môi trường

Đã tạo virtual environment và cài dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Kết quả: cài đặt thành công các thư viện chính như `mcp`, `starlette`, `uvicorn`, `pytest`, `pytest-asyncio`, `python-dotenv`.

### 2.2. Khởi tạo database

Đã chạy:

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py --reset
```

Kết quả database sau khi reset:

| Bảng | Số dòng |
|---|---:|
| products | 12 |
| customers | 8 |
| orders | 17 |

Database được tạo tại:

```text
data\lab26.db
```

### 2.3. Chạy smoke client

Đã chạy:

```powershell
.\.venv\Scripts\python.exe scripts\test_client.py
```

Kết quả:

```text
24/24 tests passed
```

Smoke client kiểm tra trực tiếp các chức năng:

- `search_records`
- `insert_record`
- `aggregate_data`
- `db://schema`
- `db://stats`

Sau khi đối chiếu rubric, `search_records` đã được bổ sung thêm sắp xếp và phân trang bằng các tham số `order_by`, `order_dir`, `limit`, `offset`. `insert_record` cũng đã được bổ sung trường `record` để trả về payload vừa insert.

### 2.4. Chạy pytest

Đã chạy:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

Kết quả:

```text
55 passed, 5 warnings
```

Các nhóm test đã pass:

- Search records
- Search ordering và offset pagination
- Insert records
- Insert trả về inserted payload
- Aggregate data
- Resources
- Table schema resource
- Edge cases
- HTTP auth
- Rate limiting

5 warnings còn lại là cảnh báo `datetime.utcnow()` deprecated trong `server/http_server.py`. Warning này không ảnh hưởng đến kết quả chạy lab.

## 3. Debug Và Sửa Lỗi

### 3.1. Lỗi Unicode khi chạy PowerShell

Khi chạy `scripts/init_db.py`, PowerShell báo lỗi encode với ký tự Unicode như dấu tick.

Lỗi gặp phải:

```text
UnicodeEncodeError: 'charmap' codec can't encode character
```

Nguyên nhân: Windows PowerShell đang dùng encoding CP1252, không in được một số ký tự Unicode.

Đã sửa:

- Trong `scripts/init_db.py`, thay ký tự Unicode bằng text ASCII như `OK`, `WARNING`.
- Trong `scripts/test_client.py`, thay ký tự line drawing, dấu tick, dấu nhân, mũi tên Unicode bằng ASCII.

Kết quả: các script chạy ổn định trên Windows PowerShell.

### 3.2. Lỗi HTTP MCP server

Khi test HTTP MCP server, request có token vẫn trả lỗi 500.

Log lỗi:

```text
RuntimeError: Task group is not initialized. Make sure to use run().
```

Nguyên nhân: FastMCP streamable HTTP app cần lifespan/session manager được chạy trong Starlette app.

Đã sửa trong `server/http_server.py`:

```python
lifespan=lambda app: mcp.session_manager.run()
```

Kết quả sau khi sửa:

- `GET /health`: 200 OK
- `POST /mcp` không token: 401 Unauthorized
- `POST /mcp` có Bearer token và MCP initialize body: 200 OK

### 3.3. Lỗi MCP Inspector trên Windows path

Ban đầu Inspector chạy với argument:

```text
server\main.py
```

Inspector hiểu sai thành:

```text
servermain.py
```

Lỗi:

```text
can't open file ...\servermain.py
```

Đã sửa cách chạy Inspector bằng module mode:

```powershell
npx @modelcontextprotocol/inspector .\.venv\Scripts\python.exe -m server.main
```

Kết quả: Inspector kết nối được MCP server.

### 3.4. Cấu hình VS Code Copilot thay cho Claude Desktop

Ban đầu hướng dẫn có phần Claude Desktop, nhưng trong quá trình làm thực tế đã chuyển sang dùng VS Code Copilot.

Đã tạo file:

```text
.vscode\mcp.json
```

Nội dung:

```json
{
  "servers": {
    "lab26-sales-db": {
      "type": "stdio",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": ["-m", "server.main"],
      "env": {
        "DB_PATH": "${workspaceFolder}\\data\\lab26.db"
      }
    }
  }
}
```

Kết quả: VS Code Copilot có thể nhận MCP server `lab26-sales-db` trong workspace.

## 4. Kiểm Thử Với MCP Inspector

Đã chạy Inspector:

```powershell
npx @modelcontextprotocol/inspector .\.venv\Scripts\python.exe -m server.main
```

Inspector chạy tại:

```text
http://localhost:6274
```

Các nội dung cần xác nhận trong Inspector:

### Tools

Có 3 tools:

- `search_records`
- `insert_record`
- `aggregate_data`

### Resources

Có các resources:

- `db://schema`
- `db://stats`
- `db://table/{table_name}`

### Test tool thành công

Tool: `search_records`

Input trong form Inspector:

```text
table: products
filters: {}
limit: 10
```

Kết quả: trả về danh sách sản phẩm trong bảng `products`.

### Test tool lỗi

Tool: `search_records`

Input:

```text
table: nonexistent
filters: {}
limit: 10
```

Kết quả: trả về error hợp lệ:

```text
Invalid table 'nonexistent'. Choose from: ['customers', 'orders', 'products']
```

## 5. Kiểm Thử Với VS Code Copilot

Đã cấu hình MCP server cho VS Code bằng file `.vscode/mcp.json`.

Các prompt dùng để kiểm thử trong Copilot Chat Agent mode:

```text
Use lab26-sales-db MCP. Phân tích doanh số Q3-2025: doanh thu theo vùng và top sản phẩm.
```

```text
Use lab26-sales-db MCP. Tìm tất cả sản phẩm Electronics trong database.
```

```text
Use lab26-sales-db MCP. Thêm sản phẩm mới: Webcam 4K, danh mục Electronics, giá 1200000 VND, tồn kho 30 chiếc.
```

```text
Use lab26-sales-db MCP. Tìm schema của bảng orders.
```

Khi Copilot yêu cầu quyền chạy tool, chọn Allow để cho phép gọi MCP tool.

## 6. Kiểm Thử HTTP Server Bonus

Đã chạy HTTP server với token:

```powershell
$env:MCP_AUTH_TOKEN = "demo-token"
.\.venv\Scripts\python.exe server\http_server.py
```

Server chạy tại:

```text
http://localhost:8000
```

### Health check

Lệnh:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/health -Method GET
```

Kết quả:

```json
{
  "status": "ok",
  "server": "lab26-sales-db",
  "transport": "http"
}
```

### Không token

Lệnh:

```powershell
try {
  Invoke-WebRequest -Uri http://localhost:8000/mcp -Method POST -ErrorAction Stop
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

Kết quả:

```text
401
```

### Có Bearer token

Lệnh:

```powershell
$body = @{
  jsonrpc = "2.0"
  id = 1
  method = "initialize"
  params = @{
    protocolVersion = "2025-03-26"
    capabilities = @{}
    clientInfo = @{ name = "manual-smoke"; version = "1.0" }
  }
} | ConvertTo-Json -Depth 8

Invoke-WebRequest -Uri http://localhost:8000/mcp -Method POST -Headers @{ Authorization = "Bearer demo-token"; Accept = "application/json, text/event-stream" } -ContentType "application/json" -Body $body
```

Kết quả:

```text
StatusCode: 200
```

## 7. Ảnh Chụp Cần Nộp

Các ảnh chụp nên đặt trong:

```text
submission\screenshots\
```

Danh sách ảnh cần có:

| Tên file gợi ý | Nội dung |
|---|---|
| `02-inspector-tools.png` | MCP Inspector tab Tools có 3 tools |
| `03-inspector-resources.png` | MCP Inspector tab Resources |
| `04-search-products-success.png` | Gọi `search_records` với `products` thành công |
| `05-search-invalid-table-error.png` | Gọi `search_records` với `nonexistent` trả error |
| `06-vscode-copilot-tools.png` | VS Code Copilot hiển thị MCP tools của `lab26-sales-db` |
| `07-vscode-copilot-results.png` | VS Code Copilot gọi MCP tools và trả kết quả phân tích/tìm kiếm |
| `08-http-auth.png` | HTTP health, 401 no token, 200 with token |

## 8. Video Demo Cần Nộp

Video demo nên đặt tại:

```text
submission\demo-video.mp4
```

Flow video khoảng 2 phút:

| Thời gian | Nội dung |
|---|---|
| 0:00 - 0:25 | Terminal chạy `pytest tests\ -v`, hiển thị `55 passed` |
| 0:25 - 0:55 | MCP Inspector: tools list, gọi tool thành công, gọi tool lỗi |
| 0:55 - 1:35 | VS Code Copilot: chạy 2 prompt dùng MCP |
| 1:35 - 2:00 | HTTP bonus: `/health`, no-token 401, Bearer-token 200 |

## 9. Cấu Trúc Nộp Bài Đề Xuất

```text
Day26-Track03-MCP_and_A2A_Infrastructure\
├── README.md
├── RUN_REPORT.md
├── .vscode\
│   └── mcp.json
├── server\
├── scripts\
├── tests\
├── docs\
├── data\
└── submission\
    ├── screenshots\
    │   ├── 02-inspector-tools.png
    │   ├── 03-inspector-resources.png
    │   ├── 04-search-products-success.png
    │   ├── 05-search-invalid-table-error.png
    │   ├── 06-vscode-copilot-tools.png
    │   ├── 07-vscode-copilot-results.png
    │   └── 08-http-auth.png
    └── demo-video.mp4
```

## 10. Kết Luận

Lab 26 đã chạy thành công. MCP server hoạt động với STDIO transport, MCP Inspector, VS Code Copilot và HTTP transport có Bearer token auth. Toàn bộ test tự động đã pass:

```text
55 passed
```

Các lỗi phát sinh trong quá trình chạy thực tế trên Windows đã được debug và sửa, bao gồm lỗi Unicode console, lỗi HTTP MCP lifespan và lỗi đường dẫn khi chạy MCP Inspector.
