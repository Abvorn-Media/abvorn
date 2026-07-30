import re

with open(r"C:\Users\Jean Mare\Documents\Default Project\docs\index.html", encoding="utf-8", errors="replace") as f:
    index = f.read()

# Extract head block
head_end = index.find("</head>")
head_block = index[:head_end]

# Extract header with nav
nav_start = index.find('<a class="skip-link"')
nav_end = index.find("</nav>") + len("</nav>")
nav_block = index[nav_start:nav_end]

# Logo
m = re.search(r'<img src="([^"]*logo[^"]*)"', index)
logo = m.group(1) if m else "/abvorn/logo.svg"

# Footer
footer_start = index.rfind('<footer class="footer"')
footer_end = index.find("</html>")
footer_block = index[footer_start:footer_end]

# Show key parts
print("LOGO:", logo)
print()
print("=== HEAD (favicon and fonts) ===")
for line in head_block.split("\n"):
    if any(k in line for k in ["icon", "font", "style", "meta name"]):
        print(line.strip()[:150])
print()
print("=== NAV ===")
print(nav_block[:600])
print()
print("=== FOOTER (first 600 chars) ===")
print(footer_block[:600])