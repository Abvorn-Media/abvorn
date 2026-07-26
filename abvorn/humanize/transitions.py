"""Transition injector — adds conversational flow between paragraphs."""

import re, logging, random

logger = logging.getLogger("abvorn.humanize.transitions")

TRANSITIONS = {
    "contrast": [
        "But here's the thing:",
        "That said,",
        "Here's the catch:",
        "The flip side:",
        "On the other hand,",
        "But don't take our word for it —",
    ],
    "emphasis": [
        "Here's what matters:",
        "The short version:",
        "The key insight:",
        "What you need to know:",
        "Here's the headline:",
    ],
    "example": [
        "Take the Sony WH-1000XM5:",
        "Consider this:",
        "Here's a real example:",
        "Case in point:",
    ],
    "elaboration": [
        "Here's why:",
        "Here's how it works:",
        "What does that mean in practice?",
        "Let's break that down:",
    ],
    "conclusion": [
        "The bottom line:",
        "Here's what we recommend:",
        "After all that testing,",
        "Here's where we landed:",
    ],
    "concession": [
        "To be fair,",
        "In its defense,",
        "Credit where it's due:",
        "That's not to say it's bad —",
    ],
}

_CONTEXT_SIGNALS = {
    "but": "contrast",
    "however": "contrast",
    "unfortunately": "contrast",
    "the problem": "contrast",
    "the catch": "contrast",
    "importantly": "emphasis",
    "key": "emphasis",
    "most": "emphasis",
    "crucial": "emphasis",
    "for example": "example",
    "for instance": "example",
    "such as": "example",
    "specifically": "elaboration",
    "in other words": "elaboration",
    "that means": "elaboration",
    "in summary": "conclusion",
    "to sum up": "conclusion",
    "ultimately": "conclusion",
    "honestly": "concession",
    "admittedly": "concession",
}


class TransitionInjector:
    """Adds natural transition phrases to improve conversational flow."""

    def inject_transitions(self, text: str) -> str:
        """Analyze text and add natural transition phrases where missing."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) < 2:
            return text

        result = [paragraphs[0]]
        injected = 0

        for i in range(1, len(paragraphs)):
            prev_lower = paragraphs[i - 1].lower()
            curr = paragraphs[i]
            curr_lower = curr.lower()

            already_has_transition = any(
                curr_lower.startswith(phrase.lower().rstrip(":").rstrip(","))
                for category in TRANSITIONS.values()
                for phrase in category
            )
            if already_has_transition:
                result.append(curr)
                continue

            context = self._detect_context(prev_lower, curr_lower)
            if context and injected < max(1, len(paragraphs) // 3):
                transition = random.choice(TRANSITIONS[context])
                curr = transition + " " + curr[0].lower() + curr[1:] if curr[0].isupper() else transition + " " + curr
                injected += 1

            result.append(curr)

        return "\n\n".join(result)

    def inject_transitions_html(self, html: str) -> str:
        """Same as inject_transitions but works on HTML content."""
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        if not paragraphs:
            return html

        text_blocks = [re.sub(r'<[^>]+>', '', p).strip() for p in paragraphs]

        plain = "\n\n".join(text_blocks)
        modified = self.inject_transitions(plain)
        modified_paragraphs = modified.split("\n\n")

        result_html = html
        for i, (orig_p, mod_text) in enumerate(zip(paragraphs, modified_paragraphs)):
            stripped_orig = re.sub(r'<[^>]+>', '', orig_p).strip()
            orig_html_tag = re.match(r'(<p[^>]*>)', orig_p)
            close_tag = "</p>"

            if stripped_orig and mod_text and stripped_orig != mod_text:
                if orig_html_tag:
                    new_p = orig_html_tag.group(1) + mod_text + close_tag
                    result_html = result_html.replace(orig_p, new_p, 1)

        return result_html

    def _detect_context(self, prev_para: str, curr_para: str) -> str:
        """Detect the conversational context between two paragraphs."""
        for signal, context in _CONTEXT_SIGNALS.items():
            if signal in curr_para[:100]:
                return context
        if any(word in curr_para[:80] for word in ["best", "winner", "recommend", "top pick"]):
            return "conclusion"
        if any(word in curr_para[:80] for word in ["downside", "drawback", "limitation", "downside"]):
            return "concession"
        return None