"""Apply new CSS_SHARED to all existing pages."""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_cycle import CSS_SHARED, FONT_LINK, SITE_BASE, nav_html, STORY_HTML, SOCIAL_HTML, NAV_SCRIPT, ANALYTICS_HTML
from pathlib import Path

docs = Path("docs")
all_slugs = [n["slug"] for n in __import__("json").load(open("cycle_state.json"))["niches"]]

# Collect all HTML files
html_files = list(docs.rglob("*.html"))
count = 0

for fpath in html_files:
    old = fpath.read_text(encoding="utf-8")
    if "<style>" not in old:
        continue
    
    # Replace the entire style block (everything between <style> and </style>)
    new = re.sub(
        r'<style>.*?</style>',
        f'<style>{CSS_SHARED}</style>',
        old,
        flags=re.DOTALL
    )
    
    # Add FONT_LINK before the style tag if not present
    if FONT_LINK not in new and "fonts.googleapis.com" not in new:
        # Add it after the meta viewport or title tag
        new = new.replace(
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n' + FONT_LINK
        )
    
    # Fix nav to include how-we-test if missing
    nav_tag = nav_html(all_slugs)
    if "how-we-test" not in new:
        new = re.sub(
            r'<nav>.*?</nav>',
            nav_tag,
            new,
            flags=re.DOTALL
        )
    
    if new != old:
        fpath.write_text(new, encoding="utf-8")
        count += 1
        print(f"  Updated: {fpath}")

print(f"\nUpdated {count} files")
