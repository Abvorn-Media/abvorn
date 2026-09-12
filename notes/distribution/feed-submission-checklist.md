# Feed + Discover submission checklist (item 3)

Verified before this list: https://abvorn.com/feed.xml is valid RSS 2.0 with
144 items, newest pubDate 2026-09-04. robots.txt points crawlers at
https://abvorn.com/sitemap.xml.

## Feed aggregators (add once, evergreen traffic)
1. Flipboard - magazine builder, add source: https://abvorn.com/feed.xml
   (URL -> add feed; let it pull the first ~16 items, then "Add to magazine").
2. Feedly - add source: https://abvorn.com/feed.xml (instant, good for
   anyone following via RSS readers + enables Feedly Discovery).
3. Folio - add feed https://abvorn.com/feed.xml.
4. (Optional) Inoreader discovery, NewsBlur - same feed URL.

## Google Discover (via Search Console)
- Requires the GSC property for abvorn.com to be verified and the sitemap
  submitted: https://abvorn.com/sitemap.xml
- Discover eligibility is automatic once Google sees the content; new/unique
  articles are what triggers it. Ensure each page has an og:image (features
  already render social cards) - Discover requires a large image.
- Check "Performance -> Discovery" in GSC weekly.

## AI / answer-engine visibility (already live)
- https://abvorn.com/llms.txt and /llms-full.txt are generated every cycle -
  keep them in sitemap/robots so crawlers keep seeing them.

## Verification loop
- After first submission, check GA4 "User acquisition" weekly for source
  "Referral" = flipboard.com/feedly.com, and GSC for the first Discover
  impressions. That data feeds the win-seo-growth loop's evidence gate.