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
SWEED_CDN    = "media-prime.sweedpos.com"
DATA_FILE    = Path(__file__).parent / "docs" / "products.json"
CST          = timezone(timedelta(hours=-6))

# Only scrape and display these 4 categories
TARGET_CATS = ("flower", "pre-roll", "vapes", "edibles")

# Sweed category URL slugs to try for each target category
CATEGORY_URLS = [
    # Flower
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu/flower",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?category=flower",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?type=flower",
    # Pre-Roll
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu/pre-rolls",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu/pre-roll",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?category=pre-roll",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?type=pre_roll",
    # Vapes
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu/vapes",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu/vape-pens",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?category=vapes",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?type=vape",
    # Edibles
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu/edibles",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?category=edibles",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?type=edible",
]

# Paginated base menu pages
PAGINATED_URLS = [
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?page=2",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?page=3",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?page=4",
    f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu?page=5",
]

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


# ── Sweed POS native API normalizer ──────────────────────────────────────────
# Endpoint confirmed: https://shop.mnlegitcannabis.com/_api/Products/GetProductList
# Each product has nested category/brand/strain objects and a variants array.

_WEIGHT_TO_TIER = {
    "1g": "gram",  "2g": "two_gram",  "3.5g": "eighth",
    "7g": "quarter", "14g": "half_ounce", "28g": "ounce",
}

def _normalize_sweed_product(raw: dict) -> dict | None:
    name = _str(raw.get("name") or "")
    if not name:
        return None

    brand    = _str((raw.get("brand") or {}).get("name") or "")
    category = _str((raw.get("category") or {}).get("name") or
                    (raw.get("productType") or {}).get("name") or "")

    strain_info = raw.get("strain") or {}
    prevalence  = strain_info.get("prevalence") or {}
    strain_raw  = _str(prevalence.get("name") or "").title()
    _smap = {"Indica": "Indica", "Sativa": "Sativa", "Hybrid": "Hybrid",
             "Hybrid Indica": "Hybrid (Indica)", "Hybrid Sativa": "Hybrid (Sativa)",
             "Cbd": "CBD", "Cbg": "CBG"}
    strain_type = _smap.get(strain_raw, strain_raw)

    flavors  = [f["name"] for f in (strain_info.get("flavors")  or []) if f.get("name")]
    terpenes = [t["name"] for t in (strain_info.get("terpenes") or []) if t.get("name")]
    effects  = [e["name"] for e in (raw.get("effects")          or []) if e.get("name")]

    images = raw.get("images") or []
    image  = _str(images[0]) if images else ""

    description = _str(raw.get("description") or "")

    # Variants → price tiers, THC/CBD, stock status
    variants   = raw.get("variants") or []
    thc = cbd  = ""
    price = weight = ""
    price_tiers: dict = {}
    in_stock    = False

    for v in variants:
        avail    = (v.get("orderingAvailability") or {}).get("reason", "")
        v_stock  = avail == "Available" and (v.get("availableQty") or 0) > 0
        if v_stock:
            in_stock = True

        v_price = v.get("price") or 0
        v_name  = _str(v.get("name") or "")  # "4g", "3.5g", "1 Pack", etc.

        lab      = v.get("labTests") or {}
        thc_info = lab.get("thc") or {}
        cbd_info = lab.get("cbd") or {}

        if not thc and thc_info.get("value"):
            thc = _pct(str(thc_info["value"][0]))
        if not cbd and cbd_info.get("value"):
            cbd = _pct(str(cbd_info["value"][0]))

        if v_price:
            key = _WEIGHT_TO_TIER.get(v_name.lower().replace(" ", ""),
                                      v_name.lower().replace(" ", "_").replace(".", "_"))
            price_tiers[key] = _price(v_price)
            if not price or v_stock:
                price  = _price(v_price)
                weight = v_name

    return {
        "name": name, "brand": brand, "category": category,
        "strain_type": strain_type, "thc": thc, "cbd": cbd,
        "cbg": "", "cbn": "",
        "terpenes": terpenes, "effects": effects, "flavors": flavors,
        "weight": weight, "price": price, "price_tiers": price_tiers,
        "in_stock": in_stock, "image": image, "description": description,
    }


def _parse_sweed_response(data) -> list[dict]:
    """Extract products from a /_api/Products/GetProductList response."""
    candidates: list = []
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        for key in ("items", "products", "data", "result", "results"):
            v = data.get(key)
            if isinstance(v, list) and v:
                candidates = v
                break
            if isinstance(v, dict):
                for key2 in ("items", "products"):
                    v2 = v.get(key2)
                    if isinstance(v2, list) and v2:
                        candidates = v2
                        break
                if candidates:
                    break

    if not candidates or not isinstance(candidates[0], dict):
        return []
    if "variants" not in candidates[0] and "strain" not in candidates[0]:
        return []

    results = []
    for item in candidates:
        p = _normalize_sweed_product(item)
        if p and p["category"].lower() in TARGET_CATS:
            results.append(p)
    return results


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

SWEED_API_URL  = f"https://{STORE_DOMAIN}/_api/Products/GetProductList"
SWEED_API_PATH = "/_api/Products/GetProductList"  # relative for in-browser fetch

def _sweed_post_body(page_num: int, page_size: int) -> dict:
    return {
        "filters": {}, "page": page_num, "pageSize": page_size,
        "sortingMethodId": 7, "searchTerm": "", "platformOs": "web", "sourcePage": 1,
    }

def try_sweed_api() -> list[dict]:
    """
    POST to the confirmed Sweed storefront API.
    The WAF typically blocks server-side requests; Playwright is the real path.
    This runs first as a quick optimistic attempt.
    """
    session = requests.Session()
    session.headers.update({**HEADERS, "Accept": "application/json",
                            "Content-Type": "application/json"})
    for page_size in (500, 100, 24):
        try:
            r = session.post(SWEED_API_URL, json=_sweed_post_body(1, page_size), timeout=15)
            if r.status_code == 200:
                data  = r.json()
                found = _parse_sweed_response(data)
                if found:
                    log(f"Sweed direct API (pageSize={page_size}): {len(found)} products")
                    # If we got a full page, keep paginating
                    if len(found) >= page_size:
                        found = _sweed_paginate_requests(session, page_size, found)
                    return found
        except Exception:
            pass
    return []

def _sweed_paginate_requests(session, page_size: int, first_page: list) -> list[dict]:
    """Continue paginating via direct HTTP after a successful first page."""
    all_products = {product_key(p): p for p in first_page}
    page_num = 2
    while True:
        try:
            r = session.post(SWEED_API_URL, json=_sweed_post_body(page_num, page_size), timeout=15)
            if r.status_code != 200:
                break
            found = _parse_sweed_response(r.json())
            if not found:
                break
            for p in found:
                all_products[product_key(p)] = p
            log(f"  Sweed API page {page_num}: {len(found)} products")
            if len(found) < page_size:
                break
            page_num += 1
        except Exception:
            break
    return list(all_products.values())


def fetch_all_sweed_via_browser(page) -> list[dict]:
    """
    POST to /_api/Products/GetProductList using Playwright's request API.
    page.context.request shares the browser's cookies (set by visiting the menu),
    so this bypasses the WAF cleanly without any JS embedding.
    """
    import json as _json

    ctx_request = page.context.request

    def _ctx_post(page_size: int, page_num: int) -> list[dict]:
        try:
            resp = ctx_request.post(
                SWEED_API_URL,
                data=_json.dumps(_sweed_post_body(page_num, page_size)),
                headers={"Content-Type": "application/json",
                         "Accept": "application/json",
                         "Referer": MENU_URL},
            )
            log(f"  API POST page={page_num} size={page_size} → HTTP {resp.status}")
            if not resp.ok:
                return []
            data = resp.json()
            return _parse_sweed_response(data)
        except Exception as e:
            log(f"  API POST error (page={page_num}, size={page_size}): {e}")
            return []

    all_products: dict[str, dict] = {}

    # Try large pageSize first — get everything in one shot
    for page_size in (500, 200, 100):
        products = _ctx_post(page_size, 1)
        if products:
            for p in products:
                all_products[product_key(p)] = p
            log(f"Sweed browser API (pageSize={page_size}): {len(products)} products")
            if len(products) < page_size:
                log(f"Got all products in one call ({len(all_products)} total)")
                return list(all_products.values())
            # Server capped us — paginate with this size
            log(f"Hit cap at pageSize={page_size}, paginating...")
            page_num = 2
            while True:
                found = _ctx_post(page_size, page_num)
                if not found:
                    break
                for p in found:
                    all_products[product_key(p)] = p
                log(f"  page {page_num}: {len(found)} (total: {len(all_products)})")
                if len(found) < page_size:
                    break
                page_num += 1
            return list(all_products.values())

    return []  # all attempts failed


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


# ── Strategy 3: Playwright — scrapes every category page + paginates ─────────

CARD_SELS = (
    "[data-testid='product-card']", "[data-testid='menu-product-card']",
    ".product-card", "[class*='ProductCard']", "[class*='product_card']",
    "[class*='MenuCard']", ".menu-item",
)

# Sweed POS: map href slug prefixes to strain types
_HREF_STRAIN = {"hybrid": "Hybrid", "indica": "Indica", "sativa": "Sativa",
                "cbd": "CBD", "cbg": "CBG"}


def _dom_scrape_page(page) -> list[dict]:
    """Extract all product cards visible on the current Sweed POS page.

    Sweed renders each product as <a id="product-XXXXX" aria-label="Name, Cat. Wt - $Price">.
    Class names are CSS-module hashes and change on every deploy, so we rely on:
      - aria-label  → name, category, weight, price
      - href slug   → category + strain type
      - inner_text  → THC/CBD percentages via regex
      - "X by Brand" text pattern → brand name
    """
    found = []

    # Primary: Sweed product link elements
    cards = page.query_selector_all("[id^='product-']")

    if not cards:
        # Generic fallback for other platforms
        for sel in CARD_SELS:
            cards = page.query_selector_all(sel)
            if cards:
                break

    for card in cards:
        p: dict = {}

        # aria-label="Cap Junky Flower, Flower. 4g - $55.00"
        aria = card.get_attribute("aria-label") or ""
        aria_m = re.match(r'^(.+?),\s*(.+?)\.\s*([^\s]+(?:\s+[^\s-][^\s]*)?)\s+-\s+(\$[\d.]+)', aria)
        if aria_m:
            p["name"]     = aria_m.group(1).strip()
            p["category"] = aria_m.group(2).strip()
            p["weight"]   = aria_m.group(3).strip()
            p["price"]    = aria_m.group(4).strip()

        # href="/south-metro/menu/flower-5221/hybrid-cap-junky-flower-4g-383073"
        href = card.get_attribute("href") or ""
        href_m = re.search(r'/menu/([a-z-]+?)-\d+/([a-z]+)-', href)
        if href_m:
            if not p.get("category"):
                p["category"] = href_m.group(1).replace("-", " ").title()
            strain_slug = href_m.group(2)
            if strain_slug in _HREF_STRAIN:
                p["strain_type"] = _HREF_STRAIN[strain_slug]

        # Full visible text for regex extraction (resilient to class name changes)
        text = card.inner_text()

        # "THC: 29%"  /  "CBD: 0.08%"
        thc_m = re.search(r'THC:\s*([\d.]+\s*%)', text)
        cbd_m = re.search(r'CBD:\s*([\d.]+\s*%)', text)
        if thc_m: p["thc"] = thc_m.group(1).replace(" ", "")
        if cbd_m: p["cbd"] = cbd_m.group(1).replace(" ", "")

        # Strain type from visible text if href didn't give it
        if not p.get("strain_type"):
            for s in ("Hybrid (Indica)", "Hybrid (Sativa)", "Hybrid", "Indica", "Sativa", "CBD"):
                if s in text:
                    p["strain_type"] = s
                    break

        # "Flower by Campfire Cannabis" → brand = "Campfire Cannabis"
        brand_m = re.search(r'(?:Flower|Pre-?Roll|Vapes?|Edible|Concentrate)\s+by\s+([^\n]+)', text)
        if brand_m:
            p["brand"] = brand_m.group(1).strip()

        # Name from h2 if aria-label parse failed
        if not p.get("name"):
            el = card.query_selector("h2")
            if el: p["name"] = el.inner_text().strip()

        # Image
        img = card.query_selector("img")
        if img:
            p["image"] = (img.get_attribute("src") or
                          img.get_attribute("data-src") or
                          img.get_attribute("data-lazy-src") or "")

        if not p.get("name"):
            continue

        raw = normalize(p)
        if not raw["category"]:    raw["category"]    = _guess_category(raw["name"])
        if not raw["strain_type"]: raw["strain_type"] = _guess_strain(raw["name"])
        raw["name"] = _clean_name(raw["name"])
        if raw["category"].lower() in TARGET_CATS:
            found.append(raw)

    return found


def _load_page(page, url, label=""):
    """Navigate and scroll to fully load a menu page."""
    from playwright.sync_api import TimeoutError as PwTimeout
    log(f"  → {label or url}")
    try:
        page.goto(url, wait_until="networkidle", timeout=45000)
    except PwTimeout:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(6)
        except Exception:
            return
    # Scroll down to trigger infinite-scroll / lazy loads
    for _ in range(8):
        prev_h = page.evaluate("document.body.scrollHeight")
        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        time.sleep(1.0)
        new_h = page.evaluate("document.body.scrollHeight")
        if new_h == prev_h:
            break   # no more content loaded
    page.evaluate("window.scrollTo(0,0)")
    time.sleep(0.5)


def try_playwright() -> list[dict]:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    all_products: dict[str, dict] = {}   # keyed by product_key to deduplicate
    captured: list[tuple[str, dict]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = ctx.new_page()

        def on_response(resp):
            ct = resp.headers.get("content-type", "")
            if "json" in ct:
                try:
                    body = resp.json()
                    captured.append((resp.url, body))
                except Exception:
                    pass

        page.on("response", on_response)

        # ── Pass 0: load menu page then call API directly from browser context ─
        # This bypasses the WAF (browser has session cookies) and fetches ALL
        # products in one shot using the confirmed POST endpoint with pagination.
        log("Playwright: loading menu to establish session...")
        _load_page(page, MENU_URL, "menu (session init)")

        log("Playwright: fetching all products via browser API call...")
        api_products = fetch_all_sweed_via_browser(page)
        if api_products:
            for p in api_products:
                all_products[product_key(p)] = p
            log(f"Browser API: {len(all_products)} total products — skipping DOM scrape")
        else:
            # ── Pass 1: fall back to intercepting per-page XHR + DOM scraping ─
            log("Browser API failed — falling back to page-by-page scraping...")
            for url in PAGINATED_URLS:
                captured.clear()
                _load_page(page, url, f"page {PAGINATED_URLS.index(url)+1}")

                captured.sort(key=lambda x: len(str(x[1])), reverse=True)
                found_json = []
                for api_url, body in captured:
                    found_json = _parse_sweed_response(body) or find_products(body)
                    if found_json:
                        log(f"    JSON: {len(found_json)} products from {api_url[:70]}")
                        break

                items = found_json or _dom_scrape_page(page)
                if not items:
                    log("    No products on page — stopping pagination")
                    break
                for p in items:
                    all_products[product_key(p)] = p
                log(f"    Got {len(items)} products (total so far: {len(all_products)})")

            # ── Pass 2: individual category URLs ──────────────────────────────
            log("Playwright: scraping category-specific pages...")
            for url in CATEGORY_URLS:
                captured.clear()
                _load_page(page, url)

                found_json = []
                for api_url, body in captured:
                    found_json = _parse_sweed_response(body) or find_products(body)
                    if found_json:
                        break

                items = found_json or _dom_scrape_page(page)
                if items:
                    before = len(all_products)
                    for p in items:
                        all_products[product_key(p)] = p
                    new = len(all_products) - before
                    if new:
                        log(f"    +{new} new products from {url}")

        # ── Pass 3: try Algolia from rendered source ───────────────────────────
        if not all_products:
            html  = page.content()
            found = try_algolia(html)
            for p in found:
                all_products[product_key(p)] = p

        browser.close()

    products = list(all_products.values())
    log(f"Playwright total: {len(products)} unique products across all pages")
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

    # Keep only the 4 target categories
    products = [p for p in products if p.get("category","").lower() in TARGET_CATS]
    log(f"After category filter: {len(products)} products")

    db = load_db()
    db = merge(db, products)
    save_db(db)
    in_stock = sum(1 for p in db["products"].values() if p.get("in_stock", True))
    log(f"Done — {len(products)} scraped, {in_stock} total in stock")
    return db


if __name__ == "__main__":
    run()
