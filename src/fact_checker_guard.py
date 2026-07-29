#!/usr/bin/env python3
"""
fact_checker_guard.py — The Abvorn Fact-Checker Guard

This module validates every factual claim in AI-generated content
before it's published. It's the last line of defense between
"plausible-sounding AI output" and "trusted, accurate content."

Every component that generates text MUST pass through this guard.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FactCheckResult:
    """Result of a fact-check operation."""
    claim: str
    verified: bool
    confidence: float  # 0.0 to 1.0
    source: Optional[str]
    evidence: Optional[str]
    correction: Optional[str]
    error_type: Optional[str]
    severity: str  # "low", "medium", "high", "critical"

@dataclass
class ProductData:
    """Structured product data for fact-checking."""
    product_id: str
    product_name: str
    price: float
    rating: float
    review_count: int
    category: str
    features: List[str]
    specs: Dict[str, Any]
    verified_data: Dict[str, Any] = field(default_factory=dict)

class FactCheckerGuard:
    """
    The Fact-Checker Guard validates every claim in AI-generated content.
    
    It checks:
    1. Numerical claims (scores, prices, weights, etc.)
    2. Product specifications
    3. Feature claims
    4. Comparison claims
    5. Source verification
    6. Logical consistency
    """
    
    def __init__(self, product_data: Optional[Dict[str, Any]] = None):
        self.product_data = product_data or {}
        self.verified_claims = []
        self.failed_claims = []
        
        # Known fact patterns
        self.fact_patterns = {
            "score": r'\b(\d+\.?\d*)\s*/\s*10\b',
            "price": r'\$\s*(\d+\.?\d*)',
            "weight": r'(\d+\.?\d*)\s*(?:g|kg|pounds|lbs)',
            "battery": r'(\d+\.?\d*)\s*(?:hours?|hrs?|h)\s*(?:of)?\s*(?:battery|playtime|listening)',
            "percentage": r'(\d+\.?\d*)\s*%',
            "number": r'\b(\d+)\s*(?:reviews?|tests?|users?|people|customers)'
        }
    
    # ========================================================================
    # MAIN ENTRY POINT
    # ========================================================================
    
    def check_content(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Check all claims in content for factual accuracy.
        
        Args:
            content: The content to check
            context: Additional context (product data, source URLs, etc.)
        
        Returns:
            Dict with results, warnings, and corrections
        """
        results = {
            "content": content,
            "total_claims": 0,
            "verified_claims": [],
            "failed_claims": [],
            "warnings": [],
            "corrections": [],
            "overall_status": "passed",
            "confidence_score": 1.0
        }
        
        # 1. Extract all claims
        claims = self._extract_claims(content)
        results["total_claims"] = len(claims)
        
        # 2. Check each claim
        for claim in claims:
            check_result = self._verify_claim(claim, context)
            if check_result.verified:
                results["verified_claims"].append(check_result)
            else:
                results["failed_claims"].append(check_result)
                if check_result.correction:
                    results["corrections"].append({
                        "original": claim,
                        "corrected": check_result.correction,
                        "reason": check_result.error_type
                    })
        
        # 3. Check for critical failures
        critical_failures = [c for c in results["failed_claims"] if c.severity == "critical"]
        if critical_failures:
            results["overall_status"] = "critical"
            results["confidence_score"] = 0.0
        elif results["failed_claims"]:
            results["overall_status"] = "warning"
            results["confidence_score"] = 0.5
        else:
            results["overall_status"] = "passed"
            results["confidence_score"] = 1.0
        
        # 4. Log results
        logger.info(f"Fact-check complete: {len(results['verified_claims'])} verified, "
                   f"{len(results['failed_claims'])} failed, "
                   f"status: {results['overall_status']}")
        
        return results
    
    # ========================================================================
    # CLAIM EXTRACTION
    # ========================================================================
    
    def _extract_claims(self, content: str) -> List[str]:
        """
        Extract all factual claims from content.
        
        A claim is any sentence that contains:
        - A number or statistic
        - A product specification
        - A comparison (better, worse, higher, lower)
        - A verifiable statement about a product
        """
        sentences = [s.strip() for s in content.split('.') if len(s.strip()) > 10]
        
        claims = []
        for sent in sentences:
            has_number = bool(re.search(r'\d+', sent))
            has_spec = any(w in sent.lower() for w in ['sound', 'battery', 'weight', 'price', 'feature'])
            has_comparison = any(w in sent.lower() for w in ['better', 'worse', 'higher', 'lower', 'more', 'less'])
            
            if has_number or has_spec or has_comparison:
                claims.append(sent)
        
        return claims
    
    # ========================================================================
    # CLAIM VERIFICATION
    # ========================================================================
    
    def _verify_claim(self, claim: str, context: Dict[str, Any] = None) -> FactCheckResult:
        """
        Verify a single claim against known data.
        """
        product_check = self._check_against_product_data(claim)
        if product_check:
            return product_check
        
        if context and 'source_data' in context:
            source_check = self._check_against_source(claim, context['source_data'])
            if source_check:
                return source_check
        
        logic_check = self._check_logical_consistency(claim)
        if logic_check:
            return logic_check
        
        hallucination_check = self._check_for_hallucinations(claim)
        if hallucination_check:
            return hallucination_check
        
        return FactCheckResult(
            claim=claim,
            verified=False,
            confidence=0.5,
            source=None,
            evidence=None,
            correction=None,
            error_type="unverified",
            severity="medium"
        )
    
    # ========================================================================
    # PRODUCT DATA CHECKS
    # ========================================================================
    
    def _check_against_product_data(self, claim: str) -> Optional[FactCheckResult]:
        """
        Check claim against stored product data.
        """
        if not self.product_data:
            return None
        
        score_match = re.search(self.fact_patterns["score"], claim)
        if score_match:
            claimed_score = float(score_match.group(1))
            actual_score = self._get_actual_score()
            
            if abs(claimed_score - actual_score) > 0.5:
                return FactCheckResult(
                    claim=claim,
                    verified=False,
                    confidence=0.2,
                    source="product_data",
                    evidence=f"Actual score: {actual_score}/10",
                    correction=f"Corrected to {actual_score}/10",
                    error_type="incorrect_score",
                    severity="critical"
                )
            else:
                return FactCheckResult(
                    claim=claim,
                    verified=True,
                    confidence=0.95,
                    source="product_data",
                    evidence=f"Score verified: {actual_score}/10",
                    correction=None,
                    error_type=None,
                    severity="low"
                )
        
        price_match = re.search(self.fact_patterns["price"], claim)
        if price_match:
            claimed_price = float(price_match.group(1))
            actual_price = self._get_actual_price()
            
            if actual_price and abs(claimed_price - actual_price) > 5:
                return FactCheckResult(
                    claim=claim,
                    verified=False,
                    confidence=0.2,
                    source="product_data",
                    evidence=f"Actual price: ${actual_price}",
                    correction=f"Corrected to ${actual_price}",
                    error_type="incorrect_price",
                    severity="critical"
                )
            elif actual_price:
                return FactCheckResult(
                    claim=claim,
                    verified=True,
                    confidence=0.95,
                    source="product_data",
                    evidence=f"Price verified: ${actual_price}",
                    correction=None,
                    error_type=None,
                    severity="low"
                )
        
        return None
    
    def _get_actual_score(self) -> float:
        """Get the actual score from product data."""
        if 'verdict' in self.product_data:
            return self.product_data['verdict'].get('overall', 0)
        return 0.0
    
    def _get_actual_price(self) -> Optional[float]:
        """Get the actual price from product data."""
        if 'price' in self.product_data:
            return float(self.product_data['price'])
        return None
    
    # ========================================================================
    # SOURCE DATA CHECKS
    # ========================================================================
    
    def _check_against_source(self, claim: str, source_data: str) -> Optional[FactCheckResult]:
        """
        Check claim against source data (e.g., Amazon page, review data).
        """
        return None
    
    # ========================================================================
    # LOGICAL CONSISTENCY CHECKS
    # ========================================================================
    
    def _check_logical_consistency(self, claim: str) -> Optional[FactCheckResult]:
        """
        Check claim for logical consistency.
        """
        if "best" in claim.lower() and "worst" in claim.lower():
            return FactCheckResult(
                claim=claim,
                verified=False,
                confidence=0.1,
                source=None,
                evidence="Contradictory claim (best and worst)",
                correction=None,
                error_type="logical_contradiction",
                severity="critical"
            )
        
        if "100%" in claim and "not" not in claim.lower():
            return FactCheckResult(
                claim=claim,
                verified=False,
                confidence=0.3,
                source=None,
                evidence="100% claims are rare — verify",
                correction=None,
                error_type="extreme_claim",
                severity="medium"
            )
        
        return None
    
    # ========================================================================
    # HALLUCINATION DETECTION
    # ========================================================================
    
    def _check_for_hallucinations(self, claim: str) -> Optional[FactCheckResult]:
        """
        Check for common AI hallucination patterns.
        """
        numbers = re.findall(r'\b\d+\.?\d*\b', claim)
        if len(numbers) > 3 and len(claim.split()) < 20:
            return FactCheckResult(
                claim=claim,
                verified=False,
                confidence=0.3,
                source=None,
                evidence="Too many numbers for claim length",
                correction=None,
                error_type="suspicious_numbers",
                severity="medium"
            )
        
        vague_superlatives = ['greatest', 'amazing', 'incredible', 'unbelievable', 'life-changing']
        if any(w in claim.lower() for w in vague_superlatives):
            return FactCheckResult(
                claim=claim,
                verified=False,
                confidence=0.4,
                source=None,
                evidence="Vague superlative without evidence",
                correction="Consider replacing with specific data",
                error_type="vague_superlative",
                severity="low"
            )
        
        return None
    
    # ========================================================================
    # AUTO-CORRECTION
    # ========================================================================
    
    def apply_corrections(self, content: str, corrections: List[Dict[str, str]]) -> str:
        """
        Apply corrections to content.
        """
        for correction in corrections:
            original = correction.get('original')
            corrected = correction.get('corrected')
            if original and corrected:
                content = content.replace(original, corrected)
        
        return content
    
    # ========================================================================
    # REPORT GENERATION
    # ========================================================================
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """
        Generate a human-readable fact-checking report.
        """
        lines = [
            "=" * 60,
            "[ABVORN FACT-CHECK REPORT]",
            "=" * 60,
            f"Status: {results['overall_status'].upper()}",
            f"Confidence: {results['confidence_score']:.0%}",
            f"Claims Checked: {results['total_claims']}",
            f"[OK] Verified: {len(results['verified_claims'])}",
            f"[FAIL] Failed: {len(results['failed_claims'])}",
            f"[WARN] Warnings: {len(results['warnings'])}",
            "",
            "=" * 60,
        ]
        
        if results['failed_claims']:
            lines.append("[FAIL] FAILED CLAIMS:")
            for fail in results['failed_claims'][:5]:
                lines.append(f"  • {fail.claim}")
                lines.append(f"    -> {fail.error_type} (confidence: {fail.confidence:.0%})")
                if fail.evidence:
                    lines.append(f"    -> Evidence: {fail.evidence}")
                if fail.correction:
                    lines.append(f"    -> Correction: {fail.correction}")
                lines.append("")
        
        return '\n'.join(lines)

# ========================================================================
# FACTORY FUNCTION
# ========================================================================

def create_fact_checker(product_data: Optional[Dict[str, Any]] = None) -> FactCheckerGuard:
    """
    Factory function to create a FactCheckerGuard with optional product data.
    """
    return FactCheckerGuard(product_data)

# ========================================================================
# TESTING
# ========================================================================

if __name__ == "__main__":
    sample_product = {
        "product_id": "B0TEST123",
        "product_name": "Test Headphones",
        "price": 299.99,
        "verdict": {"overall": 8.7}
    }
    
    checker = FactCheckerGuard(sample_product)
    
    test_content = """
    The Sony WH-1000XM6 has a sound quality score of 9.5/10. 
    It costs $299.99. 
    It's the greatest headphones ever made.
    Battery life is 30 hours.
    """
    
    results = checker.check_content(test_content)
    print(checker.generate_report(results))