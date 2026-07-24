"""Telegram notifier — sends key metrics and alerts to your Telegram."""

import logging, requests

logger = logging.getLogger("abvorn.deploy.notifier")

from ..core.secrets import load_secrets


class TelegramNotifier:
    """Sends formatted updates to Telegram."""

    def __init__(self, token: str = "", chat_id: str = ""):
        if not token or not chat_id:
            secrets = load_secrets()
            self.token = token or secrets.get("TELEGRAM_TOKEN", "")
            self.chat_id = chat_id or secrets.get("TELEGRAM_CHAT_ID", "")
        else:
            self.token = token
            self.chat_id = chat_id

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
        """Report a completed cycle with key metrics."""
        emoji = "✅" if status == "success" else "❌" if status == "failed" else "⏭️"
        text = (
            f"{emoji} <b>Cycle Report</b>\n"
            f"• Niche: <code>{niche}</code>\n"
            f"• Status: {status}\n"
            f"• Persona: {persona or 'N/A'}\n"
        )
        if title:
            text += f"• Title: {title[:100]}\n"
        if revenue:
            text += f"• Revenue: ${revenue:.2f}\n"
        if success_rate:
            text += f"• Success rate: {success_rate:.0%}\n"
        return self.send(text)

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