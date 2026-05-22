"""
Menu scraper for MN Legit Cannabis – South Metro (Sweed POS platform).

Strategy (in order):
  1. Sweed /_api   – direct call to /_api/Products/GetProductList (richest data)
  2. Sweed API     – legacy guessed endpoints
  3. Algolia API   – extract app/key from page JS
  4. Playwright    – full browser with JSON interception + DOM fallback
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

# Sweed category IDs for the 4 target categories (avoids scraping full menu)
TARGET_CAT_IDS = [5221, 5222, 5223, 5684]  # Flower, Pre-Rolls, Edibles, Vapes

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
    for key in ("image_url", "image", "photo", "thumbnail", "featured_image", "imageUrl", "thumbnailUrl"):
        v = raw.get(key)
        if v: return _str(v)
    photos = raw.get("photos") or raw.get("images") or []
    if isinstance(photos, list) and photos:
        p0 = photos[0]
        if isinstance(p0, dict):
            return _str(p0.get("original_url") or p0.get("url") or p0.get("thumbnail_url") or "")
        return _str(p0)
    return ""

def _nested_cannabinoid(raw: dict, key: str) -> str:
    """Extract from nested structures like cannabinoids:{thc:{value:22.4}} or lab_results:{thc:'22.4%'}."""
    for parent in ("cannabinoids", "lab_results", "test_results", "potency"):
        obj = raw.get(parent)
        if isinstance(obj, dict):
            v = obj.get(key) or obj.get(key.upper())
            if v:
                if isinstance(v, dict):
                    return str(v.get("value") or v.get("amount") or v.get("percentage") or "")
                return str(v)
    return ""

def normalize(raw: dict) -> dict:
    name     = _str(raw.get("name") or raw.get("title") or raw.get("product_name") or "Unknown")
    brand    = _str(raw.get("brand") or raw.get("brand_name") or raw.get("brandName")
                   or raw.get("manufacturer") or raw.get("producer") or raw.get("vendor")
                   or raw.get("supplier") or "")
    category = _str(raw.get("category") or raw.get("category_name") or raw.get("categoryName")
                   or raw.get("product_type") or raw.get("productType")
                   or raw.get("root_type") or raw.get("type") or "")

    # strain_type: try every known field name across Sweed, Jane, Leafly, etc.
    strain = _str(
        raw.get("strain_type") or raw.get("strainType")
        or raw.get("cannabis_type") or raw.get("cannabisType")
        or raw.get("lineage") or raw.get("lineage_type") or raw.get("lineageType")
        or raw.get("kind") or raw.get("classification")
        or raw.get("type_name") or raw.get("typeName") or ""
    ).title()
    _map = {
        "Indica":"Indica","Sativa":"Sativa","Hybrid":"Hybrid",
        "Hybrid Indica":"Hybrid (Indica)","Hybrid Sativa":"Hybrid (Sativa)",
        "Indica-Dominant Hybrid":"Hybrid (Indica)","Sativa-Dominant Hybrid":"Hybrid (Sativa)",
        "Cbd":"CBD","Cbg":"CBG","Not Applicable":"","N/A":"","":"",
    }
    strain = _map.get(strain, strain)

    thc = _pct(
        raw.get("percent_thc") or raw.get("thc") or raw.get("thc_content") or raw.get("thcContent")
        or raw.get("thc_percentage") or raw.get("thcPercentage") or raw.get("thc_percent")
        or _nested_cannabinoid(raw, "thc") or ""
    )
    cbd = _pct(
        raw.get("percent_cbd") or raw.get("cbd") or raw.get("cbd_content") or raw.get("cbdContent")
        or raw.get("cbd_percentage") or raw.get("cbdPercentage")
        or _nested_cannabinoid(raw, "cbd") or ""
    )
    cbg = _pct(raw.get("percent_cbg") or raw.get("cbg") or _nested_cannabinoid(raw, "cbg") or "")
    cbn = _pct(raw.get("percent_cbn") or raw.get("cbn") or _nested_cannabinoid(raw, "cbn") or "")

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


# ── Sweed /_api/Products/GetProductList normalizer + fetcher ─────────────────

SWEED_CAT_MAP = {
    "pre-rolls":"Pre-Roll","pre-roll":"Pre-Roll","preroll":"Pre-Roll",
    "flower":"Flower",
    "vapes":"Vapes","vape":"Vapes","disposables":"Vapes","cartridges":"Vapes",
    "edibles":"Edibles","edible":"Edibles",
}
SWEED_STRAIN_MAP = {
    "indica dominant":"Indica","indica-dominant":"Indica",
    "sativa dominant":"Sativa","sativa-dominant":"Sativa",
    "balanced hybrid":"Hybrid","hybrid":"Hybrid",
    "indica":"Indica","sativa":"Sativa","cbd":"CBD","cbg":"CBG",
}
SWEED_WEIGHT_TIERS = {
    "1":"gram","1.0":"gram",
    "2":"two_gram","2.0":"two_gram",
    "3.5":"eighth",
    "7":"quarter","7.0":"quarter",
    "14":"half_ounce","14.0":"half_ounce",
    "28":"ounce","28.0":"ounce",
}

def _lab_pct(lab: dict, key: str) -> str:
    obj = (lab or {}).get(key)
    if not isinstance(obj, dict): return ""
    vals = obj.get("value") or []
    unit = obj.get("unitAbbr", "")
    if vals:
        return f"{vals[0]:.1f}%" if unit == "%" else f"{vals[0]}{unit}"
    return ""

def normalize_sweed_product(raw: dict) -> dict:
    name = _str(raw.get("name", "")).rstrip("-").strip()

    cat_obj   = raw.get("category") or {}
    cat_raw   = _str(cat_obj.get("name") if isinstance(cat_obj, dict) else "").lower().strip()
    category  = SWEED_CAT_MAP.get(cat_raw, cat_raw.title())

    brand_obj = raw.get("brand") or {}
    brand     = _str(brand_obj.get("name") if isinstance(brand_obj, dict) else "")

    strain_obj  = raw.get("strain") or {}
    prev_obj    = strain_obj.get("prevalence") or {}
    strain_raw  = _str(prev_obj.get("name") if isinstance(prev_obj, dict) else "").lower()
    strain_type = SWEED_STRAIN_MAP.get(strain_raw, "")
    if not strain_type:
        for t in (raw.get("tags") or []):
            tk = _str(t.get("name") if isinstance(t, dict) else "").lower()
            if tk in SWEED_STRAIN_MAP:
                strain_type = SWEED_STRAIN_MAP[tk]
                break

    terpenes = [t["name"] for t in (strain_obj.get("terpenes") or []) if isinstance(t, dict) and t.get("name")]
    flavors  = [f["name"] for f in (strain_obj.get("flavors")  or []) if isinstance(f, dict) and f.get("name")]
    effects  = [e["name"] for e in (raw.get("effects")         or []) if isinstance(e, dict) and e.get("name")]

    images = raw.get("images") or []
    image  = _str(images[0]) if images else ""

    variants  = [v for v in (raw.get("variants") or []) if isinstance(v, dict)]
    thc = cbd = ""
    weight = price = ""
    price_tiers: dict = {}
    in_stock = False

    for v in variants:
        qty    = v.get("availableQty") or 0
        reason = ((v.get("orderingAvailability") or {}).get("reason") or "")
        if qty > 0 or reason == "Available":
            in_stock = True

        lab = v.get("labTests") or {}
        if lab and not thc:
            thc = _lab_pct(lab, "thc")
            cbd = _lab_pct(lab, "cbd")

        us  = v.get("unitSize") or {}
        val = us.get("value")
        abbr = (us.get("unitAbbr") or "").upper()
        if val is not None:
            w_str = f"{val:g}{abbr}"
            if not weight:
                weight = w_str
            tier_key = SWEED_WEIGHT_TIERS.get(str(val)) or SWEED_WEIGHT_TIERS.get(f"{val:.1f}")
            if not tier_key:
                tier_key = re.sub(r"[^a-z0-9]", "_", (v.get("name") or w_str).lower())
            if v.get("price"):
                price_tiers[tier_key] = f"${v['price']:.2f}"
        elif v.get("price") and not price:
            price = f"${v['price']:.2f}"

    if len(price_tiers) == 1:
        price = list(price_tiers.values())[0]
        price_tiers = {}

    return {
        "name": name, "brand": brand, "category": category,
        "strain_type": strain_type, "thc": thc, "cbd": cbd, "cbg": "", "cbn": "",
        "terpenes": terpenes, "effects": effects, "flavors": flavors,
        "weight": weight, "price": price, "price_tiers": price_tiers,
        "in_stock": in_stock, "image": image,
        "description": _str(raw.get("description", "")),
    }


def try_sweed_list_api() -> list[dict]:
    """Call /_api/Products/GetProductList directly — returns brand, strain, THC, prices."""
    base_url = f"https://{STORE_DOMAIN}/_api/Products/GetProductList"
    session  = requests.Session()
    session.headers.update({
        **HEADERS,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": MENU_URL,
        "Origin": f"https://{STORE_DOMAIN}",
    })

    all_products: list[dict] = []
    page = 1
    PAGE_SIZE = 100

    while True:
        params = {"page": page, "pageSize": PAGE_SIZE}
        try:
            r = session.get(base_url, params=params, timeout=15)
            if r.status_code not in (200, 201):
                r = session.post(base_url, json=params, timeout=15)
            if r.status_code not in (200, 201):
                log(f"  Sweed List API page {page}: HTTP {r.status_code}")
                break
            data  = r.json()
            _save_debug(f"{base_url}?page={page}", data)
            items = data.get("list") or []
            total = data.get("total") or 0
            if not items:
                break
            log(f"  Sweed List API page {page}: {len(items)} items (total={total})")
            all_products.extend(normalize_sweed_product(i) for i in items)
            if len(all_products) >= total or len(items) < PAGE_SIZE:
                break
            page += 1
        except Exception as e:
            log(f"  Sweed List API error page {page}: {e}")
            break

    if all_products:
        log(f"Sweed List API total: {len(all_products)} products")
    return all_products


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
            log(f"  Sweed API {r.status_code}: {url}")
            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    data = {"raw_text": r.text[:500]}
                _save_debug(url, data)
                found = find_products(data)
                if found:
                    log(f"Sweed API ({url}): {len(found)} products")
                    return found
                else:
                    log(f"  → 200 but find_products found nothing. Top keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
        except Exception as e:
            log(f"  Sweed API error {url}: {e}")
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
        _save_debug(url, data)
        found = find_products(data)
        if found:
            log(f"Algolia: {len(found)} products")
            if found:
                sample = found[0]
                log(f"  Sample fields: {[k for k,v in sample.items() if v]}")
            return found
        else:
            log(f"  Algolia 200 but no products found. Top keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
    except Exception as e:
        log(f"Algolia query failed: {e}")
    return []


# ── Sweed per-product detail enrichment ──────────────────────────────────────

DEBUG_FILE  = Path(__file__).parent / "docs" / "sweed_raw.json"
_debug_blobs: list = []

def _save_debug(url: str, data):
    """Accumulate raw API responses; flush to DEBUG_FILE at end of run."""
    _debug_blobs.append({"url": url, "data": data})
    try:
        DEBUG_FILE.write_text(json.dumps(_debug_blobs, indent=2, default=str))
    except Exception:
        pass

def sweed_product_id(image_url: str) -> str:
    """Extract numeric Sweed product ID from CDN image URL."""
    m = re.search(r'/(\d+)_[a-f0-9-]+\.(png|jpg|avif|webp)', image_url or "")
    return m.group(1) if m else ""

def try_sweed_detail(pid: str, session: requests.Session) -> dict:
    """Try to fetch full product record from Sweed's storefront API using its numeric ID."""
    endpoints = [
        f"https://{STORE_DOMAIN}/api/products/{pid}",
        f"https://{STORE_DOMAIN}/{STORE_SLUG}/api/products/{pid}",
        f"https://{STORE_DOMAIN}/api/menu-products/{pid}",
        f"https://prime.sweedpos.com/api/v1/products/{pid}",
        f"https://prime.sweedpos.com/api/products/{pid}",
        f"https://api.sweedpos.com/v1/products/{pid}",
        f"https://api.sweedpos.com/v2/products/{pid}",
    ]
    for url in endpoints:
        try:
            r = session.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and (data.get("name") or data.get("id")):
                    log(f"    Sweed detail API hit: {url}")
                    return data
        except Exception:
            pass
    return {}

def enrich_products(products: list[dict]) -> list[dict]:
    """Attempt to enrich each product with full details from Sweed's per-product API."""
    session = requests.Session()
    session.headers.update({**HEADERS, "Accept": "application/json"})
    enriched_count = 0
    result = []
    for p in products:
        pid = sweed_product_id(p.get("image", ""))
        if pid:
            raw = try_sweed_detail(pid, session)
            if raw:
                merged = normalize(raw)
                # Preserve fields we already have
                merged["image"]      = p.get("image") or merged.get("image", "")
                merged["first_seen"] = p.get("first_seen", "")
                merged["last_seen"]  = p.get("last_seen", "")
                merged["in_stock"]   = p.get("in_stock", True)
                if not merged.get("category"):
                    merged["category"] = p.get("category", "")
                enriched_count += 1
                result.append(merged)
                continue
        result.append(p)
    if enriched_count:
        log(f"Enriched {enriched_count}/{len(products)} products via Sweed detail API")
    return result


# ── Strategy 3: Playwright — scrapes every category page + paginates ─────────

CARD_SELS = (
    "[data-testid='product-card']", "[data-testid='menu-product-card']",
    ".product-card", "[class*='ProductCard']", "[class*='product_card']",
    "[class*='MenuCard']", ".menu-item",
)


def _dom_scrape_page(page) -> list[dict]:
    """Extract all product cards visible on the current page."""
    found = []
    for sel in CARD_SELS:
        cards = page.query_selector_all(sel)
        if not cards:
            continue
        for card in cards:
            p: dict = {}
            for ns in ["h2", "h3", "[class*='name']", "[class*='title']"]:
                el = card.query_selector(ns)
                if el: p["name"] = el.inner_text().strip(); break
            for bs in ["[class*='brand']"]:
                el = card.query_selector(bs)
                if el: p["brand"] = el.inner_text().strip(); break
            for ss in ["[class*='strain']", "[class*='lineage']", "[class*='cannabis-type']",
                       "[class*='cannabisType']", "[data-strain]", "[data-lineage]"]:
                el = card.query_selector(ss)
                if el:
                    p["strain_type"] = el.inner_text().strip()
                    break
            for cs in ["[class*='category']", "[class*='product-type']", "[data-category]"]:
                el = card.query_selector(cs)
                if el: p["category"] = el.inner_text().strip(); break
            for ps in ["[class*='price']", "[class*='Price']", "[data-price]"]:
                el = card.query_selector(ps)
                if el: p["price"] = el.inner_text().strip(); break
            for ts in ["[class*='thc']", "[class*='THC']", "[class*='potency']",
                       "[class*='Potency']", "[data-thc]"]:
                el = card.query_selector(ts)
                if el: p["thc"] = el.inner_text().strip(); break
            for cs2 in ["[class*='cbd']", "[class*='CBD']", "[data-cbd]"]:
                el = card.query_selector(cs2)
                if el: p["cbd"] = el.inner_text().strip(); break
            for ws in ["[class*='weight']", "[class*='size']", "[class*='net-weight']", "[data-weight]"]:
                el = card.query_selector(ws)
                if el: p["weight"] = el.inner_text().strip(); break
            img = card.query_selector("img")
            if img:
                p["image"] = (img.get_attribute("src") or
                              img.get_attribute("data-src") or
                              img.get_attribute("data-lazy-src") or "")
            if p.get("name"):
                raw = normalize(p)
                if not raw["category"]:    raw["category"]    = _guess_category(raw["name"])
                if not raw["strain_type"]: raw["strain_type"] = _guess_strain(raw["name"])
                raw["name"] = _clean_name(raw["name"])
                # Only keep target categories
                if raw["category"].lower() in TARGET_CATS:
                    found.append(raw)
        if found:
            break
    return found


def _load_page(page, url, label=""):
    """Navigate and scroll to fully load a menu page."""
    try:
        from playwright.sync_api import TimeoutError as PwTimeout
    except ImportError:
        return
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
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    except ImportError:
        log("Playwright not installed — skipping browser fallback")
        return []

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

        # ── Pass 1: paginated base menu pages ─────────────────────────────────
        log("Playwright: scraping paginated menu pages...")
        for url in PAGINATED_URLS:
            captured.clear()
            _load_page(page, url, f"page {PAGINATED_URLS.index(url)+1}")

            # Try JSON first
            captured.sort(key=lambda x: len(str(x[1])), reverse=True)
            found_json = []
            for api_url, body in captured:
                found_json = find_products(body)
                if found_json:
                    log(f"    JSON: {len(found_json)} products from {api_url[:70]}")
                    break

            items = found_json or _dom_scrape_page(page)
            if not items:
                log(f"    No products on page — stopping pagination")
                break
            for p in items:
                all_products[product_key(p)] = p
            log(f"    Got {len(items)} products (total so far: {len(all_products)})")

        # ── Pass 2: individual category URLs ──────────────────────────────────
        log("Playwright: scraping category-specific pages...")
        for url in CATEGORY_URLS:
            captured.clear()
            _load_page(page, url)

            found_json = []
            for api_url, body in captured:
                found_json = find_products(body)
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

        # ── Pass 3: __NEXT_DATA__ embedded JSON (Next.js SSR) ─────────────────
        if not all_products:
            html = page.content()
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html, re.DOTALL)
            if m:
                try:
                    next_data = json.loads(m.group(1))
                    _save_debug("__NEXT_DATA__", next_data)
                    found = find_products(next_data)
                    if found:
                        log(f"__NEXT_DATA__: {len(found)} products")
                        for p in found:
                            all_products[product_key(p)] = p
                except Exception as e:
                    log(f"__NEXT_DATA__ parse error: {e}")

        # ── Pass 4: window.__STORE_DATA__ / hydration globals ─────────────────
        if not all_products:
            for var in ("__NEXT_DATA__", "__STORE_STATE__", "__INITIAL_STATE__",
                        "__PRELOADED_STATE__", "__APP_DATA__"):
                try:
                    val = page.evaluate(f"() => window.{var}")
                    if val:
                        _save_debug(f"window.{var}", val)
                        found = find_products(val)
                        if found:
                            log(f"window.{var}: {len(found)} products")
                            for p in found:
                                all_products[product_key(p)] = p
                            break
                except Exception:
                    pass

        # ── Pass 5: try Algolia from rendered source ───────────────────────────
        if not all_products:
            found = try_algolia(html)
            for p in found:
                all_products[product_key(p)] = p

        # Save largest captured JSON blobs + page HTML snippet for inspection
        captured.sort(key=lambda x: len(str(x[1])), reverse=True)
        for u, d in captured[:5]:
            _save_debug(u, d)
        # Also save a snippet of the raw page HTML for selector debugging
        try:
            snippet = page.content()[:8000]
            _save_debug("__PAGE_HTML_SNIPPET__", {"html": snippet})
        except Exception:
            pass
        log(f"Raw API responses saved → {DEBUG_FILE}  ({len(captured)} blobs captured)")

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

    log("Trying Sweed /_api/Products/GetProductList...")
    products = try_sweed_list_api()

    if not products:
        log("Sweed List API found nothing — trying legacy Sweed endpoints...")
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

    # Attempt per-product enrichment via Sweed detail API
    log("Trying per-product detail enrichment...")
    products = enrich_products(products)

    db = load_db()
    db = merge(db, products)
    save_db(db)
    in_stock = sum(1 for p in db["products"].values() if p.get("in_stock", True))
    log(f"Done — {len(products)} scraped, {in_stock} total in stock")
    return db


if __name__ == "__main__":
    run()
