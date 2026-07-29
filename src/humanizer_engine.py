"""Humanizer Engine — transforms robotic AI text into authentic, conversational content."""

import random
import re
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class ContentType(Enum):
    YOUTUBE_SCRIPT = "youtube_script"
    TIKTOK_SCRIPT = "tiktok_script"
    INSTAGRAM_SCRIPT = "instagram_script"
    X_POST = "x_post"
    LINKEDIN_POST = "linkedin_post"
    BLOG_POST = "blog_post"
    EMAIL_NEWSLETTER = "email_newsletter"
    REVIEW_SUMMARY = "review_summary"
    SOCIAL_COMMENT = "social_comment"
    WEBSITE_COPY = "website_copy"
    CHANNEL_DESCRIPTION = "channel_description"
    VIDEO_TITLE = "video_title"
    VIDEO_DESCRIPTION = "video_description"
    THUMBNAIL_TEXT = "thumbnail_text"
    VOICEOVER_SCRIPT = "voiceover_script"
    AGENT_OUTPUT = "agent_output"
    QUESTION_HYPOTHESIS = "question_hypothesis"
    VERDICT_SUMMARY = "verdict_summary"
    GENERIC = "generic"


@dataclass
class HumanizerConfig:
    warmth: float = 0.8
    directness: float = 0.9
    humor: float = 0.3
    vulnerability: float = 0.4
    conversational: float = 0.8
    conciseness: float = 0.7


class HumanizerEngine:
    def __init__(self, config: Optional[HumanizerConfig] = None):
        self.config = config or HumanizerConfig()
        self._init_voice_elements()

    def _init_voice_elements(self):
        self.openers = {
            "general": [
                "Here\u2019s the thing\u2026",
                "Look,",
                "Honestly?",
                "Let\u2019s be real for a second.",
                "Here\u2019s what nobody tells you\u2026",
                "Quick truth bomb:",
                "Real talk:",
                "I\u2019m just gonna say it:",
                "Between you and me\u2026",
                "For what it\u2019s worth\u2026",
                "Here\u2019s the deal:",
                "Spoiler alert:",
                "Truth is:",
            ],
            "tiktok": [
                "Wait, hold up\u2026",
                "Okay, so\u2026",
                "You\u2019re not gonna believe this\u2026",
                "This just hit me\u2026",
                "Real quick\u2026",
            ],
            "youtube": [
                "Welcome back to Abvorn.",
                "Today, we\u2019re diving deep into\u2026",
                "Let\u2019s cut through the noise\u2026",
                "Here\u2019s what the data actually says\u2026",
            ],
            "linkedin": [
                "Here\u2019s an insight that\u2019s been on my mind\u2026",
                "In my experience\u2026",
                "The data tells a fascinating story\u2026",
            ],
            "instagram": [
                "Okay, let\u2019s talk about\u2026",
                "Been getting a lot of questions about\u2026",
                "Here\u2019s the honest take on\u2026",
            ],
            "x": [
                "Hot take:",
                "Thread alert:",
                "Can we talk about\u2026",
                "Unpopular opinion:",
            ],
            "email": [
                "Hey there,",
                "Hope you\u2019re having a great week.",
                "Real quick \u2014 I wanted to share\u2026",
            ],
        }
        self.bridges = [
            "Which means\u2026",
            "So what does that actually mean for you?",
            "Here\u2019s the translation:",
            "In plain English:",
            "What that really tells us is\u2026",
            "And that matters because\u2026",
            "The takeaway?",
            "Bottom line:",
            "Here\u2019s what you need to know:",
            "Let me break that down:",
            "Put simply:",
            "The truth is:",
            "So here\u2019s the thing:",
        ]
        self.trust_signals = {
            "general": [
                "We don\u2019t have all the answers, but here\u2019s what we know\u2026",
                "We could be wrong, but the data says\u2026",
                "To be completely transparent\u2026",
                "We were surprised by this too\u2026",
                "Full disclosure:",
                "We didn\u2019t expect this, but\u2026",
                "Honestly, we were skeptical at first\u2026",
                "We\u2019re still learning, but here\u2019s what we\u2019ve found\u2026",
                "Take it with a grain of salt, but\u2026",
            ],
            "review": [
                "We tested this ourselves. Here\u2019s what we found\u2026",
                "Not sponsored. Not affiliated. Just honest data.",
                "We bought this with our own money.",
                "We don\u2019t take kickbacks. We take data.",
            ],
            "email": [
                "I\u2019m writing this as a real person, not a chatbot.",
                "You\u2019re on this list because you care about making smart decisions.",
                "No fluff. No BS. Just the truth.",
            ],
        }
        self.ctas = {
            "general": [
                "What do you think?",
                "Would you buy this?",
                "What\u2019s your experience?",
                "Curious \u2014 what\u2019s your take?",
                "Let me know in the comments.",
                "Share this with someone who needs to see it.",
                "Save this for later.",
                "Follow for more honest reviews.",
            ],
            "tiktok": [
                "Follow for more honest reviews! \U0001F514",
                "Save this if you found it helpful! \U0001F4BE",
                "Tag someone who needs to hear this! \U0001F4CC",
                "What would you do? Comment below! \U0001F4AC",
            ],
            "youtube": [
                "Subscribe for weekly deep dives! \U0001F514",
                "Like if you found this useful! \U0001F44D",
                "Share this with a friend who needs the truth! \U0001F4E4",
                "What should we review next? Comment below! \U0001F4AC",
            ],
            "instagram": [
                "Double tap if you agree! \u2764\ufe0f",
                "Save this for later! \U0001F4E4",
                "Share with a friend! \U0001F4E4",
                "Follow for more honest reviews! \U0001F514",
            ],
            "linkedin": [
                "What\u2019s your take? Comment below! \U0001F4A1",
                "Follow for more industry insights! \U0001F4C8",
                "Share if you found this valuable! \U0001F48E",
            ],
            "x": [
                "RT if you agree! \U0001F504",
                "Reply with your thoughts! \U0001F4AC",
                "What do you think?",
            ],
            "email": [
                "Hit reply and let me know what you think.",
                "Share this with a colleague who\u2019d find it useful.",
                "Forward this to a friend who\u2019s looking to buy.",
            ],
        }
        self.slang = {
            "tiktok": ["literally", "honestly", "actually", "seriously", "pretty", "super", "totally"],
            "instagram": ["honestly", "actually", "seriously", "pretty", "super"],
            "x": ["honestly", "actually", "pretty"],
            "linkedin": [],
            "youtube": ["honestly", "actually", "pretty", "seriously"],
            "email": [],
            "blog": [],
            "generic": ["honestly", "actually"],
        }
        self.contractions = {
            "do not": "don\u2019t",
            "cannot": "can\u2019t",
            "will not": "won\u2019t",
            "should not": "shouldn\u2019t",
            "could not": "couldn\u2019t",
            "would not": "wouldn\u2019t",
            "i am": "I\u2019m",
            "you are": "you\u2019re",
            "it is": "it\u2019s",
            "that is": "that\u2019s",
            "what is": "what\u2019s",
            "who is": "who\u2019s",
            "where is": "where\u2019s",
            "when is": "when\u2019s",
            "why is": "why\u2019s",
            "how is": "how\u2019s",
            "are not": "aren\u2019t",
            "were not": "weren\u2019t",
            "has not": "hasn\u2019t",
            "have not": "haven\u2019t",
            "does not": "doesn\u2019t",
            "did not": "didn\u2019t",
            "is not": "isn\u2019t",
            "was not": "wasn\u2019t",
        }

    def humanize(self, text: str, content_type: Union[str, ContentType] = None,
                 context: Optional[Dict[str, Any]] = None) -> str:
        if content_type is None:
            content_type = ContentType.GENERIC
        if isinstance(content_type, str):
            try:
                content_type = ContentType(content_type)
            except ValueError:
                content_type = ContentType.GENERIC

        if not text or len(text.split()) < 3:
            return text

        analysis = self._analyze_text(text)
        if analysis["robotic_score"] > 0.4:
            text = self._rewrite_human(text, content_type, context)

        text = self._apply_rhythm(text, content_type)
        text = self._inject_bridges(text)
        text = self._inject_trust_signals(text, content_type)
        text = self._add_opener(text, content_type)
        text = self._add_cta(text, content_type)
        text = self._apply_voice_polish(text, content_type)

        return text.strip()

    def _analyze_text(self, text: str) -> Dict[str, Any]:
        scores = []
        issues = []
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 0]

        if sentences:
            avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_len > 15:
                scores.append(0.3)
                issues.append("sentences_too_long")
            elif avg_len > 12:
                scores.append(0.15)

        contraction_count = sum(text.lower().count(c) for c in list(self.contractions.values()))
        if contraction_count < 2 and len(text.split()) > 20:
            scores.append(0.3)
            issues.append("no_contractions")

        passive_patterns = ["was ", "were ", "been ", "being ", "by the ", "is being", "are being"]
        passive_count = sum(text.lower().count(p) for p in passive_patterns)
        if passive_count > 3:
            scores.append(0.2)
            issues.append("passive_voice")

        if "?" not in text and len(text.split()) > 30:
            scores.append(0.15)
            issues.append("no_questions")

        not_contractions = ["don\u2019t", "can\u2019t", "won\u2019t", "shouldn\u2019t", "couldn\u2019t", "wouldn\u2019t"]
        if not any(c in text.lower() for c in not_contractions):
            scores.append(0.1)
            issues.append("no_not_contractions")

        formal_words = ["thus", "hence", "therefore", "whereas", "notwithstanding", "hereby"]
        if any(w in text.lower() for w in formal_words):
            scores.append(0.15)
            issues.append("formal_language")

        return {
            "robotic_score": min(sum(scores), 1.0),
            "issues": issues,
            "needs_rewrite": sum(scores) > 0.4,
        }

    def _rewrite_human(self, text: str, content_type: ContentType,
                       context: Optional[Dict[str, Any]]) -> str:
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        numbers = re.findall(r"\d+\.\d+|\d+", text)

        humanized_parts = []
        if sentences:
            first = sentences[0]
            if len(first.split()) > 12:
                words = first.split()
                mid = len(words) // 2
                humanized_parts.append(" ".join(words[:mid]) + ".")
                humanized_parts.append(" ".join(words[mid:]) + ".")
            else:
                humanized_parts.append(first)

        for i, sent in enumerate(sentences[1:4], 1):
            if numbers and i <= len(numbers):
                bridge = random.choice(self.bridges)
                humanized_parts.append(f"{bridge} {sent}")
            else:
                humanized_parts.append(sent)

        if random.random() < self.config.vulnerability:
            trust = random.choice(
                self.trust_signals.get(content_type.value, self.trust_signals["general"])
            )
            humanized_parts.append(trust)

        result = ". ".join(humanized_parts)
        result = self._add_opener(result, content_type)
        result = self._add_cta(result, content_type)
        return result

    def _apply_rhythm(self, text: str, content_type: ContentType) -> str:
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if len(sentences) < 3:
            return text

        humanized = []
        for i, sent in enumerate(sentences):
            words = sent.split()
            if i % 2 == 0 and len(words) > 12:
                mid = len(words) // 2
                first = " ".join(words[:mid])
                second = " ".join(words[mid:])
                humanized.append(first + ".")
                if len(second) > 1:
                    humanized.append(second + ".")
            else:
                humanized.append(sent + ".")

        return " ".join(humanized)

    def _inject_bridges(self, text: str) -> str:
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        result = []
        for sent in sentences:
            if re.search(r"\d+\.?\d*", sent):
                has_bridge = any(b.lower() in sent.lower() for b in self.bridges)
                if not has_bridge and random.random() < 0.5:
                    bridge = random.choice(self.bridges)
                    result.append(f"{bridge} {sent}")
                    continue
            result.append(sent)
        return ". ".join(result)

    def _inject_trust_signals(self, text: str, content_type: ContentType) -> str:
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if len(sentences) < 3:
            return text

        insert_index = max(1, int(len(sentences) * random.uniform(0.6, 0.7)))
        trust = random.choice(
            self.trust_signals.get(content_type.value, self.trust_signals["general"])
        )
        sentences.insert(insert_index, trust)
        return ". ".join(sentences)

    def _add_opener(self, text: str, content_type: ContentType) -> str:
        all_openers = []
        for key, values in self.openers.items():
            all_openers.extend(values)

        has_opener = any(o.lower() in text[:80].lower() for o in all_openers)
        if not has_opener and len(text.split()) > 15:
            openers = self.openers.get(content_type.value, self.openers["general"])
            opener = random.choice(openers)
            return f"{opener} {text}"
        return text

    def _add_cta(self, text: str, content_type: ContentType) -> str:
        all_ctas = []
        for key, values in self.ctas.items():
            all_ctas.extend(values)

        has_cta = any(c.lower() in text.lower() for c in all_ctas)
        if not has_cta and len(text.split()) > 20:
            ctas = self.ctas.get(content_type.value, self.ctas["general"])
            cta = random.choice(ctas)
            return f"{text} {cta}"
        return text

    def _apply_voice_polish(self, text: str, content_type: ContentType) -> str:
        text = self._add_contractions(text)
        text = self._add_slang(text, content_type)
        text = self._convert_numbers(text)
        return text

    def _add_contractions(self, text: str) -> str:
        if random.random() > self.config.conversational:
            return text
        for formal, casual in self.contractions.items():
            text = text.replace(f" {formal} ", f" {casual} ")
            text = text.replace(f" {formal}.", f" {casual}.")
            text = text.replace(f" {formal},", f" {casual},")
        return text

    def _add_slang(self, text: str, content_type: ContentType) -> str:
        if random.random() > 0.3:
            return text
        slang_list = self.slang.get(content_type.value, self.slang["generic"])
        if not slang_list:
            return text
        for slang in slang_list:
            if random.random() < 0.2:
                if "very" in text.lower():
                    text = text.replace("very", slang, 1)
                elif "really" in text.lower():
                    text = text.replace("really", slang, 1)
        return text

    def _convert_numbers(self, text: str) -> str:
        number_words = {
            "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
            "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten",
        }
        for num, word in number_words.items():
            if random.random() < 0.3:
                text = text.replace(f" {num} ", f" {word} ")
        return text

    def humanize_youtube_script(self, script: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(script, ContentType.YOUTUBE_SCRIPT, context)

    def humanize_tiktok_script(self, script: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(script, ContentType.TIKTOK_SCRIPT, context)

    def humanize_instagram_caption(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.INSTAGRAM_SCRIPT, context)

    def humanize_x_post(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.X_POST, context)

    def humanize_linkedin_post(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.LINKEDIN_POST, context)

    def humanize_blog_post(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.BLOG_POST, context)

    def humanize_email(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.EMAIL_NEWSLETTER, context)

    def humanize_review_summary(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.REVIEW_SUMMARY, context)

    def humanize_social_comment(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.SOCIAL_COMMENT, context)

    def humanize_website_copy(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.WEBSITE_COPY, context)

    def humanize_channel_description(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.CHANNEL_DESCRIPTION, context)

    def humanize_video_title(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.VIDEO_TITLE, context)

    def humanize_video_description(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.VIDEO_DESCRIPTION, context)

    def humanize_thumbnail_text(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.THUMBNAIL_TEXT, context)

    def humanize_voiceover(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.VOICEOVER_SCRIPT, context)

    def humanize_agent_output(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.AGENT_OUTPUT, context)

    def humanize_question_hypothesis(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.QUESTION_HYPOTHESIS, context)

    def humanize_verdict_summary(self, text: str, context: Dict[str, Any] = None) -> str:
        return self.humanize(text, ContentType.VERDICT_SUMMARY, context)


def create_humanizer(config: Optional[Dict[str, float]] = None) -> HumanizerEngine:
    if config:
        return HumanizerEngine(HumanizerConfig(**config))
    return HumanizerEngine()


if __name__ == "__main__":
    humanizer = HumanizerEngine()
    test_texts = {
        "robotic_script": (
            "The Sony WH-1000XM6 has a sound quality score of 9.2. "
            "The battery life score is 6.5. It is a good option for people who care about sound quality. "
            "The price is high. It may not be suitable for budget-conscious consumers. "
            "This product is recommended for audiophiles."
        ),
        "blog_intro": (
            "In this review, we will examine the Sony WH-1000XM6 headphones. "
            "Our analysis focuses on sound quality, battery life, comfort, and value for money. "
            "The findings are based on extensive testing."
        ),
        "email": (
            "This is an email about our latest review. "
            "We have tested the Sony WH-1000XM6 and found it to be exceptional. "
            "Click the link to read more."
        ),
    }

    print("=" * 60)
    print("ROBOTIC TEXT -> HUMANIZED TEXT")
    print("=" * 60)
    for name, text in test_texts.items():
        print(f"\n{name.upper()}:")
        print(f"ROBOTIC:  {text}")
        print(f"HUMANIZED: {humanizer.humanize(text, ContentType.GENERIC)}")
        print("-" * 40)
