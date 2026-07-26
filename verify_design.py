import sys
sys.path.insert(0, r'C:\Users\Jean Mare\Documents\Default Project')
from run_cycle import CSS_SHARED, NAV_SCRIPT

checks = [
    (":root{", "design tokens"),
    ("prefers-color-scheme:dark", "dark mode"),
    ("--primary", "primary token"),
    ("--font-display", "font token"),
    ("--shadow-lg", "shadow token"),
    ("backdrop-filter:blur", "backdrop blur"),
    ("scroll-behavior:smooth", "smooth scroll"),
    ("::selection", "selection color"),
    ("clamp(", "fluid type"),
    ("cubic-bezier", "custom easing"),
    ("::after", "cat-card underline"),
    ("color-mix", "dynamic border colors"),
]
for token, name in checks:
    assert token in CSS_SHARED, "Missing: " + name
    print("OK:", name)

from run_cycle import build_root_index, build_category_page, build_article_page
state = {"niches": [{"slug": "test", "name": "Test", "posts": 1}]}
html = build_root_index(state, [])
cat = build_category_page("test", "Test", [{"title": "Best", "slug": "reviews/test"}], ["test"], "tag")
products = [{"name": "P", "price": "$9", "description": "G", "features": ["a"]}]
art = build_article_page("test", "Test", "Post", "<p>b</p>", "<p>i</p>", "Prod", "desc", ["test"],
                          products=products, pexels_key="k", amazon_tag="t", form_url="https://x.com")

for name, doc in [("root", html), ("cat", cat), ("art", art)]:
    assert NAV_SCRIPT.strip() in doc, name + " missing nav script"
    assert 'class="skip-link"' in doc, name + " missing skip link"
    assert 'id="main"' in doc, name + " missing main id"
    assert "</html>" in doc, name + " missing closing html"
    assert "</body>" in doc, name + " missing closing body"
    print("OK:", name, "complete")

print("\nALL CHECKS PASSED")
