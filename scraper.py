"""
Menu scraper for MN Legit Cannabis – South Metro.
Targets shop.mnlegitcannabis.com (Jane / iHeartJane platform).
Captures: strain type, THC/CBD %, terpenes, effects, price tiers, images.
"""

import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

MENU_URL  = "https://shop.mnlegitcannabis.com/south-metro/menu"
DATA_FILE = Path(__file__).parent / "docs" / "products.json"
CST       = timezone(timedelta(hours=-6))

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

# Jane platform Algolia app/index (common across Jane stores)
ALGOLIA_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json",
    "Content-Type": "application/json",
}


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S CST')}] {msg}", flush=True)


# ── Normalise raw product dict to our schema ──────────────────────────────────

def _str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(v)
    return str(v).strip()


def _pct(v) -> str:
    """Format a percentage value like 22.4 → '22.4%'"""
    if not v:
        return ""
    s = _str(v).replace("%", "").strip()
    try:
        return f"{float(s):.1f}%"
    except ValueError:
        return s


def _list(v) -> list:
    if isinstance(v, list):
        return [_str(i) for i in v if i]
    if isinstance(v, str) and v:
        return [v]
    return []


def normalize(raw: dict) -> dict:
    # ── Identity
    name     = _str(raw.get("name") or raw.get("title") or "Unknown")
    brand    = _str(raw.get("brand") or raw.get("brand_name") or raw.get("brandName") or "")
    category = _str(raw.get("category") or raw.get("kind") or raw.get("type") or raw.get("root_type") or "")

    # ── Strain type  (Jane uses "strain_type", fallbacks vary)
    strain = _str(
        raw.get("strain_type") or raw.get("strainType") or
        raw.get("lineage") or raw.get("strain") or ""
    ).strip().title()
    # Normalise common values
    _strain_map = {
        "Indica": "Indica", "Sativa": "Sativa",
        "Hybrid": "Hybrid", "Hybrid Indica": "Hybrid (Indica)",
        "Hybrid Sativa": "Hybrid (Sativa)", "Cbd": "CBD",
        "Cbg": "CBG", "Not Applicable": "",
    }
    strain = _strain_map.get(strain, strain)

    # ── Potency
    thc = _pct(raw.get("percent_thc") or raw.get("thc") or raw.get("thc_content") or
               raw.get("thcContent") or raw.get("thcPercent") or "")
    cbd = _pct(raw.get("percent_cbd") or raw.get("cbd") or raw.get("cbd_content") or
               raw.get("cbdContent") or raw.get("cbdPercent") or "")
    cbg = _pct(raw.get("percent_cbg") or raw.get("cbg") or "")
    cbn = _pct(raw.get("percent_cbn") or raw.get("cbn") or "")

    # ── Terpenes  (array or comma string)
    terpenes_raw = raw.get("terpenes") or raw.get("dominant_terpene") or []
    if isinstance(terpenes_raw, str) and terpenes_raw:
        terpenes = [t.strip() for t in terpenes_raw.split(",") if t.strip()]
    else:
        terpenes = _list(terpenes_raw)

    # ── Effects / flavors
    effects  = _list(raw.get("effects")  or raw.get("effect")  or [])
    flavors  = _list(raw.get("flavors")  or raw.get("flavor")  or [])

    # ── Weight / unit
    weight = _str(raw.get("weight") or raw.get("size") or raw.get("net_weight") or "")

    # ── Pricing  – single price + per-weight tiers
    price_each = raw.get("price_each") or raw.get("price") or ""
    if isinstance(price_each, (int, float)):
        price_each = f"${price_each:.2f}"
    else:
        price_each = _str(price_each)

    raw_prices = raw.get("prices") or {}
    tiers = {}
    tier_keys = [
        ("gram",       ["gram",       "1g",  "one_gram"]),
        ("two_gram",   ["two_gram",   "2g"]),
        ("eighth",     ["eighth",     "3.5g","eighth_ounce"]),
        ("quarter",    ["quarter",    "7g",  "quarter_ounce"]),
        ("half_ounce", ["half_ounce", "14g", "half"]),
        ("ounce",      ["ounce",      "28g", "oz"]),
        ("unit",       ["unit",       "each","piece"]),
    ]
    for label, keys in tier_keys:
        for k in keys:
            v = raw_prices.get(k) or raw.get(k)
            if v:
                tiers[label] = f"${float(v):.2f}" if isinstance(v, (int, float)) else _str(v)
                break

    # ── Images
    photos = raw.get("photos") or []
    if isinstance(photos, list) and photos:
        photo = _str(photos[0].get("url") or photos[0]) if isinstance(photos[0], dict) else _str(photos[0])
    else:
        photo = _str(raw.get("image") or raw.get("image_url") or raw.get("photo") or
                     raw.get("thumbnail") or "")

    # ── Description
    description = _str(raw.get("description") or raw.get("desc") or "")

    return {
        "name":        name,
        "brand":       brand,
        "category":    category,
        "strain_type": strain,
        "thc":         thc,
        "cbd":         cbd,
        "cbg":         cbg,
        "cbn":         cbn,
        "terpenes":    terpenes,
        "effects":     effects,
        "flavors":     flavors,
        "weight":      weight,
        "price":       price_each,
        "price_tiers": tiers,
        "in_stock":    bool(raw.get("in_stock", True)),
        "image":       photo,
        "description": description,
    }


# ── JSON / API extraction ─────────────────────────────────────────────────────

PRODUCT_KEYS = ("products", "items", "menu_items", "menuItems", "hits", "data")

def extract_nested(data, depth=0) -> list[dict]:
    if depth > 12:
        return []
    if isinstance(data, dict):
        for key in PRODUCT_KEYS:
            if key in data and isinstance(data[key], list) and data[key]:
                sample = data[key][0]
                if isinstance(sample, dict) and any(
                    k in sample for k in ("name", "price", "category", "percent_thc")
                ):
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


# ── Requests (lightweight) scraper ────────────────────────────────────────────

def scrape_requests() -> list[dict]:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        r = session.get(MENU_URL, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # Next.js __NEXT_DATA__ (Jane stores often embed full product list here)
        for tag in soup.find_all("script", {"id": "__NEXT_DATA__"}):
            try:
                data  = json.loads(tag.string)
                found = extract_nested(data)
                if found:
                    log(f"requests/__NEXT_DATA__: {len(found)} products")
                    return found
            except Exception:
                pass

        # window.__PRELOADED_STATE__ or similar inline JSON
        for tag in soup.find_all("script"):
            src = tag.string or ""
            for marker in ("__PRELOADED_STATE__", "__INITIAL_STATE__", "window.__STATE__"):
                if marker in src:
                    try:
                        start = src.index("{", src.index(marker))
                        # find matching brace
                        depth, end = 0, start
                        for i, ch in enumerate(src[start:], start):
                            if ch == "{":
                                depth += 1
                            elif ch == "}":
                                depth -= 1
                                if depth == 0:
                                    end = i + 1
                                    break
                        data  = json.loads(src[start:end])
                        found = extract_nested(data)
                        if found:
                            log(f"requests/{marker}: {len(found)} products")
                            return found
                    except Exception:
                        pass

    except requests.RequestException as e:
        log(f"requests error: {e}")
    return []


# ── Playwright (JS-rendered) scraper ──────────────────────────────────────────

def scrape_playwright() -> list[dict]:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    products    = []
    intercepted = []   # (url, body) tuples

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()

        def on_response(resp):
            url = resp.url.lower()
            # Jane API calls: /api/menu, /products, Algolia, etc.
            if any(k in url for k in ("menu", "products", "items", "inventory",
                                       "algolia", "search", "catalog")):
                try:
                    body = resp.json()
                    intercepted.append((resp.url, body))
                except Exception:
                    pass

        page.on("response", on_response)

        log(f"Playwright → {MENU_URL}")
        try:
            page.goto(MENU_URL, wait_until="networkidle", timeout=50000)
        except PwTimeout:
            try:
                page.goto(MENU_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(8)
            except Exception:
                pass

        # Wait for product cards
        CARD_SELS = (
            "[data-testid='product-card']",
            "[data-testid='menu-product-card']",
            ".product-card",
            "[class*='ProductCard']",
            "[class*='product_card']",
            ".menu-item",
            "[class*='MenuCard']",
        )
        for sel in CARD_SELS:
            try:
                page.wait_for_selector(sel, timeout=8000)
                log(f"Cards found: {sel}")
                break
            except PwTimeout:
                continue

        # Scroll to load lazy products
        for _ in range(5):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(1)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

        # 1. Best source: intercepted API/Algolia JSON
        # Sort by response size descending (bigger = more products)
        intercepted.sort(key=lambda x: len(str(x[1])), reverse=True)
        for url, body in intercepted:
            found = extract_nested(body)
            if found:
                products = found
                log(f"Playwright/API ({url[:60]}): {len(found)} products")
                break

        # 2. __NEXT_DATA__
        if not products:
            try:
                nd    = page.evaluate("() => JSON.parse(document.getElementById('__NEXT_DATA__').textContent)")
                found = extract_nested(nd)
                if found:
                    products = found
                    log(f"Playwright/__NEXT_DATA__: {len(found)} products")
            except Exception:
                pass

        # 3. DOM scraping — richer field extraction per card
        if not products:
            log("Playwright: DOM card extraction")
            for sel in CARD_SELS:
                cards = page.query_selector_all(sel)
                if not cards:
                    continue
                for card in cards:
                    p = {}
                    # name
                    for ns in ["h2", "h3", "[class*='name']", "[class*='title']"]:
                        el = card.query_selector(ns)
                        if el:
                            p["name"] = el.inner_text().strip()
                            break
                    # brand
                    for bs in ["[class*='brand']", "[class*='Brand']"]:
                        el = card.query_selector(bs)
                        if el:
                            p["brand"] = el.inner_text().strip()
                            break
                    # category / strain
                    for cs in ["[class*='category']", "[class*='kind']", "[class*='strain']", "[class*='type']"]:
                        el = card.query_selector(cs)
                        if el:
                            p["category"] = el.inner_text().strip()
                            break
                    # price
                    for ps in ["[class*='price']", "[class*='Price']"]:
                        el = card.query_selector(ps)
                        if el:
                            p["price"] = el.inner_text().strip()
                            break
                    # THC
                    for ts in ["[class*='thc']", "[class*='THC']", "[class*='potency']"]:
                        el = card.query_selector(ts)
                        if el:
                            p["thc"] = el.inner_text().strip()
                            break
                    # CBD
                    for cs2 in ["[class*='cbd']", "[class*='CBD']"]:
                        el = card.query_selector(cs2)
                        if el:
                            p["cbd"] = el.inner_text().strip()
                            break
                    # image
                    img = card.query_selector("img")
                    if img:
                        p["image"] = img.get_attribute("src") or img.get_attribute("data-src") or ""
                    if p.get("name"):
                        products.append(normalize(p))
                if products:
                    log(f"Playwright/DOM: {len(products)} products")
                    break

        browser.close()
    return products


# ── Database helpers ──────────────────────────────────────────────────────────

def product_key(p: dict) -> str:
    key = f"{p.get('name','').lower().strip()}-{p.get('brand','').lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


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


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log("=" * 56)
    log(f"Scraping {MENU_URL}")

    products = scrape_requests()
    if not products:
        log("Falling back to Playwright...")
        products = scrape_playwright()

    if not products:
        log("WARNING: 0 products — site may need cookies/auth.")
        db = load_db()
        save_db(db)
        return db

    db = load_db()
    db = merge(db, products)
    save_db(db)

    in_stock = sum(1 for p in db["products"].values() if p.get("in_stock", True))
    log(f"Done — {len(products)} scraped, {in_stock} total in stock")
    return db


if __name__ == "__main__":
    run()
