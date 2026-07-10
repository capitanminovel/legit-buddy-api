# MN Legit Cannabis – South Metro · Staff Guide

Live menu: **[capitanminovel.github.io/legit-buddy-api](https://capitanminovel.github.io/legit-buddy-api)**

---

## What This Is

A fully automated cannabis menu for MN Legit Cannabis (South Metro). Several times a day a GitHub Actions pipeline scrapes the live inventory from the Sweed POS system, enriches any new strains with AI-generated profiles, and publishes an updated static page to GitHub Pages. No server needed — it's just a folder of files.

---

## For Staff: Using the Menu Page

### Browsing Products
- Use the **category tabs** (Flower · Pre-Roll · Vapes · Edibles) to filter by type.
- Tap any product card to open its **Strain Guide** — lineage, therapeutic uses, aroma, terpenes, and misc notes.
- The **✨ New in the Last 3 Days** section at the top highlights recently added inventory.
- The **🚫 Sold Out** section shows what left the menu in the last 2 days.
- Use the **Type** chips (All / Indica / Sativa / Hybrid) to filter by strain type.

### Mood Filter ("Find Your Vibe")
Click any mood chip to instantly filter and rank products for that use case:

| Chip | Best For |
|---|---|
| 😴 Wind Down | Sleep, heavy relaxation, end of shift |
| 🧘 Anxiety Relief | Stress, social anxiety, PTSD, tension |
| ⬆ Lift Up | Energy, mood boost, afternoon pick-me-up |
| 🎨 Get Creative | Focus, art, writing, problem-solving |
| 😄 Get Social | Parties, going out, laughing |
| 💆 Pain & Body | Chronic pain, inflammation, muscle soreness |
| ✨ Just Happy | General well-being, balanced euphoria |
| 🌹 Aphrodisiac | Intimacy, romance, lowered inhibitions |

Each card shows a **score badge (1–10)**:
- 🟢 **7–10 (green border)** — strong match, this strain was built for this vibe
- 🟡 **4–6 (amber border)** — decent match, will do the job
- ⚫ **1–3 (gray border)** — weak match, present but not ideal

Cards automatically sort **best → weakest** when a mood is active.

Tap **ℹ️ How it works** next to the mood chips for the full science breakdown of each mood.

### Search
Type anything into the search bar — `anxiety`, `PTSD`, `sleep`, `pain`, `Myrcene`, `citrus`, `creative` — and it searches across terpene profiles, therapeutic uses, aroma descriptions, and lineage.

### Dark Mode
Toggle with the **🌙 Dark** button in the header. Preference is saved across visits (dark is the default until a visitor switches to light).

### Staff Guide
Tap **📖 Staff Guide** in the header for an in-page reference on how the menu, search, and mood scoring work.

---

## How Strain Profiles Are Generated

When a new product appears in the scrape that doesn't yet have an enriched profile, `enrich_strains.py` calls the **Claude API** (claude-sonnet-4-6) and generates:

| Field | Description |
|---|---|
| `lineage` | Full genetic lineage with breeder name |
| `therapeutic` | Medical/therapeutic use cases |
| `negative` | Side effects and cautions |
| `aroma` | Sensory aroma description |
| `misc` | Breeder info, THC range, appearance, best timing |

These are saved to `docs/strains_enriched.json` and are never overwritten once generated (each key is written once and kept).

> **Important:** Terpene data comes directly from each brand's **COA (Certificate of Analysis)** as entered into the Sweed POS system. This is the only source we trust for terpene accuracy. Dispensary-listed "effects" are marketing copy and are intentionally ignored everywhere in this app.

---

## How Mood Rankings Work

### Data Source
All mood scoring is driven exclusively by **COA terpene data** — the actual lab-tested terpene profile of each product. Dispensary effect labels (e.g., "Relaxing", "Energetic" listed on product pages) are not used.

### Terpene → Effect Mapping
Based on peer-reviewed research:

| Terpene | Research-backed effects |
|---|---|
| Myrcene | Relaxing, Sleepy, Body High, Calming, Hungry |
| Limonene | Uplifting, Happy, Euphoric, Energetic, Focused, Aroused |
| Caryophyllene | Calming, Relaxing, Body High, Tingly, Aroused |
| Linalool | Sleepy, Calming, Relaxing, Blissful, Aroused |
| Pinene / B-Pinene | Focused, Creative, Energetic, Uplifting, Cerebral |
| Terpinolene | Creative, Uplifting, Euphoric, Energetic, Giggly, Aroused |
| Humulene | Calming, Body High |
| Ocimene | Uplifting, Energetic, Social, Aroused |
| Valencene | Uplifting, Happy, Social |
| Bisabolol | Calming, Relaxing, Blissful |
| Geraniol | Calming, Happy, Blissful, Aroused, Tingly |
| Terpinene | Uplifting, Energetic |

*Sources: Russo 2011 (Br J Pharmacol), Kamal et al. 2018 (Front Neurosci), Gertsch 2008 (PNAS), Miyazawa & Yamafuji 2005*

### Scoring Formula
Scores are position-weighted — a terpene listed **first** in the COA is the dominant terpene and contributes the most. This reflects that COA terpene lists are ordered by concentration.

| COA Position | Points |
|---|---|
| 1st (dominant) | 4.0 |
| 2nd | 2.5 |
| 3rd | 1.5 |
| 4th+ (minor) | 0.75 |

Effect matches add a smaller bonus. Final score is scaled to **0–10**.

### Claude AI Ratings
Once per new strain, `enrich_strains.py` also asks Claude to rate the strain 0–10 for each mood using strict calibration rules:
- Most strains should land in the **3–6** range
- **8–10** reserved for strains where 2+ dominant terpenes align perfectly
- No strain can score 8+ on more than 3 moods (forces real trade-offs)
- Hard ceilings apply per mood (e.g., no Caryophyllene → Pain & Body max 5)

When Claude ratings are present in `strains_enriched.json`, they override the computed formula. When absent (new product not yet rated), the formula runs as fallback.

---

## Dependencies

### Python (3.11+)
```
pip install -r requirements.txt
playwright install chromium --with-deps
```

| Package | Used For |
|---|---|
| `requests` | Sweed POS API calls |
| `playwright` | Headless browser scraping (also used as a DOM fallback if the direct API is blocked) |
| `anthropic` | Claude API — strain enrichment + mood ratings |

### API Keys
| Secret | Where to Set | Used By |
|---|---|---|
| `ANTHROPIC_API_KEY` | GitHub → Settings → Secrets → Actions | `enrich_strains.py` |

### GitHub Actions
The pipeline runs automatically several times a day. To trigger it manually:
**GitHub → Actions → Daily Menu Scrape → Run workflow**

This is useful after:
- Adding new products to the store (forces immediate enrichment)
- Updating the mood prompt in `enrich_strains.py` (clear `mood_ratings` from `strains_enriched.json` first)

---

## File Map

```
legit-buddy-api/
├── scraper.py               # Pulls live inventory from Sweed POS API
├── enrich_strains.py        # Calls Claude API to enrich + rate new strains
├── build_preview.py         # Builds docs/index.html
├── test_api.py              # Pre-flight check — is the Sweed API reachable right now?
│
├── docs/
│   ├── products.json           # Scraped inventory (auto-updated)
│   ├── strains_enriched.json   # Claude-enriched strain profiles + mood ratings
│   ├── index.html              # Published GitHub Pages site (auto-built)
│   └── terpenes_research.md    # Reference: terpenes with citations
│
└── .github/workflows/
    └── daily-scrape.yml        # Automated pipeline (runs several times daily)
```
