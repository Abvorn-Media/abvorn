"""Brain knowledge — encoded principles from CRO, UX, branding, storytelling, copywriting.
Infuses expert knowledge into every subsystem. Retrieved principles augment when brain is mounted."""

CRO_PRINCIPLES = {
    "reduction": "Reduce friction at every step. Fewer clicks, less typing, shorter forms, faster load.",
    "anxiety": "Address buying anxiety before it arises. Money-back guarantees, free shipping badges, review counts.",
    "scarcity": "Limited availability drives action. But never fake scarcity — real timers, real stock counts.",
    "social_proof": "Show that others have bought and approved. Numbers > testimonials > celebrity endorsements.",
    "specificity": "Specific claims outperform general ones. '3x faster' beats 'very fast'. '$47/year' beats 'affordable'.",
    "contrast": "Highlight the difference between before/after, with/without, cheap/quality. Contrast drives clarity.",
    "commitment": "Start with a tiny ask (read more, scroll). Each small commitment makes the next one easier.",
    "reciprocity": "Give value before asking for the sale. Free guide, comparison tool, checklist → then CTA.",
    "authority": "Position as expert. Data, credentials, testing methodology, research depth all build authority.",
    "liking": "People buy from people they like. Human voice, personality, relatability, humor.",
    "unity": "Shared identity converts. 'For people like you', 'Join our community', 'From one [persona] to another'.",
    "urgency": "Time pressure (real). Limited-time deals, expiring discounts, seasonal offers.",
    "framing": "How you frame the price matters. '$0.13/day' > '$47/year'. 'Save $200' > 'Get 20% off'.",
    "anchoring": "Show the higher price first. Original vs sale. Premium vs standard. Anchoring sets reference point.",
    "decoy": "Three options → middle one wins. Add a decoy to make your target option look like the smart choice.",
    "loss_aversion": "People fear loss more than they value gain. 'Don't miss out' > 'Get yours now'.",
    "chunking": "Break decisions into small steps. Compare 3 products, not 10. Chunk choices to prevent overwhelm.",
    "defaults": "Pre-select the best option. Defaults are powerful — but use ethically. Pre-checked 'subscribe' is dark.",
    "progress": "Show progress toward a goal. '2 of 5 steps complete'. Progress bars drive completion.",
    "endowment": "Make them feel ownership before buying. 'Your bundle', 'Your comparison', 'Your picks'."
}

UX_PRINCIPLES = {
    "first_impression": "Users judge in 50ms. Clean design, fast load, clear hierarchy — before they read a word.",
    "hick_law": "More choices = more time to decide. Limit options per screen. 3 products > 7 products > 15 products.",
    "fitts_law": "Bigger + closer = faster interaction. CTAs should be large, thumb-friendly, near relevant content.",
    "miller_law": "Working memory holds 7±2 items. Group information into chunks of 5-9. Navigation, features, testimonials.",
    "jakob_law": "Users expect your site to work like other sites. Familiar patterns > creative innovation. Don't hide the cart.",
    "proximity": "Related items belong together. Product name, price, rating, and CTA in one visual group.",
    "similarity": "Similar elements = similar function. All links look like links. All buttons look like buttons.",
    "closure": "People see complete shapes from incomplete ones. Skeleton loading > full loading states.",
    "figure_ground": "Clear contrast between content and background. Cards, shadows, borders create visual hierarchy.",
    "common_region": "Elements in same bounded area are perceived as related. Use cards, sections, containers.",
    "serial_position": "First and last items in lists are remembered best. Put CTAs and key info at start or end.",
    "cognitive_load": "Minimize mental effort. Clear labels, consistent navigation, eliminated jargon.",
    "error_prevention": "Prevent errors, don't just handle them. Confirm before delete, validate inline, constrain inputs.",
    "consistency": "Same patterns everywhere. Same CTA style, same button colors, same mobile menu across all pages.",
    "feedback": "Every action gets a reaction. Button press → visual feedback. Form submit → success message.",
    "affordance": "Design elements should signal their purpose. Underlined = clickable. Button shape = pressable.",
    "readability": "16px minimum font. 60-75 characters per line. High contrast. No walls of text without breaks.",
    "mobile_first": "Design for thumb zone (bottom 1/3 of screen). CTAs there. Navigation there. Primary action there.",
    "progressive_disclosure": "Show what's needed now, reveal more on demand. 'Read more', 'Show specs', accordions.",
    "doorway_effect": "Getting started is the hardest part. Auto-play demo, pre-filled forms, immediate value."
}

BRANDING_PRINCIPLES = {
    "differentiation": "If you're the same as competitors, price is the only differentiator. Find your unique stance.",
    "voice_consistency": "Same voice on every touchpoint. Blog, social, email, support — one personality.",
    "personality_traits": "Pick 3 personality traits and never deviate. Abvorn: Trustworthy, Direct, Insider.",
    "emotional_story": "Brands are stories people tell themselves. What story does your customer tell when they recommend you?",
    "value_position": "Never compete on price alone. Compete on expertise, trust, convenience, or community.",
    "visual_identity": "Colors, typography, spacing — create a system, not a collection. Every visual choice carries meaning.",
    "tone_spectrum": "Know when to shift tone. Educational → authoritative. Social → playful. Crisis → empathetic.",
    "brand_promises": "3 promises max. Keep all of them. Abvorn: 'Save time', 'Buy better', 'Trust our research'.",
    "enemy_customer": "Know who you're NOT for as clearly as who you ARE. A brand that serves everyone serves no one.",
    "foundation_story": "Why does this brand exist? Not 'to sell products' — 'because most buying advice is paid, not earned'.",
    "culture_brand": "Build a following, not just a customer base. Shared values, inside jokes, community rituals.",
    "premium_signals": "Price is not the only premium signal. Better materials, curated selection, expert-only tone.",
    "transparency": "Radical transparency builds trust no competitor can match. Show process, admit flaws, reveal margins.",
    "rituals": "Brand rituals create belonging. Weekly roundups, annual awards, signature formats. Repeat them forever.",
    "owned_media": "Rent vs own. Social platforms are rented. Email list, blog, community are owned. Invest in owned."
}

STORYTELLING_PRINCIPLES = {
    "arc": "Every piece needs a beginning (problem), middle (journey), end (resolution). Even a product review.",
    "hero_customer": "The customer is the hero. Your brand is the guide. Guide ≠ hero. Never make yourself the hero.",
    "stakes": "Why does this matter? What's lost if they choose wrong? Money, time, safety, status, peace of mind.",
    "empathy": "Show you understand their pain before offering the solution. 'We know how frustrating it is when...'",
    "concrete_details": "Abstract = ignored. Concrete = remembered. 'Scratched on day 3' > 'poor quality'. '$47' > 'affordable'.",
    "unexpectedness": "Surprise breaks patterns. 'What if everything you know about buying a mattress is wrong?'",
    "credibility_chain": "Who told you? → What did you find? → Why should they care? Chain of credibility builds trust.",
    "show_dont_tell": "'We tested for 40 hours' > 'We're thorough'. 'The handle broke on day 3' > 'It's not durable'.",
    "pattern_interrupt": "Break reader's autopilot. Start with a question, a shocking stat, a confession, a paradox.",
    "mini_stories": "Embed short stories (2-3 sentences) in product reviews. 'I bought this for my dad. He called me twice.'",
    "open_loops": "Create curiosity gaps. 'There's one thing most buyers miss — and it costs them hundreds.' Close it later.",
    "metaphor": "Complex ideas need simple frames. 'Think of it like a Swiss Army knife. Lots of tools, but you'll only use two.'",
    "sensory_language": "Engage all senses. 'The aluminum body feels cool and solid in your hand.' Not 'It's well-built'.",
    "specificity": "'3 hours of testing with 12 different materials' beats 'extensive testing'. Specificity is credibility.",
    "transformation": "Show the before and after. 'Before: 30 minutes grinding beans. After: Fresh espresso in 30 seconds.'"
}

COPYWRITING_PRINCIPLES = {
    "pas": "Problem → Agitate → Solve. State their problem, make it hurt, offer the solution. Classic but effective.",
    "aida": "Attention → Interest → Desire → Action. Hook them, keep them, make them want it, tell them what to do.",
    "hook_first": "First sentence is the only sentence that matters. If they don't read it, nothing else exists.",
    "benefits_over_features": "Features tell, benefits sell. '1000W motor' (feature) vs 'Crush ice in 10 seconds' (benefit).",
    "you_not_we": "Use 'you' more than 'we'. The reader is the star. You'll save. You'll love. You'll wonder why you waited.",
    "simple_words": "Big words = small trust. 'Buy' > 'purchase'. 'Use' > 'utilize'. 'End' > 'terminate'. Grade 8 reading level.",
    "short_sentences": "One idea per sentence. Vary length. Short punchy sentences keep rhythm. Longer ones add flow.",
    "active_voice": "'We recommend' > 'It is recommended by us'. Active is direct, confident, personal.",
    "pain_before_gain": "State the pain before the solution. Readers won't value the solution until they feel the pain.",
    "social_proof_specific": "'12,000+ buyers in 2025' > 'Popular choice'. '4.7/5 from 892 reviews' > 'Highly rated'.",
    "urgency_honest": "Real urgency only. 'Pre-order bonus ends Friday' > 'Limited time offer (always available)'. ",
    "objection_handling": "Answer objections before they're asked. 'Is it worth the price?' → Show cost-per-use breakdown.",
    "scannable": "Most people scan, not read. Headlines, bold, bullets, short paragraphs. Make scanning informative.",
    "call_to_action": "One clear CTA per page. 'Buy now on Amazon' > 'Click here to see options and maybe buy something'.",
    "power_words": "You, free, because, instantly, new, proven, results, guarantee, easy, save, secret, now."
}

DOMAINS = {
    "cro": {"label": "Conversion Rate Optimisation", "principles": CRO_PRINCIPLES},
    "ux": {"label": "UX Design", "principles": UX_PRINCIPLES},
    "branding": {"label": "Branding", "principles": BRANDING_PRINCIPLES},
    "storytelling": {"label": "Storytelling", "principles": STORYTELLING_PRINCIPLES},
    "copywriting": {"label": "Copywriting", "principles": COPYWRITING_PRINCIPLES},
}


def get_principles(domain: str = None) -> dict:
    """Get all principles, optionally filtered by domain."""
    if domain:
        d = DOMAINS.get(domain)
        return {d["label"]: d["principles"]} if d else {}
    return {d["label"]: d["principles"] for d in DOMAINS.values()}


def get_principle(domain: str, name: str) -> str:
    """Get the text of a single principle."""
    d = DOMAINS.get(domain)
    if d and name in d["principles"]:
        return d["principles"][name]
    return ""


def query_principles(topic: str, limit: int = 5) -> list:
    """Search across all domains for relevant principles."""
    topic_lower = topic.lower()
    results = []
    for domain_key, domain_data in DOMAINS.items():
        for name, text in domain_data["principles"].items():
            if topic_lower in name.lower() or topic_lower in text.lower():
                results.append({
                    "domain": domain_data["label"],
                    "principle": name,
                    "text": text
                })
    return results[:limit]


def summarize_domain(domain: str) -> str:
    """Formatted summary of all principles in a domain."""
    d = DOMAINS.get(domain)
    if not d:
        return ""
    lines = [f"=== {d['label']} ==="]
    for name, text in d["principles"].items():
        lines.append(f"  {name}: {text}")
    return "\n".join(lines)


ALL_DOMAINS = list(DOMAINS.keys())