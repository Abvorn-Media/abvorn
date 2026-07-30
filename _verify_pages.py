import re, json
from pathlib import Path

pages = list(Path('docs/reviews').glob('*/index.html'))
print(f'Found {len(pages)} article pages\n')

for p in sorted(pages):
    niche = p.parent.name
    html = p.read_text(encoding='utf-8')
    checks = []
    checks.append(('breakdown bars', 'breakdown' in html or 'verdict-bar' in html))
    checks.append(('radar chart', 'Chart' in html and 'radar' in html))
    checks.append(('date badges', 'published-date' in html or 'updated-date' in html))
    checks.append(('gold buttons', 'buy-btn' in html))
    checks.append(('product grid', 'product-section' in html))
    
    scores = re.findall(r'overall[^0-9]+([\d.]+)', html)
    has_scores = any(float(s) > 0 for s in scores) if scores else False
    checks.append((f'scores >0 ({len(scores)} found)', has_scores))
    
    fails = [c[0] for c in checks if not c[1]]
    if fails:
        print(f'  FAIL {niche}: {", ".join(fails)}')
    else:
        print(f'  OK   {niche}')

print('\nDone.')
