"""Remove the Privacy link from the header nav on every page.

Idempotent: matches the header-nav anchor whose text is exactly "Privacy"
(<a href=".../privacy.html">Privacy</a>), leaving the footer's
">Privacy policy</a>" link untouched. Re-runs change nothing.
"""
import io
import re
import sys
from pathlib import Path

PRIVACY_HEADER = re.compile(r'\n?\s*<a href="[^"]*/privacy\.html">Privacy</a>')


def patch_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    if ">Privacy</a>" not in text:
        return False
    new = PRIVACY_HEADER.sub("", text, count=1)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    docs = Path("docs")
    changed = []
    for p in sorted(docs.rglob("*.html")):
        if patch_file(p):
            changed.append(str(p).replace("\\", "/"))
    print(f"Patched: {len(changed)} pages")
    for c in changed:
        print(f"  {c}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
