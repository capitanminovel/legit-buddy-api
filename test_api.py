"""
Quick pre-flight test for the Sweed API.
Run this directly (python test_api.py) to verify the API is reachable and
returning products before kicking off the full Playwright scraper.

Exit code 0 = at least one category returned products.
Exit code 1 = all requests blocked or returned 0 products.
"""

import json
import sys
import time
from datetime import datetime

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STORE_DOMAIN = "shop.mnlegitcannabis.com"
MENU_URL     = f"https://{STORE_DOMAIN}/south-metro/menu"
API_URL      = f"https://{STORE_DOMAIN}/_api/Products/GetProductList"

CATEGORIES = {
    "flower":   5221,
    "pre-roll": 5222,
    "edibles":  5223,
    "vapes":    5684,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type":    "application/json",
    "Referer":         MENU_URL,
    "Origin":          f"https://{STORE_DOMAIN}",
}


def _post_body(cat_id: int, page: int = 1, page_size: int = 5) -> dict:
    return {
        "filters": {"category": [cat_id]},
        "page": page, "pageSize": page_size,
        "sortingMethodId": 7, "searchTerm": "",
        "platformOs": "web", "sourcePage": 1,
    }


def _count_items(data) -> int:
    """Return number of product items found in the response."""
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("items", "products", "data", "result", "results"):
            v = data.get(key)
            if isinstance(v, list):
                return len(v)
            if isinstance(v, dict):
                for key2 in ("items", "products"):
                    v2 = v.get(key2)
                    if isinstance(v2, list):
                        return len(v2)
    return 0


def _sample_name(data) -> str:
    """Return first product name from response for quick sanity-check."""
    candidates = []
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
    if candidates and isinstance(candidates[0], dict):
        return candidates[0].get("name", "")
    return ""


def run_test():
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"\n{'='*60}")
    print(f"  Sweed API Test — {STORE_DOMAIN}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0

    for cat_name, cat_id in CATEGORIES.items():
        try:
            t0   = time.time()
            resp = session.post(API_URL, json=_post_body(cat_id), timeout=15)
            ms   = int((time.time() - t0) * 1000)

            if resp.status_code != 200:
                print(f"  [{cat_name:<9}]  HTTP {resp.status_code}  ({ms}ms)  ✗ BLOCKED")
                failed += 1
                continue

            try:
                data = resp.json()
            except Exception:
                print(f"  [{cat_name:<9}]  HTTP 200  ({ms}ms)  ✗ Invalid JSON")
                failed += 1
                continue

            count  = _count_items(data)
            sample = _sample_name(data)

            if count == 0:
                print(f"  [{cat_name:<9}]  HTTP 200  ({ms}ms)  ✗ 0 products  (response keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__})")
                failed += 1
            else:
                print(f"  [{cat_name:<9}]  HTTP 200  ({ms}ms)  ✓ {count} products  (e.g. \"{sample}\")")
                passed += 1

        except requests.exceptions.ConnectionError:
            print(f"  [{cat_name:<9}]  ✗ Connection error")
            failed += 1
        except requests.exceptions.Timeout:
            print(f"  [{cat_name:<9}]  ✗ Timeout")
            failed += 1
        except Exception as e:
            print(f"  [{cat_name:<9}]  ✗ {e}")
            failed += 1

    print(f"\n  Result: {passed}/{passed+failed} categories reachable via direct HTTP\n")

    if passed == 0:
        print("  → API is WAF-blocked. Scraper will use Playwright (browser) instead.")
        print("    This is expected — the full scraper should still work.\n")
        return False
    else:
        print("  → API accessible directly. Direct API path will be used.\n")
        return True


if __name__ == "__main__":
    ok = run_test()
    sys.exit(0 if ok else 1)
