"""Add Google Analytics tag to homepage and category pages."""
import re
from pathlib import Path

GA_HTML = '\n<script async src="https://www.googletagmanager.com/gtag/js?id=G-J0GTXLC86C"></script>\n<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)};gtag(\'js\',new Date());gtag(\'config\',\'G-J0GTXLC86C\');</script>\n'

def add_ga(filepath):
    html = filepath.read_text(encoding="utf-8")
    if 'G-XXXXXXXXXX' in html:
        # Swap the placeholder for the real measurement ID in place.
        html = html.replace('G-XXXXXXXXXX', 'G-J0GTXLC86C')
        filepath.write_text(html, encoding="utf-8")
        return True
    if 'gtag/js?id=G-J0GTXLC86C' in html:
        return False
    # Insert GA after </head> or before <style>
    html = html.replace('</head>', f'{GA_HTML}</head>')
    html = html.replace('</style>\n</head>', f'</style>{GA_HTML}</head>')
    filepath.write_text(html, encoding="utf-8")
    return True

docs = Path("docs")
updated = 0

# Homepage
if add_ga(docs / "index.html"):
    updated += 1
    print("  Added GA to homepage")

# Category pages (exclude reviews/ which already have it, and assets/)
for niche_dir in sorted(docs.iterdir()):
    if not niche_dir.is_dir() or niche_dir.name in ('reviews', 'assets', 'plans', 'specs', 'superpowers'):
        continue
    idx = niche_dir / "index.html"
    if idx.exists() and add_ga(idx):
        updated += 1
        print(f"  Added GA to {idx}")

print(f"\nDone: {updated} files updated with analytics.")
