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

import scraper

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
2. The terpene list below is an UNORDERED set of terpenes detected in this batch's COA.
   Sweed's API reports presence/absence only — it does NOT report concentration or
   rank terpenes by dominance, so list position carries no meaning. Do not treat any
   terpene as "dominant" based on where it appears in the list.
3. You MUST spread scores across the full 1-10 range. Do NOT cluster at 7-10.
   - Most strains should score 3-6 for most moods.
   - 8-10 means this strain is EXCEPTIONAL for that mood — 2+ of the mood's key terpenes are present.
   - 1-2 means the key terpenes for that mood are absent entirely.
4. If Total Terpene % is known, use it only as a mild overall-intensity modifier — a
   higher total suggests more pronounced effects generally, a low or unknown total
   means score conservatively. This never overrides rule 1 (presence still required).
5. A strain cannot score 8+ on more than 3 moods. Force trade-offs.

Strain: {name}
Type: {strain_type}
COA Terpenes detected (unordered — presence only, no concentration data): {terpenes}
Total Terpene % (COA, if known): {total_terpenes_pct}
Lineage: {lineage}

Mood scoring keys (terpenes listed are the ONLY relevant ones; presence-based, not ranked).
Sources: docs/terpenes_research.md in this repo (Russo 2011/2019, Kamal et al. 2018,
Gertsch et al. 2008, Gadotti et al. 2021, Miyazawa & Yamafuji 2005, Komori et al. 1995).
- wind_down: Myrcene, Linalool (primary — sedative/muscle-relaxant per Russo 2011).
  Caryophyllene, Nerolidol (secondary — also sedative per research doc). No Myrcene/Linalool → max 4.
- anxiety_relief: Nerolidol, Linalool (primary — Kamal 2018 found trans-Nerolidol the
  STRONGEST anxiolytic correlate, ahead of Linalool/Caryophyllene). Caryophyllene, Limonene
  (secondary). No Nerolidol/Linalool → max 5. Guaiol present → Kamal 2018 found Guaiol
  NEGATIVELY correlated with anxiety relief (possibly anxiogenic) — cap this mood at 4
  regardless of other terpenes present.
- lift_up: Limonene, Terpinolene, Ocimene, Valencene. No Limonene/Terpinolene → max 4.
- get_creative: Pinene (alpha or beta), Terpinolene. No Pinene → max 5.
- get_social: Limonene, Terpinolene. No both → max 4.
- pain_body: Caryophyllene (CB2 agonist, primary). Myrcene, Humulene, Bisabolol, Camphene
  (secondary — Bisabolol and Camphene share the same Cav3.2 pain-channel mechanism per
  Gadotti et al. 2021). No Caryophyllene → max 5.
- just_happy: Limonene + Linalool together → high. Missing either → max 6.
- aphrodisiac: Limonene, Linalool, Geraniol, Caryophyllene, Terpinolene. Needs 2+ → 7+.

Example calibration for a strain with Myrcene, Caryophyllene, and trace-level Limonene present, Total Terpene % low/unknown:
wind_down:6, anxiety_relief:4, lift_up:2, get_creative:1, get_social:2, pain_body:5, just_happy:3, aphrodisiac:2

Respond with ONLY valid JSON (no markdown, no explanation):
{{"wind_down":0,"anxiety_relief":0,"lift_up":0,"get_creative":0,"get_social":0,"pain_body":0,"just_happy":0,"aphrodisiac":0}}"""

# Used only when the product has NO COA terpene data at all (empty terpenes list).
# Falling back to the presence-based rubric above would floor every mood to its
# "absent" score, which looks like "bad for everything" when the truth is "no data."
# Products in this path always carry coa_status=no_coa on the live menu, so this
# is visibly marked as an estimate rather than a lab result.
RESEARCH_RATINGS_PROMPT = """You are a cannabis strain researcher. This product has NO
COA terpene test on file — Sweed's system has no lab-confirmed terpene data for this batch.

Instead of lab data, use your general knowledge of cannabis genetics: identify the strain
by name/lineage if you can (breeder databases, seed bank catalogs, grower/cultivar
information, known phenotype reports), and estimate its TYPICAL terpene profile and
resulting mood ratings from that.

CRITICAL RULES:
1. If you can identify this specific strain/genetics with reasonable confidence, use its
   well-documented typical terpene profile to rate moods, same logic as COA-based rating
   (see mood-terpene keys below).
2. If you do NOT recognize this strain/brand and have no confident genetics information,
   do NOT guess extremes. Default to neutral, moderate scores (4-6) across all moods —
   honest uncertainty, not a fabricated profile.
3. A strain cannot score 8+ on more than 3 moods. Force trade-offs.
4. This is explicitly an ESTIMATE, not a lab result — be conservative. Prefer scores in
   the 3-7 range; reserve 8-10 only for genetics you are genuinely confident about.

Product: {name}
Brand: {brand}
Category: {category}
Type: {strain_type}
Lineage (from strain-profile step, if identified): {lineage}
Therapeutic notes (from strain-profile step, if any): {therapeutic}

Mood-terpene keys, for reference if you identify a typical profile (same as COA-based
rating — sources: docs/terpenes_research.md, Russo 2011/2019, Kamal et al. 2018,
Gertsch et al. 2008, Gadotti et al. 2021):
- wind_down: Myrcene, Linalool primary; Caryophyllene, Nerolidol secondary.
- anxiety_relief: Nerolidol, Linalool primary (Nerolidol is the strongest documented
  anxiolytic correlate); Caryophyllene, Limonene secondary. Guaiol present → cap at 4.
- lift_up: Limonene, Terpinolene primary; Ocimene, Valencene secondary.
- get_creative: Pinene primary; Terpinolene secondary.
- get_social: Limonene, Terpinolene.
- pain_body: Caryophyllene primary; Myrcene, Humulene, Bisabolol, Camphene secondary.
- just_happy: Limonene + Linalool together.
- aphrodisiac: Limonene, Linalool, Geraniol, Caryophyllene, Terpinolene — needs 2+.

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
    has_coa_terpenes = bool(product.get("terpenes"))
    if has_coa_terpenes:
        prompt = RATINGS_PROMPT.format(
            name=product.get("name", ""),
            strain_type=product.get("strain_type", ""),
            terpenes=", ".join(product.get("terpenes") or []),
            total_terpenes_pct=product.get("total_terpenes_pct") or "unknown",
            lineage=enriched.get("lineage", ""),
            therapeutic=enriched.get("therapeutic", ""),
        )
    else:
        # No COA terpene data at all — fall back to genetics-knowledge estimation
        # instead of flooring every mood score (see RESEARCH_RATINGS_PROMPT).
        prompt = RESEARCH_RATINGS_PROMPT.format(
            name=product.get("name", ""),
            brand=product.get("brand", ""),
            category=product.get("category", ""),
            strain_type=product.get("strain_type", ""),
            lineage=enriched.get("lineage", "unknown"),
            therapeutic=enriched.get("therapeutic", "unknown"),
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

    # Migrate strain profiles from the old name+brand text key onto Sweed's
    # product-id key (scraper.py switched product_key() on 2026-08-26) —
    # otherwise every already-enriched product looks new and gets re-enriched.
    migrated = 0
    for key, product in db["products"].items():
        if key in existing:
            continue
        legacy = scraper._legacy_key(product)
        if legacy != key and legacy in existing:
            existing[key] = existing.pop(legacy)
            migrated += 1
    if migrated:
        print(f"Migrated {migrated} strain profile(s) to new product-id keys.")
        with open(STRAINS_PATH, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

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

    # Step 2: add mood ratings to any strain that is missing them.
    # For COA-backed products, rating depends only on (terpenes, total_terpenes_pct) —
    # many share an identical profile (same strain sold as flower/pre-roll/etc), so
    # cache by that signature to avoid paying for the same rating twice. No-COA
    # products skip the cache (see below) since they're rated individually by name.
    needs_ratings = [k for k in existing if "mood_ratings" not in existing[k]]
    if needs_ratings:
        print(f"\nRating moods for {len(needs_ratings)} strain(s)...")
        signature_cache: dict[tuple, dict] = {}
        api_calls = 0
        for key in needs_ratings:
            product = db["products"].get(key, {"name": key})
            terpenes = product.get("terpenes") or []
            # No-COA products go through the research-based prompt, which depends
            # on the product's own name/lineage, not a shared "empty" signature —
            # caching those would wrongly copy one strain's rating onto another.
            sig = ((tuple(sorted(terpenes)), product.get("total_terpenes_pct") or "")
                   if terpenes else None)
            if sig is not None and sig in signature_cache:
                ratings = signature_cache[sig]
                print(f"  → {product.get('name')} (cached, same terpene profile)")
            else:
                print(f"  → {product.get('name')}")
                ratings = rate_moods(client, product, existing[key])
                api_calls += 1
                if ratings and sig is not None:
                    signature_cache[sig] = ratings
            if ratings:
                existing[key]["mood_ratings"] = ratings
                print(f"    ✓ {ratings}")
                with open(STRAINS_PATH, "w") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
        print(f"\n{api_calls} API call(s) for {len(needs_ratings)} strain(s) "
              f"({len(needs_ratings) - api_calls} reused via cache).")
    else:
        print("All mood ratings already present.")

    print(f"\nDone. Saved → {STRAINS_PATH}")


if __name__ == "__main__":
    run()
