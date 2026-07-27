"""Generate sleek product-style SVG hero images for each niche."""
import json
from pathlib import Path

state = json.load(open("cycle_state.json"))
assets = Path("docs") / "assets"
assets.mkdir(exist_ok=True)

palette = {
    "primary": "#d4633e",
    "primary_dark": "#b84d2a",
    "accent": "#1a8a7a",
    "accent_light": "#d4ede8",
    "bg": "#faf6f1",
    "bg_dark": "#2a2724",
    "text_warm": "#6b6560",
    "border": "#e3dbd4",
}

# Category-specific visual motifs
niche_motifs = {
    "wireless-headphones": {"icon": "M400,300 Q400,200 500,200 Q600,200 600,300 Q600,400 500,400 Q400,400 400,300", "accent_color": palette["primary"], "label": "Noise Cancelling"},
    "gaming-mice": {"icon": "M300,250 L500,180 L700,250 L700,380 L500,450 L300,380 Z", "accent_color": palette["accent"], "label": "Precision Gaming"},
    "4k-monitors": {"icon": "M250,200 L950,200 L950,420 L250,420 Z", "accent_color": "#8b6fba", "label": "Ultra HD"},
    "laptops": {"icon": "M300,200 L900,200 L900,380 L300,380 Z M320,380 L320,420 L880,420 L880,380", "accent_color": palette["primary"], "label": "Performance"},
    "streaming-devices": {"icon": "M400,250 Q600,220 800,250 L800,370 Q600,400 400,370 Z", "accent_color": palette["accent"], "label": "4K Streaming"},
    "mechanical-keyboards": {"icon": "M250,320 L950,320 L950,380 L250,380 Z M300,260 L500,260 L500,320", "accent_color": "#5a8bba", "label": "Mechanical"},
    "wireless-earbuds": {"icon": "M350,250 A150,150 0 1,1 250,250 A50,50 0 1,0 350,250 M650,250 A150,150 0 1,0 750,250 A50,50 0 1,1 650,250", "accent_color": palette["primary"], "label": "True Wireless"},
    "fitness-trackers": {"icon": "M400,200 L600,200 L600,400 L400,400 Z M380,240 L620,240 M380,360 L620,360", "accent_color": palette["accent"], "label": "Activity Tracking"},
    "webcams": {"icon": "M400,200 A100,100 0 1,1 600,200 L600,350 A100,100 0 1,1 400,350 Z", "accent_color": "#8b6fba", "label": "1080p+ HD"},
    "smart-home": {"icon": "M500,200 L700,300 L600,300 L700,400 L500,400 L300,400 L400,300 L300,300 Z", "accent_color": palette["accent"], "label": "Smart Living"},
}

for n in state["niches"]:
    slug = n["slug"]
    name = n["name"]
    motif = niche_motifs.get(slug, {"icon": "M400,200 Q600,150 800,200 L800,400 Q600,450 400,400 Z", "accent_color": palette["primary"], "label": "Top Pick"})

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{palette['bg']};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#e8dfd6;stop-opacity:1"/>
    </linearGradient>
    <linearGradient id="accentBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{motif['accent_color']};stop-opacity:0.08"/>
      <stop offset="100%" style="stop-color:{motif['accent_color']};stop-opacity:0.02"/>
    </linearGradient>
    <linearGradient id="productGlow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{motif['accent_color']};stop-opacity:0.15"/>
      <stop offset="100%" style="stop-color:{motif['accent_color']};stop-opacity:0.05"/>
    </linearGradient>
    <filter id="shadow">
      <feDropShadow dx="0" dy="4" stdDeviation="12" flood-color="{motif['accent_color']}" flood-opacity="0.15"/>
    </filter>
    <filter id="glow">
      <feGaussianBlur stdDeviation="30" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect width="1200" height="630" fill="url(#accentBg)"/>

  <!-- Accent circles -->
  <circle cx="950" cy="100" r="350" fill="{motif['accent_color']}" opacity="0.04"/>
  <circle cx="250" cy="500" r="250" fill="{motif['accent_color']}" opacity="0.03"/>
  <circle cx="600" cy="315" r="180" fill="{motif['accent_color']}" opacity="0.02"/>

  <!-- Product silhouette area -->
  <g filter="url(#shadow)">
    <path d="{motif['icon']}" fill="url(#productGlow)" stroke="{motif['accent_color']}" stroke-width="3" opacity="0.8"/>
  </g>

  <!-- Rating badge -->
  <g transform="translate(60, 60)">
    <rect width="100" height="32" rx="16" fill="{palette['bg']}" stroke="{palette['border']}" stroke-width="1" opacity="0.9"/>
    <text x="50" y="21" font-family="'Trebuchet MS',Arial,sans-serif" font-size="13" font-weight="700" fill="{motif['accent_color']}" text-anchor="middle">★ 4.8 / 5.0</text>
  </g>

  <!-- Category badge -->
  <g transform="translate(60, 100)">
    <rect width="{len(motif['label'])*9 + 24}" height="28" rx="14" fill="{motif['accent_color']}"/>
    <text x="{len(motif['label'])*4.5 + 12}" y="19" font-family="'Trebuchet MS',Arial,sans-serif" font-size="11" font-weight="700" fill="#fff" text-anchor="middle" letter-spacing="1">{motif['label']}</text>
  </g>

  <!-- Title -->
  <text x="600" y="520" font-family="Georgia,'Times New Roman',serif" font-size="52" font-weight="700" fill="{palette['bg_dark']}" text-anchor="middle" letter-spacing="-1">Best {name}</text>

  <!-- Divider -->
  <rect x="540" y="540" width="120" height="3" rx="2" fill="{motif['accent_color']}"/>

  <!-- Subtitle -->
  <text x="600" y="575" font-family="'Trebuchet MS',Arial,sans-serif" font-size="18" fill="{palette['text_warm']}" text-anchor="middle" letter-spacing="1">EXPERT TESTED · HONEST REVIEWS</text>
</svg>'''

    filepath = assets / f"{slug}.svg"
    filepath.write_text(svg, encoding="utf-8")
    print(f"  Generated: {filepath.name}")

# Home hero — more editorial, moody
svg_home = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="hg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{palette['primary']};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#8b6fba;stop-opacity:1"/>
    </linearGradient>
    <linearGradient id="hgBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{palette['bg']};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#e8dfd6;stop-opacity:1"/>
    </linearGradient>
    <filter id="hgShadow">
      <feDropShadow dx="0" dy="8" stdDeviation="24" flood-color="{palette['primary']}" flood-opacity="0.1"/>
    </filter>
  </defs>
  <rect width="1200" height="630" fill="url(#hgBg)"/>
  <circle cx="850" cy="150" r="350" fill="{palette['primary']}" opacity="0.05"/>
  <circle cx="350" cy="480" r="250" fill="{palette['accent']}" opacity="0.04"/>
  <g filter="url(#hgShadow)">
    <circle cx="600" cy="300" r="140" fill="none" stroke="{palette['primary']}" stroke-width="1" opacity="0.3"/>
    <circle cx="600" cy="300" r="100" fill="none" stroke="{palette['accent']}" stroke-width="1" opacity="0.3"/>
    <circle cx="600" cy="300" r="60" fill="{palette['primary']}" opacity="0.06"/>
  </g>
  <text x="600" y="250" font-family="Georgia,'Times New Roman',serif" font-size="72" font-weight="700" fill="{palette['bg_dark']}" text-anchor="middle" letter-spacing="-1">Abvorn</text>
  <text x="600" y="310" font-family="'Trebuchet MS',Arial,sans-serif" font-size="22" fill="{palette['text_warm']}" text-anchor="middle" letter-spacing="3">PRODUCT REVIEWS &amp; BUYING GUIDES</text>
  <rect x="540" y="340" width="120" height="3" rx="2" fill="{palette['primary']}"/>
  <text x="600" y="390" font-family="Georgia,'Times New Roman',serif" font-size="28" fill="{palette['bg_dark']}" text-anchor="middle" font-style="italic">We test so you can buy with confidence</text>
  <g transform="translate(450, 440)">
    <rect width="300" height="50" rx="25" fill="url(#hg)"/>
    <text x="150" y="31" font-family="'Trebuchet MS',Arial,sans-serif" font-size="15" font-weight="700" fill="#fff" text-anchor="middle" letter-spacing="1">BROWSE LATEST REVIEWS</text>
  </g>
</svg>'''
(assets / "hero-home.svg").write_text(svg_home, encoding="utf-8")
print("  Generated: hero-home.svg")

# Favicon
favicon = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <defs><linearGradient id="fg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:{palette['primary']}"/><stop offset="100%" style="stop-color:{palette['primary_dark']}"/></linearGradient></defs>
  <rect width="32" height="32" rx="8" fill="url(#fg)"/>
  <text x="16" y="23" font-family="Georgia,serif" font-size="20" font-weight="bold" fill="#fff" text-anchor="middle">A</text>
</svg>'''
(assets / "favicon.svg").write_text(favicon, encoding="utf-8")
(Path("docs") / "assets" / "favicon.svg").write_text(favicon, encoding="utf-8")
print("  Generated: favicon.svg")

print("\nDone! Sleek product hero images generated.")
