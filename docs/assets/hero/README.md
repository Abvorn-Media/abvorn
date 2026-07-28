# Product Images — Upload Guide
> **SITE-006** — Instructions for hero image upload vs AI fallback logic.

## Where to Upload

```
docs/assets/hero/{niche-slug}.jpg
```

Example: `docs/assets/hero/wireless-headphones.jpg`

## File Spec

| Property | Value |
|----------|-------|
| **Dimensions** | 1920 × 1080 pixels (16:9 landscape) |
| **Format** | JPG (sRGB, progressive optional) |
| **Quality** | 80–85% compression (under 500 KB per file ideal) |
| **Orientation** | Landscape only |

Do **not** upload PNG, WebP, SVG, or other formats — the carousel only loads JPG.

## Naming Convention

Use the exact slug from the URL:

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

Homepage hero: `docs/assets/hero/hero-home.jpg`

## What the Image Should Show

- **Product hero shot** — the best-reviewed product in the category, centered or slightly offset
- Clean background (white, gradient, or lifestyle setting)
- No text overlays, logos, or branding on the image itself
- Well-lit, sharp, true-to-life colors
- Example style: Amazon product hero shots, Best Buy category banners

## How It's Used

Once uploaded, the carousel on each category page will:

1. Load `hero/{slug}.jpg` as the slide background (full-bleed)
2. Render the product name, badge ("Our Pick"), and CTA button on top
3. Auto-rotate between slides every 5 seconds

If no JPG exists for a niche, the system falls back to the SVG placeholder.

## Bulk Upload Checklist

- [ ] All 10 niche JPGs in `docs/assets/hero/`
- [ ] `hero-home.jpg` for the homepage
- [ ] Each file under 500 KB
- [ ] Verify on live site after push
