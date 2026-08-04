"""Email sender — sends persona-targeted emails via Gmail SMTP."""

import logging, smtplib, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from .template import render_persona_update, render_lead_magnet_email
from ..core.secrets import load_secrets

logger = logging.getLogger("abvorn.crm.sender")


class EmailSender:
    """Sends beautiful, persona-targeted emails via Gmail SMTP."""

    def __init__(self, email: str = None, password: str = None):
        if email is None or password is None:
            secrets = load_secrets()
            self.email = email or secrets.get("GMAIL_USER", "")
            self.password = password or secrets.get("GMAIL_APP_PASSWORD", "")
        else:
            self.email = email
            self.password = password

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send a single email via Gmail SMTP."""
        if not self.email or not self.password:
            logger.warning("Gmail not configured — email skipped")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"Abvorn <{self.email}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.email, self.password)
                server.sendmail(self.email, [to_email], msg.as_string())
            logger.info(f"Email sent to {to_email}: {subject[:50]}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_persona_content(self, persona_id: str, niche: str,
                              content: dict,
                              recipients: list[dict] = None,
                              subscriber_db=None) -> dict:
        """Send persona-targeted content update to matching subscribers."""
        if not recipients and subscriber_db:
            recipients = subscriber_db.get_subscribers(niche=niche)

        post_title = content.get("post_title", "New guide")
        post_url = content.get("post_url", "#")
        persona_name = content.get("persona_name", persona_id)
        sent = 0
        errors = 0

        for sub in recipients or []:
            email = sub.get("email", "")
            name = sub.get("name", email.split("@")[0])
            tracking_consent = bool(sub.get("tracking_consent", 0))
            html = render_persona_update(
                to_name=name, persona_name=persona_name,
                post_title=post_title, post_url=post_url,
                niche=niche,
                tracking_consent=tracking_consent,
            )
            ok = self.send_email(email, f"New: {post_title[:50]}", html)
            if ok:
                sent += 1
            else:
                errors += 1

        logger.info(f"Persona '{persona_id}': {sent} sent, {errors} errors")
        return {"sent": sent, "errors": errors, "total": len(recipients or [])}

    def send_lead_magnet(self, email: str, name: str,
                          magnet_title: str, magnet_url: str = "#",
                          niche: str = "products") -> bool:
        """Send a lead magnet delivery email."""
        html = render_lead_magnet_email(
            to_name=name, magnet_title=magnet_title,
            magnet_url=magnet_url, niche=niche,
        )
        return self.send_email(email, f"Your {niche} guide is here", html)