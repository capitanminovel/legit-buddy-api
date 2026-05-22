"""
Menu scraper for MN Legit Cannabis – South Metro (Sweed POS platform).

Strategy (in order):
  1. Sweed API      – direct call to known Sweed/Prime API endpoints
  2. Algolia API    – extract app/key from page JS, query index directly
  3. Playwright     – full browser, intercept every XHR/fetch response for JSON products
  4. DOM fallback   – parse visible card HTML, infer category/strain from name
"""

import hashlib
import json
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

STORE_SLUG   = "south-metro"
STORE_DOMAIN = "shop.mnlegitcannabis.com"
MENU_URL     = f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu"
# Sweed POS CDN prefix confirms the platform
SWEED_CDN    = "media-prime.sweedpos.com"
DATA_FILE  = Path(__file__).parent / "docs" / "products.json"
CST        = timezone(timedelta(hours=-6))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://shop.mnlegitcannabis.com/",
}


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S CST')}] {msg}", flush=True)


# ── Normalise any raw product dict → our schema ───────────────────────────────

def _pct(v) -> str:
    if not v: return ""
    s = str(v).replace("%", "").strip()
    try:    return f"{float(s):.1f}%"
    except: return str(v).strip()

def _lst(v) -> list:
    if isinstance(v, list): return [str(i).strip() for i in v if i]
    if isinstance(v, str) and v: return [v]
    return []

def _str(v) -> str:
    return "" if v is None else str(v).strip()

def _price(v) -> str:
    if not v: return ""
    if isinstance(v, (int, float)): return f"${v:.2f}"
    return str(v).strip()

def _img(raw: dict) -> str:
    """Extract best image URL from a Jane product dict."""
    # Jane stores images in photos[].url or photos[].original_url
    photos = raw.get("photos") or []
    if isinstance(photos, list) and photos:
        p0 = photos[0]
        if isinstance(p0, dict):
            return _str(p0.get("original_url") or p0.get("url") or p0.get("thumbnail_url") or "")
        return _str(p0)
    # Fallback fields
    for key in ("image_url", "image", "photo", "thumbnail", "featured_image"):
        v = raw.get(key)
        if v: return _str(v)
    return ""


def normalize(raw: dict) -> dict:
    name     = _str(raw.get("name") or raw.get("title") or "Unknown")
    brand    = _str(raw.get("brand") or raw.get("brand_name") or raw.get("brandName") or "")
    category = _str(raw.get("category") or raw.get("kind") or raw.get("type") or raw.get("root_type") or "")

    # strain_type: Jane uses "strain_type" key
    strain = _str(raw.get("strain_type") or raw.get("strainType") or raw.get("lineage") or "").title()
    _map = {"Indica":"Indica","Sativa":"Sativa","Hybrid":"Hybrid",
            "Hybrid Indica":"Hybrid (Indica)","Hybrid Sativa":"Hybrid (Sativa)",
            "Cbd":"CBD","Cbg":"CBG","Not Applicable":"","N/A":"","":""}
    strain = _map.get(strain, strain)

    thc = _pct(raw.get("percent_thc") or raw.get("thc") or raw.get("thc_content") or raw.get("thcContent") or "")
    cbd = _pct(raw.get("percent_cbd") or raw.get("cbd") or raw.get("cbd_content") or raw.get("cbdContent") or "")
    cbg = _pct(raw.get("percent_cbg") or raw.get("cbg") or "")
    cbn = _pct(raw.get("percent_cbn") or raw.get("cbn") or "")

    # Terpenes
    t_raw = raw.get("terpenes") or raw.get("dominant_terpene") or []
    terpenes = ([x.strip() for x in t_raw.split(",") if x.strip()]
                if isinstance(t_raw, str) else _lst(t_raw))

    # Price tiers — Jane key names
    raw_p = raw.get("prices") or {}
    tiers = {}
    for label, keys in [
        ("gram",       ["gram",       "one_gram",    "1g"]),
        ("two_gram",   ["two_gram",   "2g"]),
        ("eighth",     ["eighth",     "eighth_ounce","3.5g"]),
        ("quarter",    ["quarter",    "quarter_ounce","7g"]),
        ("half_ounce", ["half_ounce", "half",        "14g"]),
        ("ounce",      ["ounce",      "28g",         "oz"]),
        ("unit",       ["unit",       "each"]),
    ]:
        for k in keys:
            v = raw_p.get(k) or raw.get(k)
            if v:
                tiers[label] = _price(v)
                break

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
        "effects":     _lst(raw.get("effects") or raw.get("effect") or []),
        "flavors":     _lst(raw.get("flavors") or raw.get("flavor") or []),
        "weight":      _str(raw.get("weight") or raw.get("size") or raw.get("net_weight") or ""),
        "price":       _price(raw.get("price_each") or raw.get("price") or ""),
        "price_tiers": tiers,
        "in_stock":    bool(raw.get("in_stock", True)),
        "image":       _img(raw),
        "description": _str(raw.get("description") or raw.get("desc") or ""),
    }


# ── Find product arrays buried in any JSON blob ───────────────────────────────

PROD_KEYS = ("products", "items", "menu_items", "menuItems", "hits", "data", "results")

def find_products(data, depth=0) -> list[dict]:
    if depth > 12: return []
    if isinstance(data, dict):
        for k in PROD_KEYS:
            if k in data and isinstance(data[k], list) and data[k]:
                s = data[k][0]
                if isinstance(s, dict) and any(
                    x in s for x in ("name","price","category","percent_thc","strain_type","photos")
                ):
                    return [normalize(p) for p in data[k]]
        for v in data.values():
            r = find_products(v, depth+1)
            if r: return r
    elif isinstance(data, list):
        for item in data:
            r = find_products(item, depth+1)
            if r: return r
    return []


# ── Strategy 1: Sweed POS API ─────────────────────────────────────────────────

def try_sweed_api() -> list[dict]:
    """
    Hit known Sweed POS / Prime API endpoints.
    Image CDN = media-prime.sweedpos.com → API likely at prime.sweedpos.com
    """
    endpoints = [
        # Sweed Prime storefront API patterns
        f"https://prime.sweedpos.com/api/stores/{STORE_SLUG}/products",
        f"https://prime.sweedpos.com/api/stores/{STORE_SLUG}/menu",
        f"https://api.sweedpos.com/v1/stores/{STORE_SLUG}/products",
        f"https://api.sweedpos.com/v1/menu/{STORE_SLUG}",
        # Store-hosted endpoints
        f"https://{STORE_DOMAIN}/api/menu",
        f"https://{STORE_DOMAIN}/api/products",
        f"https://{STORE_DOMAIN}/{STORE_SLUG}/api/products",
        f"https://{STORE_DOMAIN}/{STORE_SLUG}/api/menu",
        # Common SPA data endpoints
        f"https://{STORE_DOMAIN}/api/v1/menu",
        f"https://{STORE_DOMAIN}/api/v2/menu",
    ]
    session = requests.Session()
    session.headers.update({**HEADERS, "Accept": "application/json"})
    for url in endpoints:
        try:
            r = session.get(url, timeout=12)
            if r.status_code == 200:
                data = r.json()
                found = find_products(data)
                if found:
                    log(f"Sweed API ({url}): {len(found)} products")
                    return found
        except Exception:
            pass
    return []


# ── Category / strain inference (fallback when API fields are missing) ────────

def _guess_category(name: str) -> str:
    n = name.lower()
    if any(x in n for x in ("pre-roll","preroll","pre roll")): return "Pre-Roll"
    if any(x in n for x in ("disposable",)):                   return "Vapes"
    if any(x in n for x in ("cartridge","cart","vape")):       return "Vapes"
    if any(x in n for x in ("battery","spinner","pipe","grinder","accessory")): return "Accessories"
    if any(x in n for x in ("gummy","gummies","edible","chocolate","cookie","brownie","beverage","drink")): return "Edibles"
    if any(x in n for x in ("tincture","oil","sublingual")):   return "Tinctures"
    if any(x in n for x in ("topical","cream","lotion","balm","patch")): return "Topicals"
    if any(x in n for x in ("concentrate","wax","shatter","badder","rosin","hash","live resin","distillate","sauce")): return "Concentrates"
    if "flower" in n:                                           return "Flower"
    return ""

def _guess_strain(name: str) -> str:
    n = name.lower()
    if "indica" in n: return "Indica"
    if "sativa" in n: return "Sativa"
    if "hybrid" in n: return "Hybrid"
    if "cbd"    in n: return "CBD"
    return ""

def _clean_name(name: str) -> str:
    """Remove trailing category keywords already visible in the category badge."""
    patterns = [
        r'\s*[-–]\s*PRE-?ROLL\s*$',
        r'\s*[-–]\s*FLOWER\s*$',
        r'\s*\bFlower\b\s*$',
        r'\s*\bPRE-?ROLL\b\s*$',
    ]
    for pat in patterns:
        name = re.sub(pat, '', name, flags=re.I).strip()
    return name


# ── Strategy 2: Algolia direct query ─────────────────────────────────────────

def try_algolia(page_html: str = "") -> list[dict]:
    """
    Jane embeds Algolia app ID + API key + index name in page JS.
    Extract them and query Algolia directly — gets full product data + images.
    """
    if not page_html:
        try:
            r = requests.get(MENU_URL, headers=HEADERS, timeout=20)
            page_html = r.text
        except Exception:
            return []

    # Patterns seen in Jane-powered sites
    app_id  = re.search(r'"?applicationId"?\s*:\s*"([A-Z0-9]{10})"', page_html)
    api_key = re.search(r'"?apiKey"?\s*:\s*"([a-f0-9]{32})"', page_html)
    index   = re.search(r'"?indexName"?\s*:\s*"([^"]+menu[^"]*)"', page_html, re.I)

    # Also try env-style variables
    if not app_id:
        app_id = re.search(r'ALGOLIA_APP_ID["\s:=]+([A-Z0-9]{10})', page_html)
    if not api_key:
        api_key = re.search(r'ALGOLIA_API_KEY["\s:=]+([a-f0-9]{32})', page_html)

    if not (app_id and api_key):
        log("Algolia: credentials not found in page source")
        return []

    app  = app_id.group(1)
    key  = api_key.group(1)
    idx  = index.group(1) if index else f"menu_{STORE_SLUG}"

    log(f"Algolia: app={app} index={idx}")
    url  = f"https://{app}-dsn.algolia.net/1/indexes/{idx}/query"
    body = {"hitsPerPage": 500, "attributesToRetrieve": ["*"]}
    try:
        r = requests.post(url, json=body,
                          headers={"X-Algolia-Application-Id": app,
                                   "X-Algolia-API-Key": key,
                                   "Content-Type": "application/json"},
                          timeout=15)
        data  = r.json()
        found = find_products(data)
        if found:
            log(f"Algolia: {len(found)} products")
            return found
    except Exception as e:
        log(f"Algolia query failed: {e}")
    return []


# ── Strategy 3: Playwright full browser ──────────────────────────────────────

def try_playwright() -> list[dict]:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    captured: list[tuple[str, dict]] = []   # (url, body)
    products: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = ctx.new_page()

        # Capture EVERY JSON response — don't filter by URL keyword
        def on_response(resp):
            ct = resp.headers.get("content-type", "")
            if "json" in ct:
                try:
                    body = resp.json()
                    captured.append((resp.url, body))
                except Exception:
                    pass

        page.on("response", on_response)

        log(f"Playwright → {MENU_URL}")
        try:
            page.goto(MENU_URL, wait_until="networkidle", timeout=60000)
        except PwTimeout:
            try:
                page.goto(MENU_URL, wait_until="domcontentloaded", timeout=35000)
                time.sleep(10)
            except Exception:
                pass

        # Scroll to trigger lazy loads
        for _ in range(6):
            page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
            time.sleep(1.2)
        page.evaluate("window.scrollTo(0,0)")
        time.sleep(2)

        # --- 3a. Mine captured JSON responses (largest first = most products)
        captured.sort(key=lambda x: len(str(x[1])), reverse=True)
        log(f"Playwright: captured {len(captured)} JSON responses")
        for url, body in captured:
            found = find_products(body)
            if found:
                products = found
                log(f"  ✓ {len(found)} products from {url[:80]}")
                break

        # --- 3b. Try extracting Algolia creds from rendered page source
        if not products:
            html = page.content()
            products = try_algolia(html)

        # --- 3c. __NEXT_DATA__
        if not products:
            try:
                nd    = page.evaluate("()=>JSON.parse(document.getElementById('__NEXT_DATA__').textContent)")
                found = find_products(nd)
                if found:
                    products = found
                    log(f"Playwright/__NEXT_DATA__: {len(found)} products")
            except Exception:
                pass

        # --- 3d. DOM card scraping with image extraction
        if not products:
            log("Playwright: DOM card fallback")
            CARD_SELS = (
                "[data-testid='product-card']", "[data-testid='menu-product-card']",
                ".product-card", "[class*='ProductCard']", "[class*='product_card']",
                "[class*='MenuCard']", ".menu-item",
            )
            for sel in CARD_SELS:
                cards = page.query_selector_all(sel)
                if not cards: continue
                for card in cards:
                    p: dict = {}
                    for ns in ["h2","h3","[class*='name']","[class*='title']"]:
                        el = card.query_selector(ns)
                        if el: p["name"] = el.inner_text().strip(); break
                    for bs in ["[class*='brand']"]:
                        el = card.query_selector(bs)
                        if el: p["brand"] = el.inner_text().strip(); break
                    for cs in ["[class*='strain']","[class*='kind']","[class*='category']"]:
                        el = card.query_selector(cs)
                        if el: p["category"] = el.inner_text().strip(); break
                    for ps in ["[class*='price']"]:
                        el = card.query_selector(ps)
                        if el: p["price"] = el.inner_text().strip(); break
                    for ts in ["[class*='thc']","[class*='potency']"]:
                        el = card.query_selector(ts)
                        if el: p["thc"] = el.inner_text().strip(); break
                    for cs2 in ["[class*='cbd']"]:
                        el = card.query_selector(cs2)
                        if el: p["cbd"] = el.inner_text().strip(); break
                    img = card.query_selector("img")
                    if img:
                        p["image"] = (img.get_attribute("src") or
                                      img.get_attribute("data-src") or
                                      img.get_attribute("data-lazy-src") or "")
                    if p.get("name"):
                        raw = normalize(p)
                        # Fill missing fields from name inference
                        if not raw["category"]:
                            raw["category"]    = _guess_category(raw["name"])
                        if not raw["strain_type"]:
                            raw["strain_type"] = _guess_strain(raw["name"])
                        raw["name"] = _clean_name(raw["name"])
                        products.append(raw)
                if products:
                    log(f"DOM cards: {len(products)} products")
                    break

        browser.close()
    return products


# ── Database helpers ──────────────────────────────────────────────────────────

def product_key(p: dict) -> str:
    key = f"{p.get('name','').lower().strip()}-{p.get('brand','').lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def load_db() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f: return json.load(f)
    return {"products": {}, "last_updated": None, "store": "South Metro"}

def save_db(db: dict):
    db["last_updated"] = datetime.now(CST).isoformat()
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f: json.dump(db, f, indent=2)
    log(f"Saved → {DATA_FILE}")

def merge(db: dict, fresh: list[dict]) -> dict:
    now  = datetime.now(CST).isoformat()
    data = db.get("products", {})
    seen = set()
    for p in fresh:
        pid = product_key(p)
        seen.add(pid)
        if pid not in data:
            p["first_seen"] = now
            log(f"  NEW: {p['name']}")
        else:
            p["first_seen"] = data[pid]["first_seen"]
        p["last_seen"] = now
        data[pid] = p
    for pid, p in data.items():
        if pid not in seen:
            p["in_stock"] = False
    db["products"] = data
    return db


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log("=" * 56)
    log(f"Scraping {MENU_URL}")

    products = try_sweed_api()

    if not products:
        log("Sweed API found nothing — trying Algolia...")
        products = try_algolia()

    if not products:
        log("Algolia found nothing — launching Playwright...")
        products = try_playwright()

    if not products:
        log("WARNING: 0 products scraped. Keeping existing data unchanged.")
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
