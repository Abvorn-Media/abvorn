# Abvorn

Autonomous AI-powered affiliate content network. Generates expert product reviews, deploys to GitHub Pages, posts to social media, and runs optimization cycles — all without human intervention.

## Quick Start

```bash
git clone https://github.com/YOUR_USER/YOUR_REPO.git
cd YOUR_REPO
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e .
```

Create `~/.abvorn/boardroom/secrets.json` with your keys (see `.env.example`):

```bash
cp .env.example ~/.abvorn/boardroom/secrets.json
# edit with your actual keys
```

Bootstrap and run:

```bash
abvorn migrate      # create first site
abvorn cycle        # test one content cycle
abvorn daemon       # start autonomous mode
```

## Commands

```
abvorn daemon         Run all agents continuously
abvorn cycle          One full discovery -> content -> deploy cycle
abvorn brain-refresh  Scan and index the knowledge brain
abvorn once [niche]   Run pipeline for a specific niche
abvorn pause          Kill switch — stop all cycles
abvorn resume         Resume after pause
abvorn status         Show system status
abvorn health         Health check with stats
abvorn migrate        Bootstrap initial site
abvorn --version      Show version
abvorn --dry-run      Preview without executing
```

Or run via `python -m abvorn <command>`.

## Architecture

```
Scanner (trends) -> Factory (content) -> SiteAwareDeployer (GitHub Pages)
     |                   |                       |
Scheduler (queue)   Pipeline (email)     CrossLinker (sister sites)
     |                   |                       |
Optimizer (daemon)  CTA (hooks)         PersuasionWidget (product recs)
```

| Module | Path | Purpose |
|--------|------|---------|
| Sites | `abvorn/sites/` | Multi-site model, brand engine |
| Deploy | `abvorn/deploy/` | GitHub Pages, brand template |
| Content | `abvorn/content/` | Pipeline, persuasion factory |
| Agents | `abvorn/agents/` | Supervisor, research, writer |
| Brain | `abvorn/brain/` | Knowledge principles, RAG |
| CRM | `abvorn/crm/` | Subscriber DB, email sender |
| Monitor | `abvorn/monitor/` | Error reporter, daemon guard |

## n8n Workflows

Five active workflows on the Oracle server (`92.4.157.87:5678`):

| Workflow | Purpose |
|----------|---------|
| Video Render | Generate short-form video from content |
| Reflection Pipeline | Post-cycle learning extraction |
| Evolution Check | Track agent improvement over time |
| GSC Analysis | Pull Google Search Console data into Sheets |
| Publish Content | Deploy generated articles to GitHub Pages |

Import workflow JSONs from `n8n/workflows/` into your n8n instance.

## API Endpoints

The mobile server (`mobile_server.py`) exposes:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | System health check |
| `/api/content/recent` | GET | Recent generated content |
| `/api/newsletter/subscribe` | POST | Email subscriber signup |
| `/api/entitlements/pending` | GET | Pending permission approvals |
| `/api/entitlements/approve` | POST | Approve a pending action |
| `/api/surplus` | GET | Surplus metrics |

## Testing

```bash
pytest tests/ -v
```

24 tests covering the n8n bridge, entitlements, and reflection feedback loop.

## Configuration

Secrets live in `~/.abvorn/boardroom/secrets.json`. See `.env.example` for all keys.

Core config in `config.yaml`:

```yaml
economic:
  mode: "estimated"
  estimated_conversion_rate: 0.07
  estimated_commission_rate: 0.06
  average_order_value: 50
```

## License

MIT
