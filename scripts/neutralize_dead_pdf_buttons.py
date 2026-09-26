import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def git(args, **kw):
    return subprocess.run(["git"] + args, capture_output=True, **kw)

broken = []
r = git(["grep", "-l", "class=.pdf-download-btn", "origin/main", "--", "docs"])
if r.returncode != 0:
    print("no matches")
    raise SystemExit(0)
for line in r.stdout.decode("utf-8", "replace").splitlines():
    if not line.strip():
        continue
    f = line.split(":", 1)[1] if line.startswith("origin") else line.split(":", 1)[0]
    c = git(["show", "origin/main:" + f])
    if c.returncode != 0:
        continue
    content = c.stdout.decode("utf-8", "replace")
    m = re.search(r'href="(https://abvorn\.com/reviews/[^"#]+\.pdf)"', content)
    if not m:
        continue
    pdf_rel = m.group(1).replace("https://abvorn.com/", "docs/")
    exists = git(["cat-file", "-e", "origin/main:" + pdf_rel]).returncode == 0
    if not exists:
        broken.append((f, m.group(1)))
        print("BROKEN:", f, "->", pdf_rel)

print("broken pdf buttons:", len(broken))

# Neutralize: drop the hero-pdf <a class="pdf-download-btn"> block and blank
# out pdf_url in the guide JS payload so the submit path keeps working but the
# dead "Download PDF" link disappears (mirrors daemon-deployed pages).
for f, _ in broken:
    p = os.path.join(root, f.replace("/", os.sep))
    t = open(p, encoding="utf-8").read()
    orig = t
    # remove <p class="hero-pdf">...</p> block (contains the button)
    t = re.sub(r'<p class="hero-pdf">.*?</p>\n?', "", t, flags=re.S)
    # blank out pdf_url in the JS payload
    t = re.sub(r'"pdf_url":\s*"[^"]*"', '"pdf_url": ""', t)
    if t != orig:
        open(p, "w", encoding="utf-8").write(t)
        print("neutralized", f)
    else:
        print("UNCHANGED", f)

print("done")