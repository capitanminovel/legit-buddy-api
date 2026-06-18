# MN Legit Cannabis — Roadmap & Project Notes

## Background

The owner asked me to build this same page for another dispensary they own, and I will be compensated for it. My plan is to first upgrade the current store's page so I can present it as a polished demo and example of what the new build will look like. Same core features for now, better everything else.

I have a DigitalOcean droplet available. We will be moving this repo to private, so hosting needs to move off GitHub Pages and onto the droplet. This also opens the door to real API calls instead of falling back on Playwright like we currently do.

---

## Immediate Next Steps

1. **Upgrade current store's page** — use it as the demo/presentation for the owner
2. **Present demo** — show the owner what the new store's page will look like
3. **Start new build** for the other dispensary on the droplet

---

## Infrastructure Changes

- Move repo from public GitHub to **private repo**
- Deploy to **DigitalOcean droplet** (already have one)
- With a real server we can use **direct API calls** instead of Playwright fallback
- May need to clean up the droplet before setting up
- Each store gets its own instance

---

## Upgrade Goals

### Strain Profile Generator
- **Current sources for strain profiles** *(need to confirm which are actually used)*
  - Lab COA data
  - Campfire Cannabis descriptions
  - Preferred strain website
  - Ask what is currently being used to generate profiles
- **Planned features**
  - Interactive strain profile UI
  - Selectable generation — not all strains generate at once, user picks which
  - Ability to add a new strain's info **before** it's in Sweed
    - Pre-loaded strain profile will be ready
    - Product won't appear in the menu until it's live in Sweed

### Schedule
- Better UI overall
- Image uploader for schedule photos
  - Restricted behind PIN

### Products
- Add a quick, easy description on each product card for fast selling or staff understanding of the strain

### Overall UI
- More professional look — this is now a paid product
  - Full light and dark mode
- Keep the current "fun mode" (GIFs, personality) as an optional setting the user can toggle and customize — lower priority, add later

### New Educational Section (Staff)
- Common things budtenders need to know
  - Research available training materials
  - Look into skills/content frameworks for budtender education
- Strain education
- Simple training modules with fun quizzes

---

## Technical Notes

- Moving to DigitalOcean removes the GitHub Pages restriction on private repos
- Real server = real API calls, no more Playwright fallback for scraping
- Scraper cron job replaces GitHub Actions
- Need to scope out droplet cleanup before new deployment
