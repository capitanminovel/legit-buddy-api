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

RATINGS_PROMPT = """You are a cannabis terpene pharmacology expert. Rate this strain 0-10 for each mood category based ONLY on its actual COA terpene profile. Use the research below.

Strain: {name}
Type: {strain_type}
COA Terpenes: {terpenes}
Lineage: {lineage}
Therapeutic: {therapeutic}

Terpene → mood science (use this to score):
- wind_down: Myrcene (GABA sedation), Linalool (anxiolytic/sleep), Caryophyllene (CB2 muscle)
- anxiety_relief: Linalool (GABA↑, cortisol↓), Caryophyllene (CB2 anti-anxiety), Limonene (5-HT1A)
- lift_up: Limonene (dopamine/serotonin↑, Komori 1995), Terpinolene (cerebral), Ocimene/Valencene (citrus energy)
- get_creative: Pinene (AChE inhibition, memory/focus, Miyazawa 2005), Terpinolene (cerebral drive)
- get_social: Limonene + Terpinolene (euphoria, giggles, social ease)
- pain_body: Caryophyllene (CB2 agonist, Gertsch 2008 PNAS), Myrcene (analgesic), Humulene (anti-inflammatory)
- just_happy: Limonene + Linalool + Terpinolene (balanced euphoria and warmth)
- aphrodisiac: Limonene (dopamine↑ desire), Linalool (anxiety↓, #1 arousal blocker), Geraniol (rose/romance), Caryophyllene (CB2 tactile sensitivity), Terpinolene (lowers inhibitions)

Scoring guide:
- 0: terpene not present, no match
- 1-3: weak — one minor matching terpene
- 4-6: moderate — one strong or two minor matching terpenes
- 7-9: strong — two or more matching terpenes present in COA
- 10: exceptional — multiple primary terpenes align perfectly

Respond with ONLY valid JSON (no markdown):
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
