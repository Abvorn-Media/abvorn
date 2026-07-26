# Email CRM — Lead Capture, Persona-Targeted Sending, Beautiful Template

## Concept
Moves SubscriberDB from passive storage to active email engine. Every content cycle triggers personalized emails to subscribers matched by persona.

## Architecture

### Template (`abvorn/crm/template.py`)
Single consistent HTML email:
- Branded header (Abvorn logo/name, tagline)
- Personalization: `Hi {name},`
- Content slot: post title + intro paragraph + link ("Read the full guide →")
- Lead magnet slot: "Download your free checklist"
- Footer: affiliate disclosure, unsubscribe link, brand copyright
- Inline CSS, responsive, works in Gmail/Outlook/Apple Mail

### Sender (`abvorn/crm/sender.py`)
- `send_email(to, subject, html)` — via Gmail SMTP (smtp.gmail.com:587, TLS)
- `send_persona_content(persona_id, niche, content)` — queries SubscriberDB for matching persona_id, sends personalized to each
- `send_lead_magnet(email, name, magnet)` — sends the lead magnet download after signup
- Uses secrets: GMAIL_USER, GMAIL_APP_PASSWORD
- Logs open/click tracking (via template pixel + link tracking)

### Lead Capture Flow
1. Reader gets lead magnet offer → enters email
2. System calls `send_lead_magnet(email, name, magnet)` + stores in SubscriberDB
3. Factory generates content for persona X → system calls `send_persona_content(persona_x, niche, content)`
4. All subscribers of persona_x get: "Hey, we found something for you..."

### Files
- Create: `abvorn/crm/template.py`
- Create: `abvorn/crm/sender.py`
- Create: `tests/test_sender.py`
- Modify: `abvorn/daemon.py` — wire into cycle