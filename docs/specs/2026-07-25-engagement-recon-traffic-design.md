# Engagement, Trend Recon, Traffic Analytics — Design Spec

## Composio Rate Limit Strategy
- MentionWatcher: poll every 15 min (not every daemon cycle)
- Deduplicate — never reply to same mention twice
- Only reply to substantive mentions (questions, comments, critiques — not "@" spam or bots)
- Trend recon uses ZERO Composio calls
- GA4 uses Google Data API directly

## 1. Engagement Monitoring (`abvorn/engagement/`)

### MentionWatcher
- Polls Composio `TWITTER_GET_MENTIONS` every 15 min
- Stores `replied_mention_ids` in state meta to avoid duplicates
- Returns new mentions with: text, author, tweet_id, timestamp

### ReplyGenerator
- LLM crafts reply using: mention text + original post context + brand voice
- Warm, helpful, never defensive — even on criticism
- Only generates replies for substantive mentions (len > 20 chars, not spam)

### ReplyPoster
- Posts via Composio `TWITTER_CREATE_TWEET` with `reply_to` param
- Logs success/failure, tracks response time
- Falls back silently if platform doesn't support reply API

### Integration into SocialAmbassador
- `act("engage")` → MentionWatcher.poll() → ReplyGenerator.craft() → ReplyPoster.post()
- Stores replied IDs in state
- Sends weekly engagement summary via Telegram

## 2. Trend Recon (`abvorn/trends/recon/`)

### DuckDuckGoSource
- Searches "best [niche] 2026", "top rated [niche]", "[niche] review"
- Extracts product names, mentions, frequency
- Returns list of ProductCandidate(name, source, confidence, mention_count)

### AmazonSource  
- Scrapes Amazon top sellers / new releases by category
- Uses requests + BeautifulSoup (no API key)
- Returns ProductCandidate with price, rating, review count

### RedditSource
- Searches `/r/[niche]` and broader subs for recommendation threads
- Extracts products mentioned with upvote-weighted confidence

### GoogleTrendsSource
- Uses `pytrends` for rising queries in niche categories
- Returns trending terms with volume trajectory

### TrendScanner
- Aggregates across providers
- Deduplicates by product name (fuzzy match)
- Scores by: freshness × signal density × source diversity
- Returns top 10 products per niche

## 3. Traffic Analytics (`abvorn/analytics/ga4.py`)

### GA4Client
- Uses `google-analytics-data` library
- Pulls: page views, sessions, active users, traffic sources, top 10 pages
- Queries last 7 days by default
- Caches results for 1 hour (rate limit friendly)

### Integration
- Merges into AnalyticsEngine alongside internal signals
- New `/traffic` Telegram command
- Falls back gracefully if GA4 credentials missing

## 4. Roadmap Update
- Move all modules to Shipped section
- Add engagement/recon/traffic as Tier 1
- Remove stale "Nothing in active build" line

## Testing
- Engagement: 8 tests (watcher poll, dedup, reply gen, reply post, integration)
- Recon: 8 tests (each source + aggregator)
- GA4: 4 tests (client init, query, cache, fallback)
- Total: ~20 new tests