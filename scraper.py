"""
Menu scraper for MN Legit Cannabis – South Metro (Sweed POS platform).

Strategy (in order):
  1. Direct API  – POST to /_api/Products/GetProductList per category (fast; WAF often blocks)
  2. Browser API – same POST via Playwright's request context (shares session cookies, bypasses WAF)
  3. DOM fallback – parse visible product cards if both API paths fail
"""

import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

STORE_SLUG   = "south-metro"
STORE_DOMAIN = "shop.mnlegitcannabis.com"
MENU_URL     = f"https://{STORE_DOMAIN}/{STORE_SLUG}/menu"
DATA_FILE    = Path(__file__).parent / "docs" / "products.json"
CST          = timezone(timedelta(hours=-6))

TARGET_CATS  = ("flower", "pre-roll", "vapes", "edibles")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"https://{STORE_DOMAIN}/",
}


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S CST')}] {msg}", flush=True)

_debug_log: list = []

def _write_debug(cat_name: str, page_num: int, raw):
    """Append response structure info to docs/debug_api.json for inspection."""
    entry = {"category": cat_name, "page": page_num}
    if isinstance(raw, list):
        entry["top_level"] = f"list[{len(raw)}]"
        entry["first_item_keys"] = list(raw[0].keys()) if raw else []
    elif isinstance(raw, dict):
        entry["top_level"] = "dict"
        entry["keys"] = list(raw.keys())
        for k, v in raw.items():
            if isinstance(v, str):
                entry[k] = v[:300]  # capture string values (errors, etc.)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                entry["list_key"] = k
                entry["list_len"] = len(v)
                entry["item_keys"] = list(v[0].keys())
                break
            elif isinstance(v, dict):
                for k2, v2 in v.items():
                    if isinstance(v2, list) and v2 and isinstance(v2[0], dict):
                        entry["nested_list_key"] = f"{k}.{k2}"
                        entry["list_len"] = len(v2)
                        entry["item_keys"] = list(v2[0].keys())
                        break
    else:
        entry["top_level"] = type(raw).__name__
    _debug_log.append(entry)
    debug_path = Path(__file__).parent / "docs" / "debug_api.json"
    with open(debug_path, "w") as f:
        json.dump(_debug_log, f, indent=2)


# ── Utility formatters ────────────────────────────────────────────────────────

def _pct(v) -> str:
    if not v: return ""
    s = str(v).replace("%", "").strip()
    try:    return f"{float(s):.1f}%"
    except: return str(v).strip()

def _str(v) -> str:
    return "" if v is None else str(v).strip()

def _price(v) -> str:
    if not v: return ""
    if isinstance(v, (int, float)): return f"${v:.2f}"
    return str(v).strip()

def _lst(v) -> list:
    if isinstance(v, list): return [str(i).strip() for i in v if i]
    if isinstance(v, str) and v: return [v]
    return []


# ── Sweed POS API normalizer ──────────────────────────────────────────────────
# Endpoint: https://shop.mnlegitcannabis.com/_api/Products/GetProductList
# Confirmed category IDs from browser Network tab

SWEED_API_URL = f"https://{STORE_DOMAIN}/_api/Products/GetProductList"

SWEED_CATEGORIES = {
    "flower":   5221,
    "pre-roll": 5222,
    "edibles":  5223,
    "vapes":    5684,
}

_WEIGHT_TO_TIER = {
    "1g": "gram", "2g": "two_gram", "3.5g": "eighth",
    "7g": "quarter", "14g": "half_ounce", "28g": "ounce",
}

_STRAIN_MAP = {
    "Indica": "Indica", "Sativa": "Sativa", "Hybrid": "Hybrid",
    "Hybrid Indica": "Hybrid (Indica)", "Hybrid Sativa": "Hybrid (Sativa)",
    "Indica Dominant": "Hybrid (Indica)", "Sativa Dominant": "Hybrid (Sativa)",
    "Indica-Dominant": "Hybrid (Indica)", "Sativa-Dominant": "Hybrid (Sativa)",
    "Cbd": "CBD", "Cbg": "CBG",
}

_CAT_NORM = {
    "flower": "flower",
    "pre-roll": "pre-roll", "pre-rolls": "pre-roll", "preroll": "pre-roll",
    "prerolls": "pre-roll", "pre roll": "pre-roll", "pre rolls": "pre-roll",
    "vape": "vapes", "vapes": "vapes", "vape cartridge": "vapes",
    "vape cartridges": "vapes", "cartridge": "vapes", "cartridges": "vapes",
    "disposable": "vapes", "disposables": "vapes",
    "edible": "edibles", "edibles": "edibles",
}

def _norm_category(raw_cat: str) -> str:
    return _CAT_NORM.get(raw_cat.lower().strip(), raw_cat)


def _sweed_post_body(page_num: int, page_size: int, category_id: int) -> dict:
    return {
        "filters": {"category": [category_id]},
        "page": page_num, "pageSize": page_size,
        "sortingMethodId": 7, "searchTerm": "",
        "platformOs": "web", "sourcePage": 1,
    }


def _normalize_sweed_product(raw: dict) -> dict | None:
    name = _str(raw.get("name") or "")
    if not name:
        return None

    brand    = _str((raw.get("brand") or {}).get("name") or "")
    category = _norm_category(_str((raw.get("category") or {}).get("name") or
                                   (raw.get("productType") or {}).get("name") or ""))

    strain_info = raw.get("strain") or {}
    strain_raw  = _str((strain_info.get("prevalence") or {}).get("name") or "").title()
    strain_type = _STRAIN_MAP.get(strain_raw, strain_raw)
    if not strain_type:
        # fall back to tags array (e.g. [{"name": "Indica"}, {"name": "Hybrid"}])
        tag_names = [t["name"] for t in (raw.get("tags") or []) if t.get("name")]
        for tag in tag_names:
            if tag.title() in _STRAIN_MAP:
                strain_type = _STRAIN_MAP[tag.title()]
                break

    terpenes = [t["name"] for t in (strain_info.get("terpenes") or []) if t.get("name")]
    flavors  = [f["name"] for f in (strain_info.get("flavors")  or []) if f.get("name")]
    effects  = [e["name"] for e in (raw.get("effects")          or []) if e.get("name")]

    images = raw.get("images") or []
    image  = _str(images[0]) if images else ""

    variants    = raw.get("variants") or []
    thc = cbd   = ""
    price = weight = ""
    price_tiers: dict = {}
    in_stock    = False

    for v in variants:
        avail   = (v.get("orderingAvailability") or {}).get("reason", "")
        v_stock = avail == "Available" and (v.get("availableQty") or 0) > 0
        if v_stock:
            in_stock = True

        v_price = v.get("price") or 0
        v_name  = _str(v.get("name") or "")

        lab = v.get("labTests") or {}
        if not thc and (lab.get("thc") or {}).get("value"):
            thc = _pct(str(lab["thc"]["value"][0]))
        if not cbd and (lab.get("cbd") or {}).get("value"):
            cbd = _pct(str(lab["cbd"]["value"][0]))

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
        "in_stock": in_stock, "image": image,
        "description": _str(raw.get("description") or ""),
    }


def _parse_sweed_response(data, force_category: str = "") -> list[dict]:
    """Extract and normalize products from a GetProductList API response.

    force_category: when set, override the API's category name with this value
    (avoids filtering failures when the API uses unexpected category names).
    """
    candidates: list = []
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        for key in ("items", "products", "list", "data", "result", "results"):
            v = data.get(key)
            if isinstance(v, list) and v:
                candidates = v
                break
            if isinstance(v, dict):
                for key2 in ("items", "products", "list"):
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
        if not p:
            continue
        if force_category:
            p["category"] = force_category
        if p["category"].lower() in TARGET_CATS:
            results.append(p)
    return results


# ── Strategy 1: Direct HTTP POST (fast, WAF often blocks outside browser) ─────

def try_sweed_api() -> list[dict]:
    session = requests.Session()
    session.headers.update({**HEADERS, "Accept": "application/json",
                             "Content-Type": "application/json"})
    all_products: dict[str, dict] = {}
    any_success = False

    for cat_name, cat_id in SWEED_CATEGORIES.items():
        page_num = 1
        while True:
            try:
                r = session.post(SWEED_API_URL,
                                 json=_sweed_post_body(page_num, 24, cat_id),
                                 timeout=15)
                if r.status_code != 200:
                    break
                found = _parse_sweed_response(r.json(), force_category=cat_name)
                if not found:
                    break
                any_success = True
                for p in found:
                    all_products[product_key(p)] = p
                log(f"Direct API [{cat_name}] page {page_num}: {len(found)} products")
                if len(found) < 24:
                    break
                page_num += 1
            except Exception:
                break

    if any_success:
        log(f"Direct API total: {len(all_products)} products")
        return list(all_products.values())
    return []


# ── Strategy 2: Playwright browser (page.evaluate fetch — true browser request) ─

def _sweed_fetch_all(page, store_id) -> list[dict]:
    """POST per category using page.evaluate() so fetch runs inside Chromium.
    Requires store_id captured from the page's own live API requests."""
    PAGE_SIZE    = 24
    all_products: dict[str, dict] = {}

    for cat_name, cat_id in SWEED_CATEGORIES.items():
        log(f"  Fetching [{cat_name}] (id={cat_id})")
        page_num = 1
        while True:
            try:
                payload = _sweed_post_body(page_num, PAGE_SIZE, cat_id)
                payload["storeId"] = store_id
                result = page.evaluate("""async (args) => {
                    try {
                        const resp = await fetch(args.url, {
                            method: 'POST',
                            credentials: 'include',
                            headers: {
                                'Content-Type': 'application/json',
                                'Accept': 'application/json'
                            },
                            body: JSON.stringify(args.payload)
                        });
                        if (!resp.ok) {
                            const body = await resp.text();
                            return {__error: 'HTTP ' + resp.status + ': ' + body.substring(0, 300)};
                        }
                        const data = await resp.json();
                        return {__status: resp.status, __data: data};
                    } catch(e) {
                        return {__error: String(e)};
                    }
                }""", {"url": SWEED_API_URL, "payload": payload})

                if not isinstance(result, dict) or "__error" in result:
                    log(f"    page {page_num} → error: {result}")
                    _write_debug(cat_name, page_num, {"__error": str(result)})
                    break

                log(f"    page {page_num} → HTTP {result.get('__status')}")
                raw = result.get("__data")
                _write_debug(cat_name, page_num, raw)
                found = _parse_sweed_response(raw, force_category=cat_name)
                if not found:
                    log(f"    0 products in response")
                    break
                for p in found:
                    all_products[product_key(p)] = p
                log(f"    +{len(found)} products (total: {len(all_products)})")
                if len(found) < PAGE_SIZE:
                    break
                page_num += 1
            except Exception as e:
                log(f"    error: {e}")
                break

    return list(all_products.values())


# ── DOM fallback (Sweed card structure) ───────────────────────────────────────

_HREF_STRAIN = {"hybrid": "Hybrid", "indica": "Indica", "sativa": "Sativa",
                "cbd": "CBD", "cbg": "CBG"}


def _dom_scrape_page(page) -> list[dict]:
    """Parse visible product cards. Uses aria-label, href slug, and text regex —
    all stable signals that don't depend on CSS module class names."""
    found = []
    cards = page.query_selector_all("[id^='product-']")

    for card in cards:
        p: dict = {}

        # aria-label="Cap Junky Flower, Flower. 4g - $55.00"
        aria  = card.get_attribute("aria-label") or ""
        aria_m = re.match(r'^(.+?),\s*(.+?)\.\s*([^\s]+(?:\s+[^\s-][^\s]*)?)\s+-\s+(\$[\d.]+)', aria)
        if aria_m:
            p["name"]     = aria_m.group(1).strip()
            p["category"] = aria_m.group(2).strip()
            p["weight"]   = aria_m.group(3).strip()
            p["price"]    = aria_m.group(4).strip()

        # href="/south-metro/menu/flower-5221/hybrid-cap-junky-flower-4g-383073"
        href  = card.get_attribute("href") or ""
        href_m = re.search(r'/menu/([a-z-]+?)-\d+/([a-z]+)-', href)
        if href_m:
            if not p.get("category"):
                p["category"] = href_m.group(1).replace("-", " ").title()
            slug = href_m.group(2)
            if slug in _HREF_STRAIN:
                p["strain_type"] = _HREF_STRAIN[slug]

        text = card.inner_text()

        thc_m = re.search(r'THC:\s*([\d.]+\s*%)', text)
        cbd_m = re.search(r'CBD:\s*([\d.]+\s*%)', text)
        if thc_m: p["thc"] = thc_m.group(1).replace(" ", "")
        if cbd_m: p["cbd"] = cbd_m.group(1).replace(" ", "")

        if not p.get("strain_type"):
            for s in ("Hybrid (Indica)", "Hybrid (Sativa)", "Hybrid", "Indica", "Sativa", "CBD"):
                if s in text:
                    p["strain_type"] = s
                    break

        brand_m = re.search(r'(?:Flower|Pre-?Roll|Vapes?|Edible|Concentrate)\s+by\s+([^\n]+)', text)
        if brand_m:
            p["brand"] = brand_m.group(1).strip()

        if not p.get("name"):
            el = card.query_selector("h2")
            if el: p["name"] = el.inner_text().strip()

        img = card.query_selector("img")
        if img:
            p["image"] = (img.get_attribute("src") or
                          img.get_attribute("data-src") or "")

        if not p.get("name"):
            continue

        # Normalise into output schema
        name     = _str(p.get("name", ""))
        category = _str(p.get("category", ""))
        if not category:
            category = _guess_category(name)

        strain = _str(p.get("strain_type", "")) or _guess_strain(name)
        name   = _clean_name(name)

        if category.lower() not in TARGET_CATS:
            continue

        found.append({
            "name": name, "brand": _str(p.get("brand", "")),
            "category": category, "strain_type": strain,
            "thc": _str(p.get("thc", "")), "cbd": _str(p.get("cbd", "")),
            "cbg": "", "cbn": "",
            "terpenes": [], "effects": [], "flavors": [],
            "weight": _str(p.get("weight", "")),
            "price": _str(p.get("price", "")), "price_tiers": {},
            "in_stock": True,
            "image": _str(p.get("image", "")), "description": "",
        })

    return found


def _guess_category(name: str) -> str:
    n = name.lower()
    if any(x in n for x in ("pre-roll", "preroll", "pre roll")): return "Pre-Roll"
    if any(x in n for x in ("disposable", "cartridge", "cart", "vape")): return "Vapes"
    if any(x in n for x in ("gummy", "gummies", "edible", "chocolate", "brownie")): return "Edibles"
    if "flower" in n: return "Flower"
    return ""

def _guess_strain(name: str) -> str:
    n = name.lower()
    if "indica" in n: return "Indica"
    if "sativa" in n: return "Sativa"
    if "hybrid" in n: return "Hybrid"
    return ""

def _clean_name(name: str) -> str:
    for pat in (r'\s*[-–]\s*PRE-?ROLL\s*$', r'\s*[-–]\s*FLOWER\s*$',
                r'\s*\bFlower\b\s*$', r'\s*\bPRE-?ROLL\b\s*$'):
        name = re.sub(pat, '', name, flags=re.I).strip()
    return name


# ── Playwright orchestrator ───────────────────────────────────────────────────

# Category page URL slugs (from Sweed's URL structure: /menu/<slug>-<id>)
CATEGORY_PAGE_URLS = {
    "flower":   f"{MENU_URL}/flower-{SWEED_CATEGORIES['flower']}",
    "pre-roll": f"{MENU_URL}/pre-rolls-{SWEED_CATEGORIES['pre-roll']}",
    "edibles":  f"{MENU_URL}/edibles-{SWEED_CATEGORIES['edibles']}",
    "vapes":    f"{MENU_URL}/vapes-{SWEED_CATEGORIES['vapes']}",
}


def try_playwright() -> list[dict]:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    all_products: dict[str, dict] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            ignore_https_errors=True,
        )
        page = ctx.new_page()

        # Intercept GetProductList API responses triggered by the page itself
        pending: list = []

        def on_response(response):
            if "GetProductList" in response.url and response.status == 200:
                try:
                    pending.append(response.json())
                except Exception:
                    pass

        page.on("response", on_response)

        # Navigate to each category page — the browser makes its own API calls
        for cat_name, cat_url in CATEGORY_PAGE_URLS.items():
            log(f"  Loading [{cat_name}] → {cat_url}")
            before = len(pending)
            try:
                page.goto(cat_url, wait_until="networkidle", timeout=40000)
            except PwTimeout:
                try:
                    page.goto(cat_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(3)
                except Exception as e:
                    log(f"    load error: {e}")
                    continue

            new_responses = pending[before:]
            cat_products = 0
            for data in new_responses:
                found = _parse_sweed_response(data, force_category=cat_name)
                for p in found:
                    all_products[product_key(p)] = p
                cat_products += len(found)
                _write_debug(cat_name, len(all_products), data)
            log(f"    {len(new_responses)} API response(s), {cat_products} products")

        log(f"Navigation scrape: {len(all_products)} products")

        # DOM fallback only if we got nothing at all
        if not all_products:
            log("Falling back to DOM scrape on main menu page...")
            page.goto(MENU_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            dom_products = _dom_scrape_page(page)
            for p in dom_products:
                all_products[product_key(p)] = p
            log(f"DOM scrape: {len(all_products)} products")

        browser.close()

    log(f"Playwright total: {len(all_products)} unique products")
    return list(all_products.values())


# ── Database helpers ──────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Strip accents and trailing punctuation so keys stay stable across minor name changes."""
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()
    return s.rstrip(" -–—.,")

def product_key(p: dict) -> str:
    key = f"{_normalize(p.get('name',''))}-{_normalize(p.get('brand',''))}"
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
        elif data[pid].get("category") != p.get("category"):
            p["first_seen"] = now
            log(f"  CATEGORY CHANGE ({data[pid].get('category')} → {p.get('category')}): {p['name']}")
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
    # Always initialise debug file so git add never fails on missing path
    debug_path = Path(__file__).parent / "docs" / "debug_api.json"
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    with open(debug_path, "w") as f:
        json.dump([], f)

    products = try_sweed_api()

    if not products:
        log("Direct API blocked — launching Playwright...")
        products = try_playwright()

    if not products:
        log("WARNING: 0 products scraped. Keeping existing data.")
        db = load_db()
        save_db(db)
        return db

    products = [p for p in products if p.get("category", "").lower() in TARGET_CATS]
    log(f"After category filter: {len(products)} products")

    db = load_db()
    db = merge(db, products)
    save_db(db)
    in_stock = sum(1 for p in db["products"].values() if p.get("in_stock", True))
    log(f"Done — {len(products)} scraped, {in_stock} in stock")
    return db


if __name__ == "__main__":
    run()
