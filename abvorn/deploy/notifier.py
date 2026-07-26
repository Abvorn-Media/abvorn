"""Telegram notifier — sends key metrics and alerts to your Telegram.
   Now supports bidirectional command processing."""

import logging, requests, json, time

logger = logging.getLogger("abvorn.deploy.notifier")

from ..core.secrets import load_secrets


class TelegramNotifier:
    """Sends formatted updates to Telegram and processes incoming commands."""

    def __init__(self, token: str = "", chat_id: str = "", bus=None):
        if not token or not chat_id:
            secrets = load_secrets()
            self.token = token or secrets.get("TELEGRAM_TOKEN", "")
            self.chat_id = chat_id or secrets.get("TELEGRAM_CHAT_ID", "")
        else:
            self.token = token
            self.chat_id = chat_id
        self.bus = bus
        self._last_update_id = 0

    COMMANDS = {
        "/status": "Show system status - agents running, last cycle, queue size",
        "/health": "Show health report",
        "/report": "Show latest optimization report",
        "/traffic": "Show traffic analytics from GA4",
        "/predict [niche]": "Show predictive trend velocity",
        "/pause": "Engage kill switch - pause all cycles",
        "/resume": "Disengage kill switch - resume cycles",
        "/agents": "List all agents and their status",
        "/deploy [niche]": "Trigger a deploy for a specific niche",
        "/sites": "List all sites and their niches",
        "/site <slug>": "Show site details",
        "/errors": "Show error report from bug detector",
        "/backup": "Create manual state DB backup",
        "/backups": "List available backups",
        "/backup-restore <name>": "Restore state DB from backup",
        "/env": "Show current environment mode",
        "/help": "Show this help message",
    }

    def send(self, text: str) -> bool:
        """Send a plain text message to Telegram."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured — skipping notification")
            return False
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            resp = requests.post(url, json={"chat_id": self.chat_id, "text": text[:4000], "parse_mode": "HTML"}, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"Telegram API error: {resp.status_code} {resp.text[:200]}")
                return False
            return True
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")
            return False

    def report_cycle(self, niche: str, status: str, title: str = "",
                     revenue: float = 0.0, success_rate: float = 0.0,
                     persona: str = "") -> bool:
        """Report a completed cycle — warm, human, encouraging."""
        if status == "success":
            text = (
                f"✨ Good news from Abvorn HQ!\n\n"
                f"Just wrapped up <b>{niche}</b> and it's looking solid."
            )
            if title:
                text += f"\n\n📄 <b>{title[:100]}</b>"
            if revenue:
                text += f"\n💰 Revenue: ${revenue:.2f}"
            text += f"\n\nAlways learning, always improving. On to the next one! 🚀"
        elif status == "failed":
            text = (
                f"🤔 Hit a snag with <b>{niche}</b> — nothing we can't handle. "
                f"Already adjusting the approach. Will keep you posted."
            )
        else:
            text = f"⏭️ <b>{niche}</b> — skipped this cycle. No hard feelings, just good timing."
        return self.send(text)

    def reply(self, text: str) -> bool:
        """Alias for send — replies to a command."""
        return self.send(text)

    def process_command(self, text: str, supervisor=None, health=None,
                        scheduler=None, state=None) -> str:
        """Parse and execute a Telegram command. Returns response text."""
        cmd = text.strip().lower()
        parts = cmd.split(maxsplit=1)
        base_cmd = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if base_cmd == "/help":
            lines = ["<b>Available commands:</b>"]
            for cmd_name, desc in self.COMMANDS.items():
                lines.append(f"• {cmd_name} — {desc}")
            return "\n".join(lines)

        if base_cmd == "/predict":
            lines = ["📈 <b>Predictive Trends</b>"]
            target_niche = arg.strip().lower() if arg else ""
            scanner = getattr(self, '_trend_scanner', None)
            if scanner and getattr(scanner, '_state', None):
                try:
                    from abvorn.trends.predict.velocity import VelocityTracker
                    vt = VelocityTracker()
                    niches = [target_niche] if target_niche else ["tv", "laptop", "robot vacuum", "monitor", "smart home"]
                    for niche in niches:
                        velocity = vt.get_velocity(niche, scanner._state)
                        rising = sorted(velocity.items(), key=lambda x: -x[1]["frequency"])[:3]
                        if rising:
                            lines.append(f"\n<b>{niche.title()}:</b>")
                            for name, v in rising:
                                icon = "🔥" if v["frequency"] >= 3 else "↑" if v["frequency"] >= 2 else "●"
                                lines.append(f"  {icon} {name.title()} (freq: {v['frequency']}, sources: {v['sources']})")
                    if len(lines) == 1:
                        lines.append("• No velocity data yet — run a trend cycle first")
                except Exception as e:
                    lines.append(f"• Error: {e}")
            else:
                lines.append("• Trend scanner not available")
            return "\n".join(lines)

        if base_cmd == "/traffic":
            lines = ["📈 <b>Traffic Analytics</b>"]
            if hasattr(self, '_analytics_engine') and self._analytics_engine:
                report = self._analytics_engine.generate_insight_report(site_id=arg if arg else None)
                lines.append(report[:3000])
            else:
                lines.append("• Analytics engine not available")
            return "\n".join(lines)

        if base_cmd == "/status":
            lines = ["📊 <b>System Status</b>"]
            if supervisor:
                agents = supervisor.get_agent_status()
                lines.append(f"• Agents: {len(agents)} total")
                for a in agents:
                    hb = f" (HB: {a['heartbeat_age_s']}s ago)" if a['heartbeat_age_s'] is not None else ""
                    lines.append(f"  - {a['name']}: {a['status']}{hb}")
            if state:
                qsize = len(state.get_all_niches()) if hasattr(state, 'get_all_niches') else 0
                lines.append(f"• Queue size: {qsize}")
            lines.append(f"• Paused: {'Yes' if state and state.get_meta('kill_switch', False) else 'No'}")
            return "\n".join(lines)

        if base_cmd == "/health":
            lines = ["🩺 <b>Health Report</b>"]
            if health:
                hc = health.check()
                lines.append(f"• Healthy: {hc.get('healthy', False)}")
                if hc.get("issues"):
                    for issue in hc["issues"]:
                        lines.append(f"  ⚠ {issue}")
                stats = health.get_stats()
                lines.append(f"• Total cycles: {stats.get('total_cycles', 0)}")
                lines.append(f"• Success rate: {stats.get('success_rate', 0) * 100:.0f}%")
            else:
                lines.append("• Health monitor not available")
            return "\n".join(lines)

        if base_cmd == "/report":
            lines = ["📋 <b>Latest Report</b>"]
            if state:
                report = state.get_meta("last_report", "No report available")
                lines.append(report[:3000] if len(report) > 3000 else report)
            else:
                lines.append("• Report not available")
            return "\n".join(lines)

        if base_cmd == "/pause":
            if state:
                state.set_meta("kill_switch", True)
                return "🔴 <b>Kill switch engaged.</b> All cycles paused."
            return "⚠ Cannot pause — state not available"

        if base_cmd == "/resume":
            if state:
                state.set_meta("kill_switch", False)
                return "🟢 <b>Kill switch disengaged.</b> Cycles resuming."
            return "⚠ Cannot resume — state not available"

        if base_cmd == "/agents":
            lines = ["🤖 <b>Registered Agents</b>"]
            if supervisor:
                agents = supervisor.get_agent_status()
                if not agents:
                    lines.append("• No agents registered")
                for a in agents:
                    lines.append(f"• {a['name']} ({a['class']}) — {a['status']}")
            else:
                lines.append("• Supervisor not available")
            return "\n".join(lines)

        if base_cmd == "/deploy":
            if not arg:
                return "⚠ Usage: <code>/deploy [niche]</code>"
            lines = [f"🚀 <b>Deploy triggered:</b> {arg}"]
            if scheduler:
                scheduler.queue_deploy(arg)
                lines.append(f"• {arg} queued for deploy")
            else:
                lines.append("• Deploy queued (no scheduler available)")
            if self.bus:
                self.bus.publish("telegram.command", {"text": text, "parsed": True})
            return "\n".join(lines)

        if base_cmd == "/sites":
            lines = ["🌐 <b>Sites</b>"]
            registry = getattr(self, '_site_registry', None)
            if registry:
                sites = registry.list()
                if sites:
                    for s in sites:
                        lines.append(f"• <b>{s.name}</b> ({s.slug}) — {len(s.niches)} niches, {s.status}")
                else:
                    lines.append("• No sites registered")
            else:
                lines.append("• Site registry not available")
            return "\n".join(lines)

        if base_cmd == "/site":
            if not arg:
                return "⚠ Usage: <code>/site [slug]</code>"
            registry = getattr(self, '_site_registry', None)
            if not registry:
                return "• Site registry not available"
            sites = registry.list()
            for s in sites:
                if s.slug == arg:
                    lines = [f"🏷 <b>{s.name}</b>"]
                    lines.append(f"  ID: {s.site_id}")
                    lines.append(f"  Slug: {s.slug}")
                    lines.append(f"  Tagline: {s.tagline or '(none)'}")
                    lines.append(f"  Colors: {s.primary_color} / {s.secondary_color}")
                    lines.append(f"  Niches: {', '.join(s.niches) if s.niches else '(none)'}")
                    lines.append(f"  Domain: {s.domain or '(none)'}")
                    lines.append(f"  Status: {s.status}")
                    return "\n".join(lines)
            return f"• Site '{arg}' not found"

        if base_cmd == "/errors":
            reporter = getattr(self, '_error_reporter', None)
            if reporter:
                return reporter.format_report()
            return "\U0001f6a8 <b>Error Reporter</b>\nNot available"

        if base_cmd == "/backup":
            bm = getattr(self, '_backup_manager', None)
            if bm:
                name = bm.create("manual")
                return f"\U0001f4be <b>Backup created</b>\n{name}"
            return "\U0001f4be <b>Backup</b>\nNot available"

        if base_cmd == "/backups":
            bm = getattr(self, '_backup_manager', None)
            if bm:
                return bm.format_list()
            return "\U0001f4be <b>Backups</b>\nNot available"

        if base_cmd == "/backup-restore":
            if not arg:
                return "\u26a0 Usage: <code>/backup-restore [name]</code>"
            bm = getattr(self, '_backup_manager', None)
            if bm and bm.restore(arg):
                return f"\u2705 <b>Restored from:</b> {arg}"
            return f"\u274c <b>Restore failed.</b> Backup '{arg}' not found."

        if base_cmd == "/env":
            env = getattr(self, '_env_mode', None)
            if env:
                return env.format_status()
            return "<b>Environment</b>\nNot configured (defaults to development)"

        return f"\u26a0 Unknown command: {base_cmd}\nUse /help to see available commands."

    def check_commands(self, bot_token: str = None, chat_id: str = None,
                       supervisor=None, health=None, scheduler=None,
                       state=None) -> list[dict]:
        """Poll Telegram for new commands, process them, send responses."""
        token = bot_token or self.token
        cid = chat_id or self.chat_id
        if not token or not cid:
            return []
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(url, params={
                "offset": self._last_update_id + 1,
                "timeout": 5,
            }, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not data.get("ok"):
                return []
            processed = []
            for update in data.get("result", []):
                update_id = update.get("update_id", 0)
                if update_id <= self._last_update_id:
                    continue
                self._last_update_id = max(self._last_update_id, update_id)
                msg = update.get("message", {})
                text = msg.get("text", "")
                msg_cid = str(msg.get("chat", {}).get("id", ""))
                if not text or not text.startswith("/"):
                    continue
                if self.bus:
                    self.bus.publish("telegram.command", {"text": text, "update_id": update_id})
                response = self.process_command(text, supervisor=supervisor,
                                                 health=health, scheduler=scheduler,
                                                 state=state)
                if msg_cid and response:
                    self.reply(response)
                processed.append({"text": text, "response": response, "update_id": update_id})
            return processed
        except Exception as e:
            logger.warning(f"Telegram command poll failed: {e}")
            return []

    def report_health(self, stats: dict) -> bool:
        """Report system health stats."""
        text = (
            f"🩺 <b>Health Check</b>\n"
            f"• Total cycles: {stats.get('total_cycles', 0)}\n"
            f"• Success rate: {stats.get('success_rate', 0):.0%}\n"
            f"• Avg duration: {stats.get('avg_duration_s', 0):.0f}s\n"
            f"• Opportunities: {stats.get('pending_opportunities', 0)} pending"
        )
        return self.send(text)

    def report_error(self, niche: str, error: str, attempt: int = 0) -> bool:
        """Report an error or failure."""
        text = (
            f"🚨 <b>Error Report</b>\n"
            f"• Niche: <code>{niche}</code>\n"
            f"• Attempt: {attempt + 1}\n"
            f"• Error: {error[:300]}"
        )
        return self.send(text)