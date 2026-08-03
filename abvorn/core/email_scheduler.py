"""email_scheduler.py — Abvorn's automated email schedules.

Checks triggered price alerts and sends them via Listmonk transactional
email, plus creates periodic digest campaigns from the unified DB.
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict

from abvorn.core.unified_database import get_unified_db
from abvorn.core.listmonk_client import get_listmonk

logger = logging.getLogger(__name__)


class EmailScheduler:
    def __init__(self):
        self.db = get_unified_db()
        self.listmonk = get_listmonk()

    def check_price_alerts(self) -> List[Dict]:
        alerts = self.db.get_triggered_alerts()
        emails = []
        for alert in alerts:
            emails.append({
                "email": alert['email'],
                "subject": f"Price Drop: {alert['product_name']}",
                "body": self._build_price_alert_email(alert),
                "alert_id": alert['id']
            })
        return emails

    def _build_price_alert_email(self, alert: Dict) -> str:
        return f"""
        <h2>Price Drop Alert!</h2>
        <p>The price for <strong>{alert['product_name']}</strong> has dropped to <strong>${alert['current_price']}</strong>.</p>
        <p>You set an alert for ${alert['target_price']}.</p>
        <p><a href="https://camelcamelcamel.com/product/{alert['asin']}">View Full Price History</a></p>
        <p>&mdash;<br>Abvorn, your trusted product review platform.</p>
        """

    def send_price_alert_emails(self):
        alerts = self.check_price_alerts()
        for alert in alerts:
            try:
                self.listmonk.send_transactional_email(
                    to_email=alert['email'],
                    subject=alert['subject'],
                    body_html=alert['body']
                )
                logger.info("Sent price alert to %s", alert['email'])
                conn = sqlite3.connect(self.db.db_path)
                c = conn.cursor()
                c.execute("UPDATE price_alerts SET status = 'triggered', triggered_at = ? WHERE id = ?",
                          (datetime.now().isoformat(), alert['alert_id']))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error("Failed to send price alert to %s: %s", alert['email'], e)

    def send_weekly_digest(self, list_ids: List[int]):
        content = self._build_newsletter_content()
        if not content:
            return
        try:
            self.listmonk.create_campaign(
                name=f"Weekly Digest {datetime.now().strftime('%Y-%m-%d')}",
                subject="Abvorn Weekly Product Reviews",
                body_html=content,
                list_ids=list_ids
            )
            logger.info("Weekly digest campaign created")
        except Exception as e:
            logger.error("Failed to send weekly digest: %s", e)

    def _build_newsletter_content(self) -> str:
        return "<h1>Weekly Digest</h1><p>Latest reviews and insights...</p>"