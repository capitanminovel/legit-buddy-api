"""Renders products.json into a fully static HTML file — no JS fetch needed."""
import json
import html as _html
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
    if d == 0:        return '<span class="new-badge">New Today</span>'
    if d <= NEW_DAYS: return f'<span class="recent-badge">New ({d}d ago)</span>'
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

    # Meta row: strain type · THC% · Supplier
    strain_meta = (f'<span class="meta-strain {strain_class(p["strain_type"])}">{p["strain_type"]}</span>'
                   if p.get("strain_type") else "")
    thc_meta    = f'<span class="meta-thc">THC {p["thc"]}</span>' if p.get("thc") else ""
    brand_meta  = f'<span class="meta-brand">{p["brand"]}</span>'   if p.get("brand") else ""
    meta_parts  = [x for x in [strain_meta, thc_meta, brand_meta] if x]
    sep         = '<span class="meta-sep">·</span>'
    meta_row    = (f'<div class="card-meta">{sep.join(meta_parts)}</div>'
                   if meta_parts else "")

    terps  = "".join(f'<span class="terp">{t}</span>' for t in (p.get("terpenes") or [])[:3])
    terp_h = f'<div class="terp-row">{terps}</div>' if terps else ""

    efx   = "".join(f'<span class="effect">{e}</span>' for e in (p.get("effects") or [])[:3])
    efx_h = f'<div class="effects-row">{efx}</div>' if efx else ""

    tiers = p.get("price_tiers") or {}
    if tiers:
        chips   = "".join(f'<div class="tier">{v}<span>{TIER_LABELS.get(k,k)}</span></div>'
                          for k,v in tiers.items())
        price_h = f'<div class="price-tiers">{chips}</div>'
    elif p.get("price"):
        price_h = f'<div class="price-single">{p["price"]}</div>'
    else:
        price_h = ""

    weight_h = f'<div class="card-weight">{p["weight"]}</div>' if p.get("weight") else ""

    data_attr = _html.escape(json.dumps(p), quote=True)

    return f"""
    <div class="card" data-product="{data_attr}" onclick="openModal(this)">
      <div class="card-img">{img}{badges}{potency}</div>
      <div class="card-body">
        <div class="card-name">{p["name"]}</div>
        {meta_row}{weight_h}{terp_h}{efx_h}
        <div class="price-section">{price_h}</div>
      </div>
    </div>"""

# ── Modal JS (plain string — not an f-string so JS template literals are fine) ──
MODAL_JS = r"""
function esc(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
const CAT_ICONS_JS={flower:'🌿','pre-roll':'🚬',preroll:'🚬',edible:'🍬',edibles:'🍬',concentrate:'💎',vape:'💨',vapes:'💨'};
function catIconJs(c){return CAT_ICONS_JS[(c||'').toLowerCase()]||'🌱';}
function strainClassJs(s){
  const t=(s||'').toLowerCase();
  if(t.includes('indica'))return'strain-indica';
  if(t.includes('sativa'))return'strain-sativa';
  if(t.includes('hybrid'))return'strain-hybrid';
  if(t.includes('cbd'))return'strain-cbd';
  return'strain-default';
}
function newBadgeJs(iso){
  if(!iso)return'';
  const days=Math.floor((Date.now()-new Date(iso))/86400000);
  if(days===0)return'<span class="new-badge">New Today</span>';
  if(days<=3)return`<span class="recent-badge">New (${days}d ago)</span>`;
  return'';
}

function openModal(card){
  const p=JSON.parse(card.dataset.product);
  const ci=catIconJs(p.category||'');

  const imgHtml=p.image
    ?`<img src="${esc(p.image)}" alt="${esc(p.name)}" onerror="this.style.display='none'" style="width:100%;max-height:240px;object-fit:cover;border-radius:12px 12px 0 0">`
    :`<div style="display:flex;align-items:center;justify-content:center;height:120px;font-size:3.5rem;background:#f9fafb;border-radius:12px 12px 0 0">${ci}</div>`;

  const sc=strainClassJs(p.strain_type||'');
  const strainBadge=p.strain_type?`<span class="strain-badge ${sc}">${esc(p.strain_type)}</span>`:'';
  const ageBadge=newBadgeJs(p.first_seen||'');

  const cannabRows=[
    p.thc?`<div class="modal-canna"><span class="modal-canna-label">THC</span><span class="modal-canna-val thc-val">${esc(p.thc)}</span></div>`:'',
    p.cbd?`<div class="modal-canna"><span class="modal-canna-label">CBD</span><span class="modal-canna-val cbd-val">${esc(p.cbd)}</span></div>`:'',
    p.cbg?`<div class="modal-canna"><span class="modal-canna-label">CBG</span><span class="modal-canna-val cbg-val">${esc(p.cbg)}</span></div>`:'',
    p.cbn?`<div class="modal-canna"><span class="modal-canna-label">CBN</span><span class="modal-canna-val">${esc(p.cbn)}</span></div>`:'',
  ].filter(Boolean).join('');

  const TIER_LABELS={gram:'1g',two_gram:'2g',eighth:'⅛ oz',quarter:'¼ oz',half_ounce:'½ oz',ounce:'1 oz',unit:'Unit'};
  const tiers=p.price_tiers||{};
  let priceHtml='';
  if(Object.keys(tiers).length){
    priceHtml='<div class="price-tiers">'+Object.entries(tiers).map(([k,v])=>`<div class="tier">${esc(v)}<span>${TIER_LABELS[k]||k}</span></div>`).join('')+'</div>';
  }else if(p.price){
    priceHtml=`<div class="price-single">${esc(p.price)}</div>`;
  }

  const terpsHtml=(p.terpenes||[]).map(t=>`<span class="terp">${esc(t)}</span>`).join('');
  const efxHtml=(p.effects||[]).map(e=>`<span class="effect">${esc(e)}</span>`).join('');
  const flvHtml=(p.flavors||[]).map(f=>`<span class="flavor">${esc(f)}</span>`).join('');

  const firstSeen=p.first_seen?new Date(p.first_seen).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):'';

  document.getElementById('modal-content').innerHTML=`
    ${imgHtml}
    <div class="modal-body">
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        ${strainBadge}${ageBadge}
      </div>
      <div class="modal-name">${esc(p.name)}</div>
      ${p.brand?`<div class="modal-supplier">by ${esc(p.brand)}</div>`:''}
      ${p.weight||p.category?`<div style="font-size:.8rem;color:var(--muted);margin-top:2px">${[p.weight,p.category].filter(Boolean).map(esc).join(' · ')}</div>`:''}
      ${cannabRows?`<div class="modal-section-title">Cannabinoids</div><div class="modal-canna-row">${cannabRows}</div>`:''}
      ${priceHtml?`<div class="modal-section-title">Pricing</div>${priceHtml}`:''}
      ${terpsHtml?`<div class="modal-section-title">Terpenes</div><div class="terp-row">${terpsHtml}</div>`:''}
      ${efxHtml?`<div class="modal-section-title">Effects</div><div class="effects-row">${efxHtml}</div>`:''}
      ${flvHtml?`<div class="modal-section-title">Flavors</div><div class="flavors-row">${flvHtml}</div>`:''}
      ${p.description?`<div class="modal-section-title">About</div><div class="modal-desc">${esc(p.description)}</div>`:''}
      ${firstSeen?`<div style="font-size:.72rem;color:var(--muted);margin-top:16px;padding-top:12px;border-top:1px solid var(--border)">First seen: ${firstSeen}</div>`:''}
    </div>
  `;
  document.getElementById('modal-overlay').classList.remove('hidden');
  document.body.style.overflow='hidden';
}

function closeModal(e){
  if(e&&e.target.id!=='modal-overlay')return;
  document.getElementById('modal-overlay').classList.add('hidden');
  document.body.style.overflow='';
}
function closeModalBtn(){
  document.getElementById('modal-overlay').classList.add('hidden');
  document.body.style.overflow='';
}
document.addEventListener('keydown',function(e){
  if(e.key==='Escape')closeModalBtn();
});
"""

def build():
    with open(DATA) as f:
        db = json.load(f)

    now     = datetime.now(CST)
    ts      = now.strftime("%a, %b %d %Y — %I:%M %p CST")
    TARGET  = ("flower", "pre-roll", "vapes", "edibles")
    all_p   = [(k,v) for k,v in db["products"].items()
               if v.get("in_stock", True) and (v.get("category","").lower() in TARGET)]

    all_p.sort(key=lambda x: (age_days(x[1].get("first_seen","")), x[1].get("name","")))

    from collections import defaultdict
    cats = defaultdict(list)
    for _, p in all_p:
        cats[p.get("category") or "Other"].append(p)

    new_items = [p for _, p in all_p if age_days(p.get("first_seen","")) <= NEW_DAYS]

    new_section = ""
    if new_items:
        new_cards   = "".join(build_card(p) for p in new_items)
        new_section = f"""
    <section class="section new-arrivals-section" data-cat="all">
      <div class="new-arrivals-head">
        <span class="new-arrivals-title">✨ New in the Last 3 Days</span>
        <span class="new-arrivals-count">{len(new_items)} product{"s" if len(new_items)!=1 else ""}</span>
      </div>
      <div class="grid">{new_cards}</div>
    </section>
    <div class="section-divider" data-cat="all"></div>"""

    tab_btns  = '<button class="tab on" data-cat="all" onclick="filterCat(this)">All Products</button>\n'
    tab_btns += "\n".join(
        f'<button class="tab" data-cat="{c.lower()}" onclick="filterCat(this)">{cat_icon(c)} {c}</button>'
        for c in sorted(cats)
    )

    sections = ""
    for cat in sorted(cats):
        items    = cats[cat]
        cards    = "".join(build_card(p) for p in items)
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
    .card{{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;display:flex;flex-direction:column;transition:box-shadow .15s,transform .15s;cursor:pointer}}
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
    .card-name{{font-size:.9rem;font-weight:600;line-height:1.3;color:var(--text)}}
    .card-meta{{display:flex;align-items:center;gap:4px;flex-wrap:wrap;margin-top:3px;margin-bottom:2px}}
    .meta-strain{{font-size:.68rem;font-weight:700;padding:1px 7px;border-radius:20px;color:#fff;letter-spacing:.2px;text-transform:uppercase}}
    .meta-strain.strain-indica{{background:var(--indica)}}.meta-strain.strain-sativa{{background:var(--sativa)}}
    .meta-strain.strain-hybrid{{background:var(--hybrid)}}.meta-strain.strain-cbd{{background:var(--cbd)}}
    .meta-strain.strain-default{{background:#6b7280}}
    .meta-thc{{font-size:.72rem;font-weight:600;color:var(--new)}}
    .meta-brand{{font-size:.72rem;color:var(--muted);font-weight:500}}
    .meta-sep{{font-size:.7rem;color:#d1d5db}}
    .card-weight{{font-size:.74rem;color:var(--muted)}}
    .terp-row{{display:flex;gap:4px;flex-wrap:wrap;margin-top:3px}}
    .terp{{font-size:.65rem;background:#f0fdf4;color:var(--brand);border:1px solid #bbf7d0;padding:1px 6px;border-radius:10px}}
    .effects-row{{display:flex;gap:4px;flex-wrap:wrap;margin-top:2px}}
    .effect{{font-size:.65rem;background:#eff6ff;color:#3b82f6;border:1px solid #bfdbfe;padding:1px 6px;border-radius:10px}}
    .flavors-row{{display:flex;gap:4px;flex-wrap:wrap;margin-top:2px}}
    .flavor{{font-size:.65rem;background:#fefce8;color:#ca8a04;border:1px solid #fde68a;padding:1px 6px;border-radius:10px}}
    .price-section{{margin-top:auto;padding-top:10px}}
    .price-single{{font-size:1rem;font-weight:700;color:var(--brand)}}
    .price-tiers{{display:flex;gap:5px;flex-wrap:wrap}}
    .tier{{font-size:.7rem;font-weight:500;border:1px solid var(--border);border-radius:5px;padding:3px 7px;color:var(--text);background:#fafafa}}
    .tier span{{display:block;font-size:.62rem;color:var(--muted)}}
    footer{{text-align:center;padding:20px;font-size:.72rem;color:var(--muted);border-top:1px solid var(--border);background:var(--white)}}
    .new-arrivals-section{{background:linear-gradient(135deg,#f0fdf4,#ecfdf5);border:2px solid #86efac;border-radius:12px;padding:20px;margin-bottom:32px}}
    .new-arrivals-head{{display:flex;align-items:baseline;gap:10px;margin-bottom:18px}}
    .new-arrivals-title{{font-size:1.15rem;font-weight:700;color:var(--new)}}
    .new-arrivals-count{{font-size:.8rem;color:var(--muted)}}
    .section-divider{{height:2px;background:linear-gradient(90deg,var(--brand-lt),transparent);margin:0 0 36px;border-radius:1px}}
    .hidden{{display:none!important}}
    /* Modal */
    .modal-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:100;display:flex;align-items:center;justify-content:center;padding:20px}}
    .modal-box{{background:var(--white);border-radius:14px;width:100%;max-width:480px;max-height:90vh;overflow-y:auto;position:relative;box-shadow:0 20px 60px rgba(0,0,0,.3)}}
    .modal-close{{position:sticky;top:10px;float:right;margin:10px 10px 0 0;background:rgba(0,0,0,.45);border:none;color:#fff;width:30px;height:30px;border-radius:50%;cursor:pointer;font-size:1rem;display:flex;align-items:center;justify-content:center;flex-shrink:0;z-index:5}}
    .modal-close:hover{{background:rgba(0,0,0,.65)}}
    .modal-body{{padding:14px 18px 24px;clear:both}}
    .modal-name{{font-size:1.25rem;font-weight:700;line-height:1.3;color:var(--text);margin-top:4px}}
    .modal-supplier{{font-size:.82rem;color:var(--muted);margin-top:3px;font-weight:500}}
    .modal-section-title{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-top:18px;margin-bottom:7px;border-top:1px solid var(--border);padding-top:12px}}
    .modal-canna-row{{display:flex;gap:10px;flex-wrap:wrap}}
    .modal-canna{{display:flex;flex-direction:column;align-items:center;background:#f9fafb;border:1px solid var(--border);border-radius:8px;padding:8px 14px;min-width:70px}}
    .modal-canna-label{{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--muted)}}
    .modal-canna-val{{font-size:1.1rem;font-weight:700;color:var(--text)}}
    .thc-val{{color:var(--new)}}.cbd-val{{color:var(--cbd)}}.cbg-val{{color:var(--cbg)}}
    .modal-desc{{font-size:.85rem;color:#374151;line-height:1.65}}
    @media(max-width:640px){{
      header{{padding:0 14px}}.tabs{{padding:0 14px}}main{{padding:18px 14px 50px}}.legend{{padding:10px 14px}}
      .grid{{grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:12px}}.card-img{{height:140px}}
      .modal-overlay{{padding:10px}}.modal-box{{max-height:95vh}}
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
  <div class="legend-item" style="margin-left:auto;font-size:.72rem;color:var(--muted)">Tap a card for full details</div>
</div>
<div class="tabs-wrap"><div class="tabs" id="tabs">{tab_btns}</div></div>
<main>{new_section}{sections}</main>
<footer>Auto-updated daily at 4:30 PM CST &nbsp;·&nbsp; MN Legit Cannabis South Metro</footer>

<!-- Product detail modal -->
<div id="modal-overlay" class="modal-overlay hidden" onclick="closeModal(event)">
  <div class="modal-box" id="modal-box">
    <button class="modal-close" onclick="closeModalBtn()">✕</button>
    <div id="modal-content"></div>
  </div>
</div>

<script>
{MODAL_JS}
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
