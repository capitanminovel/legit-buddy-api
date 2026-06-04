"""
Dev preview — same data as production, enhanced visual styling.
Outputs docs/dev.html.  Run:  python build_dev.py
"""
import subprocess
from pathlib import Path

subprocess.run(["python3", "build_preview.py"], check=True)

html = Path("docs/index.html").read_text(encoding="utf-8")

DEV_BANNER = """
<div style="position:fixed;bottom:0;left:0;right:0;background:#7c3aed;color:#fff;
  text-align:center;font-size:.75rem;font-weight:700;padding:6px 8px;z-index:99999;
  letter-spacing:.3px;box-shadow:0 -2px 8px rgba(124,58,237,.35)">
  ⚗️ DEV PREVIEW — visual experiments only, does not affect the live page
</div>
"""

DEV_CSS = """
<style id="dev-overrides">

/* ── System fonts ── */
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif; }

/* ── Pure black palette — OLED, Netflix/Apple TV elevation model ── */
body.dark {
  --brand:    #4ade80;   /* 7.8:1 on #000 — WCAG AA */
  --brand-lt: #0a1f12;
  --text:     #ffffff;
  --muted:    #9ca3af;
  --border:   #1e1e1e;
  --bg:       #000000;   /* pure black */
  --white:    #111111;   /* card surface */
  --indica:   #a78bfa;
  --sativa:   #fbbf24;
  --hybrid:   #38bdf8;
  --cbd:      #60a5fa;
  --cbg:      #818cf8;
  --new:      #4ade80;
}

/* ── Borderless elevation — cards float via shadow only ── */
body.dark .card {
  border-color: transparent;
  box-shadow: 0 2px 10px rgba(0,0,0,.7);
}
body.dark .card:hover {
  background: #1a1a1a;
  box-shadow: 0 10px 36px rgba(0,0,0,.9);
  transform: translateY(-3px);
}
body.dark .card-img {
  background: #1a1a1a;
  border-bottom-color: transparent;
}
body.dark .no-img { opacity: .25; filter: grayscale(1); }

body.dark header,
body.dark .tabs-wrap,
body.dark .legend,
body.dark footer     { background: #0a0a0a; border-color: #1e1e1e; }
body.dark .mood-bar  { background: #111111; border-color: #1e1e1e; }

body.dark .tab:hover           { color: #4ade80; }
body.dark .tab.on              { color: #4ade80; border-bottom-color: #4ade80; }
body.dark .search-input        { background: #111111; border-color: #1e1e1e; }
body.dark .search-input:focus  { background: #1a1a1a; border-color: #4ade80; }
body.dark .mood-chip           { background: #111111; border-color: #1e1e1e; }
body.dark .mood-chip:hover     { border-color: #4ade80; }
body.dark .mood-chip.on        { background: #0a2016; color: #4ade80; border-color: #4ade80; }
body.dark .tier                { background: #1a1a1a; border-color: #1e1e1e; }
body.dark .terp                { background: #0a1a10; color: #4ade80; border-color: #1a3a22; cursor: help; }
body.dark .price-single        { color: #4ade80; }
body.dark .new-arrivals-section { background: linear-gradient(135deg,#0a1a10,#0a0a0a); border-color: #1e3a24; }
body.dark .sold-row            { background: #0a0a0a; }

/* ── Section title accent bars by category ── */
body.dark [data-cat="flower"]   .section-title { border-left: 3px solid #4ade80; padding-left: 12px; }
body.dark [data-cat="pre-roll"] .section-title { border-left: 3px solid #fb923c; padding-left: 12px; }
body.dark [data-cat="vapes"]    .section-title { border-left: 3px solid #38bdf8; padding-left: 12px; }
body.dark [data-cat="edibles"]  .section-title { border-left: 3px solid #e879f9; padding-left: 12px; }

/* ── Tab count badges ── */
.tab-count {
  display: inline-block;
  background: #1e1e1e;
  color: #9ca3af;
  font-size: .65rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 10px;
  margin-left: 4px;
  vertical-align: middle;
  letter-spacing: 0;
}
body.dark .tab.on .tab-count { background: #0a2016; color: #4ade80; }

/* ── Sticky search row (moved into tabs-wrap by JS) ── */
.tabs-wrap .search-row {
  padding: 6px 24px 10px;
  border-top: 1px solid #1e1e1e;
  max-width: 640px;
}
.tabs-wrap .search-row .search-wrap { max-width: 100%; }

/* ── Hide "tap for details" hint ── */
.card-detail-hint { display: none !important; }

/* ── Base ── */
:root { --radius: 14px; }
body  { font-size: 15px; line-height: 1.5; }

.header-inner { height: 70px; gap: 16px; }
.tab { padding: 14px 18px; font-size: .86rem; }

.grid {
  grid-template-columns: repeat(auto-fill, minmax(235px, 1fr));
  gap: 20px;
}
.card {
  border-radius: var(--radius);
  transition: box-shadow .18s ease-out, transform .18s ease-out, background .18s;
}

.card-img    { height: 190px; }
.card-body   { padding: 14px 16px 16px; gap: 6px; }
.card-name   { font-size: 1rem; font-weight: 700; line-height: 1.3; letter-spacing: -.01em; }
.card-brand  { font-size: .75rem; letter-spacing: .4px; }
.card-weight { font-size: .76rem; }

.strain-badge, .new-badge, .recent-badge { font-size: .68rem; padding: 3px 9px; }
.potency-pill { font-size: .72rem; padding: 3px 8px; }

.terp {
  font-size: .72rem;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 600;
  letter-spacing: .2px;
}

.price-single { font-size: 1.15rem; font-weight: 800; color: var(--brand); }
.tier         { font-size: .74rem; padding: 4px 9px; }
.tier span    { font-size: .64rem; }

.search-input {
  padding: 10px 38px 10px 36px;
  font-size: .88rem;
  border-radius: 28px;
}

.mood-bar-label { font-size: .8rem; font-weight: 800; letter-spacing: .05em; }
.mood-chip      { padding: 8px 14px; font-size: .78rem; min-height: 36px; }

.section       { margin-bottom: 56px; }
.section-head  { margin-bottom: 22px; }
.section-title { font-size: 1.2rem; font-weight: 800; letter-spacing: -.02em; }
.section-count { font-size: .82rem; }

.sold-row  { padding: 10px 14px; border-radius: 10px; }
.sold-name { font-size: .92rem; }

.new-arrivals-section { padding: 24px; border-radius: 16px; }
.new-arrivals-title   { font-size: 1.2rem; }

.legend { font-size: .76rem; gap: 14px; padding: 10px 24px; }

/* ── Schedule ── */
.sched-shift      { padding: 10px 18px; font-size: .86rem; }
.sched-shift-name { min-width: 150px; font-size: .9rem; font-weight: 700; }
.sched-shift-time { font-size: .84rem; }
.sched-day        { border-radius: 14px; }

/* ── Mobile ── */
@media (max-width: 640px) {
  body { font-size: 14.5px; }

  .grid      { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .card-img  { height: 145px; }
  .card-body { padding: 10px 10px 12px; gap: 5px; }
  .card-name { font-size: .91rem; }

  .tab         { padding: 12px 13px; min-height: 44px; }
  .mood-chip   { padding: 8px 10px; min-height: 38px; font-size: .76rem; }
  .header-inner { gap: 10px; }

  .tabs-wrap .search-row { padding: 6px 12px 10px; }
}
</style>
"""

DEV_JS = """
<script>
(function() {
  document.documentElement.classList.add('dark-pending');
  document.addEventListener('DOMContentLoaded', function() {

    // Force dark mode
    document.body.classList.add('dark');
    var btn = document.getElementById('darkToggle');
    if (btn) btn.textContent = '☀️ Light';

    // Move search row into sticky tabs-wrap
    var searchRow = document.querySelector('.mood-bar .search-row');
    var tabsWrap  = document.querySelector('.tabs-wrap');
    if (searchRow && tabsWrap) tabsWrap.appendChild(searchRow);

    // Tab count badges
    document.querySelectorAll('.tab[data-cat]').forEach(function(tab) {
      var cat = tab.dataset.cat;
      var total;
      if (cat === 'all') {
        total = document.querySelectorAll('.card').length;
      } else {
        var section = document.querySelector('.section[data-cat="' + cat + '"]');
        if (!section) return;
        var countEl = section.querySelector('[data-total]');
        if (!countEl) return;
        total = countEl.dataset.total;
      }
      var badge = document.createElement('span');
      badge.className = 'tab-count';
      badge.textContent = total;
      tab.appendChild(badge);
    });

    // Terpene tooltips
    var TERP = {
      'Myrcene':       'Earthy, musky · sedating, muscle relaxant',
      'Caryophyllene': 'Spicy, peppery · anti-inflammatory, CB2 agonist',
      'Limonene':      'Citrus · mood-lifting, stress relief',
      'Pinene':        'Pine · alertness, memory retention',
      'Linalool':      'Floral, lavender · calming, anti-anxiety',
      'Terpinolene':   'Floral, herbal · cerebral, creative',
      'Ocimene':       'Sweet, herbal · uplifting',
      'Humulene':      'Earthy, woody · appetite suppressant',
      'Bisabolol':     'Floral, nutty · soothing, anti-irritant',
      'Geraniol':      'Rose, floral · relaxing, neuroprotective',
      'Valencene':     'Citrus, sweet · anti-inflammatory',
    };
    document.querySelectorAll('.terp').forEach(function(el) {
      var name = el.textContent.trim();
      if (TERP[name]) el.title = name + ' — ' + TERP[name];
    });

  });
})();
</script>
"""

html = html.replace("</head>", DEV_CSS + DEV_JS + "\n</head>", 1)
html = html.replace("</body>", DEV_BANNER + "\n</body>", 1)
html = html.replace("<title>MN Legit Cannabis", "<title>[DEV] MN Legit Cannabis", 1)
html = html.replace(
    "🌿 MN Legit Cannabis · South Metro · Updated daily at 4:30 PM CST",
    "⚗️ DEV PREVIEW — MN Legit Cannabis · South Metro",
    1,
)

out = Path("docs/dev.html")
out.write_text(html, encoding="utf-8")
print(f"Dev build → {out}")
