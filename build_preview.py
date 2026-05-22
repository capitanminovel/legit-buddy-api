"""Renders products.json into a fully static HTML file — no JS fetch needed."""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

CST      = timezone(timedelta(hours=-6))
DATA     = Path(__file__).parent / "docs" / "products.json"
OUT      = Path(__file__).parent / "docs" / "index.html"
NEW_DAYS = 3

CAT_ICONS = {
    "flower":"🌿","pre-roll":"🚬","pre_roll":"🚬","preroll":"🚬",
    "edible":"🍬","edibles":"🍬","concentrate":"💎","concentrates":"💎",
    "vape":"💨","vapes":"💨","cartridge":"💨","cartridges":"💨",
    "tincture":"💧","tinctures":"💧","topical":"🧴","topicals":"🧴",
    "capsule":"💊","capsules":"💊","accessory":"🛠️","accessories":"🛠️",
    "beverage":"🥤","beverages":"🥤",
}
TIER_LABELS = {
    "gram":"1g","two_gram":"2g","eighth":"⅛ oz",
    "quarter":"¼ oz","half_ounce":"½ oz","ounce":"1 oz","unit":"Unit",
}

def cat_icon(c): return CAT_ICONS.get((c or "").lower().strip(), "🌱")

def strain_class(s):
    t = (s or "").lower()
    if "indica" in t: return "strain-indica"
    if "sativa" in t: return "strain-sativa"
    if "hybrid" in t: return "strain-hybrid"
    if "cbd"    in t: return "strain-cbd"
    if "cbg"    in t: return "strain-cbg"
    return "strain-default"

def age_days(iso):
    try:
        dt = datetime.fromisoformat(iso)
        return (datetime.now(CST) - dt).days
    except Exception:
        return 999

def new_badge(first_seen):
    d = age_days(first_seen)
    if d == 0:          return '<span class="new-badge">New Today</span>'
    if d <= NEW_DAYS:   return f'<span class="recent-badge">New ({d}d ago)</span>'
    return ""

def build_card(p):
    ci = cat_icon(p.get("category", ""))
    img = (f'<img src="{p["image"]}" alt="{p["name"]}" loading="lazy" onerror="this.parentNode.innerHTML=\'<div class=no-img>{ci}</div>\'">'
           if p.get("image")
           else f'<div class="no-img">{ci}</div>')

    strain_b = (f'<span class="strain-badge {strain_class(p["strain_type"])}">{p["strain_type"]}</span>'
                if p.get("strain_type") else "")
    age_b    = new_badge(p.get("first_seen", ""))
    badges   = f'<div class="badges">{age_b}{strain_b}</div>' if (strain_b or age_b) else ""

    thc_pill = f'<span class="potency-pill thc">THC {p["thc"]}</span>' if p.get("thc") else ""
    cbd_pill = f'<span class="potency-pill cbd">CBD {p["cbd"]}</span>' if p.get("cbd") else ""
    potency  = f'<div class="potency-row">{thc_pill}{cbd_pill}</div>' if (thc_pill or cbd_pill) else ""

    terps  = "".join(f'<span class="terp">{t}</span>' for t in (p.get("terpenes") or [])[:3])
    terp_h = f'<div class="terp-row">{terps}</div>' if terps else ""

    efx   = "".join(f'<span class="effect">{e}</span>' for e in (p.get("effects") or [])[:3])
    efx_h = f'<div class="effects-row">{efx}</div>' if efx else ""

    minors = " · ".join(filter(None, [
        f'CBG {p["cbg"]}' if p.get("cbg") else "",
        f'CBN {p["cbn"]}' if p.get("cbn") else "",
    ]))
    minor_h = f'<div style="font-size:.68rem;color:var(--muted);margin-top:2px">{minors}</div>' if minors else ""

    tiers = p.get("price_tiers") or {}
    if tiers:
        chips = "".join(f'<div class="tier">{v}<span>{TIER_LABELS.get(k,k)}</span></div>'
                        for k,v in tiers.items())
        price_h = f'<div class="price-tiers">{chips}</div>'
    elif p.get("price"):
        price_h = f'<div class="price-single">{p["price"]}</div>'
    else:
        price_h = ""

    weight_h = f'<div class="card-weight">{p["weight"]}</div>' if p.get("weight") else ""
    brand_h  = f'<div class="card-brand">{p["brand"]}</div>'   if p.get("brand")  else ""

    return f"""
    <div class="card">
      <div class="card-img">{img}{badges}{potency}</div>
      <div class="card-body">
        {brand_h}
        <div class="card-name">{p["name"]}</div>
        {weight_h}{minor_h}{terp_h}{efx_h}
        <div class="price-section">{price_h}</div>
      </div>
    </div>"""

def build():
    with open(DATA) as f:
        db = json.load(f)

    now     = datetime.now(CST)
    ts      = now.strftime("%a, %b %d %Y — %I:%M %p CST")
    all_p   = [(k,v) for k,v in db["products"].items() if v.get("in_stock", True)]

    # Sort: newest first, then alpha
    all_p.sort(key=lambda x: (age_days(x[1].get("first_seen","")), x[1].get("name","")))

    # Group by category
    from collections import defaultdict
    cats = defaultdict(list)
    for _, p in all_p:
        cats[p.get("category") or "Other"].append(p)

    # Tab buttons
    tab_btns = '<button class="tab on" data-cat="all" onclick="filterCat(this)">All Products</button>\n'
    tab_btns += "\n".join(
        f'<button class="tab" data-cat="{c.lower()}" onclick="filterCat(this)">{cat_icon(c)} {c}</button>'
        for c in sorted(cats)
    )

    # Sections
    sections = ""
    for cat in sorted(cats):
        items   = cats[cat]
        cards   = "".join(build_card(p) for p in items)
        sections += f"""
    <section class="section" data-cat="{cat.lower()}">
      <div class="section-head">
        <span class="section-title">{cat_icon(cat)} {cat}</span>
        <span class="section-count">{len(items)} product{"s" if len(items)!=1 else ""}</span>
      </div>
      <div class="grid">{cards}</div>
    </section>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MN Legit Cannabis – South Metro Menu</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{
      --brand:#1a7a4a;--brand-lt:#e8f5ee;--text:#111827;--muted:#6b7280;
      --border:#e5e7eb;--bg:#f3f4f6;--white:#ffffff;
      --indica:#7c3aed;--sativa:#d97706;--hybrid:#0891b2;--cbd:#2563eb;--cbg:#6366f1;
      --new:#16a34a;--radius:10px;
    }}
    body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px}}
    .top-bar{{background:var(--brand);color:#fff;text-align:center;font-size:.75rem;padding:6px;letter-spacing:.3px}}
    header{{background:var(--white);border-bottom:1px solid var(--border);padding:0 24px;position:sticky;top:0;z-index:30}}
    .header-inner{{max-width:1400px;margin:0 auto;display:flex;align-items:center;gap:20px;height:64px}}
    .logo{{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1.05rem;color:var(--brand);text-decoration:none;white-space:nowrap}}
    .logo-leaf{{width:34px;height:34px;background:var(--brand);border-radius:50% 50% 50% 0;display:flex;align-items:center;justify-content:center;font-size:1rem;color:#fff;flex-shrink:0}}
    .header-meta{{margin-left:auto;text-align:right;font-size:.75rem;color:var(--muted);line-height:1.5}}
    .header-meta strong{{color:var(--brand)}}
    .tabs-wrap{{background:var(--white);border-bottom:1px solid var(--border);position:sticky;top:64px;z-index:20}}
    .tabs{{max-width:1400px;margin:0 auto;display:flex;gap:2px;overflow-x:auto;padding:0 24px;scrollbar-width:none}}
    .tabs::-webkit-scrollbar{{display:none}}
    .tab{{flex-shrink:0;padding:12px 16px;border:none;background:none;font-family:inherit;font-size:.82rem;font-weight:500;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;transition:color .15s,border-color .15s;white-space:nowrap}}
    .tab:hover{{color:var(--brand)}}
    .tab.on{{color:var(--brand);border-bottom-color:var(--brand)}}
    .legend{{display:flex;gap:14px;flex-wrap:wrap;align-items:center;padding:10px 24px;background:var(--white);border-bottom:1px solid var(--border);font-size:.74rem;color:var(--muted)}}
    .legend-item{{display:flex;align-items:center;gap:5px}}
    main{{max-width:1400px;margin:0 auto;padding:28px 24px 60px}}
    .section{{margin-bottom:44px}}
    .section-head{{display:flex;align-items:baseline;gap:10px;margin-bottom:18px}}
    .section-title{{font-size:1.1rem;font-weight:700}}
    .section-count{{font-size:.8rem;color:var(--muted)}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}}
    .card{{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;display:flex;flex-direction:column;transition:box-shadow .15s,transform .15s}}
    .card:hover{{box-shadow:0 4px 16px rgba(0,0,0,.10);transform:translateY(-2px)}}
    .card-img{{position:relative;background:#f9fafb;border-bottom:1px solid var(--border);height:170px;overflow:hidden;display:flex;align-items:center;justify-content:center}}
    .card-img img{{width:100%;height:100%;object-fit:cover;display:block}}
    .no-img{{font-size:3.2rem;color:#d1d5db}}
    .badges{{position:absolute;top:8px;left:8px;display:flex;flex-direction:column;gap:4px}}
    .strain-badge{{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.66rem;font-weight:700;letter-spacing:.3px;text-transform:uppercase;color:#fff}}
    .strain-indica{{background:var(--indica)}}.strain-sativa{{background:var(--sativa)}}
    .strain-hybrid{{background:var(--hybrid)}}.strain-cbd{{background:var(--cbd)}}
    .strain-cbg{{background:var(--cbg)}}.strain-default{{background:#6b7280}}
    .new-badge{{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.66rem;font-weight:700;letter-spacing:.3px;text-transform:uppercase;background:var(--new);color:#fff}}
    .recent-badge{{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.66rem;font-weight:700;letter-spacing:.3px;text-transform:uppercase;background:#f59e0b;color:#fff}}
    .potency-row{{position:absolute;bottom:8px;right:8px;display:flex;gap:4px}}
    .potency-pill{{background:rgba(0,0,0,.65);color:#fff;font-size:.67rem;font-weight:600;padding:2px 6px;border-radius:4px}}
    .potency-pill.thc{{background:rgba(22,163,74,.85)}}.potency-pill.cbd{{background:rgba(37,99,235,.85)}}
    .card-body{{padding:12px 13px 14px;flex:1;display:flex;flex-direction:column;gap:4px}}
    .card-brand{{font-size:.72rem;color:var(--muted);font-weight:500;text-transform:uppercase;letter-spacing:.3px}}
    .card-name{{font-size:.9rem;font-weight:600;line-height:1.3;color:var(--text)}}
    .card-weight{{font-size:.74rem;color:var(--muted)}}
    .terp-row{{display:flex;gap:4px;flex-wrap:wrap;margin-top:3px}}
    .terp{{font-size:.65rem;background:#f0fdf4;color:var(--brand);border:1px solid #bbf7d0;padding:1px 6px;border-radius:10px}}
    .effects-row{{display:flex;gap:4px;flex-wrap:wrap;margin-top:2px}}
    .effect{{font-size:.65rem;background:#eff6ff;color:#3b82f6;border:1px solid #bfdbfe;padding:1px 6px;border-radius:10px}}
    .price-section{{margin-top:auto;padding-top:10px}}
    .price-single{{font-size:1rem;font-weight:700;color:var(--brand)}}
    .price-tiers{{display:flex;gap:5px;flex-wrap:wrap}}
    .tier{{font-size:.7rem;font-weight:500;border:1px solid var(--border);border-radius:5px;padding:3px 7px;color:var(--text);background:#fafafa}}
    .tier span{{display:block;font-size:.62rem;color:var(--muted)}}
    footer{{text-align:center;padding:20px;font-size:.72rem;color:var(--muted);border-top:1px solid var(--border);background:var(--white)}}
    .hidden{{display:none!important}}
    @media(max-width:640px){{
      header{{padding:0 14px}}.tabs{{padding:0 14px}}main{{padding:18px 14px 50px}}.legend{{padding:10px 14px}}
      .grid{{grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:12px}}.card-img{{height:140px}}
    }}
  </style>
</head>
<body>
<div class="top-bar">🌿 MN Legit Cannabis · South Metro · Updated daily at 4:30 PM CST</div>
<header>
  <div class="header-inner">
    <a class="logo" href="#">
      <div class="logo-leaf">🌿</div>
      <div><div>Legit Cannabis</div><div style="font-size:.7rem;font-weight:400;color:var(--muted)">South Metro</div></div>
    </a>
    <div class="header-meta">
      <div>Last updated: <strong>{ts}</strong></div>
      <div>{len(all_p)} products in stock</div>
    </div>
  </div>
</header>
<div class="legend">
  <div class="legend-item"><span class="strain-badge strain-indica">Indica</span></div>
  <div class="legend-item"><span class="strain-badge strain-sativa">Sativa</span></div>
  <div class="legend-item"><span class="strain-badge strain-hybrid">Hybrid</span></div>
  <div class="legend-item"><span class="strain-badge strain-cbd">CBD</span></div>
  <div class="legend-item"><span class="new-badge">New Today</span> Added today</div>
  <div class="legend-item"><span class="recent-badge">New (2d)</span> Within 3 days</div>
</div>
<div class="tabs-wrap"><div class="tabs" id="tabs">{tab_btns}</div></div>
<main>{sections}</main>
<footer>Auto-updated daily at 4:30 PM CST &nbsp;·&nbsp; MN Legit Cannabis South Metro</footer>
<script>
function filterCat(btn) {{
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  const sel = btn.dataset.cat;
  document.querySelectorAll('.section').forEach(s => {{
    s.classList.toggle('hidden', sel !== 'all' && s.dataset.cat !== sel);
  }});
  window.scrollTo({{top:0,behavior:'smooth'}});
}}
</script>
</body>
</html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"Built → {OUT}  ({len(all_p)} products)")

build()
