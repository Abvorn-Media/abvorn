# Autonomous Affiliate Network — Design Spec

> Multiple sites, one brain. Each category gets its own branded destination. Shared intelligence, cross-linking, unified analytics.

---

## 1. Hosting Model

Single GitHub Pages repo. Each site occupies `docs/{site-slug}/`. No new infra.

- **Dev deploy**: `https://{owner}.github.io/{repo}/{site-slug}/{niche}/`
- **Production**: when a custom domain is configured per site, canonical URLs update
- **Directory root** (`/`): network directory listing all sites ("Our Sites"), with "Powered by Abvorn" footer
- **Site home** (`/{site-slug}/`): lists all published posts for that site

---

## 2. Site Model

Stored in `sites` table of the existing state DB (SQLite via `AbvornState`).

```
site_id:        UUID (auto)
slug:           "tech-gadgets" (directory name, URL path segment)
name:           "Tech & Gadgets"
tagline:        "Honest reviews for smart shoppers"
domain:         "" (optional — set when a custom domain arrives)
logo_text:      "Tech & Gadgets"
logo_icon:      "🔌" (emoji or SVG path — no image files to manage)
primary_color:  "#1a73e8"
secondary_color:"#34a853"
voice_rules:    JSON (per-site overrides, can be empty)
created_at:     ISO timestamp
niches:         ["tv", "laptop", "monitor", "robot-vacuum", "smart-home"]
status:         "active" | "paused"
```

### SiteRegistry

CRUD class operating on the `sites` table:

- `register(config) -> site_id` — creates a new site
- `get(site_id) -> Site` — fetch by ID
- `find_by_niche(niche_slug) -> Site | None` — returns the site whose niches list includes this niche
- `assign_niche(site_id, niche_slug)` — adds a niche to a site's list
- `auto_assign(niche_slug) -> Site | None` — if no site covers this niche, returns None (daemon decides whether to prompt)
- `list() -> list[Site]` — all sites
- `count() -> int`

### Site Discovery

When a new niche is found by `OpportunityScanner` and `auto_assign()` returns None, the daemon sends a Telegram prompt:

> `New niche "wireless-earbuds" doesn't fit any existing site. Create a new site, or assign to an existing one?`

Creating a new site is a two-step prompt — daemon proposes the site config via LLM (name, tagline, colors based on niche analysis), user approves/rejects.

---

## 3. Brand Engine

Single function: `get_brand(site_id) -> BrandConfig`

### Global invariants (never overridable)

- Banned phrases list from `abvorn/brand.py`
- Affiliate disclosure requirements
- Trust signals format
- Mission statement (internal)

### Per-site identity (from Site model + voice_rules + audience persona)

- Brand name, tagline
- Colors → CSS variables in templates
- Logo = `{logo_icon} {logo_text}` in header/footer
- Voice tweaks (allowed platform tone overrides within global constraints)
- **Design DNA**: the site's primary audience persona (from PersonaEngine) drives layout, typography, density, and visual mood

### Design DNA system

Each persona type maps to a design DNA profile — a set of CSS variable overrides injected as `<body class="dna-{profile}">`:

| DNA Profile | Persona | Typography | Layout | Cards | Imagery | Buttons |
|-------------|---------|------------|--------|-------|---------|---------|
| `tech` | Technical buyer, spec-shopper | Sans-serif, compact, high density | Dense grids, expandable spec tables | Flat, border-defined | Screenshots, diagrams, comparison charts | Outline, sharp corners |
| `warm` | Lifestyle buyer, family-oriented | Rounded sans-serif, generous line-height | Wide layouts, image-led sections | Soft shadows, rounded | Lifestyle photos, room setups | Filled, rounded |
| `premium` | Premium buyer, quality-seeker | Serif headlines, generous spacing | Minimal, white space heavy | Elevated, subtle borders | Hero imagery, editorial | Ghost, thin borders |

Resolution: `BrandConfig` is a frozen dataclass. Per-site `voice_rules` merge on top of global defaults. If `voice_rules` is empty, global voice applies as-is. Design DNA is derived from the site's dominant niche persona, not manually configured.

Consumed by: HTML template renderer (deploy), social post formatter (via PlatformAgent), Telegram dashboard (showing brand name).

---

## 4. SiteAwareDeployer

Wraps the existing `GitHubDeployer`. Minimal changes:

### Pre-deploy hook

1. Look up niche → `SiteRegistry.find_by_niche(niche)`
2. `get_brand(site_id)` → merged `BrandConfig`
3. Pass `BrandConfig` into the template renderer

### Template changes (in `deploy/github.py`)

| Element | Change |
|---------|--------|
| `<title>` | Uses brand name instead of "Abvorn" |
| `<h1>` / header | Brand name + logo |
| CSS | `--primary`, `--secondary` injected as CSS variables |
| Footer | `"Powered by Abvorn"` link to `/` |
| Canonical URL | Uses `site.domain` if set, else `/{site-slug}/{niche}/` |
| Affiliate disclaimer | Always includes brand name, format unchanged |
| Social share tags | `og:site_name` = brand name |

### Output path

`docs/{site-slug}/{niche-slug}/index.html` (was `docs/{niche-slug}/`)

### Redirect from old paths

`docs/{niche-slug}/index.html` → `<meta http-equiv="refresh" content="0; url=/tech-gadgets/{niche-slug}/">`

### Site homepage

After each deploy, render `docs/{site-slug}/index.html` listing all published posts for that site.

---

## 5. CrossLinker

Lightweight component that adds contextual cross-site links after content generation.

### Mechanism

1. After a post is generated for niche A, query `CrossNicheIntelligence.compute_niche_similarity(niche_A)` for related niches
2. Pick the top candidate (similarity > threshold) from a different site
3. Inject 1 natural link into the post body: `"Looking for {related_topic}? Check out our guide to {related_product}"`

### Constraints

- Max 2 links per post
- Minimum similarity threshold (configurable per site, default 0.3)
- Never links to a niche on the same site (sister site only)
- Falls back to the site's own homepage if no specific niche content matches
- Failure never blocks deploy — logged and skipped

### Data flow

CrossLinker reads from the state DB's `posts` table (title, slug, niche) and the `sites` table. No new data stores.

---

## 6. Analytics & Dashboard

### Per-site analytics

`AnalyticsEngine` gains an optional `site_id` filter. `GA4Client` already returns page-path-level data — filter by `/{site-slug}/` prefix.

### Telegram commands

- `/sites` — list all sites, niche count, status
- `/traffic tech-gadgets` — traffic for a specific site
- `/traffic` — aggregate across all sites (existing behavior)
- `/site create` — multi-step prompt to bootstrap a new site

### Dashboard HTML

Root `index.html` shows an "Our Sites" page: cards for each site with name, tagline, niche count, link to site home. Clean, minimal, no Abvorn brand visible except the footer link.

---

## 7. Bootstrap Migration

### Initial state

5 existing niches under a flat `docs/{niche}/` structure. No site config exists.

### Migration steps

1. Auto-create **"Tech & Gadgets"** site with all 5 niches
2. Render redirect HTML at each old `docs/{niche}/index.html` path
3. Rewrite `docs/index.html` to the network directory layout
4. First full deploy writes all content under `docs/tech-gadgets/{niche}/`

### Rollforward only

Once migrated, old paths serve redirects. No reverse migration needed — the system is cumulative.

---

## 8. Testing Strategy

| Component | Test approach |
|-----------|---------------|
| Site model | Unit: create, fetch, assign niche, find_by_niche, auto_assign |
| SiteRegistry | Unit: CRUD operations, edge cases (empty niches, duplicate slugs) |
| BrandEngine | Unit: merge global + per-site, frozen config, empty voice_rules = global fallback |
| SiteAwareDeployer | Integration: mock SiteRegistry, verify output path and template vars change |
| CrossLinker | Unit: similarity threshold, max links, sister-site-only, graceful failure |
| Redirect | Unit: meta refresh HTML format, old→new path mapping |
| Analytics filter | Integration: site_id filter on GA4 client mock |
| Telegram commands | Unit: /sites, /traffic X, /site create flow |

---

## 9. Files & Modules

| File | Purpose |
|------|---------|
| `abvorn/sites/model.py` | `Site` dataclass, `BrandConfig` dataclass |
| `abvorn/sites/registry.py` | `SiteRegistry` — state DB CRUD |
| `abvorn/sites/brand.py` | `get_brand()` — merges global + per-site |
| `abvorn/sites/__init__.py` | Package init, exports |
| `abvorn/deploy/site_deployer.py` | SiteAwareDeployer wrapper |
| `abvorn/deploy/crosslinker.py` | CrossLinker — contextual sister-site links |
| `abvorn/deploy/redirect.py` | Redirect HTML generator for old paths |
| `tests/sites_test.py` | Site model + registry tests |
| `tests/brand_test.py` | BrandEngine tests |
| `tests/crosslinker_test.py` | CrossLinker tests |
| `tests/deploy_test.py` | SiteAwareDeployer integration tests |

### Changes to existing files

| File | Change |
|------|--------|
| `abvorn/deploy/github.py` | Accept `BrandConfig` parameter in render, use for title/colors/logo/footer |
| `abvorn/deploy/notifier.py` | Add `/sites`, `/site create`, `/traffic X` commands |
| `abvorn/deploy/dashboard.py` | Render site-network root page |
| `abvorn/daemon.py` | Wire SiteRegistry into notifier + deployer |
| `abvorn/core/state.py` | Add `sites` table schema |
| `abvorn/analytics/engine.py` | Optional `site_id` filter in insight report |

---

## 10. Non-Goals

- Per-site social accounts (same composio key, brand name injected into posts)
- Custom domains in this iteration (domain field exists as config, deployer uses it for canonical URLs)
- Site-specific analytics credentials (all sites share one GA4 property, filtered by path prefix)
- Multi-repo deployment (everything goes to one repo)
- User-facing auth or admin UI (Telegram is the admin interface)
