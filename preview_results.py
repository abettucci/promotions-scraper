#!/usr/bin/env python3
"""
Genera un preview visual de los resultados del scraper y lo abre en el browser.

Uso:
    python preview_results.py                         # usa test_result_carrefour.json
    python preview_results.py test_result_dia.json
    python preview_results.py test_result_carrefour.json test_result_dia.json
"""
import json
import sys
import os
import subprocess
import html as html_mod
from pathlib import Path

# ── Colores por entidad ────────────────────────────────────────
ENTITY_COLORS = {
    'Banco Galicia':     '#CC2529',
    'Banco Nación':      '#003F87',
    'Banco Provincia':   '#00589B',
    'Santander':         '#EC0000',
    'BBVA':              '#004481',
    'Macro':             '#FFCC00',
    'HSBC':              '#DB0011',
    'Credicoop':         '#003366',
    'Supervielle':       '#E8000D',
    'Banco Ciudad':      '#005B9A',
    'Itaú':              '#EC7000',
    'Comafi':            '#006633',
    'Banco Patagonia':   '#0055A5',
    'Carrefour Banco':   '#004C98',
    'Mercado Pago':      '#009EE3',
    'Cuenta DNI':        '#0033A0',
    'MODO':              '#7C3AED',
    'Naranja X':         '#FF6600',
    'Ualá':              '#AA00FF',
    'Personal Pay':      '#00B2E3',
    'Tap':               '#1DB954',
}

def entity_color(promo):
    for k, v in ENTITY_COLORS.items():
        if k in (promo.get('bank') or '') or k in (promo.get('wallet') or ''):
            return v
    return '#374151'

def entity_name(promo):
    parts = []
    if promo.get('bank'):   parts.append(promo['bank'])
    if promo.get('wallet'): parts.append(promo['wallet'])
    if promo.get('card_type'): parts.append(promo['card_type'])
    return ' · '.join(parts) if parts else 'Sin entidad'

def discount_label(promo):
    d = promo.get('discount', '')
    if not d:
        return ''
    if d.endswith('%'):
        return d
    # e.g. "6cuotas"
    m = __import__('re').match(r'(\d+)\s*cuotas?', d, __import__('re').IGNORECASE)
    if m:
        return f"{m.group(1)} CSI"
    return d

def store_icons(promo):
    mapping = {
        'Hipermercado': ('🏬', '#1e40af'),
        'Market':       ('🛒', '#065f46'),
        'Express':      ('⚡', '#92400e'),
        'Maxi':         ('📦', '#5b21b6'),
        'Online':       ('🌐', '#0e7490'),
    }
    stores = promo.get('store_types') or ''
    badges = []
    for s, (icon, color) in mapping.items():
        if s in stores:
            badges.append(
                f'<span style="background:{color}20;color:{color};border:1px solid {color}40;'
                f'border-radius:4px;padding:2px 6px;font-size:11px;white-space:nowrap">'
                f'{icon} {s}</span>'
            )
    return ' '.join(badges) if badges else ''

def extra_badges(promo):
    badges = []
    # tope
    if promo.get('tope'):
        badges.append(f'<span style="background:#fef3c720;color:#92400e;border:1px solid #fcd34d;'
                       f'border-radius:4px;padding:2px 6px;font-size:11px">🔝 {html_mod.escape(promo["tope"])}</span>')
    # aplica en (DIA)
    if promo.get('aplica_en'):
        badges.append(f'<span style="background:#ede9fe20;color:#5b21b6;border:1px solid #c4b5fd;'
                       f'border-radius:4px;padding:2px 6px;font-size:11px">📍 {html_mod.escape(promo["aplica_en"])}</span>')
    # tipo de tarjeta (Shell, etc.)
    if promo.get('card_type'):
        badges.append(f'<span style="background:#e0f2fe20;color:#0369a1;border:1px solid #7dd3fc;'
                       f'border-radius:4px;padding:2px 6px;font-size:11px">💳 {html_mod.escape(promo["card_type"])}</span>')
    # tipo pago
    if promo.get('payment_type'):
        badges.append(f'<span style="background:#ecfdf520;color:#065f46;border:1px solid #6ee7b7;'
                       f'border-radius:4px;padding:2px 6px;font-size:11px">💳 {html_mod.escape(promo["payment_type"])}</span>')
    # validez (Cencosud)
    if promo.get('validez'):
        badges.append(f'<span style="background:#e0f2fe20;color:#0369a1;border:1px solid #7dd3fc;'
                       f'border-radius:4px;padding:2px 6px;font-size:11px">🏪 {html_mod.escape(promo["validez"])}</span>')
    # rango de fechas de vigencia
    vf = promo.get('valid_from') or ''
    vu = promo.get('valid_until') or ''
    if vf and vu:
        date_str = f"{vf} → {vu}"
    elif vu:
        date_str = f"hasta {vu}"
    elif vf:
        date_str = f"desde {vf}"
    else:
        date_str = ''
    if date_str:
        badges.append(f'<span style="background:#f0f9ff20;color:#0c4a6e;border:1px solid #bae6fd;'
                       f'border-radius:4px;padding:2px 6px;font-size:11px">📆 {html_mod.escape(date_str)}</span>')
    # exclusiones
    if promo.get('exclusions'):
        excl = promo['exclusions'][:80]
        badges.append(f'<span style="background:#fff7ed20;color:#7c2d12;border:1px solid #fed7aa;'
                       f'border-radius:4px;padding:2px 6px;font-size:10px">⚠️ {html_mod.escape(excl)}</span>')
    # TNA/TEA/CFT (Cencosud cuotas)
    fin = ' | '.join(f"{k.upper()}: {promo[k]}" for k in ('tna','tea','cft') if promo.get(k))
    if fin:
        badges.append(f'<span style="background:#f0fdf420;color:#166534;border:1px solid #86efac;'
                       f'border-radius:4px;padding:2px 6px;font-size:10px">📊 {html_mod.escape(fin)}</span>')
    return ' '.join(badges)

def card_html(promo, idx):
    color  = entity_color(promo)
    entity = html_mod.escape(entity_name(promo))
    disc   = discount_label(promo)
    title  = html_mod.escape((promo.get('title') or '')[:120])
    days   = html_mod.escape(promo.get('valid_days') or '')
    terms  = html_mod.escape((promo.get('terms_raw') or promo.get('legal_text') or '')[:600])
    img    = promo.get('image_url') or ''
    stores = store_icons(promo)
    extras = extra_badges(promo)

    if img:
        img_html = (
            f'<div>'
            f'<img src="{html_mod.escape(img)}" alt="{entity}" '
            f'style="max-height:48px;max-width:120px;object-fit:contain;filter:drop-shadow(0 1px 2px rgba(0,0,0,.2))">'
            f'<div style="font-size:11px;color:#6b7280;margin-top:3px">{entity}</div>'
            f'</div>'
        )
    else:
        img_html = f'<div style="font-size:13px;font-weight:600;color:{color}">{entity}</div>'

    disc_html = (
        f'<div style="background:{color};color:#fff;border-radius:8px;'
        f'padding:6px 14px;font-size:22px;font-weight:800;letter-spacing:-0.5px;'
        f'white-space:nowrap">{html_mod.escape(disc)}</div>'
        if disc else ''
    )

    return f'''
<div class="card" style="border-top:4px solid {color}">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px">
    <div style="min-width:0">{img_html}</div>
    {disc_html}
  </div>
  <div style="font-size:13px;color:#1f2937;line-height:1.4;margin-bottom:8px">{title}</div>
  {f'<div style="font-size:12px;color:#6b7280;margin-bottom:6px">📅 {days}</div>' if days else ''}
  {f'<div style="margin-bottom:6px;display:flex;flex-wrap:wrap;gap:4px">{stores}</div>' if stores else ''}
  {f'<div style="margin-bottom:8px;display:flex;flex-wrap:wrap;gap:4px">{extras}</div>' if extras else ''}
  {f"""<details style="margin-top:8px">
    <summary style="font-size:11px;color:#9ca3af;cursor:pointer;user-select:none">Ver legales</summary>
    <div style="font-size:10px;color:#6b7280;margin-top:6px;line-height:1.5;
                max-height:200px;overflow-y:auto;background:#f9fafb;
                padding:8px;border-radius:4px">{terms}</div>
  </details>""" if terms else ''}
</div>'''

def build_html(all_promos_by_source):
    total = sum(len(v) for v in all_promos_by_source.values())
    sources_html = ''
    for source, promos in all_promos_by_source.items():
        cards = '\n'.join(card_html(p, i) for i, p in enumerate(promos))
        sources_html += f'''
<section style="margin-bottom:48px">
  <h2 style="font-size:18px;font-weight:700;color:#111827;margin-bottom:4px">{html_mod.escape(source)}</h2>
  <p style="font-size:13px;color:#6b7280;margin-bottom:20px">{len(promos)} promociones</p>
  <div class="grid">{cards}</div>
</section>'''

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Preview — Scraper Resultados</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #f3f4f6; color: #111827; padding: 32px 24px; }}
  header {{ max-width:1200px; margin:0 auto 32px; }}
  h1 {{ font-size:24px; font-weight:800; color:#111827; }}
  .meta {{ font-size:13px; color:#6b7280; margin-top:4px; }}
  main {{ max-width:1200px; margin:0 auto; }}
  .grid {{ display:grid;
           grid-template-columns: repeat(auto-fill, minmax(280px,1fr));
           gap:16px; }}
  .card {{ background:#fff; border-radius:12px; padding:16px;
           box-shadow:0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);
           transition: transform .15s, box-shadow .15s; }}
  .card:hover {{ transform:translateY(-2px);
                 box-shadow:0 4px 12px rgba(0,0,0,.12); }}
  details summary::-webkit-details-marker {{ color:#9ca3af; }}
</style>
</head>
<body>
<header>
  <h1>Promotions Scraper — Preview</h1>
  <p class="meta">{total} promociones totales &nbsp;·&nbsp;
     {', '.join(all_promos_by_source.keys())}</p>
</header>
<main>{sources_html}</main>
</body>
</html>'''

def main():
    files = sys.argv[1:] or ['test_result_carrefour.json']

    all_promos = {}
    for f in files:
        path = Path(f)
        if not path.exists():
            # Try in same directory as script
            path = Path(__file__).parent / f
        if not path.exists():
            print(f"⚠️  No se encontró: {f}")
            continue
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        name = path.stem.replace('test_result_', '').capitalize()
        all_promos[name] = data
        print(f"✅ {name}: {len(data)} promociones")

    if not all_promos:
        print("❌ No hay datos para mostrar")
        sys.exit(1)

    out = Path(__file__).parent / 'preview.html'
    out.write_text(build_html(all_promos), encoding='utf-8')
    print(f"\n📄 HTML generado: {out}")

    # Abrir en el browser
    subprocess.Popen(['open', str(out)])
    print("🌐 Abriendo en el browser...")

if __name__ == '__main__':
    main()
