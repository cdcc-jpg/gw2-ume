"""Stage 7: Trust Scoring and Module_Action Assignment.

Zero Domain Semantics in Python: Mathematical and rule-based trust attribution.
Assigns Module_Action:
- Literal Typed: Object is a literal value (numeric, string, timestamp, unmapped categorical).
- Deterministic Mapped: Object is a resolved concept URI with confidence >= 0.62 AND predicate review_flag is False.
- HITL Validation:
  - Downgrade rule: If predicate review_flag was True in Stage 5, downgrade to HITL Validation even if object was confident!
  - Object confidence is in [0.40, 0.62).
  - Predicate confidence is weak and flagged for human review.
- Literal Boxed: Object confidence < 0.40 or low-confidence ambiguous mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from gw2_ume.use_pipeline.stage5_cascade import MatchResult
from gw2_ume.use_pipeline.stage6_object_resolution import ObjectResolutionResult


@dataclass
class TrustScore:
    """Trust score and Module_Action attribution for a triple."""
    module_action: str  # Literal Typed, Deterministic Mapped, HITL Validation, Literal Boxed
    confidence: float
    review_flag: bool
    rationale: str


class TrustScorer:
    """Stage 7 Trust Scorer: assigns Module_Action and computes final composite confidence."""

    @staticmethod
    def score_triple(
        predicate_match: MatchResult,
        object_match: ObjectResolutionResult,
    ) -> TrustScore:
        """Computes trust score and assigns Module_Action based on predicate and object confidence."""
        pred_conf = predicate_match.confidence
        obj_conf = object_match.confidence
        pred_review = predicate_match.review_flag

        # Composite confidence
        composite_conf = round(pred_conf * obj_conf, 4)

        # 1. Literal Objects
        if not object_match.is_concept:
            # If predicate is strong and reviewed or deterministic
            if pred_review:
                return TrustScore(
                    module_action="HITL Validation",
                    confidence=composite_conf,
                    review_flag=True,
                    rationale="Literal object with weak/reranked predicate requiring review",
                )
            return TrustScore(
                module_action="Literal Typed",
                confidence=composite_conf,
                review_flag=False,
                rationale="Standard literal value with high confidence predicate",
            )

        # 2. Concept Objects (Categorical mapped to URI)
        # High confidence concept object (>= 0.62)
        if obj_conf >= 0.62:
            # DOWNGRADE RULE: If predicate review_flag was True in Stage 5,
            # downgrade to HITL Validation even if object was confident!
            if pred_review:
                return TrustScore(
                    module_action="HITL Validation",
                    confidence=composite_conf,
                    review_flag=True,
                    rationale="Downgraded to HITL Validation because predicate review_flag is True despite confident object",
                )
            return TrustScore(
                module_action="Deterministic Mapped",
                confidence=composite_conf,
                review_flag=False,
                rationale="High confidence deterministic match for both predicate and concept object",
            )

        # Medium confidence concept object ([0.40, 0.62))
        if 0.40 <= obj_conf < 0.62:
            return TrustScore(
                module_action="HITL Validation",
                confidence=composite_conf,
                review_flag=True,
                rationale="Moderate confidence concept match requiring human verification",
            )

        # Low confidence concept object (< 0.40)
        return TrustScore(
            module_action="Literal Boxed",
            confidence=composite_conf,
            review_flag=True,
            rationale="Low confidence concept match isolated as Literal Boxed",
        )
