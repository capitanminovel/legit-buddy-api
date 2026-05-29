"""
Dev preview — same data as production, enhanced visual styling.
Outputs docs/dev.html.  Run:  python build_dev.py
"""
import subprocess
from pathlib import Path

# Generate the production build first so dev.html always has fresh data
subprocess.run(["python3", "build_preview.py"], check=True)

html = Path("docs/index.html").read_text(encoding="utf-8")

# ── Dev banner (fixed bottom strip) ──────────────────────────────────────────
DEV_BANNER = """
<div style="position:fixed;bottom:0;left:0;right:0;background:#7c3aed;color:#fff;
  text-align:center;font-size:.75rem;font-weight:700;padding:6px 8px;z-index:99999;
  letter-spacing:.3px;box-shadow:0 -2px 8px rgba(124,58,237,.35)">
  ⚗️ DEV PREVIEW — visual experiments only, does not affect the live page
</div>
"""

# ── CSS overrides injected after the existing stylesheet ────────────────────
DEV_CSS = """
<style id="dev-overrides">
/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   DEV VISUAL ENHANCEMENTS
   Edit freely — only docs/dev.html is affected.
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

:root {
  --radius: 14px;
}

/* ── Base readability ── */
body { font-size: 15px; line-height: 1.5; }

/* ── Header ── */
.header-inner { height: 70px; gap: 16px; }
.logo { font-size: 1.1rem; }

/* ── Tabs ── */
.tab { padding: 14px 18px; font-size: .86rem; }

/* ── Cards ── */
.grid {
  grid-template-columns: repeat(auto-fill, minmax(235px, 1fr));
  gap: 20px;
}
.card { border-radius: var(--radius); }
.card:hover {
  box-shadow: 0 8px 28px rgba(0,0,0,.14);
  transform: translateY(-3px);
}
.card-img { height: 190px; }
.card-body { padding: 14px 16px 16px; gap: 6px; }
.card-name  { font-size: 1.05rem; font-weight: 700; line-height: 1.35; }
.card-brand { font-size: .78rem; letter-spacing: .5px; }
.card-weight { font-size: .78rem; }

/* ── Badges & pills ── */
.strain-badge, .new-badge, .recent-badge { font-size: .7rem; padding: 3px 9px; }
.potency-pill { font-size: .74rem; padding: 3px 8px; }

/* ── Terpene chips ── */
.terp { font-size: .72rem; padding: 3px 9px; border-radius: 12px; }

/* ── Pricing ── */
.price-single { font-size: 1.15rem; font-weight: 800; }
.tier         { font-size: .74rem; padding: 4px 9px; }
.tier span    { font-size: .65rem; }

/* ── Search bar ── */
.search-input {
  padding: 10px 38px 10px 36px;
  font-size: .9rem;
  border-radius: 28px;
}

/* ── Mood bar ── */
.mood-bar-label { font-size: .82rem; font-weight: 800; }
.mood-chip { padding: 8px 14px; font-size: .8rem; min-height: 36px; }

/* ── Sections ── */
.section { margin-bottom: 56px; }
.section-head { margin-bottom: 22px; }
.section-title { font-size: 1.2rem; }
.section-count { font-size: .84rem; }

/* ── Sold-out rows ── */
.sold-row  { padding: 10px 14px; border-radius: 10px; }
.sold-name { font-size: .95rem; }
.sold-when { font-size: .8rem; }

/* ── New arrivals section ── */
.new-arrivals-section { padding: 24px; border-radius: 16px; }
.new-arrivals-title   { font-size: 1.2rem; }

/* ── Schedule ── */
.sched-shift      { padding: 10px 18px; font-size: .86rem; }
.sched-shift-name { min-width: 150px; font-size: .9rem; font-weight: 700; }
.sched-shift-time { font-size: .84rem; }
.sched-day        { border-radius: 14px; }

/* ── Legend items larger ── */
.legend { font-size: .78rem; gap: 16px; padding: 11px 24px; }

/* ── Mobile ── */
@media (max-width: 640px) {
  body { font-size: 14.5px; }

  /* Lock to 2 columns so cards never collapse to 1 */
  .grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .card-img  { height: 155px; }
  .card-body { padding: 12px 12px 14px; gap: 5px; }
  .card-name { font-size: .95rem; }

  /* 44 px min touch targets (WCAG 2.5.5) */
  .tab       { padding: 12px 14px; min-height: 44px; }
  .mood-chip { padding: 8px 11px;  min-height: 38px; }
  .sched-filter-btn { min-height: 38px; }

  .header-inner { gap: 10px; }
}

/* ── Print / contrast improvements ── */
@media (prefers-contrast: more) {
  .card-brand { color: var(--text); }
  .muted      { color: var(--text); }
}
</style>
"""

# Inject overrides just before </head>
html = html.replace("</head>", DEV_CSS + "\n</head>", 1)

# Inject dev banner just before </body>
html = html.replace("</body>", DEV_BANNER + "\n</body>", 1)

# Mark title so browser tab is clearly labelled
html = html.replace(
    "<title>MN Legit Cannabis",
    "<title>[DEV] MN Legit Cannabis",
    1,
)

# Mark the top bar so it's obvious this is dev
html = html.replace(
    "🌿 MN Legit Cannabis · South Metro · Updated daily at 4:30 PM CST",
    "⚗️ DEV PREVIEW — MN Legit Cannabis · South Metro",
    1,
)

out = Path("docs/dev.html")
out.write_text(html, encoding="utf-8")
print(f"Dev build → {out}")
