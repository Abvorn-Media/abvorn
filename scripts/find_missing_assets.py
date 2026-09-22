import re, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
out = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/main", "--", "docs"], capture_output=True, text=True).stdout.splitlines()
tree = set("docs" + "/" + p for p in [] )
# build map of actual files
actual = set()
for line in out:
    actual.add(line)  # e.g. docs/assets/tv.svg
# fetch index + category pages to collect src/href refs
candidates = [l for l in out if l.endswith(".html") and ("index.html" in l or "docs/categories/" in l)]
missing = {}
for path in candidates:
    try:
        r = subprocess.run(["git", "show", f"origin/main:{path}"], capture_output=True)
        if r.returncode != 0:
            continue
        content = r.stdout.decode("utf-8")
    except Exception:
        continue
    refs = re.findall(r'(?:src|href)="(/(?:assets|hero)[^"?#]*)"', content)
    for r in refs:
        # resolve root-relative to docs path
        doc_path = "docs" + r
        if doc_path.endswith("/"):
            doc_path += "index.html"
        if doc_path not in actual:
            missing.setdefault(doc_path, set()).add(path)
for target in sorted(missing):
    print("MISSING:", target)
    print("   referenced by:", ", ".join(sorted(missing[target]))[:300])
print("total missing targets:", len(missing))