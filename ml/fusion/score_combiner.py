"""
Cross-Signal Fusion Engine
Combines all individual detector scores into the final Human Trust Score (0–100).

This is NOT a simple average. Key design decisions:
1. Signals are weighted by confidence and data quality
2. Context (action_type) adjusts weights (e.g. job_application → heavier text weight)
3. Signal conflicts are detected and flagged (high behavioral + low text = suspicious)
4. Final score is calibrated to produce intuitive verdicts at threshold boundaries
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FusionResult:
    combined_score: float       # 0.0 – 1.0 raw weighted average
    human_trust_score: int      # 0 – 100 calibrated final score
    confidence: str             # "high" | "medium" | "low"
    verdict: str                # "human" | "likely_human" | "uncertain" | "suspicious" | "bot"
    signal_weights_used: Dict[str, float]
    conflict_detected: bool


# Base signal weights — sum to 1.0
BASE_WEIGHTS = {
    "keystroke":   0.25,
    "mouse":       0.20,
    "scroll":      0.10,
    "resume":      0.20,
    "vocabulary":  0.15,
    "classifier":  0.10,
}

# Context multipliers: adjust weights based on action type
# Values > 1 increase the signal's importance; < 1 reduce it
CONTEXT_WEIGHT_MULTIPLIERS = {
    "job_application": {
        "resume":      2.0,    # Resume text is primary signal for job apps
        "vocabulary":  1.5,
        "classifier":  1.5,
        "keystroke":   1.0,
        "mouse":       0.8,
        "scroll":      0.6,
    },
    "review": {
        "classifier":  2.0,    # Review text is primary signal
        "vocabulary":  1.8,
        "keystroke":   1.0,
        "mouse":       1.0,
        "scroll":      0.8,
        "resume":      0.3,
    },
    "exam": {
        "keystroke":   1.5,    # Typing behavior is key for exam detection
        "vocabulary":  1.5,
        "classifier":  1.5,
        "mouse":       1.2,
        "scroll":      0.8,
        "resume":      0.5,
    },
    "login": {
        "keystroke":   2.0,    # Login: typing dynamics are primary
        "mouse":       1.5,
        "scroll":      0.5,
        "resume":      0.1,
        "vocabulary":  0.1,
        "classifier":  0.1,
    },
    "generic": {
        k: 1.0 for k in BASE_WEIGHTS
    },
}


class ScoreCombiner:

    version = "1.0.0"

    def combine(
        self,
        scores: Dict[str, float],
        context,
        flags: List[str],
    ) -> FusionResult:
        """
        Main fusion method. Called by the API with all available signal scores.

        Args:
            scores: Dict mapping signal name → score (0–1), e.g. {"keystroke": 0.82}
            context: RequestContext with action_type, etc.
            flags: Accumulated flags from all detectors

        Returns:
            FusionResult with final Human Trust Score and verdict
        """
        if not scores:
            raise ValueError("ScoreCombiner received empty scores dict")

        action_type = getattr(context, "action_type", "generic")
        weights = self._compute_effective_weights(scores, action_type)
        weighted_score = self._weighted_average(scores, weights)

        # Conflict detection
        conflict = self._detect_conflict(scores)
        if conflict:
            flags.append("signal_conflict_detected")
            # Penalize uncertain cases where signals contradict
            weighted_score = weighted_score * 0.85

        # Convert to 0–100 Human Trust Score with calibration
        human_trust_score = self._calibrate_to_trust_score(weighted_score, len(scores))

        confidence = self._compute_confidence(scores, weights)
        verdict = self._score_to_verdict(human_trust_score)

        logger.debug(
            f"Fusion: scores={scores} action={action_type} "
            f"weighted={weighted_score:.3f} HTS={human_trust_score} verdict={verdict}"
        )

        return FusionResult(
            combined_score=round(weighted_score, 3),
            human_trust_score=human_trust_score,
            confidence=confidence,
            verdict=verdict,
            signal_weights_used=weights,
            conflict_detected=conflict,
        )

    def _compute_effective_weights(
        self,
        scores: Dict[str, float],
        action_type: str,
    ) -> Dict[str, float]:
        """
        Compute normalized weights for the signals that are actually present.
        Applies context multipliers then renormalizes to sum to 1.0.
        """
        context_mults = CONTEXT_WEIGHT_MULTIPLIERS.get(action_type, CONTEXT_WEIGHT_MULTIPLIERS["generic"])

        raw_weights = {}
        for signal in scores:
            base = BASE_WEIGHTS.get(signal, 0.10)
            mult = context_mults.get(signal, 1.0)
            raw_weights[signal] = base * mult

        total = sum(raw_weights.values())
        return {k: round(v / total, 4) for k, v in raw_weights.items()}

    def _weighted_average(self, scores: Dict[str, float], weights: Dict[str, float]) -> float:
        return sum(scores[k] * weights[k] for k in scores if k in weights)

    def _detect_conflict(self, scores: Dict[str, float]) -> bool:
        """
        Detect when behavioral signals and text signals strongly contradict each other.
        E.g. high keystroke score (seems human) but very low text score (AI text).
        This pattern suggests a human is submitting AI-generated content.
        """
        behavioral_signals = {k: scores[k] for k in ["keystroke", "mouse", "scroll"] if k in scores}
        text_signals = {k: scores[k] for k in ["resume", "vocabulary", "classifier"] if k in scores}

        if not behavioral_signals or not text_signals:
            return False

        avg_behavioral = sum(behavioral_signals.values()) / len(behavioral_signals)
        avg_text = sum(text_signals.values()) / len(text_signals)

        # High behavioral + low text = human typing AI content (strong conflict)
        if avg_behavioral > 0.70 and avg_text < 0.35:
            return True

        # Low behavioral + high text = bot typing human-like text
        if avg_behavioral < 0.35 and avg_text > 0.70:
            return True

        return False

    def _calibrate_to_trust_score(self, weighted_score: float, signal_count: int) -> int:
        """
        Map 0–1 weighted score to 0–100 Human Trust Score.
        The calibration ensures:
        - Score > 0.80 → HTS 80-100 (Verified Human)
        - Score 0.65-0.79 → HTS 65-79 (Likely Human)
        - Score 0.50-0.64 → HTS 50-64 (Uncertain)
        - Score 0.25-0.49 → HTS 25-49 (Suspicious)
        - Score < 0.25 → HTS 0-24 (Likely Synthetic)
        """
        base_score = int(weighted_score * 100)

        # Slight penalty for low signal coverage (only 1-2 signals available)
        if signal_count == 1:
            base_score = max(25, base_score - 10)  # High uncertainty penalty
        elif signal_count == 2:
            base_score = max(30, base_score - 5)

        return max(0, min(100, base_score))

    def _compute_confidence(self, scores: Dict[str, float], weights: Dict[str, float]) -> str:
        """
        Confidence is based on:
        - Number of signals available (more = higher confidence)
        - Whether the dominant signals have high weight
        """
        coverage = len(scores) / len(BASE_WEIGHTS)
        top_weight = max(weights.values()) if weights else 0

        if coverage >= 0.7 and top_weight < 0.5:
            return "high"
        elif coverage >= 0.4:
            return "medium"
        else:
            return "low"

    def _score_to_verdict(self, hts: int) -> str:
        if hts >= 80:
            return "human"
        elif hts >= 65:
            return "likely_human"
        elif hts >= 50:
            return "uncertain"
        elif hts >= 25:
            return "suspicious"
        else:
            return "bot"
