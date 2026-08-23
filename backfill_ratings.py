"""
One-off backfill: recompute mood_ratings for every strain already in
docs/strains_enriched.json using the corrected (order-independent) rubric
from enrich_strains.py's RATINGS_PROMPT, WITHOUT calling the Anthropic API.

Why this exists: the old ratings were computed by an LLM call that was told
"terpene list order = concentration order," which is false for this data
source (Sweed's API returns terpenes as an unordered presence list). This
script re-derives ratings mechanically from the same rubric, using terpene
presence only, so nothing already spent on the OLD calls is duplicated and
no new API tokens are spent. Not meant to be run again / kept long-term —
enrich_strains.py (with the corrected prompt) is the source of truth for
any NEW strain going forward.

Usage: python backfill_ratings.py [--dry-run]
"""

import json
import sys
from pathlib import Path

PRODUCTS_PATH = Path(__file__).parent / "docs" / "products.json"
STRAINS_PATH  = Path(__file__).parent / "docs" / "strains_enriched.json"

MYRCENE, LINALOOL, CARYOPHYLLENE = "myrcene", "linalool", "caryophyllene"
LIMONENE, TERPINOLENE = "limonene", "terpinolene"
OCIMENE, VALENCENE, PINENE = "ocimene", "valencene", "pinene"
HUMULENE, GERANIOL = "humulene", "geraniol"
NEROLIDOL, GUAIOL, BISABOLOL, CAMPHENE = "nerolidol", "guaiol", "bisabolol", "camphene"

_PINENE_ALIASES = {"pinene", "a pinene", "b pinene", "alpha pinene", "beta pinene"}


def _terp_set(terpenes: list[str]) -> set[str]:
    names = {t.strip().lower() for t in terpenes}
    if names & _PINENE_ALIASES:
        names.add(PINENE)
    return names


def _wind_down(t):
    primaries = sum(x in t for x in (MYRCENE, LINALOOL))
    sec = min(sum(x in t for x in (CARYOPHYLLENE, NEROLIDOL)), 2)
    if primaries == 0: return {0: 2, 1: 3, 2: 4}[sec]
    if primaries == 1: return {0: 4, 1: 5, 2: 6}[sec]
    return {0: 8, 1: 8, 2: 9}[sec]

def _anxiety_relief(t):
    # Kamal et al. 2018: trans-Nerolidol is the strongest documented anxiolytic
    # correlate (stronger than Linalool/Caryophyllene) — treated as a primary here.
    primaries = sum(x in t for x in (NEROLIDOL, LINALOOL))
    sec = sum(x in t for x in (CARYOPHYLLENE, LIMONENE))
    if primaries == 0:
        score = {0: 1, 1: 3, 2: 5}[sec]
    elif primaries == 1:
        score = {0: 6, 1: 7, 2: 8}[sec]
    else:
        score = {0: 8, 1: 9, 2: 9}[sec]
    # Kamal et al. 2018: Guaiol is NEGATIVELY correlated with anxiety relief
    # (possibly anxiogenic) — cap regardless of everything else present.
    if GUAIOL in t:
        score = min(score, 4)
    return score

def _lift_up(t):
    primaries = sum(x in t for x in (LIMONENE, TERPINOLENE))
    sec = min(sum(x in t for x in (OCIMENE, VALENCENE)), 2)
    if primaries == 0: return {0: 1, 1: 3, 2: 4}[sec]
    if primaries == 1: return {0: 5, 1: 6, 2: 7}[sec]
    return {0: 8, 1: 9, 2: 9}[sec]

def _get_creative(t):
    sec = TERPINOLENE in t
    if PINENE not in t: return 4 if sec else 1
    return 9 if sec else 7

def _get_social(t):
    primaries = sum(x in t for x in (LIMONENE, TERPINOLENE))
    return {0: 2, 1: 5, 2: 8}[primaries]

def _pain_body(t):
    # Gadotti et al. 2021: Bisabolol and Camphene share the same Cav3.2
    # pain-channel mechanism as Myrcene/Humulene's more general anti-inflammatory role.
    sec = min(sum(x in t for x in (MYRCENE, HUMULENE, BISABOLOL, CAMPHENE)), 3)
    if CARYOPHYLLENE not in t: return {0: 1, 1: 2, 2: 4, 3: 5}[sec]
    return {0: 6, 1: 7, 2: 8, 3: 9}[sec]

def _just_happy(t):
    if LIMONENE in t and LINALOOL in t: return 8
    if LIMONENE in t or LINALOOL in t: return 5
    return 2

def _aphrodisiac(t):
    pool = (LIMONENE, LINALOOL, GERANIOL, CARYOPHYLLENE, TERPINOLENE)
    count = min(sum(x in t for x in pool), 5)
    return {0: 1, 1: 4, 2: 7, 3: 8, 4: 9, 5: 9}[count]


_SCORERS = {
    "wind_down": _wind_down, "anxiety_relief": _anxiety_relief,
    "lift_up": _lift_up, "get_creative": _get_creative,
    "get_social": _get_social, "pain_body": _pain_body,
    "just_happy": _just_happy, "aphrodisiac": _aphrodisiac,
}


def rate_moods_local(terpenes: list[str]) -> dict:
    """Mirrors RATINGS_PROMPT's rubric mechanically — presence-based, no
    order/dominance assumption, no total-terpenes-% signal (not yet backfilled
    into products.json for most existing products)."""
    t = _terp_set(terpenes)
    ratings = {mood: fn(t) for mood, fn in _SCORERS.items()}

    # Rule 5: a strain cannot score 8+ on more than 3 moods — keep the top 3,
    # clamp the rest down to 7.
    high = sorted((m for m in ratings if ratings[m] >= 8),
                  key=lambda m: ratings[m], reverse=True)
    for m in high[3:]:
        ratings[m] = 7
    return ratings


def run(dry_run: bool):
    with open(PRODUCTS_PATH) as f:
        products = json.load(f)["products"]
    with open(STRAINS_PATH) as f:
        strains = json.load(f)

    changed = 0
    for key, enriched in strains.items():
        product = products.get(key)
        if not product:
            print(f"  ! skip {key} — no matching product in products.json")
            continue
        old = enriched.get("mood_ratings")
        new = rate_moods_local(product.get("terpenes") or [])
        if old != new:
            changed += 1
            print(f"  {product['name']:<40} {old} -> {new}")
        enriched["mood_ratings"] = new

    print(f"\n{changed}/{len(strains)} strains changed rating(s).")
    if dry_run:
        print("Dry run — not writing file.")
        return

    with open(STRAINS_PATH, "w") as f:
        json.dump(strains, f, indent=2, ensure_ascii=False)
    print(f"Saved -> {STRAINS_PATH}")


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
