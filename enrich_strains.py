"""
Enrich new products with detailed strain profiles using the Claude API.
Run after scraper.py to fill in lineage, therapeutic, negative, aroma, and misc
for any products not yet in docs/strains_enriched.json.

Usage:
  ANTHROPIC_API_KEY=sk-ant-... python enrich_strains.py

GitHub Actions: add ANTHROPIC_API_KEY as a repo secret, then add this step
to daily-scrape.yml after the scraper runs:
  - name: Enrich new strains
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    run: python enrich_strains.py
"""

import json
import os
import sys
from pathlib import Path

import anthropic

PRODUCTS_PATH = Path(__file__).parent / "docs" / "products.json"
STRAINS_PATH  = Path(__file__).parent / "docs" / "strains_enriched.json"

PROMPT_TEMPLATE = """You are a cannabis strain expert. Given the product info below, provide a detailed strain profile.

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


def enrich_product(client: anthropic.Anthropic, key: str, product: dict) -> dict | None:
    prompt = PROMPT_TEMPLATE.format(
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
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"  ✗ Error enriching {product.get('name')}: {e}")
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

    new_keys = [k for k in db["products"] if k not in existing]

    if not new_keys:
        print("All products already enriched — nothing to do.")
        return

    print(f"Enriching {len(new_keys)} new product(s)...")
    client = anthropic.Anthropic(api_key=api_key)

    for key in new_keys:
        product = db["products"][key]
        print(f"  → {product.get('name')} ({product.get('brand')})")
        result = enrich_product(client, key, product)
        if result:
            existing[key] = result
            print(f"    ✓ Done")
            # Save after each product so partial progress is kept
            with open(STRAINS_PATH, "w") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"\nEnriched {len(new_keys)} product(s). Saved → {STRAINS_PATH}")


if __name__ == "__main__":
    run()
