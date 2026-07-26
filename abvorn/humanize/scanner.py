"""AI-ism detection scanner — finds patterns that make AI text recognizable."""

import re, logging

logger = logging.getLogger("abvorn.humanize.scanner")

AI_ISM_PATTERNS = [
    (re.compile(r'\bAdditionally,\s', re.IGNORECASE), "Sentence starting with 'Additionally,'", "Remove or replace with 'Plus,' / 'On top of that,'"),
    (re.compile(r"\bIt('s| is) worth noting that\b", re.IGNORECASE), "'It's worth noting that'", "Delete — the reader decides what's worth noting"),
    (re.compile(r'\bIn conclusion\b', re.IGNORECASE), "'In conclusion'", "Delete or replace with 'The bottom line:'"),
    (re.compile(r"\bIt('s| is) important to\b", re.IGNORECASE), "'It is important to'", "Delete — state the fact directly"),
    (re.compile(r'\bWhen it comes to\b', re.IGNORECASE), "'When it comes to'", "Replace with direct topic introduction"),
    (re.compile(r'\bthe\s+(world|realm)\s+of\b', re.IGNORECASE), "'the world/realm of'", "Be direct about the category"),
    (re.compile(r"\b(Let's|let us)\s+(dive|take a closer look)\b", re.IGNORECASE), "'Let's dive into / take a closer look'", "Just start the section"),
    (re.compile(r"\bIn today's\b", re.IGNORECASE), "'In today's...'", "Be timeless — don't reference 'today'"),
    (re.compile(r'\bUltimately,\s', re.IGNORECASE), "'Ultimately,' as opener", "Delete or replace"),
    (re.compile(r'\bNot only\b.*\bbut also\b', re.IGNORECASE), "'Not only... but also'", "Use simpler conjunction"),
    (re.compile(r'\bin order to\b', re.IGNORECASE), "'in order to'", "Replace with just 'to'"),
    (re.compile(r'\ba\s+myriad of\b|\ba\s+plethora of\b', re.IGNORECASE), "'a myriad/plethora of'", "Use 'many' or a specific number"),
    (re.compile(r"\bIt goes without saying\b", re.IGNORECASE), "'It goes without saying'", "Delete — if it goes without saying, don't say it"),
    (re.compile(r"\bNeedless to say\b", re.IGNORECASE), "'Needless to say'", "Delete"),
    (re.compile(r"\bThat being said\b", re.IGNORECASE), "'That being said'", "Replace with 'That said,'"),
    (re.compile(r"\bAll in all\b", re.IGNORECASE), "'All in all'", "Delete or replace"),
    (re.compile(r"\bIn a nutshell\b", re.IGNORECASE), "'In a nutshell'", "Delete or replace"),
    (re.compile(r"\bis\s+(widely\s+)?considered\b", re.IGNORECASE), "'is considered' (passive)", "Use active voice"),
    (re.compile(r"\bare\s+(widely\s+)?(believed|known|thought)\b", re.IGNORECASE), "'are believed/known' (passive)", "Use active voice with source"),
    (re.compile(r"\bhas\s+been\s+(shown|demonstrated|found)\b", re.IGNORECASE), "'has been shown' (passive)", "Use active voice"),
]


class AIScanner:
    """Scans text for AI-isms — patterns that make AI-generated text recognizable."""

    def scan(self, text: str) -> list[dict]:
        """Scan text for AI-isms. Returns list of {pattern, match, position, suggestion}."""
        results = []
        for regex, label, suggestion in AI_ISM_PATTERNS:
            for match in regex.finditer(text):
                results.append({
                    "pattern": label,
                    "match": match.group(),
                    "position": match.start(),
                    "suggestion": suggestion,
                })
        return sorted(results, key=lambda x: x["position"])

    def scan_html(self, html: str) -> list[dict]:
        """Scan HTML content for AI-isms, ignoring tags."""
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'&[a-z]+;', ' ', text)
        return self.scan(text)

    def count_ai_isms(self, text: str) -> int:
        return len(self.scan(text))

    def count_ai_isms_html(self, html: str) -> int:
        return len(self.scan_html(html))

    def get_ai_score(self, text: str) -> float:
        """Score 0.0-1.0 where 1.0 sounds completely human."""
        count = self.count_ai_isms(text)
        word_count = len(text.split())
        if word_count < 10:
            return 1.0
        density = count / max(1, word_count / 100)
        score = max(0.0, 1.0 - (density * 0.15))
        return round(score, 2)