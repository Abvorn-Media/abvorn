"""Sentence variator — breaks predictable sentence patterns."""

import re, logging

logger = logging.getLogger("abvorn.humanize.variator")


class SentenceVariator:
    """Varies sentence length, breaks long sentences, changes openers."""

    def vary_length(self, text: str) -> str:
        """Restructure text to mix short, medium, and long sentences."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        result = []
        for s in sentences:
            words = s.split()
            if len(words) > 25:
                result.extend(self._break_sentence(s, 25))
            else:
                result.append(s)
        return " ".join(result)

    def _break_sentence(self, sentence: str, max_words: int = 25) -> list[str]:
        """Break a long sentence into two at a natural junction."""
        words = sentence.split()
        if len(words) <= max_words:
            return [sentence]
        break_point = self._find_break_point(words, max_words)
        first = " ".join(words[:break_point])
        rest = " ".join(words[break_point:])
        rest = rest[0].lower() + rest[1:] if rest else ""
        return [first.rstrip(",") + ".", rest + "."]

    def _find_break_point(self, words: list[str], max_words: int) -> int:
        """Find best break point near max_words (after conjunction or comma)."""
        candidates = []
        for i in range(max_words - 3, min(max_words + 3, len(words))):
            if i <= 0 or i >= len(words):
                continue
            word = words[i].lower().rstrip(",:;")
            if word in ("and", "but", "or", "so", "yet", "while", "although", "because", "since", "however"):
                candidates.append(i + 1)
            elif words[i - 1].endswith(","):
                candidates.append(i)
        if candidates:
            return min(candidates, key=lambda x: abs(x - max_words))
        return max_words

    def break_long_sentences(self, text: str, max_words: int = 25) -> str:
        """Split sentences over max_words."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        result = []
        for s in sentences:
            words = s.split()
            if len(words) > max_words:
                result.extend(self._break_sentence(s, max_words))
            else:
                result.append(s)
        return " ".join(result)

    def vary_openers(self, text: str) -> str:
        """Change sentence openers so not all start with 'The', 'This', 'It'."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        result = []
        seen_openers = {}

        for s in sentences:
            words = s.split()
            if not words:
                result.append(s)
                continue
            opener = words[0].rstrip(",").lower()
            seen_openers[opener] = seen_openers.get(opener, 0) + 1
            if seen_openers[opener] >= 2 and opener in ("the", "this", "it", "these", "those", "there", "that", "you'll"):
                replacement = self._get_alternative_opener(opener)
                words[0] = replacement
                result.append(" ".join(words))
            else:
                result.append(s)
        return " ".join(result)

    def _get_alternative_opener(self, current: str) -> str:
        replacements = {
            "the": ["Here's", "What about", "Consider", "Take"],
            "this": ["That", "Here", "One", "Another"],
            "it": ["That", "Here's what", "What"],
            "these": ["Those", "Some", "A few"],
            "those": ["These", "Other", "Several"],
            "there": ["You'll find", "Expect", "Look for"],
            "that": ["This", "Here's", "One more"],
            "you'll": ["You can", "Expect to", "Here's what you"],
        }
        import random
        return random.choice(replacements.get(current, ["Here's"]))