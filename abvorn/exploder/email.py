"""Lead magnet and email sequence generation."""

import logging

logger = logging.getLogger("abvorn.exploder.email")


def generate_lead_magnet(content: dict) -> dict:
    """Generate a lead magnet (cheat sheet / checklist) from content."""
    niche = content.get("niche", content.get("post_title", "product")).lower()
    title = content.get("lead_magnet_title", f"Ultimate {niche.title()} Checklist")
    description = content.get("lead_magnet_description", f"Get our expert {niche} buying checklist.")
    magnet_content = content.get("lead_magnet_content", "1. Define your budget\n2. Identify must-have features\n3. Compare top 3 options\n4. Read real user reviews\n5. Make your choice with confidence")
    return {"title": title, "description": description, "content": magnet_content}


def generate_sequence(content: dict, persona: dict = None) -> list[dict]:
    """Generate a 5-7 email nurturing sequence tailored to persona."""
    niche = content.get("niche", content.get("post_title", "product"))
    name = persona.get("name", "the reader") if persona else "the reader"
    title = content.get("post_title", niche)
    pain = ""
    if persona:
        anxieties = persona.get("psychology", {}).get("anxieties", [])
        pain = anxieties[0].lower() if anxieties else "the frustration"

    return [
        {"day": 1, "subject": f"Your {niche} guide is here",
         "body": f"Hey there,\n\nHere's your free guide to finding the best {niche}. We hope it helps you make the right choice.\n\nCheers,\nThe Team"},
        {"day": 3, "subject": f"3 mistakes {name} makes when buying {niche}",
         "body": f"Most people looking for {niche} make these 3 mistakes:\n\n1. Not defining their real needs\n2. Overlooking {pain}\n3. Buying on price alone\n\nHere's how to avoid them..."},
        {"day": 7, "subject": f"Why the right {niche} changes everything",
         "body": f"We did the research so you don't have to. Here's a deep dive into what separates a good {niche} from a great one...\n\n[Link to full guide]"},
        {"day": 14, "subject": f"Still deciding? Here's our top pick",
         "body": f"If you're still deciding, here's the {niche} that won our tests across every category:\n\n[Product name + affiliate link]\n\nIt's the one we'd recommend to our own friends."},
        {"day": 30, "subject": f"Quick check-in — how's it going?",
         "body": f"It's been a month since your guide. How's the {niche} working out for you?\n\nAlso, we've got new guides coming for related products you might love..."},
    ]