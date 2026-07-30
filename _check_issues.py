from pathlib import Path
import re

html = Path('docs/reviews/wireless-headphones/index.html').read_text(encoding='utf-8')

# 1. Chart JS initialization code
has_chart_init = 'document.addEventListener' in html and 'verdictChart' in html
has_chart_ready = 'DOMContentLoaded' in html and 'getContext' in html
print(f'1. Chart init code present: {has_chart_init and has_chart_ready}')

# 2. CSS variables
for var in ['--bg-alt', '--text-secondary', '--border']:
    defined = var in html
    used = html.count(var) > 1
    print(f'2. {var}: defined={defined}')

# 3. Find actual article HTML body (not CSS)
# Look for the <article> tag or the content after the hero
hero_end = html.find('</header')
if hero_end > 0:
    # Find first <p> or <h2> after hero
    body_start = html.find('<p>', hero_end)
    body_end = html.find('<div class="product-section"', body_start)
    if body_end < 0:
        body_end = html.find('<section class="product-section"', body_start)
    if body_start > 0:
        body = html[body_start:body_end] if body_end > body_start else html[body_start:body_start+2000]
        text = re.sub(r'<[^>]+>', ' ', body)
        text = re.sub(r'\s+', ' ', text).strip()
        ascii_text = text.encode('ascii', 'ignore').decode()
        print(f'3. Article body text: {len(ascii_text)} chars')
        print(f'   First 300: {ascii_text[:300]}')
    else:
        print('3. No article body <p> found')

# 4. Check for __ARTICLE_BODY__ or similar placeholder leaks
if '__ARTICLE_BODY__' in html:
    print('4. WARNING: __ARTICLE_BODY__ placeholder leaked!')
else:
    print('4. No leaked placeholders')

# 5. Check the verdict data format
vd = re.search(r'abvorn-verdict-data[^>]+>(.*?)</script>', html, re.DOTALL)
if vd:
    import json
    try:
        data = json.loads(vd.group(1))
        print(f'5. Verdict data: {type(data).__name__}')
        if isinstance(data, dict):
            print(f'   Keys: {list(data.keys())}')
    except:
        print(f'5. Verdict data: raw (not parseable)')
