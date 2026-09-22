import re, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
out = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/main", "--", "docs"], capture_output=True, text=True).stdout.splitlines()
pages = [l for l in out if l.endswith(".html")]
untagged = {}
pattern = re.compile(r"https://(?:www\.)?amazon\.(?:com|co\.uk|de|ca|[a-z]{2,3})/[^\"'\s<>]+")
for path in pages:
    r = subprocess.run(["git", "show", f"origin/main:{path}"], capture_output=True)
    if r.returncode != 0:
        continue
    content = r.stdout.decode("utf-8")
    for m in pattern.finditer(content):
        url = m.group(0).rstrip(".,)")
        if "?" in url and "tag=" in url:
            continue
        if url.endswith(".png") or url.endswith(".jpg") or url.endswith(".jpeg") or url.endswith(".webp"):
            continue
        # ignore tracking/script endpoints
        if url.endswith(("gp", "nav", "ref=")) or "ref=" in url:
            continue
        untagged.setdefault(path, set()).add(url)
for p in sorted(untagged):
    print(p, "->", len(untagged[p]))
    for u in sorted(untagged[p]):
        print("    ", u[:140])