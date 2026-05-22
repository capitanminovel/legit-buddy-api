import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Legit Buddy API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CST       = timezone(timedelta(hours=-6))
DATA_FILE = Path(__file__).parent / "docs" / "products.json"


# ── Status ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "Legit Buddy API running",
        "endpoints": ["/api/menu", "/api/products", "/api/claude", "/docs"],
    }


# ── Products (from local JSON) ────────────────────────────────────────────────

@app.get("/api/products")
def get_products(category: str = None, new_only: bool = False):
    if not DATA_FILE.exists():
        raise HTTPException(404, "No product data yet — run the scraper first.")
    with open(DATA_FILE) as f:
        db = json.load(f)

    products = [
        {"id": k, **v}
        for k, v in db.get("products", {}).items()
        if v.get("in_stock", True)
    ]

    if category:
        products = [p for p in products if (p.get("category") or "").lower() == category.lower()]

    if new_only:
        now = datetime.now(CST)
        def is_new(p):
            try:
                return (now - datetime.fromisoformat(p["first_seen"])).days <= 3
            except Exception:
                return False
        products = [p for p in products if is_new(p)]

    return {
        "count": len(products),
        "last_updated": db.get("last_updated"),
        "products": products,
    }


# ── Live scrape on demand ─────────────────────────────────────────────────────

@app.post("/api/menu/refresh")
def refresh_menu():
    """Trigger a live scrape (slow — may take 30–60s with Playwright)."""
    try:
        from scraper import run
        db = run()
        in_stock = sum(1 for p in db["products"].values() if p.get("in_stock", True))
        return {"status": "ok", "in_stock": in_stock, "last_updated": db.get("last_updated")}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Claude proxy ──────────────────────────────────────────────────────────────

@app.post("/api/claude")
async def claude_proxy(request: Request):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY not set")

    body = await request.json()
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=60,
    )
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


# ── Serve the menu UI ─────────────────────────────────────────────────────────

if (Path(__file__).parent / "docs").exists():
    app.mount("/menu", StaticFiles(directory="docs", html=True), name="menu")
