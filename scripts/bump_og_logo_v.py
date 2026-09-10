"""bump_og_logo_v.py — add ?v=2 to committed og:image/twitter:image logo refs.

Telegram caches link previews by URL. The og:image bytes at /assets/logo.png
changed to the current brand, so the URL must bump to force a re-fetch. This
is a deterministic one-time sweep over the docs tree; it only touches the logo
meta reference (never nav images or src attributes).

CRLF is preserved (newline=\"\"), UTF-8 is declared on every open.
"""
import re
import sys
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"
RX = re.compile(r'content="https://abvorn\.com/assets/logo\.png"')
NEW = 'content="https://abvorn.com/assets/logo.png?v=2"'


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        problems = 0
        for f in sorted(DOCS_ROOT.rglob("*.html")):
            text = f.read_text(encoding="utf-8", newline="")
            m = RX.search(text)
            if m:
                print(f"  {f.relative_to(DOCS_ROOT.parent)}")
                problems += 1
        print(f"verified {sum(1 for _ in DOCS_ROOT.rglob('*.html'))} files; {problems} unversioned")
        sys.exit(1 if problems else 0)

    total = files = 0
    for f in sorted(DOCS_ROOT.rglob("*.html")):
        text = f.read_text(encoding="utf-8", newline="")
        if not RX.search(text):
            continue
        new_text, n = RX.subn(NEW, text)
        f.write_text(new_text, encoding="utf-8", newline="")
        total += n
        files += 1
    print(f"bumped {total} ref(s) in {files} file(s)")
    sys.exit(0)


if __name__ == "__main__":
    main()