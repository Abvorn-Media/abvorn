"""Generate AdSense-required policy pages: Privacy, Terms, Disclaimer, About."""
import os
from pathlib import Path

BASE = "https://Abvorn-Media.github.io/abvorn"
YEAR = "2026"
PUBLISHER = "Abvorn Media"

CSS = """body{font-family:'Inter',-apple-system,sans-serif;color:#2a2724;background:#faf6f1;line-height:1.7;margin:0;padding:0}
.container{max-width:720px;margin:0 auto;padding:48px 24px}
h1{font-family:Georgia,'Times New Roman',serif;font-size:2rem;font-weight:700;color:#2a2724;margin-bottom:4px;letter-spacing:-.02em}
.updated{font-size:.85rem;color:#9e9690;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid #e3dbd4}
h2{font-family:Georgia,'Times New Roman',serif;font-size:1.3rem;font-weight:700;color:#2a2724;margin:28px 0 12px}
p{margin:12px 0;font-size:.95rem;color:#6b6560}
ul{padding-left:20px;margin:12px 0}
li{margin:6px 0;font-size:.95rem;color:#6b6560}
a{color:#d4633e;text-decoration:none}
a:hover{color:#b84d2a;text-decoration:underline}
.back{display:inline-block;margin-bottom:24px;font-size:.9rem;color:#d4633e}
.back:hover{text-decoration:underline}
footer{text-align:center;padding:32px 0;border-top:1px solid #e3dbd4;font-size:.85rem;color:#9e9690}"""

# ─── Privacy Policy ────────────────────────────────────────────────
PRIVACY = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Privacy Policy — Abvorn</title>
<meta name="description" content="Abvorn privacy policy — how we collect, use, and protect your personal data.">
<link rel="icon" type="image/svg+xml" href="{BASE}/assets/favicon.svg">
<style>{CSS}</style>
</head><body>
<div class="container">
<a class="back" href="{BASE}/">&larr; Back to Abvorn</a>
<h1>Privacy Policy</h1>
<p class="updated">Last updated: July 26, {YEAR}</p>

<h2>1. Information We Collect</h2>
<p>We collect information you voluntarily provide when subscribing to our newsletter, leaving comments, or contacting us. This may include your name, email address, and any content you submit.</p>
<p>We also automatically collect certain data through cookies and similar technologies, including:</p>
<ul>
<li>Pages visited and time spent on our site</li>
<li>Browser type and device information</li>
<li>Referring website or campaign</li>
<li>IP address (anonymized where possible)</li>
</ul>

<h2>2. How We Use Your Information</h2>
<p>We use collected data to:</p>
<ul>
<li>Deliver newsletters and product updates you subscribed to</li>
<li>Display comments and community content</li>
<li>Analyze site traffic and improve our content</li>
<li>Serve relevant advertisements through Google AdSense</li>
<li>Comply with legal obligations</li>
</ul>

<h2>3. Google AdSense</h2>
<p>We use Google AdSense to display advertisements. Google uses cookies to serve ads based on your prior visits to our site and other websites. You may opt out of personalized advertising by visiting <a href="https://adssettings.google.com" target="_blank" rel="noopener">Google Ads Settings</a>.</p>
<p>Google's use of advertising cookies enables it and its partners to serve ads based on your visit to our site and/or other sites on the Internet.</p>

<h2>4. Cookies</h2>
<p>We use cookies to remember your preferences, analyze traffic, and personalize content. You can control cookie settings through your browser. Disabling cookies may affect site functionality.</p>

<h2>5. Third-Party Services</h2>
<p>We use the following third-party services that process data:</p>
<ul>
<li><strong>Google Analytics</strong> — anonymized traffic analysis</li>
<li><strong>Google AdSense</strong> — contextual and personalized advertising</li>
<li><strong>Google Identity Services</strong> — comment authentication via Google Sign-In</li>
<li><strong>Amazon Associates</strong> — affiliate program (see our Disclaimer)</li>
</ul>

<h2>6. Data Retention</h2>
<p>We retain your data only as long as necessary to provide our services. Comments are stored locally in your browser. Newsletter subscription data is retained until you unsubscribe.</p>

<h2>7. Your Rights</h2>
<p>Depending on your jurisdiction, you may have the right to access, correct, delete, or port your personal data. To exercise these rights, contact us at the email below.</p>

<h2>8. Contact</h2>
<p>For privacy inquiries: <a href="mailto:privacy@abvorn.com">privacy@abvorn.com</a></p>
</div>
<footer><p>{PUBLISHER} &mdash; Independent Reviews</p></footer>
</body></html>"""

# ─── Terms of Service ──────────────────────────────────────────────
TERMS = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Terms of Service — Abvorn</title>
<meta name="description" content="Abvorn terms of service — rules and guidelines for using our site.">
<link rel="icon" type="image/svg+xml" href="{BASE}/assets/favicon.svg">
<style>{CSS}</style>
</head><body>
<div class="container">
<a class="back" href="{BASE}/">&larr; Back to Abvorn</a>
<h1>Terms of Service</h1>
<p class="updated">Last updated: July 26, {YEAR}</p>

<h2>1. Acceptance</h2>
<p>By accessing or using Abvorn, you agree to these Terms of Service. If you do not agree, do not use the site.</p>

<h2>2. Content</h2>
<p>All product reviews, buying guides, and editorial content on Abvorn are for informational purposes only. We make every effort to ensure accuracy, but we do not guarantee that all information is complete, current, or error-free.</p>

<h2>3. Affiliate Disclosure</h2>
<p>Abvorn participates in the Amazon Services LLC Associates Program and other affiliate programs. We may earn commissions on purchases made through our links at no additional cost to you. See our full <a href="{BASE}/disclaimer/">Disclaimer</a> for details.</p>

<h2>4. User Conduct</h2>
<p>When commenting or interacting on our site, you agree not to:</p>
<ul>
<li>Post spam, harassment, or offensive content</li>
<li>Impersonate others or provide false information</li>
<li>Attempt to disrupt site operations</li>
<li>Use automated bots or scrapers without permission</li>
</ul>
<p>We reserve the right to moderate and remove comments at our discretion.</p>

<h2>5. Intellectual Property</h2>
<p>All content on Abvorn — including text, graphics, logos, and design — is owned by or licensed to {PUBLISHER} unless otherwise noted. Unauthorized reproduction or distribution is prohibited.</p>

<h2>6. Limitation of Liability</h2>
<p>Abvorn is provided "as is" without warranties of any kind. We are not liable for damages arising from the use or inability to use our site or from any purchase decisions made based on our content.</p>

<h2>7. Changes</h2>
<p>We may update these terms at any time. Changes are effective upon posting. Continued use after changes constitutes acceptance.</p>

<h2>8. Contact</h2>
<p>For questions: <a href="mailto:legal@abvorn.com">legal@abvorn.com</a></p>
</div>
<footer><p>{PUBLISHER} &mdash; Independent Reviews</p></footer>
</body></html>"""

# ─── Disclaimer ────────────────────────────────────────────────────
DISCLAIMER = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Disclaimer — Abvorn</title>
<meta name="description" content="Abvorn disclaimer — affiliate relationships, review methodology, and editorial independence.">
<link rel="icon" type="image/svg+xml" href="{BASE}/assets/favicon.svg">
<style>{CSS}</style>
</head><body>
<div class="container">
<a class="back" href="{BASE}/">&larr; Back to Abvorn</a>
<h1>Disclaimer</h1>
<p class="updated">Last updated: July 26, {YEAR}</p>

<h2>Affiliate Disclosure</h2>
<p>Abvorn is a participant in the Amazon Services LLC Associates Program, an affiliate advertising program designed to provide a means for sites to earn advertising fees by advertising and linking to Amazon.com and affiliated sites.</p>
<p>We also participate in other affiliate programs. When you click on an affiliate link and make a purchase, we may earn a commission at no additional cost to you.</p>

<h2>Editorial Independence</h2>
<p>Affiliate relationships do not influence our editorial recommendations. Our reviews and buying guides are based on independent research, testing, and analysis. We prioritize honest, data-driven recommendations over commissions.</p>
<p>Products are selected for review based on market relevance and reader interest — not affiliate commission rates. We clearly label affiliate links and sponsored content where applicable.</p>

<h2>Review Methodology</h2>
<p>Our reviews are conducted independently. We evaluate products based on:</p>
<ul>
<li>Performance benchmarks and specifications</li>
<li>Price-to-value ratio</li>
<li>User feedback and aggregated ratings</li>
<li>Real-world usability testing</li>
</ul>
<p>We do not accept payment for positive reviews. Products are tested by our team or researched using publicly available data, verified reviews, and expert consensus.</p>

<h2>Accuracy</h2>
<p>Product prices, specifications, and availability are subject to change. While we strive to keep information accurate and up to date, we recommend verifying details with the retailer before making a purchase.</p>

<h2>Third-Party Links</h2>
<p>Our site contains links to third-party websites, including retailers and affiliates. We are not responsible for the content, privacy practices, or terms of these external sites.</p>

<h2>Contact</h2>
<p>For questions about this disclaimer: <a href="mailto:disclosures@abvorn.com">disclosures@abvorn.com</a></p>
</div>
<footer><p>{PUBLISHER} &mdash; Independent Reviews</p></footer>
</body></html>"""

# ─── About ──────────────────────────────────────────────────────────
ABOUT = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>About Abvorn — Independent Product Reviews</title>
<meta name="description" content="About Abvorn — our mission, review methodology, and how we help you buy with confidence.">
<link rel="icon" type="image/svg+xml" href="{BASE}/assets/favicon.svg">
<style>{CSS}</style>
</head><body>
<div class="container">
<a class="back" href="{BASE}/">&larr; Back to Abvorn</a>
<h1>About Abvorn</h1>
<p class="updated">Independent Reviews Since {YEAR}</p>

<h2>Our Mission</h2>
<p>Abvorn helps people buy with confidence through honest, researched, and data-driven product recommendations. We cut through marketing noise to tell you what's actually worth your money.</p>

<h2>How We Review</h2>
<p>Every product we recommend goes through rigorous evaluation:</p>
<ul>
<li><strong>Research:</strong> We analyze specifications, expert opinions, and thousands of user reviews</li>
<li><strong>Test:</strong> Products are tested against real-world use cases relevant to each category</li>
<li><strong>Compare:</strong> We benchmark against competitors at similar price points</li>
<li><strong>Verify:</strong> Recommendations are updated as new products launch and market conditions change</li>
</ul>
<p>See our full <a href="{BASE}/how-we-test/">How We Test</a> page for detailed methodology.</p>

<h2>Why Trust Us</h2>
<p>We do not accept payment for positive reviews. Our revenue comes from affiliate commissions and advertising — but editorial decisions are made independently. We clearly label all affiliate links and advertisements.</p>
<p>We review products across 10+ categories, from wireless headphones and laptops to fitness trackers and smart home devices.</p>

<h2>Contact</h2>
<p>Email: <a href="mailto:contact@abvorn.com">contact@abvorn.com</a></p>
</div>
<footer><p>{PUBLISHER} &mdash; Independent Reviews</p></footer>
</body></html>"""

# ─── Write files ────────────────────────────────────────────────────
pages = [
    ("docs/privacy/index.html", PRIVACY),
    ("docs/terms/index.html", TERMS),
    ("docs/disclaimer/index.html", DISCLAIMER),
    ("docs/about/index.html", ABOUT),
]

for path_str, html in pages:
    p = Path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    print(f"  Written: {path_str}")

print("\nAll policy pages generated.")
