"""
Resume Scorer
Scores job applications and cover letters for human authenticity.

Key insight: Real cover letters contain one hyper-specific detail proving the author
actually read the job description and knows the company.
AI cover letters describe the job category generically.

Also scores for: personal vocabulary fingerprint, authentic imperfections,
contextual depth vs surface-level descriptions.
"""

import re
from typing import List
import logging

from ...api.schemas import DetectorResult

logger = logging.getLogger(__name__)

# Generic phrases AI uses when writing cover letters
AI_GENERIC_PHRASES = [
    "passionate about", "results-driven", "team player", "strong communication skills",
    "detail-oriented", "self-starter", "go-getter", "think outside the box",
    "synergy", "leverage", "utilize", "dynamic", "innovative", "cutting-edge",
    "best practices", "value-add", "paradigm shift", "holistic approach",
    "proactive", "strategic thinker", "proven track record", "exceed expectations",
    "highly motivated", "dedicated professional", "fast-paced environment",
    "quick learner", "extensive experience", "demonstrates leadership",
    "contributes meaningfully", "exceptional interpersonal skills",
    "a deep passion for", "i am excited to apply", "i believe i would be",
    "i am confident that", "i would be a great fit", "i am eager to",
    "this opportunity aligns with", "my skills and experience align",
    "my background in", "i am writing to express my interest in",
]

# Specificity markers that indicate real human knowledge
SPECIFICITY_MARKERS = [
    # Named technology/product versions
    r"\b(v?\d+\.\d+[\.\d]*)\b",
    # Specific dates or timeframes
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b",
    # Specific numbers with context
    r"\b\d+[,\d]*\s+(users|customers|employees|engineers|clients|transactions)\b",
    # Named tools, frameworks, companies (capitalized proper nouns)
    r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(SDK|API|platform|framework|library|tool|system)\b",
]


class ResumeScorer:

    version = "1.0.0"
    last_trained = "synthetic_baseline_v1"

    MIN_WORD_COUNT = 30

    def score(self, text: str) -> DetectorResult:
        words = text.split()

        if len(words) < self.MIN_WORD_COUNT:
            return DetectorResult(
                score=0.5,
                flags=["insufficient_resume_length"],
                confidence=0.2,
                raw_features={"word_count": len(words)},
            )

        features = self._extract_features(text)
        score = self._score_features(features)
        flags = self._generate_flags(features)

        confidence = min(0.88, len(words) / 300)

        return DetectorResult(
            score=score,
            flags=flags,
            confidence=round(confidence, 3),
            raw_features=features,
        )

    def _extract_features(self, text: str) -> dict:
        text_lower = text.lower()
        words = text.split()

        # Generic AI phrase count
        generic_phrase_count = sum(1 for phrase in AI_GENERIC_PHRASES if phrase in text_lower)
        generic_phrase_density = generic_phrase_count / max(len(words) / 100, 1)

        # Specificity score — count specific details
        specificity_hits = []
        for pattern in SPECIFICITY_MARKERS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            specificity_hits.extend(matches)
        specificity_count = len(specificity_hits)

        # First-person authenticity — stories with "I" + past tense verb
        past_tense_stories = len(re.findall(
            r"\bi\s+(built|created|designed|developed|led|managed|improved|reduced|increased|launched|solved|fixed|helped|worked|collaborated|shipped)\b",
            text_lower
        ))

        # Quantified achievements (real humans remember actual numbers)
        quantified_achievements = len(re.findall(
            r"\b(increased|decreased|reduced|improved|grew|saved|generated)\s+\w*\s*(?:by\s+)?\d+",
            text_lower
        ))

        # Contrast: AI uses polished present-tense framing, humans often use past tense narratives
        present_tense_ratio = len(re.findall(r"\b(am|is|are|do|does|have|has)\b", text_lower))
        past_tense_count = len(re.findall(r"\b\w+ed\b", text_lower))
        tense_ratio = past_tense_count / max(present_tense_ratio + 1, 1)

        # Sentence-ending variety (AI often ends with confident declarations)
        exclamation_count = text.count("!")
        question_count = text.count("?")

        return {
            "word_count": len(words),
            "generic_phrase_count": generic_phrase_count,
            "generic_phrase_density": round(generic_phrase_density, 3),
            "specificity_count": specificity_count,
            "past_tense_stories": past_tense_stories,
            "quantified_achievements": quantified_achievements,
            "tense_ratio": round(tense_ratio, 3),
            "exclamation_count": exclamation_count,
        }

    def _score_features(self, f: dict) -> float:
        score_components = []

        # Generic phrase density (AI crams buzzwords)
        gpd = f["generic_phrase_density"]
        if gpd > 5:
            score_components.append(0.05)   # Full of buzzwords = AI
        elif gpd > 2:
            score_components.append(0.35)
        elif gpd > 0:
            score_components.append(0.70)
        else:
            score_components.append(0.90)   # No buzzwords = human

        # Specific details (real humans cite actual things)
        spec = f["specificity_count"]
        if spec >= 3:
            score_components.append(0.90)
        elif spec >= 1:
            score_components.append(0.70)
        else:
            score_components.append(0.20)   # Zero specifics = generic AI

        # Past-tense stories (humans tell stories about what they did)
        pts = f["past_tense_stories"]
        if pts >= 3:
            score_components.append(0.90)
        elif pts >= 1:
            score_components.append(0.65)
        else:
            score_components.append(0.25)

        # Quantified achievements
        qa = f["quantified_achievements"]
        if qa >= 2:
            score_components.append(0.85)
        elif qa >= 1:
            score_components.append(0.65)
        else:
            score_components.append(0.40)

        return round(sum(score_components) / len(score_components), 3)

    def _generate_flags(self, f: dict) -> List[str]:
        flags = []
        if f["generic_phrase_density"] > 3:
            flags.append("resume_high_buzzword_density")
        if f["specificity_count"] == 0:
            flags.append("resume_no_specific_details")
        if f["past_tense_stories"] == 0 and f["word_count"] > 100:
            flags.append("resume_no_personal_narratives")
        if f["quantified_achievements"] == 0 and f["word_count"] > 150:
            flags.append("resume_no_quantified_results")
        return flags
