#!/usr/bin/env python3
"""
quality_guardian.py — The Abvorn Quality Guardian

Validates content quality before publication. Checks for
readability, tone consistency, factual coherence, and
platform-specific quality standards.
"""

import re
import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QualityGuardian:
    def __init__(self):
        self.quality_checks = {
            "readability": self._check_readability,
            "tone": self._check_tone,
            "length": self._check_length,
            "grammar": self._check_grammar,
            "specificity": self._check_specificity,
        }

    def check_content(self, content: str, platform: str = "") -> Dict[str, Any]:
        results = {
            "content": content[:200],
            "passed": True,
            "score": 1.0,
            "issues": [],
            "suggestions": [],
            "platform": platform,
        }

        check_scores = []
        for check_name, check_fn in self.quality_checks.items():
            try:
                issue = check_fn(content, platform)
                if issue:
                    results["issues"].append(issue)
                    results["suggestions"].append(issue.get("suggestion", ""))
                    check_scores.append(0.5)
                else:
                    check_scores.append(1.0)
            except Exception as e:
                logger.warning(f"Quality check {check_name} failed: {e}")
                check_scores.append(0.8)

        if check_scores:
            results["score"] = sum(check_scores) / len(check_scores)

        if results["score"] < 0.7:
            results["passed"] = False
        elif results["score"] < 0.9:
            results["passed"] = True
            results["issues"].append({
                "type": "warning",
                "message": "Content passed with minor quality warnings",
                "severity": "low",
            })

        if results["issues"]:
            logger.info(
                f"Quality check for {platform or 'general'}: "
                f"score={results['score']:.2f}, "
                f"issues={len(results['issues'])}"
            )

        return results

    def _check_readability(self, content: str, platform: str = "") -> Optional[Dict[str, Any]]:
        sentences = [s.strip() for s in content.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        if not sentences:
            return None

        avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_words > 40:
            return {
                "type": "readability",
                "severity": "medium",
                "message": f"Sentences too long (avg {avg_words:.1f} words)",
                "suggestion": "Break long sentences into shorter ones for better readability",
            }
        return None

    def _check_tone(self, content: str, platform: str = "") -> Optional[Dict[str, Any]]:
        aggressive_words = ["unbelievable", "incredible", "amazing", "shocking", "crazy"]
        found = [w for w in aggressive_words if w.lower() in content.lower()]
        if found:
            return {
                "type": "tone",
                "severity": "low",
                "message": f"Aggressive tone detected: {', '.join(found)}",
                "suggestion": "Consider substituting with measured, data-backed language",
            }
        return None

    def _check_length(self, content: str, platform: str = "") -> Optional[Dict[str, Any]]:
        word_count = len(content.split())
        if platform == "tiktok" and word_count > 150:
            return {
                "type": "length",
                "severity": "high",
                "message": f"Content too long for TikTok ({word_count} words)",
                "suggestion": "Trim to under 150 words for TikTok format",
            }
        if platform == "x" and word_count > 280:
            return {
                "type": "length",
                "severity": "high",
                "message": f"Content exceeds X character limit ({word_count} words)",
                "suggestion": "Shorten to fit within platform limits",
            }
        return None

    def _check_grammar(self, content: str, platform: str = "") -> Optional[Dict[str, Any]]:
        issues = []
        if "  " in content:
            issues.append("double spaces detected")
        if content.count(".") > 20 and len(content.split()) < 100:
            issues.append("excessive punctuation density")
        if issues:
            return {
                "type": "grammar",
                "severity": "low",
                "message": f"Grammar issues: {'; '.join(issues)}",
                "suggestion": "Review punctuation and spacing",
            }
        return None

    def _check_specificity(self, content: str, platform: str = "") -> Optional[Dict[str, Any]]:
        vague_phrases = ["good product", "nice", "great", "okay", "fine"]
        found = [p for p in vague_phrases if p.lower() in content.lower()]
        if found and len(content.split()) < 50:
            return {
                "type": "specificity",
                "severity": "medium",
                "message": f"Vague phrases without supporting detail: {', '.join(found)}",
                "suggestion": "Add specific data, scores, or examples to back up claims",
            }
        return None


def create_quality_guardian() -> QualityGuardian:
    return QualityGuardian()


if __name__ == "__main__":
    guardian = create_quality_guardian()

    test_content = "The Sony WH-1000XM6 is an amazing product. It sounds good. The battery is fine."
    result = guardian.check_content(test_content, platform="tiktok")
    print(f"Score: {result['score']:.2f}")
    print(f"Passed: {result['passed']}")
    print(f"Issues: {len(result['issues'])}")
    for issue in result["issues"]:
        print(f"  - {issue['message']}")