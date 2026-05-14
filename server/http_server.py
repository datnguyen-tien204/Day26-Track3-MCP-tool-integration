"""
Lab #26 BONUS — MCP Server with HTTP Transport + Bearer Token Auth
==================================================================
Exposes the same MCP server over HTTP (Streamable HTTP / SSE legacy).

Production security pattern:
  - Bearer token via Authorization header (OAuth 2.0 compatible)
  - Token validation middleware
  - Rate limiting per token
  - Request logging

Run:
    # Generate a token first
    python -c "import secrets; print(secrets.token_urlsafe(32))"

    # Set env var and start
    MCP_AUTH_TOKEN=<token> python server/http_server.py

    # Connect via Inspector
    npx @modelcontextprotocol/inspector http://localhost:8000/mcp
    # Header: Authorization: Bearer <token>
"""

import os
import sys
import time
import logging
import secrets
import hashlib
from collections import defaultdict
from typing import Callable, Awaitable
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

from server.database import init_db

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
HOST       = os.getenv("MCP_HOST",       "0.0.0.0")
PORT       = int(os.getenv("MCP_PORT",   "8000"))
AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")

# Rate limiting: max requests per minute per token
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("lab26.http")


# ─────────────────────────────────────────────
# Token store (in-memory; use Redis in production)
# ─────────────────────────────────────────────
class TokenStore:
    """
    Simple in-memory token store with rate limiting.
    In production: replace with Redis + OAuth 2.0 introspection.
    """

    def __init__(self) -> None:
        # {token_hash: {metadata}}
        self._tokens: dict[str, dict] = {}
        # {token_hash: [timestamps]}
        self._rate_windows: dict[str, list[float]] = defaultdict(list)

    def add_token(
        self,
        raw_token: str,
        description: str = "default",
        scopes: list[str] | None = None,
    ) -> str:
        """Hash and store a token. Returns the hash (for audit logs)."""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        self._tokens[token_hash] = {
            "description": description,
            "scopes":      scopes or ["read", "write"],
            "created_at":  datetime.utcnow().isoformat(),
            "request_count": 0,
        }
        return token_hash

    def validate(self, raw_token: str) -> dict | None:
        """Validate token and check rate limit. Returns metadata or None."""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        meta = self._tokens.get(token_hash)
        if not meta:
            return None

        # Rate-limit check: sliding window
        now = time.time()
        window = self._rate_windows[token_hash]
        self._rate_windows[token_hash] = [t for t in window if now - t < 60]

        if len(self._rate_windows[token_hash]) >= RATE_LIMIT_RPM:
            return {"error": "rate_limited", **meta}

        self._rate_windows[token_hash].append(now)
        meta["request_count"] += 1
        return meta

    def stats(self, raw_token: str) -> dict:
        """Return usage stats for a token."""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        meta = self._tokens.get(token_hash, {})
        recent = self._rate_windows.get(token_hash, [])
        return {
            **meta,
            "requests_last_60s": len(recent),
            "rate_limit_rpm":    RATE_LIMIT_RPM,
        }


token_store = TokenStore()


# ─────────────────────────────────────────────
# Auth middleware
# ─────────────────────────────────────────────
class BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates Bearer tokens on every request.

    Allows:
        - GET /health  (no auth needed)
        - GET /        (no auth needed — welcome page)
        - POST/GET /mcp* — requires valid Bearer token
    """

    OPEN_PATHS = {"/", "/health", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip auth for open paths
        if path in self.OPEN_PATHS:
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Missing/invalid Authorization header from %s", request.client)
            return JSONResponse(
                {"error": "Missing Authorization header", "detail": "Use: Authorization: Bearer <token>"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        raw_token = auth_header.removeprefix("Bearer ").strip()
        meta = token_store.validate(raw_token)

        if meta is None:
            logger.warning("Invalid token attempt from %s", request.client)
            return JSONResponse(
                {"error": "Invalid token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        if meta.get("error") == "rate_limited":
            return JSONResponse(
                {"error": "Rate limit exceeded", "retry_after": "60s"},
                status_code=429,
                headers={"Retry-After": "60"},
            )

        # Attach token metadata to request state for downstream use
        request.state.token_meta = meta
        request.state.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()[:8]

        logger.info(
            "AUTH OK  token=...%s  scope=%s  path=%s",
            raw_token[-6:], meta.get("scopes"), path,
        )

        response = await call_next(request)

        # Append audit headers
        response.headers["X-Token-Description"] = meta.get("description", "")
        response.headers["X-Request-Count"]      = str(meta.get("request_count", 0))
        return response


# ─────────────────────────────────────────────
# Route handlers (health / welcome)
# ─────────────────────────────────────────────
async def health(request: Request) -> JSONResponse:
    return JSONResponse(
        {"status": "ok", "server": "lab26-sales-db", "transport": "http"},
        status_code=200,
    )


async def welcome(request: Request) -> Response:
    html = """<!DOCTYPE html>
<html><head><title>Lab26 MCP Server</title></head>
<body style="font-family:monospace;max-width:600px;margin:40px auto">
<h1>🔌 Lab26 MCP Server</h1>
<p><strong>Transport:</strong> HTTP (Streamable HTTP)</p>
<p><strong>Auth:</strong> Bearer token required for /mcp endpoints</p>
<h2>Endpoints</h2>
<ul>
  <li><code>GET  /health</code> — Health check (no auth)</li>
  <li><code>POST /mcp</code>   — MCP JSON-RPC (auth required)</li>
  <li><code>GET  /mcp/sse</code> — SSE stream (auth required)</li>
</ul>
<h2>Connect with Inspector</h2>
<pre>npx @modelcontextprotocol/inspector http://localhost:8000/mcp
# Set header: Authorization: Bearer YOUR_TOKEN</pre>
</body></html>"""
    return Response(html, media_type="text/html")


# ─────────────────────────────────────────────
# Build the Starlette app
# ─────────────────────────────────────────────
def create_app() -> ASGIApp:
    """Create and configure the Starlette ASGI app."""
    # Import here to avoid circular deps; server must be init'd first
    from server.main import mcp  # noqa: F401

    # Register the env token (if provided)
    if AUTH_TOKEN:
        token_store.add_token(AUTH_TOKEN, description="env-default", scopes=["read", "write"])
        logger.info("Loaded token from MCP_AUTH_TOKEN env var.")
    else:
        # Generate a one-time dev token and print it
        dev_token = secrets.token_urlsafe(32)
        token_store.add_token(dev_token, description="dev-auto", scopes=["read", "write"])
        logger.warning("⚠  No MCP_AUTH_TOKEN set. Dev token (single session): %s", dev_token)

    # Get the MCP ASGI app (streamable-http transport)
    mcp_asgi = mcp.streamable_http_app()

    app = Starlette(
        routes=[
            Route("/",       welcome),
            Route("/health", health),
            Mount("/",       app=mcp_asgi),  # mounts /mcp
        ],
        lifespan=lambda app: mcp.session_manager.run(),
    )

    app.add_middleware(BearerAuthMiddleware)
    return app


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    init_db()
    logger.info("Starting HTTP MCP server on %s:%s", HOST, PORT)

    if not AUTH_TOKEN:
        logger.warning(
            "Set MCP_AUTH_TOKEN env var for a stable token. "
            "Current session uses an auto-generated token (see above)."
        )

    app = create_app()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
