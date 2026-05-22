"""
Menu scraper for MN Legit Cannabis – South Metro.
Tries lightweight requests first, falls back to Playwright if JS is needed.
Persists data to docs/products.json so GitHub Pages can serve it.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

MENU_URL  = "https://shop.mnlegitcannabis.com/south-metro/menu"
DATA_FILE = Path(__file__).parent / "docs" / "products.json"
CST       = timezone(timedelta(hours=-6))
NEW_DAYS  = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://shop.mnlegitcannabis.com/",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S CST')}] {msg}", flush=True)


def product_key(p: dict) -> str:
    return hashlib.md5(f"{p.get('name','')}-{p.get('brand','')}".encode()).hexdigest()[:12]


def normalize(raw: dict) -> dict:
    return {
        "name":        raw.get("name") or raw.get("title") or "Unknown",
        "brand":       raw.get("brand") or raw.get("brand_name") or "",
        "category":    raw.get("category") or raw.get("kind") or raw.get("type") or "",
        "price":       raw.get("price") or raw.get("price_each") or "",
        "thc":         raw.get("thc") or raw.get("thc_content") or raw.get("thcContent") or "",
        "cbd":         raw.get("cbd") or raw.get("cbd_content") or raw.get("cbdContent") or "",
        "weight":      raw.get("weight") or raw.get("size") or "",
        "in_stock":    raw.get("in_stock", True),
        "image":       raw.get("image") or raw.get("image_url") or raw.get("photo") or "",
        "description": raw.get("description") or "",
    }


def extract_nested(data, depth=0) -> list[dict]:
    """Recursively pull product arrays from JSON blobs (Next.js / embedded data)."""
    if depth > 10:
        return []
    if isinstance(data, dict):
        for key in ("products", "items", "menu_items", "menuItems", "data"):
            if key in data and isinstance(data[key], list) and data[key]:
                sample = data[key][0]
                if isinstance(sample, dict) and any(k in sample for k in ("name", "price", "category")):
                    return [normalize(p) for p in data[key]]
        for v in data.values():
            r = extract_nested(v, depth + 1)
            if r:
                return r
    elif isinstance(data, list):
        for item in data:
            r = extract_nested(item, depth + 1)
            if r:
                return r
    return []


# ── Requests scraper ──────────────────────────────────────────────────────────

def scrape_requests() -> list[dict]:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        r = session.get(MENU_URL, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # Next.js embedded data
        for tag in soup.find_all("script", {"id": "__NEXT_DATA__"}):
            try:
                data = json.loads(tag.string)
                found = extract_nested(data)
                if found:
                    log(f"requests: found {len(found)} products via __NEXT_DATA__")
                    return found
            except Exception:
                pass

        # Visible product cards
        products = []
        for sel in ("[data-testid='product-card']", ".product-card", "[class*='ProductCard']", ".menu-item"):
            cards = soup.select(sel)
            if not cards:
                continue
            for card in cards:
                p = {}
                for ns in ["h3", "h2", "[class*='name']"]:
                    el = card.select_one(ns)
                    if el:
                        p["name"] = el.get_text(strip=True)
                        break
                for ps in ["[class*='price']"]:
                    el = card.select_one(ps)
                    if el:
                        p["price"] = el.get_text(strip=True)
                        break
                for bs in ["[class*='brand']"]:
                    el = card.select_one(bs)
                    if el:
                        p["brand"] = el.get_text(strip=True)
                        break
                for cs in ["[class*='category']", "[class*='kind']"]:
                    el = card.select_one(cs)
                    if el:
                        p["category"] = el.get_text(strip=True)
                        break
                if p.get("name"):
                    products.append(normalize(p))
            if products:
                log(f"requests: found {len(products)} products via HTML cards")
                return products

    except requests.RequestException as e:
        log(f"requests error: {e}")
    return []


# ── Playwright scraper ────────────────────────────────────────────────────────

def scrape_playwright() -> list[dict]:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    products = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        intercepted = []

        def on_response(resp):
            url = resp.url
            if any(k in url for k in ("menu", "products", "items", "inventory")):
                try:
                    intercepted.append(resp.json())
                except Exception:
                    pass

        page.on("response", on_response)

        log(f"Playwright: navigating to {MENU_URL}")
        try:
            page.goto(MENU_URL, wait_until="networkidle", timeout=45000)
        except PwTimeout:
            page.goto(MENU_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(6)

        # Wait for any product selector
        for sel in ("[data-testid='product-card']", ".product-card", "[class*='ProductCard']", ".menu-item"):
            try:
                page.wait_for_selector(sel, timeout=8000)
                log(f"Playwright: found products via {sel}")
                break
            except PwTimeout:
                continue

        # 1. Intercepted API calls
        for body in intercepted:
            found = extract_nested(body)
            if found:
                products = found
                log(f"Playwright: {len(found)} products from intercepted API")
                break

        # 2. __NEXT_DATA__
        if not products:
            try:
                nd = page.evaluate("() => JSON.parse(document.getElementById('__NEXT_DATA__').textContent)")
                found = extract_nested(nd)
                if found:
                    products = found
                    log(f"Playwright: {len(found)} products from __NEXT_DATA__")
            except Exception:
                pass

        # 3. DOM fallback
        if not products:
            log("Playwright: DOM fallback")
            for sel in ("[data-testid='product-card']", ".product-card", "[class*='ProductCard']", ".menu-item"):
                cards = page.query_selector_all(sel)
                if not cards:
                    continue
                for card in cards:
                    p = {}
                    for ns in ["h3", "h2", "[class*='name']"]:
                        el = card.query_selector(ns)
                        if el:
                            p["name"] = el.inner_text().strip()
                            break
                    for ps in ["[class*='price']"]:
                        el = card.query_selector(ps)
                        if el:
                            p["price"] = el.inner_text().strip()
                            break
                    for bs in ["[class*='brand']"]:
                        el = card.query_selector(bs)
                        if el:
                            p["brand"] = el.inner_text().strip()
                            break
                    if p.get("name"):
                        products.append(normalize(p))
                if products:
                    log(f"Playwright DOM: {len(products)} products")
                    break

        browser.close()
    return products


# ── Database ──────────────────────────────────────────────────────────────────

def load_db() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"products": {}, "last_updated": None, "store": "South Metro"}


def save_db(db: dict):
    db["last_updated"] = datetime.now(CST).isoformat()
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=2)
    log(f"Saved → {DATA_FILE}")


def merge(db: dict, fresh: list[dict]) -> dict:
    now  = datetime.now(CST).isoformat()
    data = db.get("products", {})

    fresh_ids = set()
    for p in fresh:
        pid = product_key(p)
        fresh_ids.add(pid)
        if pid not in data:
            p["first_seen"] = now
            log(f"  NEW: {p['name']}")
        else:
            p["first_seen"] = data[pid]["first_seen"]
        p["last_seen"] = now
        data[pid] = p

    for pid, p in data.items():
        if pid not in fresh_ids:
            p["in_stock"] = False

    db["products"] = data
    return db


# ── Entry point ───────────────────────────────────────────────────────────────

def run():
    log("=" * 56)
    log("Starting scrape...")

    products = scrape_requests()

    if not products:
        log("Falling back to Playwright...")
        products = scrape_playwright()

    if not products:
        log("WARNING: 0 products scraped — site may need authentication or has changed structure.")
        db = load_db()
        save_db(db)
        return db

    db = load_db()
    db = merge(db, products)
    save_db(db)

    in_stock = sum(1 for p in db["products"].values() if p.get("in_stock", True))
    log(f"Done — {len(products)} scraped, {in_stock} in stock total")
    return db


if __name__ == "__main__":
    run()
