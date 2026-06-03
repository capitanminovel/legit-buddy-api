"""
Dev preview — same data as production, research-backed dark-first design.
Outputs docs/dev.html.  Run:  python build_dev.py
"""
import subprocess
from pathlib import Path

subprocess.run(["python3", "build_preview.py"], check=True)

html = Path("docs/index.html").read_text(encoding="utf-8")

DEV_BANNER = """
<div style="position:fixed;bottom:0;left:0;right:0;background:#7c3aed;color:#fff;
  text-align:center;font-size:.72rem;font-weight:700;padding:5px 8px;z-index:99999;
  letter-spacing:.3px">
  ⚗️ DEV PREVIEW — does not affect the live page
</div>
"""

DEV_CSS = """
<style id="dev-overrides">
/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Research-backed design: dark-first, WCAG-compliant,
   system fonts, Spotify/Apple Music card patterns.
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

/* ── Force dark mode on load ── */
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif; }

/* ── Proper dark palette (Material Design 3 / Apple HIG) ──
   #16a34a fails contrast on dark (3.2:1) — use #4ade80 for interactive text  */
body.dark {
  --brand:       #4ade80;   /* interactive green, 7.8:1 on #0d0d0d — AA */
  --brand-lt:    #0d2015;   /* subtle tinted surface */
  --text:        #ffffff;   /* primary text, 19:1 — AAA */
  --muted:       #9ca3af;   /* metadata/hints, 6.2:1 — AA */
  --border:      #2d2d2d;   /* standard borders */
  --bg:          #0d0d0d;   /* OLED-optimised primary background */
  --white:       #1a1a1a;   /* elevated surface (cards, header) */
  --indica:      #a78bfa;
  --sativa:      #fbbf24;
  --hybrid:      #38bdf8;
  --cbd:         #60a5fa;
  --cbg:         #818cf8;
  --new:         #4ade80;
}

/* ── Tertiary surface for hover / selected states ── */
body.dark .card:hover          { background: #262626; }
body.dark .tab:hover           { color: #4ade80; }
body.dark .tab.on              { color: #4ade80; border-bottom-color: #4ade80; }
body.dark .search-input:focus  { background: #262626; border-color: #4ade80; }
body.dark .mood-chip.on        { background: #1a3d2b; color: #4ade80; border-color: #4ade80; }
body.dark .tier                { background: #262626; border-color: #2d2d2d; }
body.dark .terp                { background: #0d2015; color: #4ade80; border-color: #1e4a2a; }

/* Price in accent green on dark */
body.dark .price-single        { color: #4ade80; }

/* ── Base ── */
:root   { --radius: 14px; }
body    { font-size: 15px; line-height: 1.5; }

/* ── Header — taller, more breathing room ── */
.header-inner { height: 70px; gap: 16px; }

/* ── Tabs ── */
.tab { padding: 14px 18px; font-size: .86rem; }

/* ── Card grid — Spotify-style 2-col on mobile, auto on desktop ── */
.grid {
  grid-template-columns: repeat(auto-fill, minmax(235px, 1fr));
  gap: 20px;
}
.card {
  border-radius: var(--radius);
  transition: box-shadow .15s ease-out, transform .15s ease-out, background .15s;
}
.card:hover {
  box-shadow: 0 8px 28px rgba(0,0,0,.25);
  transform: translateY(-2px);
}

/* ── Card body ── */
.card-img    { height: 190px; }
.card-body   { padding: 14px 16px 16px; gap: 6px; }
.card-name   { font-size: 1rem; font-weight: 700; line-height: 1.35; letter-spacing: -.01em; }
.card-brand  { font-size: .75rem; letter-spacing: .5px; }
.card-weight { font-size: .76rem; }

/* ── Badges ── */
.strain-badge, .new-badge, .recent-badge { font-size: .68rem; padding: 3px 9px; }
.potency-pill { font-size: .72rem; padding: 3px 8px; }

/* ── Terpene chips ── */
.terp { font-size: .7rem; padding: 3px 9px; border-radius: 12px; }

/* ── Pricing — larger, bolder, accent green ── */
.price-single { font-size: 1.1rem; font-weight: 800; color: var(--brand); }
.tier         { font-size: .74rem; padding: 4px 9px; }
.tier span    { font-size: .64rem; }

/* ── Search ── */
.search-input {
  padding: 10px 38px 10px 36px;
  font-size: .88rem;
  border-radius: 28px;
}

/* ── Mood bar ── */
.mood-bar-label { font-size: .8rem; font-weight: 800; letter-spacing: .05em; }
.mood-chip      { padding: 8px 14px; font-size: .78rem; min-height: 36px; }

/* ── Sections ── */
.section       { margin-bottom: 56px; }
.section-head  { margin-bottom: 22px; }
.section-title { font-size: 1.2rem; letter-spacing: -.02em; }
.section-count { font-size: .82rem; }

/* ── Sold-out ── */
.sold-row  { padding: 10px 14px; border-radius: 10px; }
.sold-name { font-size: .92rem; }

/* ── New arrivals ── */
.new-arrivals-section { padding: 24px; border-radius: 16px; }
.new-arrivals-title   { font-size: 1.2rem; }

/* ── Legend ── */
.legend { font-size: .76rem; gap: 14px; padding: 10px 24px; }

/* ── Detail hint ── */
.card-detail-hint { font-size: .65rem; letter-spacing: .3px; }

/* ── Mobile: always 2-col, 44px touch targets ── */
@media (max-width: 640px) {
  body { font-size: 14.5px; }

  .grid        { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .card-img    { height: 150px; }
  .card-body   { padding: 11px 11px 13px; gap: 5px; }
  .card-name   { font-size: .92rem; }

  .tab         { padding: 12px 13px; min-height: 44px; }
  .mood-chip   { padding: 8px 10px;  min-height: 38px; font-size: .76rem; }
  .header-inner { gap: 10px; }
}
</style>
"""

# Auto-enable dark mode (force it on for dev)
FORCE_DARK = """
<script>
(function() {
  document.documentElement.classList.add('dark-pending');
  document.addEventListener('DOMContentLoaded', function() {
    document.body.classList.add('dark');
    var btn = document.getElementById('darkToggle');
    if (btn) btn.textContent = '☀️ Light';
  });
})();
</script>
"""

# Inject before </head>
html = html.replace("</head>", DEV_CSS + FORCE_DARK + "\n</head>", 1)

# Inject dev banner before </body>
html = html.replace("</body>", DEV_BANNER + "\n</body>", 1)

# Mark title
html = html.replace("<title>MN Legit Cannabis", "<title>[DEV] MN Legit Cannabis", 1)

# Mark top bar
html = html.replace(
    "🌿 MN Legit Cannabis · South Metro · Updated daily at 4:30 PM CST",
    "⚗️ DEV PREVIEW — MN Legit Cannabis · South Metro",
    1,
)

out = Path("docs/dev.html")
out.write_text(html, encoding="utf-8")
print(f"Dev build → {out}")
