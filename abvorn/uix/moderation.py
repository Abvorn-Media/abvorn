"""CommentModerator — filters profanity, spam links, and sensitive content."""

import re
import logging

logger = logging.getLogger("abvorn.uix.moderation")

# Core profanity — non-exhaustive, catches common patterns
PROFANITY_PATTERNS = [
    r'\bf+u+c+k+\w*\b', r'\bs+h+i+t+\w*\b', r'\ba+s+s+h+o+l+e+\b',
    r'\bb+i+t+c+h+\w*\b', r'\bd+a+m+n+\w*\b', r'\bc+r+a+p+\w*\b',
    r'\bf+a+g+\w*\b', r'\bn+i+g+g+e+r+\b', r'\bd+i+c+k+\w*\b',
    r'\bp+i+s+s+\w*\b', r'\bc+o+c+k+\w*\b', r'\bs+l+u+t+\w*\b',
    r'\bw+h+o+r+e+\b', r'\bp+o+r+n+\b', r'\bs+e+x+\b',
    r'\bn+a+z+i+\b', r'\bf+a+g+g+o+t+\b', r'\br+e+t+a+r+d+\b',
    r'\bs+p+i+c+\b', r'\bn+u+t+s+a+c+e+\b',
]

# URL pattern
URL_PATTERN = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+', re.IGNORECASE)

# Suspicious patterns (multiple links, repetitive content, all-caps shouting)
SHOUT_PATTERN = re.compile(r'[A-Z\s]{30,}')
REPEAT_PATTERN = re.compile(r'(.+?)\1{4,}')
MULTI_LINK_PATTERN = re.compile(r'(https?://[^\s<>"]+).*(https?://[^\s<>"]+)', re.IGNORECASE)

class CommentModerator:
    """Moderates comments for profanity, spam, and sensitive content."""

    def __init__(self, block_links: bool = True, block_profanity: bool = True,
                 max_length: int = 1000, min_length: int = 2):
        self.block_links = block_links
        self.block_profanity = block_profanity
        self.max_length = max_length
        self.min_length = min_length

    def moderate(self, author: str, body: str) -> dict:
        """Check a comment and return moderation result.
        
        Returns: {
            "approved": bool,
            "flags": [str],
            "filtered_body": str (profanity redacted if blocked),
            "status": "approved" | "pending" | "rejected"
        }
        """
        flags = []
        text = f"{author} {body}"

        # Length checks
        if len(body) < self.min_length:
            return {"approved": False, "flags": ["too_short"], "filtered_body": body, "status": "rejected"}
        if len(body) > self.max_length:
            return {"approved": False, "flags": ["too_long"], "filtered_body": body, "status": "rejected"}

        # Link check
        urls = URL_PATTERN.findall(body)
        if urls and self.block_links:
            flags.append(f"links_blocked")
            # Strip links from body
            filtered = URL_PATTERN.sub("[link removed]", body)
        else:
            filtered = body

        # Multi-link spam
        if MULTI_LINK_PATTERN.search(body):
            flags.append("multiple_links")

        # Profanity check
        profanity_hits = []
        if self.block_profanity:
            for pattern in PROFANITY_PATTERNS:
                matches = re.findall(pattern, filtered, re.IGNORECASE)
                if matches:
                    profanity_hits.extend(matches)
                    filtered = re.sub(pattern, "[redacted]", filtered, flags=re.IGNORECASE)
        if profanity_hits:
            flags.append(f"profanity_{len(profanity_hits)}")

        # Shouting
        if SHOUT_PATTERN.search(text):
            flags.append("excessive_caps")

        # Repetition spam
        if REPEAT_PATTERN.search(text):
            flags.append("repetitive_content")

        # Determine status
        if len(flags) > 0:
            # Links are auto-rejected; profanity/shouting go to pending
            if "links_blocked" in flags:
                status = "pending"
            else:
                if any(f.startswith("profanity") for f in flags):
                    status = "pending"
                else:
                    status = "pending"
        else:
            status = "approved"

        return {
            "approved": status == "approved",
            "flags": flags,
            "filtered_body": filtered,
            "status": status
        }

    def sanitize(self, text: str) -> str:
        """Strip profanity and links from text."""
        if self.block_profanity:
            for pattern in PROFANITY_PATTERNS:
                text = re.sub(pattern, "[redacted]", text, flags=re.IGNORECASE)
        if self.block_links:
            text = URL_PATTERN.sub("[link removed]", text)
        return text[:self.max_length] if len(text) > self.max_length else text