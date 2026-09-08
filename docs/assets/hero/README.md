# Category Hero Images

> **SITE-006** — Real product photography for niche page heroes, sourced from
> Pexels and credited on page. The SVG placeholders in `docs/assets/` remain
> the fallback.

## How Images Land Here

Fetch with the maintenance script on a machine that has a Pexels key (the
prod server reads `PEXELS_KEY` from `/opt/abvorn-core/.env`):

```
python scripts/fetch_category_heroes.py --out <dir> --key "$PEXELS_KEY"
```

- Runs from the repo root. Art direction is baked into `HEROES` (object-first,
  no people, no bright backdrops — a "specimen on a dark stage") plus a default
  rank pick per niche.
- Downloads at `w=1440` from the Pexels CDN and recompresses to progressive
  JPG (q82). Files stay well under 500 KB.
- Writes `credits.json` next to the images — the page needs one entry per JPG
  to render the on-page `Photo: {photographer} — Pexels` line with a link back
  to the source.

Commit the JPGs and `credits.json`; the generated pages reference them.

## File Spec

| Property | Value |
|----------|-------|
| **Layout** | `docs/assets/hero/{niche-slug}.jpg` |
| **Format** | JPG (progressive, q≈82) |
| **Size** | ~30–180 KB (w1440) |
| **Display** | `max-width:480px`, `aspect-ratio:4/3`, `object-fit:cover` |

## Naming Convention

| Niche | Filename |
|-------|----------|
| Wireless Headphones | `wireless-headphones.jpg` |
| Gaming Mice | `gaming-mice.jpg` |
| 4K Monitors | `4k-monitors.jpg` |
| Laptops | `laptops.jpg` |
| Streaming Devices | `streaming-devices.jpg` |
| Mechanical Keyboards | `mechanical-keyboards.jpg` |
| Wireless Earbuds | `wireless-earbuds.jpg` |
| Fitness Trackers | `fitness-trackers.jpg` |
| Webcams | `webcams.jpg` |
| Smart Home | `smart-home.jpg` |

The homepage slider and `/categories/*/` listing pages use their own art
(niche SVG and generated category motifs) — do not rely on these JPGs there.

## How It's Used

`run_cycle.py::build_category_page` checks for a JPG + `credits.json` entry:
with both present it renders the photo on the hero stage with a visible credit
line; missing either, it falls back to `docs/assets/{slug}.svg` with the stage
hidden from assistive tech as before.

## Regenerating

After changing `HEROES` queries or picks in `scripts/fetch_category_heroes.py`:

1. scp the script to the server and run with the real key into a staging dir
   (see `--out`), including `--dry-run`/`--top` to rank before committing to a
   pick.
2. scp the JPGs + `credits.json` back over `docs/assets/hero/`.
3. Run the mojibake gate (`python scripts/check_publish_content.py`), the test
   suite, and verify one built niche page before committing.