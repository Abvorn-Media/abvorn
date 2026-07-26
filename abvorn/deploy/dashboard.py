"""Live system dashboard — generates a beautiful HTML status page for Abvorn.

Deployed alongside content via GitHub Pages. Shows:
- System health and cycle status
- Platform status with optimization progress
- Recent content with quality scores
- Schedule performance data
"""

import logging, json
from datetime import datetime
from pathlib import Path
from html import escape

logger = logging.getLogger("abvorn.dashboard")

_DASHBOARD_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;font-family:'Inter',-apple-system,sans-serif;background:#0a0a0a;color:#e5e5e5}
body{padding:32px 24px;max-width:1100px;margin:0 auto}
h1{font-size:2rem;font-weight:700;letter-spacing:-0.03em;margin-bottom:4px;color:#fff}
h2{font-size:1.3rem;font-weight:600;margin:32px 0 16px;color:#fff}
.subtitle{color:#888;font-size:0.9rem;margin-bottom:32px}
.status-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:40px}
.card{background:#141414;border:1px solid #222;border-radius:8px;padding:20px}
.card .label{font-size:0.75rem;color:#666;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px}
.card .value{font-size:1.5rem;font-weight:700;color:#fff}
.card .value.green{color:#4ade80}
.card .value.red{color:#f87171}
.card .value.yellow{color:#fbbf24}
.card .value.blue{color:#60a5fa}
.platforms{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-bottom:40px}
.platform{background:#141414;border:1px solid #222;border-radius:8px;padding:16px;display:flex;justify-content:space-between;align-items:center}
.platform .name{font-weight:600;color:#fff}
.platform .status-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:8px}
.platform .status-dot.active{background:#4ade80}
.platform .status-dot.stub{background:#fbbf24}
.platform .status-dot.inactive{background:#555}
.platform .meta{font-size:0.8rem;color:#666;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:0.9rem}
th{text-align:left;padding:10px 12px;border-bottom:1px solid #222;color:#888;font-weight:500;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em}
td{padding:10px 12px;border-bottom:1px solid #1a1a1a;color:#ccc}
td.score{font-weight:600}
.score.pass{color:#4ade80}
.score.blocked{color:#f87171}
.score.warn{color:#fbbf24}
.empty{color:#555;text-align:center;padding:32px;font-size:0.9rem}
.footer{margin-top:48px;padding-top:24px;border-top:1px solid #222;color:#555;font-size:0.8rem;text-align:center}
"""


def render_dashboard(health_data: dict = None, platform_data: list = None,
                     gate_summary: dict = None, cycle_history: list = None,
                     optimization_report: dict = None) -> str:
    """Render full system dashboard as HTML."""
    health = health_data or {}
    platforms = platform_data or []
    gate = gate_summary or {}
    cycles = cycle_history or []
    opt = optimization_report or {}

    system_status = health.get("healthy", True)
    total_cycles = health.get("cycles", 0)
    success_rate = health.get("success_rate", 0)
    pending_ops = health.get("pending_ops", 0)
    gate_pass_rate = gate.get("pass_rate", 0)
    total_gated = gate.get("total", 0)

    platform_rows = "".join(
        f'''<div class="platform">
            <div><div class="name"><span class="status-dot {p.get('status', 'inactive')}"></span>{escape(p.get('label', p['name']))}</div>
            <div class="meta">{escape(p.get('niche', ''))} | voice: {escape(p.get('voice', ''))}</div></div>
            <div style="text-align:right"><div class="meta">{p.get('schedule', 'optimizing...')}</div></div>
        </div>'''
        for p in platforms
    ) if platforms else '<div class="empty">No platforms registered</div>'

    cycle_rows = "".join(
        f"<tr><td>{escape(c.get('timestamp', ''))}</td><td>{escape(c.get('niche', ''))}</td><td class='score {'pass' if c.get('passed') else 'blocked'}'>{'PASS' if c.get('passed') else 'BLOCKED'}</td><td>{c.get('score', 0)}</td></tr>"
        for c in cycles[-10:]
    ) if cycles else '<tr><td colspan="4" class="empty">No cycles yet</td></tr>'

    opt_section = ""
    if opt:
        ready = opt.get("platforms_ready_for_optimization", 0)
        partial = opt.get("platforms_with_partial_data", 0)
        total_records = opt.get("total_records", 0)
        opt_section = f"""<div class="card"><div class="label">Optimization Data</div>
        <div class="value blue">{total_records}</div>
        <div style="margin-top:8px;font-size:0.8rem;color:#666">{ready} platforms ready · {partial} building data</div></div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Abvorn — System Dashboard</title><style>{_DASHBOARD_CSS}</style></head>
<body>
<h1>Abvorn</h1>
<p class="subtitle">Autonomous Content System · {datetime.now().strftime('%B %d, %Y %H:%M UTC')}</p>

<div class="status-grid">
    <div class="card">
        <div class="label">System Status</div>
        <div class="value {'green' if system_status else 'red'}">{'ACTIVE' if system_status else 'ISSUES'}</div>
    </div>
    <div class="card">
        <div class="label">Cycles Run</div>
        <div class="value">{total_cycles}</div>
    </div>
    <div class="card">
        <div class="label">Success Rate</div>
        <div class="value {'green' if success_rate > 0.8 else 'yellow'}">{success_rate:.0%}</div>
    </div>
    <div class="card">
        <div class="label">Quality Pass Rate</div>
        <div class="value {'green' if gate_pass_rate > 80 else 'yellow'}">{gate_pass_rate:.0f}%</div>
    </div>
    <div class="card">
        <div class="label">Pending Opportunities</div>
        <div class="value">{pending_ops}</div>
    </div>
    <div class="card">
        <div class="label">Content Gated</div>
        <div class="value">{total_gated}</div>
    </div>
    {opt_section}
</div>

<h2>Platforms</h2>
<div class="platforms">{platform_rows}</div>

<h2>Recent Cycles</h2>
<table><thead><tr><th>Time</th><th>Niche</th><th>Result</th><th>Score</th></tr></thead><tbody>{cycle_rows}</tbody></table>

<div class="footer">Abvorn · Built with soul · Updated every cycle<br>Help people buy with confidence</div>
</body></html>"""


def render_mini_status(gate_result: dict = None, platform: str = "",
                        niche: str = "") -> str:
    """Render a compact status snippet for inline use (Telegram, etc.)."""
    if gate_result:
        score = gate_result.get("composite_score", 0)
        passed = gate_result.get("passed", False)
        failures = gate_result.get("failures", [])
        emoji = "✅" if passed else "❌"
        parts = [f"{emoji} Gate: {score:.0f}/100"]
        if failures:
            parts.extend(f"  ⚠ {f}" for f in failures[:2])
        return "\n".join(parts)
    return f"📡 {platform}: {niche}"


def write_dashboard(output_dir: Path, health_data: dict, platform_data: list,
                     gate_summary: dict, cycle_history: list,
                     optimization_report: dict = None):
    """Write the dashboard HTML to disk (for GitHub Pages deploy)."""
    html = render_dashboard(health_data, platform_data, gate_summary,
                             cycle_history, optimization_report)
    dash_dir = output_dir / "dashboard"
    dash_dir.mkdir(parents=True, exist_ok=True)
    index = dash_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    logger.info(f"Dashboard written: {index}")
    return str(index)


class NetworkDashboard:
    """Generates and deploys network directory + per-site index pages."""

    def __init__(self, state, deployer):
        from ..sites.registry import SiteRegistry
        self._registry = SiteRegistry(state)
        self._deployer = deployer

    def deploy_root_index(self) -> bool:
        try:
            sites = self._registry.list()
            cards = []
            for s in sites:
                niche_list = "".join(f"<li>{n.replace('-', ' ').title()}</li>" for n in s.niches)
                cards.append(f"""
<div class="site-card" style="border:1px solid #ddd;border-radius:8px;padding:16px;margin:16px 0;">
  <h2><a href="/{s.slug}/" style="color:{s.primary_color or '#1a73e8'};text-decoration:none;">{s.name}</a></h2>
  <p>{s.tagline or ''}</p>
  <ul>{niche_list}</ul>
</div>""")
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Our Network</title>
<style>body{{font-family:-apple-system,sans-serif;max-width:800px;margin:0 auto;padding:20px;}}
.site-card h2 a:hover{{text-decoration:underline !important;}}
footer{{margin-top:48px;text-align:center;color:#888;font-size:14px;}}</style>
</head><body>
<h1>Our Network</h1>
<p>Expert reviews across multiple categories.</p>
{"".join(cards)}
<footer>Powered by Abvorn</footer>
</body></html>"""
            self._deployer.deploy_html(html, "")
            return True
        except Exception as e:
            logger.error(f"Root index deploy failed: {e}")
            return False

    def deploy_site_homepage(self, site) -> bool:
        try:
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site.name}</title>
<style>body{{font-family:-apple-system,sans-serif;max-width:800px;margin:0 auto;padding:20px;}}
a{{color:{site.primary_color or '#1a73e8'};}}
footer{{margin-top:48px;text-align:center;color:#888;font-size:14px;}}</style>
</head><body>
<h1>{site.name}</h1>
<p>{site.tagline or ''}</p>
<h2>Categories</h2>
<ul>{"".join(f'<li><a href="/{site.slug}/{n}/">{n.replace("-"," ").title()}</a></li>' for n in site.niches)}</ul>
<footer>Powered by Abvorn</footer>
</body></html>"""
            self._deployer.deploy_html(html, f"{site.slug}/index.html")
            return True
        except Exception as e:
            logger.error(f"Site homepage deploy failed for {site.slug}: {e}")
            return False