# Technical Handoff — MN Legit Cannabis Menu

This document is for whoever maintains this codebase going forward. It explains how the pipeline actually works, where the data comes from, what happens when something goes wrong, and the known limitations of the current design.

---

## How It Works — The Daily Flow

Four scripts run in sequence, several times a day, entirely inside GitHub Actions (no server required):

```
scraper.py  →  enrich_strains.py  →  build_preview.py  →  git commit + push
   │                  │                     │
   ▼                  ▼                     ▼
products.json   strains_enriched.json   docs/index.html
```

1. **`scraper.py`** — Pulls live inventory from the Sweed POS system.
   - Strategy 1: direct API call (fastest, but often blocked by Sweed's WAF)
   - Strategy 2: the same API call routed through a headless Playwright browser (shares real session cookies, usually bypasses the WAF)
   - Strategy 3: DOM scraping of the rendered menu page, if both API paths fail
   - Saves everything to `docs/products.json`, tracking `first_seen` / `last_seen` per product so the site can show "New" and "Sold Out" sections.

2. **`enrich_strains.py`** — For every product in `products.json` that doesn't yet have an entry in `docs/strains_enriched.json`, it calls the Claude API twice:
   - Once to generate a strain profile (lineage, therapeutic uses, negative effects, aroma, misc notes)
   - Once to rate the strain 0–10 for each of the 8 mood categories, based on its COA terpene order
   - Writes to disk after **every single strain**, not in a batch at the end — so if the job gets interrupted, nothing already paid for is lost, and it picks up where it left off next run.
   - Once a strain is enriched, it is **never re-enriched or overwritten**, even if its terpene data later changes in Sweed.

3. **`build_preview.py`** — Reads `products.json` and `strains_enriched.json` and renders one fully static `docs/index.html`, with all product/strain data embedded directly as inline JS constants. No API calls happen in the browser — the page works even if the backend Claude/Sweed integrations are completely down, because it's just serving what was last built.

4. **GitHub Actions** (`.github/workflows/daily-scrape.yml`) runs steps 1–3 on a schedule, then commits the updated `docs/` folder back to the repo. GitHub Pages serves `docs/index.html` directly — this is the entire hosting story. There is no droplet, no database, no runtime server.

### Schedule

The workflow is scheduled to target roughly 5 runs a day: **~7:00 AM, 9:00 AM, 1:00 PM, 4:30 PM, and 8:00 PM CST** (see the `cron` entries and comments in `daily-scrape.yml`). Each run takes about a minute end-to-end.

GitHub's free scheduled-workflow system does not guarantee exact timing — runs can lag by anywhere from a few minutes to a couple hours during high-traffic periods across GitHub, independent of anything in this repo. A couple of the cron entries are deliberately scheduled earlier than their target time specifically to absorb that expected delay (see the inline comments). This is a known limitation of free scheduled automation, not a bug.

To force an immediate update instead of waiting for the next scheduled run: **Actions → Daily Menu Scrape → Run workflow**.

---

## Where the Data Comes From — and What Happens When It's Wrong

**Terpenes** come exclusively from the COA (Certificate of Analysis) data each brand submits, as entered into Sweed. There is no fallback source, and dispensary "effects" labels (the marketing-style tags Sweed sometimes shows) are deliberately never used anywhere in this app — they aren't trustworthy enough.

- If a brand doesn't submit complete COA data, or Sweed's product entry is incomplete, that product will simply have fewer (or zero) terpenes listed.
- **This directly lowers its mood-filter scores** — not because the strain is actually weaker for that mood, but because there's less data to score against. A strain with only 2 terpenes listed will generally score lower than one with 7, even if the missing terpenes would have helped it.
- **The fix is always in Sweed, not in this code.** Update the COA entry there, and it will be picked up automatically on the next scrape.

**Strain profiles** (lineage, therapeutic uses, aroma, etc.) are Claude's synthesis of its own training knowledge plus the actual terpene data pulled from Sweed. For well-known commercial strains this is usually detailed and accurate. For obscure or brand-new cultivars with little public documentation, the profile will be thinner and more generic — Claude does its best with what it has, but it isn't pulling from a verified lab database for these fields (only the terpene numbers themselves are lab-verified).

**If the Sweed direct API gets blocked** (their WAF can change behavior any time), the scraper transparently falls back to the Playwright and DOM strategies — slower, but should keep working. Run `python test_api.py` any time to check which path is currently working without running the full scrape.

---

## Known Limitations

- **No human review step.** AI-generated content publishes automatically; there is no approval queue. A bad Claude response is limited to a single strain, not a full-page failure, but it does go live automatically.
- **Static site, no backend.** There's no login, no real user accounts, no built-in analytics. The FastAPI scaffolding that once existed in this repo (`main.py`) was removed because it was never actually used — GitHub Pages serves the static build directly.
- **Manual edits to `docs/index.html` don't survive.** It's fully regenerated by `build_preview.py` on every run. Any change that needs to persist must go through `products.json`, `strains_enriched.json`, or the build scripts themselves — never edit the built HTML directly.
- **Mood scoring is a heuristic, not a clinical tool.** It's grounded in published terpene pharmacology research (see `README.md` and `terpenes_research.md`), but it's a research-informed estimate, not a personalized or medically validated recommendation.
- **Sweed's WAF behavior is outside our control** and can silently degrade scraping to the slower browser-based fallback. Worth spot-checking periodically with `test_api.py`.

---

## Responsible-Use Notes

- All AI-generated content (lineage, therapeutic uses, aroma, mood scores) is informational only. It should never be presented to customers as medical advice or a guaranteed effect — individual response to cannabis varies significantly.
- This tool assumes it's operating within a legal, licensed cannabis retail business in a market where that's permitted. It does not implement its own age verification or compliance checks — that responsibility stays with the dispensary's existing point-of-sale and ID-check processes.

---

## Setup Checklist (New Environment)

1. Add `ANTHROPIC_API_KEY` as a repository secret: **Settings → Secrets and variables → Actions**
2. Confirm GitHub Pages is enabled: **Settings → Pages → Deploy from `docs/` on `main`**
3. Manually trigger the workflow once to confirm it runs end-to-end: **Actions → Daily Menu Scrape → Run workflow**
4. Watch the **Actions** tab for the first few scheduled runs to confirm nothing errors out
5. Run `python test_api.py` locally any time to check whether Sweed's direct API is currently reachable or being blocked
