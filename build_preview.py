"""Renders products.json into a fully static HTML file — no JS fetch needed."""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

CST          = timezone(timedelta(hours=-6))
DATA         = Path(__file__).parent / "docs" / "products.json"
STRAINS_DATA = Path(__file__).parent / "docs" / "strains_enriched.json"
OUT          = Path(__file__).parent / "docs" / "index.html"
NEW_DAYS     = 2

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

def build_card(p, key):
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

    effects_csv  = ",".join(p.get("effects")  or [])
    terpenes_csv = ",".join(p.get("terpenes") or [])

    return f"""
    <div class="card" data-key="{key}" data-effects="{effects_csv}" data-terpenes="{terpenes_csv}" onclick="openModal('{key}')">
      <div class="card-img">{img}{badges}{potency}</div>
      <div class="card-body">
        {brand_h}
        <div class="card-name">{p["name"]}</div>
        {weight_h}{minor_h}{terp_h}{efx_h}
        <div class="price-section">{price_h}</div>
        <div class="card-detail-hint">Tap for strain guide →</div>
      </div>
    </div>"""

def build():
    with open(DATA) as f:
        db = json.load(f)

    strains = {}
    if STRAINS_DATA.exists():
        with open(STRAINS_DATA) as f:
            strains = json.load(f)

    now     = datetime.now(CST)
    ts      = now.strftime("%a, %b %d %Y — %I:%M %p CST")
    TARGET  = ("flower", "pre-roll", "vapes", "edibles")
    all_p   = [(k,v) for k,v in db["products"].items()
               if v.get("in_stock", True) and (v.get("category","").lower() in TARGET)]

    all_p.sort(key=lambda x: (age_days(x[1].get("first_seen","")), x[1].get("name","")))

    from collections import defaultdict
    cats = defaultdict(list)
    for k, p in all_p:
        cats[p.get("category") or "Other"].append((k, p))

    new_items = [(k, p) for k, p in all_p if age_days(p.get("first_seen","")) <= NEW_DAYS]

    new_section = ""
    if new_items:
        new_cards = "".join(build_card(p, k) for k, p in new_items)
        n = len(new_items)
        new_section = f"""
    <section class="section new-arrivals-section" data-cat="all">
      <div class="new-arrivals-head">
        <span class="new-arrivals-title">✨ New in the Last 3 Days</span>
        <span class="new-arrivals-count" data-total="{n}">{n} product{"s" if n!=1 else ""}</span>
      </div>
      <div class="grid">{new_cards}</div>
    </section>
    <div class="section-divider" data-cat="all"></div>"""

    tab_btns = '<button class="tab on" data-cat="all" onclick="filterCat(this)">All Products</button>\n'
    tab_btns += "\n".join(
        f'<button class="tab" data-cat="{c.lower()}" onclick="filterCat(this)">{cat_icon(c)} {c}</button>'
        for c in sorted(cats)
    )

    sections = ""
    for cat in sorted(cats):
        items = cats[cat]
        cards = "".join(build_card(p, k) for k, p in items)
        n = len(items)
        sections += f"""
    <section class="section" data-cat="{cat.lower()}">
      <div class="section-head">
        <span class="section-title">{cat_icon(cat)} {cat}</span>
        <span class="section-count" data-total="{n}">{n} product{"s" if n!=1 else ""}</span>
      </div>
      <div class="grid">{cards}</div>
    </section>"""

    # Embed all product data + strain enrichment as JS
    products_js = json.dumps({k: v for k, v in db["products"].items()}, ensure_ascii=False)
    strains_js  = json.dumps(strains, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MN Legit Cannabis – South Metro Menu</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Nunito:wght@700;800;900&family=Nunito+Sans:wght@400;600&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{
      --brand:#1a7a4a;--brand-lt:#e8f5ee;--text:#111827;--muted:#6b7280;
      --border:#e5e7eb;--bg:#f3f4f6;--white:#ffffff;
      --indica:#7c3aed;--sativa:#d97706;--hybrid:#0891b2;--cbd:#2563eb;--cbg:#6366f1;
      --new:#16a34a;--radius:10px;
      --sg-green:#3d5c2e;--sg-pink:#e88fa2;--sg-cream:#f5f0e8;
      --sg-dark:#2a3f1f;--sg-border:#4a7030;
    }}
    body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px}}
    .top-bar{{background:var(--brand);color:#fff;text-align:center;font-size:.75rem;padding:6px;letter-spacing:.3px}}
    header{{background:var(--white);border-bottom:1px solid var(--border);padding:0 24px;position:sticky;top:0;z-index:30}}
    .header-inner{{max-width:1400px;margin:0 auto;display:flex;align-items:center;gap:20px;height:64px}}
    .logo{{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1.05rem;color:var(--brand);text-decoration:none;white-space:nowrap}}
    .logo-leaf{{width:34px;height:34px;background:var(--brand);border-radius:50% 50% 50% 0;display:flex;align-items:center;justify-content:center;font-size:1rem;color:#fff;flex-shrink:0}}
    @keyframes mascot-bob{{0%,100%{{transform:translateY(0) rotate(-1deg)}}50%{{transform:translateY(-6px) rotate(1deg)}}}}
    @keyframes mascot-blink{{0%,90%,100%{{transform:scaleY(1)}}95%{{transform:scaleY(0.1)}}}}
    .mascot-wrap{{animation:mascot-bob 3s ease-in-out infinite;flex-shrink:0;cursor:default;user-select:none}}
    .mascot-wrap:hover{{animation-duration:1s}}
    .mascot-eye{{animation:mascot-blink 4s ease-in-out infinite}}
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
    main{{max-width:1400px;margin:0 auto;padding:28px 24px 100px}}
    .section{{margin-bottom:44px}}
    .section-head{{display:flex;align-items:baseline;gap:10px;margin-bottom:18px}}
    .section-title{{font-size:1.1rem;font-weight:700}}
    .section-count{{font-size:.8rem;color:var(--muted)}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}}
    .card{{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;display:flex;flex-direction:column;transition:box-shadow .15s,transform .15s;cursor:pointer}}
    .card:hover{{box-shadow:0 4px 16px rgba(0,0,0,.12);transform:translateY(-2px)}}
    .card:hover .card-detail-hint{{opacity:1}}
    .card-detail-hint{{font-size:.67rem;color:var(--brand);font-weight:600;text-align:center;padding:4px 0 0;opacity:0;transition:opacity .15s;letter-spacing:.2px}}
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
    .new-arrivals-section{{background:linear-gradient(135deg,#f0fdf4,#ecfdf5);border:2px solid #86efac;border-radius:12px;padding:20px;margin-bottom:32px}}
    .new-arrivals-head{{display:flex;align-items:baseline;gap:10px;margin-bottom:18px}}
    .new-arrivals-title{{font-size:1.15rem;font-weight:700;color:var(--new)}}
    .new-arrivals-count{{font-size:.8rem;color:var(--muted)}}
    .section-divider{{height:2px;background:linear-gradient(90deg,var(--brand-lt),transparent);margin:0 0 36px;border-radius:1px}}
    .hidden{{display:none!important}}

    /* ── Mood / Effect filter bar ── */
    .mood-bar{{background:var(--white);border:1px solid var(--border);border-radius:12px;padding:14px 18px;margin-bottom:24px;display:flex;flex-direction:column;gap:10px}}
    .mood-bar-top{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
    .mood-bar-label{{font-size:.78rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;white-space:nowrap}}
    .mood-chips{{display:flex;gap:7px;flex-wrap:wrap;flex:1}}
    .mood-chip{{border:1.5px solid var(--border);background:var(--bg);color:var(--text);border-radius:20px;padding:6px 13px;font-size:.78rem;font-weight:600;cursor:pointer;transition:all .15s;white-space:nowrap;font-family:inherit}}
    .mood-chip:hover{{border-color:var(--sg-green);color:var(--sg-green);background:#f0fdf4}}
    .mood-chip.on{{background:var(--sg-green);color:var(--sg-pink);border-color:var(--sg-green);font-weight:700}}
    .mood-clear{{border:none;background:none;color:var(--muted);font-size:.78rem;font-weight:600;cursor:pointer;padding:6px 8px;border-radius:20px;white-space:nowrap;font-family:inherit}}
    .mood-clear:hover{{color:#e53e3e}}
    .mood-status{{font-size:.78rem;color:var(--sg-green);font-weight:500;padding:2px 0 0;line-height:1.45}}
    .mood-status strong{{font-weight:700}}
    .mood-zero{{font-size:.85rem;color:var(--muted);text-align:center;padding:32px 0;font-weight:500}}

    /* ── Text search ── */
    .search-row{{display:flex;align-items:center;gap:8px}}
    .search-wrap{{position:relative;flex:1;max-width:520px}}
    .search-icon{{position:absolute;left:11px;top:50%;transform:translateY(-50%);font-size:.85rem;pointer-events:none}}
    .search-input{{width:100%;border:1.5px solid var(--border);border-radius:24px;padding:8px 36px 8px 32px;font-size:.82rem;font-family:inherit;outline:none;background:var(--bg);color:var(--text);transition:border-color .15s}}
    .search-input:focus{{border-color:var(--sg-green);background:#fff}}
    .search-input::placeholder{{color:#aaa}}
    .search-clear{{position:absolute;right:10px;top:50%;transform:translateY(-50%);border:none;background:none;color:#aaa;font-size:1rem;cursor:pointer;padding:2px;line-height:1}}
    .search-clear:hover{{color:#e53e3e}}

    @media(max-width:640px){{
      header{{padding:0 14px}}.tabs{{padding:0 14px}}main{{padding:18px 14px 100px}}.legend{{padding:10px 14px}}
      .grid{{grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:12px}}.card-img{{height:140px}}
      .mood-bar{{padding:12px 14px}}.mood-chips{{gap:5px}}.mood-chip{{font-size:.73rem;padding:5px 10px}}
    }}

    /* ── Modal overlay ── */
    .modal-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:1000;display:flex;align-items:center;justify-content:center;padding:16px;opacity:0;pointer-events:none;transition:opacity .2s}}
    .modal-overlay.open{{opacity:1;pointer-events:all}}
    .modal-box{{background:#e8e0d0;border-radius:18px;max-width:620px;width:100%;max-height:90vh;overflow-y:auto;position:relative;transform:scale(.95);transition:transform .2s;font-family:'Nunito Sans',sans-serif}}
    .modal-overlay.open .modal-box{{transform:scale(1)}}
    .modal-close{{position:sticky;top:12px;float:right;margin:12px 16px 0 0;background:var(--sg-green);color:var(--sg-pink);border:none;border-radius:50%;width:32px;height:32px;font-size:1.1rem;cursor:pointer;font-weight:900;line-height:32px;text-align:center;z-index:10;flex-shrink:0}}
    .modal-close:hover{{background:var(--sg-dark)}}
    .modal-inner{{padding:16px 22px 22px;clear:both}}

    /* ── Strain card (inside modal) — matches legit_strain_guide.html ── */
    .sg-card{{background:white;border:3px solid var(--sg-border);border-radius:16px;padding:18px 22px;margin-bottom:14px}}
    .sg-name{{font-family:'Nunito',sans-serif;font-weight:900;font-size:22px;text-align:center;text-transform:uppercase;letter-spacing:.05em;color:var(--sg-dark);margin-bottom:2px}}
    .sg-type{{text-align:center;font-size:12.5px;font-weight:700;color:#555;margin-bottom:4px}}
    .sg-supplier{{display:block;background:var(--sg-green);color:var(--sg-pink);font-family:'Nunito',sans-serif;font-weight:800;font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;border-radius:20px;padding:3px 10px;width:fit-content;margin:0 auto 10px}}
    .sg-divider{{border:none;border-top:2px solid var(--sg-border);margin:8px 0 12px}}
    .sg-row{{font-size:12.5px;line-height:1.55;margin-bottom:4px;color:#222}}
    .sg-row strong{{font-weight:700;color:var(--sg-dark);font-family:'Nunito',sans-serif;font-size:12.5px}}
    .sg-thc-cbd{{display:flex;gap:8px;justify-content:center;margin-bottom:8px;flex-wrap:wrap}}
    .sg-pill{{font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px;font-family:'Nunito',sans-serif}}
    .sg-pill.thc{{background:#16a34a;color:#fff}}.sg-pill.cbd{{background:#2563eb;color:#fff}}
    .sg-price{{text-align:center;font-size:13px;font-weight:700;color:var(--sg-dark);margin-bottom:6px}}
    .modal-actions{{display:flex;gap:10px;margin-top:16px;justify-content:center;flex-wrap:wrap}}
    .btn-add-profile{{background:var(--sg-green);color:var(--sg-pink);border:none;border-radius:24px;padding:10px 22px;font-family:'Nunito',sans-serif;font-weight:800;font-size:13px;letter-spacing:.05em;text-transform:uppercase;cursor:pointer;transition:background .15s}}
    .btn-add-profile:hover{{background:var(--sg-dark)}}
    .btn-add-profile.added{{background:#6b7280;color:#fff}}
    .btn-close-modal{{background:transparent;color:var(--sg-green);border:2px solid var(--sg-green);border-radius:24px;padding:10px 22px;font-family:'Nunito',sans-serif;font-weight:800;font-size:13px;letter-spacing:.05em;text-transform:uppercase;cursor:pointer}}

    /* ── Profile floating button ── */
    .profile-fab{{position:fixed;bottom:28px;right:24px;background:var(--sg-green);color:var(--sg-pink);border:none;border-radius:30px;padding:12px 20px;font-family:'Nunito',sans-serif;font-weight:900;font-size:13px;letter-spacing:.05em;text-transform:uppercase;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.25);z-index:500;display:none;align-items:center;gap:8px;transition:background .15s,transform .1s}}
    .profile-fab:hover{{background:var(--sg-dark);transform:scale(1.04)}}
    .profile-fab-count{{background:var(--sg-pink);color:var(--sg-dark);border-radius:50%;width:22px;height:22px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:900}}

    /* ── Profile drawer ── */
    .profile-drawer{{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:1100;display:none;align-items:flex-end;justify-content:center}}
    .profile-drawer.open{{display:flex}}
    .profile-box{{background:#e8e0d0;width:100%;max-width:680px;max-height:85vh;border-radius:18px 18px 0 0;overflow-y:auto;padding:0 0 30px}}
    .profile-header{{display:flex;align-items:center;justify-content:space-between;padding:18px 22px 14px;background:#e8e0d0;position:sticky;top:0;border-bottom:2px solid var(--sg-border)}}
    .profile-header-title{{font-family:'Nunito',sans-serif;font-weight:900;font-size:18px;color:var(--sg-dark);text-transform:uppercase;letter-spacing:.05em}}
    .profile-header-actions{{display:flex;gap:8px;flex-wrap:wrap}}
    .btn-export{{background:var(--sg-green);color:var(--sg-pink);border:none;border-radius:20px;padding:8px 16px;font-family:'Nunito',sans-serif;font-weight:800;font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;cursor:pointer}}
    .btn-export:hover{{background:var(--sg-dark)}}
    .btn-clear{{background:transparent;color:#888;border:1px solid #ccc;border-radius:20px;padding:8px 14px;font-family:'Nunito',sans-serif;font-weight:700;font-size:11px;text-transform:uppercase;cursor:pointer}}
    .btn-close-drawer{{background:transparent;color:var(--sg-green);border:2px solid var(--sg-green);border-radius:20px;padding:8px 14px;font-family:'Nunito',sans-serif;font-weight:800;font-size:11px;text-transform:uppercase;cursor:pointer}}
    .profile-cards{{padding:16px 18px 0}}
    .profile-empty{{text-align:center;padding:40px;color:#888;font-family:'Nunito',sans-serif;font-weight:700;font-size:14px}}
    .profile-item-remove{{position:absolute;top:10px;right:12px;background:transparent;border:none;color:#aaa;font-size:18px;cursor:pointer;font-weight:700;line-height:1}}
    .profile-item-remove:hover{{color:#e53e3e}}
    @media(max-width:640px){{
      .modal-box{{max-height:95vh;border-radius:14px}}
      .profile-box{{max-height:92vh}}
      .modal-inner{{padding:12px 14px 18px}}
    }}
  </style>
</head>
<body>
<div class="top-bar">🌿 MN Legit Cannabis · South Metro · Updated daily at 4:30 PM CST</div>
<header>
  <div class="header-inner">
    <div class="mascot-wrap" title="Legit Buddy 🌿">
      <svg viewBox="0 0 60 74" width="46" height="46" xmlns="http://www.w3.org/2000/svg">
        <ellipse cx="22" cy="18" rx="5.5" ry="15" fill="#7dc45a" stroke="#2d5a1b" stroke-width="1.5" transform="rotate(-22 22 18)"/>
        <ellipse cx="30" cy="12" rx="5.5" ry="17" fill="#7dc45a" stroke="#2d5a1b" stroke-width="1.5"/>
        <ellipse cx="38" cy="18" rx="5.5" ry="15" fill="#7dc45a" stroke="#2d5a1b" stroke-width="1.5" transform="rotate(22 38 18)"/>
        <circle cx="30" cy="50" r="17" fill="#7079c0" stroke="#2d3a6e" stroke-width="1.5"/>
        <ellipse class="mascot-eye" cx="23" cy="48" rx="2.8" ry="2.8" fill="#e53e3e"/>
        <ellipse class="mascot-eye" cx="37" cy="48" rx="2.8" ry="2.8" fill="#e53e3e"/>
        <path d="M23 56 Q30 62 37 56" stroke="#2d3a6e" stroke-width="1.8" fill="none" stroke-linecap="round"/>
        <ellipse cx="22" cy="66" rx="6" ry="4.5" fill="#5a63a8" stroke="#2d3a6e" stroke-width="1"/>
        <ellipse cx="38" cy="66" rx="6" ry="4.5" fill="#5a63a8" stroke="#2d3a6e" stroke-width="1"/>
      </svg>
    </div>
    <a class="logo" href="#">
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
  <div class="legend-item" style="margin-left:auto;color:var(--brand);font-weight:600">Tap any product for strain guide →</div>
</div>
<div class="tabs-wrap"><div class="tabs" id="tabs">{tab_btns}</div></div>
<main>
  <div class="mood-bar" id="moodBar">
    <div class="mood-bar-top">
      <span class="mood-bar-label">Find your vibe</span>
      <div class="mood-chips" id="moodChips">
        <button class="mood-chip" data-mood="wind-down"      onclick="filterMood(this)" title="Myrcene + Linalool — muscle relaxation, sedation, GABAergic calm (Russo 2011)">😴 Wind Down</button>
        <button class="mood-chip" data-mood="anxiety-relief" onclick="filterMood(this)" title="Caryophyllene + Linalool + Limonene — the Kamal anxiolytic chemotype (Kamal et al. 2018, Front Neurosci)">🧘 Anxiety Relief</button>
        <button class="mood-chip" data-mood="lift-up"        onclick="filterMood(this)" title="Limonene + Terpinolene + Ocimene — mood elevation, citrus-forward uplift">⬆ Lift Up</button>
        <button class="mood-chip" data-mood="get-creative"   onclick="filterMood(this)" title="Pinene + Terpinolene — AChE inhibition sharpens focus; terpinolene drives cerebral creativity">🎨 Get Creative</button>
        <button class="mood-chip" data-mood="get-social"     onclick="filterMood(this)" title="Limonene + Terpinolene — euphoria, giggles, sociability without heavy sedation">😄 Get Social</button>
        <button class="mood-chip" data-mood="pain-body"      onclick="filterMood(this)" title="Caryophyllene (CB2 agonist) + Myrcene + Humulene — anti-inflammatory, analgesic, muscle relaxant">💆 Pain &amp; Body</button>
        <button class="mood-chip" data-mood="just-happy"     onclick="filterMood(this)" title="Limonene + Linalool — balanced euphoria and body warmth">✨ Just Happy</button>
      </div>
      <button class="mood-clear hidden" id="moodClear" onclick="clearMood()">✕ Mood</button>
    </div>
    <div class="search-row">
      <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" class="search-input"
               placeholder="Search: anxiety, PTSD, sleep, pain, creative, Myrcene…"
               oninput="handleSearch(this.value)">
        <button class="search-clear hidden" id="searchClear" onclick="clearSearch()">✕</button>
      </div>
    </div>
    <div class="mood-status hidden" id="moodStatus"></div>
  </div>
  {new_section}{sections}
  <div class="mood-zero hidden" id="moodZero">No products match this vibe right now — try another filter.</div>
</main>
<footer>Auto-updated daily at 4:30 PM CST &nbsp;·&nbsp; MN Legit Cannabis South Metro</footer>

<!-- Strain modal -->
<div class="modal-overlay" id="strainModal" onclick="closeModalOutside(event)">
  <div class="modal-box">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-inner">
      <div id="modalCard"></div>
      <div class="modal-actions">
        <button class="btn-add-profile" id="btnAddProfile" onclick="toggleProfile()">＋ Add to Profile</button>
        <button class="btn-close-modal" onclick="closeModal()">Close</button>
      </div>
    </div>
  </div>
</div>

<!-- Profile drawer -->
<div class="profile-drawer" id="profileDrawer">
  <div class="profile-box">
    <div class="profile-header">
      <div class="profile-header-title">📋 Strain Profile</div>
      <div class="profile-header-actions">
        <button class="btn-export" onclick="exportGuide()">⬇ Download Strain Guide</button>
        <button class="btn-clear" onclick="clearProfile()">Clear All</button>
        <button class="btn-close-drawer" onclick="closeDrawer()">Close</button>
      </div>
    </div>
    <div class="profile-cards" id="profileCards">
      <div class="profile-empty" id="profileEmpty">No strains added yet.<br>Tap any product card, then "Add to Profile."</div>
    </div>
  </div>
</div>

<!-- Floating profile button -->
<button class="profile-fab" id="profileFab" onclick="openDrawer()">
  📋 My Profile <span class="profile-fab-count" id="fabCount">0</span>
</button>

<script>
const PRODUCTS = {products_js};
const STRAINS  = {strains_js};

// ── Mood map: effects + terpenes that predict each vibe ──
// Sources: Russo 2011 Br J Pharmacol; Kamal et al. 2018 Front Neurosci;
//          Smith et al. 2022 PLOS ONE (terpenes > indica/sativa label)
const MOOD_MAP = {{
  'wind-down': {{
    label: 'Wind Down',
    science: 'Myrcene + Linalool stack — sedation, muscle relaxation, GABAergic calm',
    effects:  ['Sleepy','Relaxing','Calming','Chill','Body High','Unbothered'],
    terpenes: ['Myrcene','Linalool']
  }},
  'anxiety-relief': {{
    label: 'Anxiety Relief',
    science: 'Caryophyllene (CB2) + Linalool (GABA) + Limonene (5-HT1A) — Kamal 2018 anxiolytic chemotype',
    effects:  ['Calming','Chill','Relaxing','Unbothered','Blissful'],
    terpenes: ['Caryophyllene','Linalool','Limonene']
  }},
  'lift-up': {{
    label: 'Lift Up',
    science: 'Limonene mood elevation (Komori 1995) + Terpinolene cerebral uplift + Ocimene/Valencene citrus energy',
    effects:  ['Uplifting','Euphoric','Happy','Blissful','Energetic'],
    terpenes: ['Limonene','Terpinolene','Ocimene','Valencene']
  }},
  'get-creative': {{
    label: 'Get Creative',
    science: 'Pinene AChE inhibition sharpens memory + Terpinolene cerebral drive (Miyazawa & Yamafuji 2005)',
    effects:  ['Creative','Cerebral','Focused'],
    terpenes: ['Pinene','B Pinene','Terpinolene','Limonene']
  }},
  'get-social': {{
    label: 'Get Social',
    science: 'Limonene + Terpinolene — euphoria and giggles without heavy sedation',
    effects:  ['Social','Giggly','Talkative','Happy','Euphoric'],
    terpenes: ['Limonene','Terpinolene']
  }},
  'pain-body': {{
    label: 'Pain & Body',
    science: 'Caryophyllene (CB2 agonist, Gertsch 2008 PNAS) + Myrcene analgesic + Humulene anti-inflammatory',
    effects:  ['Body High','Tingly','Relaxing'],
    terpenes: ['Caryophyllene','Myrcene','Humulene','Linalool','Bisabolol']
  }},
  'just-happy': {{
    label: 'Just Happy',
    science: 'Limonene + Linalool + Terpinolene — balanced euphoria and body warmth',
    effects:  ['Happy','Euphoric','Blissful','Giggly','Tingly','Uplifting'],
    terpenes: ['Limonene','Linalool','Terpinolene']
  }}
}};

let currentKey   = null;
let profileKeys  = [];
let activeMood   = null;
let activeCat    = 'all';
let activeSearch = '';
let searchTimer  = null;

function fmtList(arr) {{
  if (!arr || !arr.length) return '—';
  return arr.join(', ');
}}

function buildSgCard(key, forExport) {{
  const p = PRODUCTS[key] || {{}};
  const s = STRAINS[key]  || {{}};
  const thcPill = p.thc ? `<span class="sg-pill thc">THC ${{p.thc}}</span>` : '';
  const cbdPill = p.cbd ? `<span class="sg-pill cbd">CBD ${{p.cbd}}</span>` : '';
  const pills   = (thcPill || cbdPill) ? `<div class="sg-thc-cbd">${{thcPill}}${{cbdPill}}</div>` : '';
  const price   = p.price ? `<div class="sg-price">${{p.price}}${{p.weight ? ' · ' + p.weight : ''}}</div>` : '';
  const removeBtn = forExport ? '' : `<button class="profile-item-remove" onclick="removeFromProfile('${{key}}')" title="Remove">✕</button>`;

  const rows = [
    s.lineage     ? `<div class="sg-row"><strong>Lineage:</strong> ${{s.lineage}}</div>` : '',
    p.effects?.length ? `<div class="sg-row"><strong>Effects:</strong> ${{fmtList(p.effects)}}</div>` : '',
    p.flavors?.length ? `<div class="sg-row"><strong>Flavors:</strong> ${{fmtList(p.flavors)}}</div>` : '',
    p.terpenes?.length ? `<div class="sg-row"><strong>Terpenes:</strong> ${{fmtList(p.terpenes)}}</div>` : '',
    s.therapeutic ? `<div class="sg-row"><strong>Therapeutic:</strong> ${{s.therapeutic}}</div>` : '',
    s.negative    ? `<div class="sg-row"><strong>Negative:</strong> ${{s.negative}}</div>` : '',
    s.aroma       ? `<div class="sg-row"><strong>Aroma:</strong> ${{s.aroma}}</div>` : '',
    s.misc        ? `<div class="sg-row"><strong>Misc:</strong> ${{s.misc}}</div>` : '',
  ].join('');

  return `
  <div class="sg-card" style="position:relative">
    ${{removeBtn}}
    <div class="sg-name">${{p.name || 'Unknown'}}</div>
    <div class="sg-type">${{p.strain_type ? '— ' + p.strain_type : ''}}</div>
    <span class="sg-supplier">${{p.brand || 'Unknown'}}</span>
    ${{pills}}${{price}}
    <hr class="sg-divider">
    ${{rows}}
  </div>`;
}}

function openModal(key) {{
  currentKey = key;
  const p = PRODUCTS[key] || {{}};
  document.getElementById('modalCard').innerHTML = buildSgCard(key, false);
  const btn = document.getElementById('btnAddProfile');
  const inProfile = profileKeys.includes(key);
  btn.textContent = inProfile ? '✓ In Profile' : '＋ Add to Profile';
  btn.classList.toggle('added', inProfile);
  document.getElementById('strainModal').classList.add('open');
  document.body.style.overflow = 'hidden';
}}

function closeModal() {{
  document.getElementById('strainModal').classList.remove('open');
  document.body.style.overflow = '';
}}

function closeModalOutside(e) {{
  if (e.target === document.getElementById('strainModal')) closeModal();
}}

function toggleProfile() {{
  if (!currentKey) return;
  const idx = profileKeys.indexOf(currentKey);
  if (idx === -1) {{
    profileKeys.push(currentKey);
  }} else {{
    profileKeys.splice(idx, 1);
  }}
  const btn = document.getElementById('btnAddProfile');
  const inProfile = profileKeys.includes(currentKey);
  btn.textContent = inProfile ? '✓ In Profile' : '＋ Add to Profile';
  btn.classList.toggle('added', inProfile);
  updateFab();
}}

function removeFromProfile(key) {{
  profileKeys = profileKeys.filter(k => k !== key);
  updateFab();
  renderProfileCards();
}}

function updateFab() {{
  const fab = document.getElementById('profileFab');
  document.getElementById('fabCount').textContent = profileKeys.length;
  fab.style.display = profileKeys.length > 0 ? 'flex' : 'none';
}}

function renderProfileCards() {{
  const el = document.getElementById('profileCards');
  const empty = document.getElementById('profileEmpty');
  if (profileKeys.length === 0) {{
    empty.style.display = 'block';
    el.innerHTML = '';
    el.appendChild(empty);
    return;
  }}
  empty.style.display = 'none';
  el.innerHTML = profileKeys.map(k => buildSgCard(k, false)).join('');
}}

function openDrawer() {{
  renderProfileCards();
  document.getElementById('profileDrawer').classList.add('open');
  document.body.style.overflow = 'hidden';
}}

function closeDrawer() {{
  document.getElementById('profileDrawer').classList.remove('open');
  document.body.style.overflow = '';
}}

function clearProfile() {{
  profileKeys = [];
  updateFab();
  renderProfileCards();
}}

function exportGuide() {{
  if (profileKeys.length === 0) return;
  const cards = profileKeys.map(k => buildSgCard(k, true)).join('');
  const today = new Date().toLocaleDateString('en-US', {{month:'long', day:'numeric', year:'numeric'}});
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Legit Cannabis – Strain Guide</title>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@700;800;900&family=Nunito+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root{{--green:#3d5c2e;--pink:#e88fa2;--cream:#f5f0e8;--dark-green:#2a3f1f;--border-green:#4a7030;--text:#1a1a1a}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#e8e0d0;font-family:'Nunito Sans',sans-serif;padding:24px 16px;color:var(--text)}}
  .page{{max-width:720px;margin:0 auto}}
  .header{{display:flex;align-items:center;gap:16px;margin-bottom:28px}}
  .logo-badge{{background:var(--green);border-radius:14px;padding:10px 16px;display:flex;align-items:center;gap:8px}}
  .logo-badge .leaf{{font-size:20px}}
  .logo-badge .name{{font-family:'Nunito',sans-serif;font-weight:900;font-size:15px;color:var(--pink);line-height:1.1;letter-spacing:.02em;text-transform:uppercase}}
  .header-title{{font-family:'Nunito',sans-serif;font-weight:900;font-size:26px;color:var(--dark-green);letter-spacing:.04em;text-transform:uppercase}}
  .header-sub{{font-size:12px;color:var(--green);font-weight:600;letter-spacing:.06em;text-transform:uppercase;margin-top:2px}}
  .sg-card{{background:white;border:3px solid var(--border-green);border-radius:16px;padding:18px 22px;margin-bottom:18px}}
  .sg-name{{font-family:'Nunito',sans-serif;font-weight:900;font-size:22px;text-align:center;text-transform:uppercase;letter-spacing:.05em;color:var(--dark-green);margin-bottom:2px}}
  .sg-type{{text-align:center;font-size:12.5px;font-weight:700;color:#555;margin-bottom:4px}}
  .sg-supplier{{display:block;background:var(--green);color:var(--pink);font-family:'Nunito',sans-serif;font-weight:800;font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;border-radius:20px;padding:3px 10px;width:fit-content;margin:0 auto 10px}}
  .sg-thc-cbd{{display:flex;gap:8px;justify-content:center;margin-bottom:8px;flex-wrap:wrap}}
  .sg-pill{{font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px;font-family:'Nunito',sans-serif}}
  .sg-pill.thc{{background:#16a34a;color:#fff}}.sg-pill.cbd{{background:#2563eb;color:#fff}}
  .sg-price{{text-align:center;font-size:13px;font-weight:700;color:var(--dark-green);margin-bottom:6px}}
  .sg-divider{{border:none;border-top:2px solid var(--border-green);margin:8px 0 12px}}
  .sg-row{{font-size:12.5px;line-height:1.55;margin-bottom:4px;color:#222}}
  .sg-row strong{{font-weight:700;color:var(--dark-green);font-family:'Nunito',sans-serif;font-size:12.5px}}
  .profile-item-remove{{display:none}}
  @media print{{body{{background:white;padding:0}}.sg-card{{break-inside:avoid}}}}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    <div class="logo-badge"><span class="leaf">🍃</span><div class="name">LEGIT<br>CANNABIS</div></div>
    <div><div class="header-title">Strain Guide</div><div class="header-sub">Staff Reference · ${{today}}</div></div>
  </div>
  ${{cards}}
</div>
</body>
</html>`;

  const blob = new Blob([html], {{type: 'text/html;charset=utf-8'}});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = 'legit-strain-guide.html';
  a.click();
  URL.revokeObjectURL(url);
}}

// ── Category + mood + text search combined filter ──
function applyFilters() {{
  const mood = activeMood ? MOOD_MAP[activeMood] : null;
  const q    = activeSearch;
  let totalVisible = 0;

  document.querySelectorAll('.card').forEach(card => {{
    const key = card.dataset.key;

    // Category check
    const section = card.closest('.section');
    const catOk = activeCat === 'all' || (section && section.dataset.cat === activeCat);

    // Mood check — match on effects OR terpenes
    let moodOk = true;
    if (mood) {{
      const cardEffects  = (card.dataset.effects  || '').split(',').filter(Boolean);
      const cardTerpenes = (card.dataset.terpenes || '').split(',').filter(Boolean);
      moodOk = mood.effects.some(e  => cardEffects.includes(e))
             || mood.terpenes.some(t => cardTerpenes.includes(t));
    }}

    // Text search — searches name, brand, strain type, effects, terpenes,
    // flavors, and the enriched therapeutic/aroma/misc/lineage fields
    let searchOk = true;
    if (q) {{
      const p = PRODUCTS[key] || {{}};
      const s = STRAINS[key]  || {{}};
      const blob = [
        p.name, p.brand, p.strain_type,
        (p.effects  || []).join(' '),
        (p.terpenes || []).join(' '),
        (p.flavors  || []).join(' '),
        s.lineage, s.therapeutic, s.negative, s.aroma, s.misc
      ].filter(Boolean).join(' ').toLowerCase();
      searchOk = blob.includes(q);
    }}

    const visible = catOk && moodOk && searchOk;
    card.classList.toggle('hidden', !visible);
    if (visible) totalVisible++;
  }});

  // Update section visibility + counts
  document.querySelectorAll('.section').forEach(s => {{
    const catOk = activeCat === 'all' || s.dataset.cat === activeCat;
    if (!catOk) {{ s.classList.add('hidden'); return; }}
    const vis = s.querySelectorAll('.card:not(.hidden)').length;
    s.classList.toggle('hidden', vis === 0);
    const countEl = s.querySelector('[data-total]');
    if (countEl) {{
      const total = countEl.dataset.total;
      countEl.textContent = mood
        ? `${{vis}} / ${{total}} matching`
        : `${{total}} product${{total == 1 ? '' : 's'}}`;
    }}
  }});

  // Divider + new-arrivals section
  document.querySelectorAll('.section-divider').forEach(d => {{
    d.classList.toggle('hidden', activeCat !== 'all');
  }});

  // Show "no results" message
  document.getElementById('moodZero').classList.toggle('hidden', totalVisible > 0);

  // Update status bar
  const statusEl = document.getElementById('moodStatus');
  const parts = [];
  if (mood)  parts.push(`<strong>${{mood.label}}:</strong> ${{mood.science}}`);
  if (q)     parts.push(`searching <strong>"${{q}}"</strong>`);
  if (parts.length) {{
    parts.push(`— ${{totalVisible}} product${{totalVisible == 1 ? '' : 's'}} found`);
    statusEl.innerHTML = parts.join(' · ');
    statusEl.classList.remove('hidden');
  }} else {{
    statusEl.classList.add('hidden');
  }}
}}

function handleSearch(val) {{
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {{
    activeSearch = val.trim().toLowerCase();
    document.getElementById('searchClear').classList.toggle('hidden', !activeSearch);
    applyFilters();
  }}, 150);
}}

function clearSearch() {{
  document.getElementById('searchInput').value = '';
  activeSearch = '';
  document.getElementById('searchClear').classList.add('hidden');
  applyFilters();
}}

function filterCat(btn) {{
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  activeCat = btn.dataset.cat;
  applyFilters();
  window.scrollTo({{top:0,behavior:'smooth'}});
}}

function filterMood(btn) {{
  const mood = btn.dataset.mood;
  if (activeMood === mood) {{
    clearMood();
    return;
  }}
  document.querySelectorAll('.mood-chip').forEach(c => c.classList.remove('on'));
  btn.classList.add('on');
  activeMood = mood;
  document.getElementById('moodClear').classList.remove('hidden');
  applyFilters();
}}

function clearMood() {{
  activeMood = null;
  document.querySelectorAll('.mood-chip').forEach(c => c.classList.remove('on'));
  document.getElementById('moodClear').classList.add('hidden');
  applyFilters();
}}

document.addEventListener('keydown', e => {{ if (e.key === 'Escape') {{ closeModal(); closeDrawer(); }} }});
</script>
</body>
</html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"Built → {OUT}  ({len(all_p)} products)")

build()
