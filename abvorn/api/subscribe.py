"""Subscribe API — captures name+email+niche into the CRM."""

import logging
from pathlib import Path
from ..crm.subscriber import SubscriberDB

logger = logging.getLogger("abvorn.api.subscribe")

DEFAULT_DB = Path.home() / ".abvorn" / "crm.db"

def handle_subscribe(data: dict, db_path: Path = None) -> dict:
    """Process a subscribe request. data should have: name, email, niche (optional).
    Returns {"status": "ok"} or {"status": "error", "message": "..."}."""
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    niche = (data.get("niche") or "tech").strip()

    if not email or "@" not in email:
        return {"status": "error", "message": "Valid email required"}
    if not name:
        return {"status": "error", "message": "Name required"}

    db = SubscriberDB(db_path or DEFAULT_DB)
    db.add_subscriber(email, f"persona_{niche}", niche)

    import sqlite3
    try:
        with sqlite3.connect(str(db_path or DEFAULT_DB)) as conn:
            conn.execute("UPDATE subscribers SET name=? WHERE email=?", (name, email))
            conn.commit()
    except Exception as e:
        logger.warning(f"Could not store name: {e}")

    logger.info(f"New subscriber: {name} <{email}> for {niche}")
    return {"status": "ok", "email": email, "niche": niche}


def subscribe_form_html() -> str:
    """Generate the subscribe form HTML for embedding in blog posts."""
    return """<div class="subscribe-box">
  <h3>Never miss a review</h3>
  <p>Get the latest buying guides and deals delivered to your inbox.</p>
  <form class="subscribe-form" onsubmit="return abvornSubscribe(event)">
    <div class="subscribe-fields">
      <input type="text" id="sub-name" placeholder="Your name" required maxlength="50">
      <input type="email" id="sub-email" placeholder="Your email" required maxlength="100">
      <button type="submit">Subscribe</button>
    </div>
    <label class="subscribe-niche">
      <select id="sub-niche">
        <option value="tech">All Tech Reviews</option>
        <option value="tv">TVs & Home Theater</option>
        <option value="laptop">Laptops</option>
        <option value="monitor">Monitors</option>
        <option value="smart home">Smart Home</option>
      </select>
    </label>
  </form>
  <div id="subscribe-status"></div>
</div>"""