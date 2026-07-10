"""
Enrich new products with detailed strain profiles using the Claude API.
Also rates each strain 1-10 for every mood category based on COA terpenes.
Run after scraper.py to fill in lineage, therapeutic, negative, aroma, misc,
and mood_ratings for any products not yet in docs/strains_enriched.json.

Usage:
  ANTHROPIC_API_KEY=sk-ant-... python enrich_strains.py

GitHub Actions: add ANTHROPIC_API_KEY as a repo secret.
"""

import json
import os
import sys
from pathlib import Path

import anthropic

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PRODUCTS_PATH = Path(__file__).parent / "docs" / "products.json"
STRAINS_PATH  = Path(__file__).parent / "docs" / "strains_enriched.json"

PROFILE_PROMPT = """You are a cannabis strain expert. Given the product info below, provide a detailed strain profile.

Product:
- Name: {name}
- Brand: {brand}
- Category: {category}
- Strain Type: {strain_type}
- THC: {thc}
- CBD: {cbd}
- Lineage hint from store: {description}
- Terpenes: {terpenes}
- Effects: {effects}
- Flavors: {flavors}

Respond with ONLY a valid JSON object (no markdown, no explanation) with these exact keys:
{{
  "lineage": "Full genetic lineage with breeder name if known (e.g. 'OG Kush x Durban Poison (Cookies Fam)')",
  "therapeutic": "Medical/therapeutic uses, comma-separated (e.g. 'Chronic pain, insomnia, stress')",
  "negative": "Side effects and cautions (e.g. 'Dry mouth, dry eyes, couch-lock at high doses')",
  "aroma": "Detailed aroma description 1-2 sentences (descriptive, sensory language)",
  "misc": "Breeder info, typical THC range, bud appearance, best use timing, notable awards or recognition, consumer guidance. 2-3 sentences."
}}

For edibles (gummies, etc.) adapt accordingly — no genetic lineage needed, focus on dosing guidance.
Be accurate and specific. Use your knowledge of cannabis genetics and strain databases."""

RATINGS_PROMPT = """You are a cannabis terpene pharmacology expert. Rate this strain 1-10 for each mood category.

CRITICAL RULES — read carefully:
1. Base scores ONLY on the COA terpenes listed. Never assume terpenes not listed.
2. Terpene ORDER matters — terpene listed first is most concentrated (dominant). Weight dominant terpenes heavily.
3. You MUST spread scores across the full 1-10 range. Do NOT cluster at 7-10.
   - Most strains should score 3-6 for most moods.
   - 8-10 means this strain is EXCEPTIONAL for that mood — 2+ dominant terpenes align perfectly.
   - 1-2 means the key terpenes for that mood are absent or only traces.
4. If a key terpene is listed 4th or later, treat it as a minor contributor (+1-2 pts max).
5. A strain cannot score 8+ on more than 3 moods. Force trade-offs.

Strain: {name}
Type: {strain_type}
COA Terpenes (in order, 1st = dominant): {terpenes}
Lineage: {lineage}

Mood scoring keys (terpenes listed are the ONLY relevant ones):
- wind_down: Myrcene (#1 driver), Linalool, Caryophyllene. No Myrcene/Linalool → max 4.
- anxiety_relief: Linalool (#1), Caryophyllene (#2), Limonene. No Linalool → max 5.
- lift_up: Limonene (#1), Terpinolene, Ocimene, Valencene. No Limonene/Terpinolene → max 4.
- get_creative: Pinene (#1, alpha or beta), Terpinolene. No Pinene → max 5.
- get_social: Limonene (#1), Terpinolene. No both → max 4.
- pain_body: Caryophyllene (#1 driver, CB2 agonist), Myrcene, Humulene. No Caryophyllene → max 5.
- just_happy: Limonene + Linalool together → high. Missing either → max 6.
- aphrodisiac: Limonene (#1), Linalool (#2), Geraniol, Caryophyllene, Terpinolene. Needs 2+ → 7+.

Example calibration for a strain with Myrcene dominant, Caryophyllene secondary, trace Limonene:
wind_down:8, anxiety_relief:5, lift_up:3, get_creative:1, get_social:2, pain_body:6, just_happy:4, aphrodisiac:3

Respond with ONLY valid JSON (no markdown, no explanation):
{{"wind_down":0,"anxiety_relief":0,"lift_up":0,"get_creative":0,"get_social":0,"pain_body":0,"just_happy":0,"aphrodisiac":0}}"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def enrich_product(client: anthropic.Anthropic, key: str, product: dict) -> dict | None:
    prompt = PROFILE_PROMPT.format(
        name=product.get("name", ""),
        brand=product.get("brand", ""),
        category=product.get("category", ""),
        strain_type=product.get("strain_type", ""),
        thc=product.get("thc", ""),
        cbd=product.get("cbd", ""),
        description=product.get("description", ""),
        terpenes=", ".join(product.get("terpenes") or []),
        effects=", ".join(product.get("effects") or []),
        flavors=", ".join(product.get("flavors") or []),
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json(msg.content[0].text)
    except Exception as e:
        print(f"  ✗ Profile error for {product.get('name')}: {e}")
        return None


def rate_moods(client: anthropic.Anthropic, product: dict, enriched: dict) -> dict | None:
    prompt = RATINGS_PROMPT.format(
        name=product.get("name", ""),
        strain_type=product.get("strain_type", ""),
        terpenes=", ".join(product.get("terpenes") or []) or "unknown",
        lineage=enriched.get("lineage", ""),
        therapeutic=enriched.get("therapeutic", ""),
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        ratings = _parse_json(msg.content[0].text)
        # Clamp all values 0-10
        return {k: max(0, min(10, int(v))) for k, v in ratings.items()}
    except Exception as e:
        print(f"  ✗ Ratings error for {product.get('name')}: {e}")
        return None


def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    with open(PRODUCTS_PATH) as f:
        db = json.load(f)

    existing = {}
    if STRAINS_PATH.exists():
        with open(STRAINS_PATH) as f:
            existing = json.load(f)

    client = anthropic.Anthropic(api_key=api_key)

    # Step 1: enrich new products
    new_keys = [k for k in db["products"] if k not in existing]
    if new_keys:
        print(f"Enriching {len(new_keys)} new product(s)...")
        for key in new_keys:
            product = db["products"][key]
            print(f"  → {product.get('name')} ({product.get('brand')})")
            result = enrich_product(client, key, product)
            if result:
                existing[key] = result
                print(f"    ✓ Profile done")
                with open(STRAINS_PATH, "w") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
    else:
        print("All products already enriched — skipping profile step.")

    # Step 2: add mood ratings to any strain that is missing them
    needs_ratings = [k for k in existing if "mood_ratings" not in existing[k]]
    if needs_ratings:
        print(f"\nRating moods for {len(needs_ratings)} strain(s)...")
        for key in needs_ratings:
            product = db["products"].get(key, {"name": key})
            print(f"  → {product.get('name')}")
            ratings = rate_moods(client, product, existing[key])
            if ratings:
                existing[key]["mood_ratings"] = ratings
                print(f"    ✓ {ratings}")
                with open(STRAINS_PATH, "w") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
    else:
        print("All mood ratings already present.")

    print(f"\nDone. Saved → {STRAINS_PATH}")


if __name__ == "__main__":
    run()
