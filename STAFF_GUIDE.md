# Legit Cannabis South Metro — Staff Menu Guide

**Live page:** [capitanminovel.github.io/legit-buddy-api](https://capitanminovel.github.io/legit-buddy-api)

---

## What Is This?

This is the internal menu and strain reference tool for MN Legit Cannabis South Metro. It updates itself every day at 4:30 PM CST — you don't need to touch anything for it to stay current. When new products hit Sweed, they'll appear here automatically, usually within 24 hours.

---

## Using the Menu

### Finding Products

At the top of the page you'll see category tabs — **Flower, Pre-Roll, Vapes, Edibles**. Tap any tab to filter down to just that category. Any products added in the last 3 days appear in a highlighted **New** section at the top.

Tap any product card to open its full strain profile — lineage, therapeutic uses, aroma, terpenes, and general notes.

### Search

The search bar works across everything — product names, terpene names, and the enriched profile fields. Try searching:

- `anxiety` or `PTSD` → finds strains with documented anxiety-relief properties
- `sleep` or `insomnia` → finds strains used for sleep
- `Myrcene` → shows every product with that terpene
- `citrus` → matches aroma descriptions
- `Cookies` → matches lineage/breeder names

### Mood Filter

The mood chips let customers (and staff) say what they're *looking for* rather than naming a specific strain. Tap a chip and every card on the page gets a **score from 1–10** showing how well it matches that vibe. Cards automatically sort best to worst.

The colored border tells you at a glance:
- 🟢 **Green border** — strong match (7 or higher)
- 🟡 **Amber border** — decent match (4–6)
- ⚫ **Gray border** — present but weak match (1–3)

Tap **ℹ️ How it works** next to the mood chips to read the full breakdown of what each mood means and the science behind it.

---

## Where the Information Comes From

There are three sources that feed this tool, and it's important to know which one to trust for what.

### 1. Sweed POS System — Product Data & Terpenes

Everything product-related — name, brand, price, THC/CBD, weight, category, terpenes, and strain type — comes directly from **your Sweed POS system**. The tool pulls a fresh copy every day.

**Terpenes in particular come from COA data that each brand submits to the store.** When a brand delivers product, they provide a Certificate of Analysis (lab test results) which the store enters into Sweed. Those are the terpenes you see on the cards — actual lab-tested values, not guesses.

> ⚠️ **Important:** If a product's terpene list looks incomplete or wrong, the fix is in Sweed — update the COA data there and it'll reflect here on the next daily update. The tool only knows what Sweed knows.

Dispensary effect labels (the "Relaxing", "Energetic" type tags sometimes set in Sweed) are intentionally **not used** anywhere in this tool — those are marketing copy and aren't consistent enough to trust. Everything mood-related is derived from terpenes only.

### 2. Claude AI — Strain Profiles

When a new strain appears that we've never seen before, the tool uses **Claude AI** (Anthropic's AI, the same company behind Claude.ai) to generate a detailed profile. Claude draws on its training data — which includes published strain databases, cannabis genetics research, and breeder documentation — to fill in:

- **Lineage** — the parent strains and who bred it
- **Therapeutic uses** — what conditions it's known to help with
- **Negative effects** — side effects to warn customers about
- **Aroma** — a detailed sensory description
- **Misc** — breeder notes, typical potency range, appearance, best timing

Claude is also given the actual terpene profile from Sweed so it can cross-reference against the chemistry. If the strain is well-documented publicly, the profile will be detailed. If it's an obscure or very new cultivar, Claude will do its best with available information and the terpene data.

These profiles are generated **once per strain** and then stored. They won't change unless manually updated.

### 3. Published Terpene Research — Mood Scoring

The mood filter scores aren't invented — they're grounded in published pharmacology research. The key papers are:

- **Russo 2011** (*British Journal of Pharmacology*) — foundational paper on cannabis terpene synergy and therapeutic applications
- **Kamal et al. 2018** (*Frontiers in Neuroscience*) — identifies the specific terpene combinations that drive anxiolytic (anxiety-reducing) effects
- **Gertsch 2008** (*PNAS*) — confirms Caryophyllene as the only terpene that directly activates cannabinoid receptors (CB2), explaining its pain and anti-inflammatory effects

This research maps each terpene to the effects it's known to produce. The tool uses those maps to score every strain against every mood, based entirely on the lab-tested terpenes from Sweed.

---

## How Mood Scores Are Calculated

When you tap a mood chip, here's what actually happens:

1. The tool looks at each product's **terpene list from Sweed COA data**
2. It checks which terpenes in that list are relevant to the mood you selected
3. It weights them by **position in the list** — the first terpene listed is the most concentrated (that's how COA reports work), so it contributes more to the score
4. A strain where the key terpene is dominant scores much higher than one where it only shows up as a trace

For example, for **Pain & Body**, the key terpene is Caryophyllene (the only terpene proven to activate CB2 receptors, which are linked to pain and inflammation):
- Caryophyllene listed **first** on the COA → likely scores 7–8
- Caryophyllene listed **third or fourth** → likely scores 4–5
- Caryophyllene **not present** → scores 1–2 regardless of anything else

The AI also provides its own 1–10 rating for each strain/mood combination, using the same logic but with additional context from its knowledge of each strain. When the AI rating is available, it takes priority over the formula.

---

## How the Strain Guide Documents Work

There are two pre-built Word documents you can download directly from the menu page:

**✅ Available Now** — contains only the strains currently in stock.
**📦 Master Cache** — contains every strain the tool has ever seen and enriched, including ones that may be out of stock.

Both are sorted by category: **Flower → Pre-Roll → Vapes.**

### Where the Document Content Comes From

Each entry in the document is built from **both sources combined**:

- **Product details** (name, brand, strain type, THC/CBD, terpenes, flavors) → from Sweed COA data
- **Enriched profile** (lineage, therapeutic, aroma, misc) → from Claude AI's research

So the document reflects everything we know about each strain — the hard lab facts from Sweed and the contextual knowledge from AI research.

### Downloading

Click either export button on the page → a popup appears with a countdown → press **Let's Go** → the `.docx` file downloads. Open it in Microsoft Word or Google Docs.

### Updating the Document with New Strains

The documents rebuild automatically every day as part of the daily update. If a new strain was added to Sweed yesterday, it'll be in the next day's download automatically — no manual steps needed.

---

## A Note on Accuracy

This tool is as accurate as the data it has access to:

- **Terpene profiles** — only as complete as what each brand submitted to Sweed. Some brands provide full 7–10 terpene COAs; others only list 2–3. A strain with only 3 terpenes listed will score lower on mood filters than one with 7 — not because it's less effective, but because we have less data to work with.
- **Strain profiles** — Claude AI is knowledgeable but not infallible. If a profile looks off, it can be manually corrected in the `strains_enriched.json` file.
- **Mood scores** — based on terpene science, not on customer reviews or anecdotal reports. A strain might feel different to different people; the scores are a research-backed starting point, not a guarantee.

---

## Quick Reference: Mood Chips

| Mood | Key Terpenes | Good For |
|---|---|---|
| 😴 Wind Down | Myrcene, Linalool | Sleep, end of day, heavy relaxation |
| 🧘 Anxiety Relief | Linalool, Caryophyllene, Limonene | Stress, anxiety, PTSD, overthinking |
| ⬆ Lift Up | Limonene, Terpinolene, Ocimene | Energy, mood boost, afternoon use |
| 🎨 Get Creative | Pinene, Terpinolene | Focus, art, writing, creative projects |
| 😄 Get Social | Limonene, Terpinolene | Going out, parties, socializing |
| 💆 Pain & Body | Caryophyllene, Myrcene, Humulene | Chronic pain, inflammation, soreness |
| ✨ Just Happy | Limonene, Linalool, Terpinolene | General well-being, balanced euphoria |
| 🌹 Aphrodisiac | Limonene, Linalool, Geraniol, Caryophyllene | Intimacy, romance, lowered inhibitions |
