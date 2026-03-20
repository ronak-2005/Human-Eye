"""
Vocabulary Analyzer — Human Imperfection Index

AI-generated text is statistically too perfect. Real human writing has:
- Consistent personal vocabulary fingerprint
- Repeated favorite words and phrases
- Informal transition words (also, but, so) vs AI's formal ones (furthermore, moreover)
- Irregular-but-consistent sentence rhythm
- Personal specificity: one detail only the author could know
"""

import re
import math
from collections import Counter
from typing import List
import logging

from ...api.schemas import DetectorResult

logger = logging.getLogger(__name__)

# Top-3000 most common English words proxy (abbreviated — load full list from file in production)
# Real humans use 85-90% of their words from this set; AI uses 60-70%
COMMON_WORDS_SAMPLE = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "it",
    "for", "not", "on", "with", "he", "as", "you", "do", "at", "this",
    "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
    "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
    "when", "make", "can", "like", "time", "no", "just", "him", "know",
    "take", "people", "into", "year", "your", "good", "some", "could",
    "them", "see", "other", "than", "then", "now", "look", "only", "come",
    "its", "over", "think", "also", "back", "after", "use", "two", "how",
    "our", "work", "first", "well", "way", "even", "new", "want", "because",
    "any", "these", "give", "day", "most", "us", "great", "between", "need",
    "large", "often", "hand", "high", "place", "hold", "turn", "real", "life",
    "few", "north", "open", "seem", "together", "next", "white", "children",
    "begin", "got", "walk", "example", "ease", "paper", "always", "music",
    "those", "both", "mark", "often", "letter", "until", "mile", "river",
    "car", "feet", "care", "second", "enough", "plain", "girl", "usual",
    "young", "ready", "above", "ever", "red", "list", "though", "feel",
    "talk", "bird", "soon", "body", "dog", "family", "direct", "pose",
    "leave", "song", "measure", "door", "product", "black", "short",
    "numeral", "class", "wind", "question", "happen", "complete", "ship",
    "area", "half", "rock", "order", "fire", "south", "problem", "piece",
    "told", "knew", "pass", "since", "top", "whole", "king", "space",
    "heard", "best", "hour", "better", "true", "play", "small", "number",
    "off", "always", "move", "try", "kind", "hand", "picture", "again",
    "change", "off", "play", "spell", "air", "away", "animal", "house",
    "point", "page", "letter", "mother", "answer", "found", "study", "still",
    "learn", "plant", "cover", "food", "sun", "four", "between", "state",
    "keep", "eye", "never", "last", "let", "thought", "city", "tree",
    "cross", "farm", "hard", "start", "might", "story", "saw", "far",
    "sea", "draw", "left", "late", "run", "don't", "while", "press",
    "close", "night", "real", "life", "few", "stop", "open", "seem",
}

# AI "tells" — formal connectives AI overuses
AI_TRANSITION_WORDS = {
    "furthermore", "moreover", "consequently", "nevertheless", "nonetheless",
    "therefore", "thus", "hence", "additionally", "subsequently", "ultimately",
    "in conclusion", "to summarize", "in summary", "it is important to note",
    "it should be noted", "it is worth mentioning", "as mentioned above",
    "as previously stated", "in light of", "with regard to", "pertaining to",
    "in terms of", "it goes without saying", "needless to say",
}

# Human natural connectives
HUMAN_TRANSITION_WORDS = {
    "also", "but", "so", "yet", "plus", "still", "anyway", "besides",
    "though", "although", "because", "since", "then", "now", "well",
    "okay", "right", "look", "honestly", "basically", "actually",
    "literally", "really", "just", "kind of", "sort of",
}


class VocabularyAnalyzer:

    version = "1.0.0"
    last_trained = "synthetic_baseline_v1"

    MIN_WORD_COUNT = 50   # Need at least 50 words for reliable scoring

    def analyze(self, text: str) -> DetectorResult:
        words = self._tokenize(text)

        if len(words) < self.MIN_WORD_COUNT:
            return DetectorResult(
                score=0.5,
                flags=["insufficient_text_length"],
                confidence=0.2,
                raw_features={"word_count": len(words)},
            )

        features = self._extract_features(text, words)
        score = self._score_features(features)
        flags = self._generate_flags(features)

        # More text = higher confidence
        confidence = min(0.90, len(words) / 500)

        return DetectorResult(
            score=score,
            flags=flags,
            confidence=round(confidence, 3),
            raw_features=features,
        )

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b[a-z']+\b", text.lower())

    def _extract_features(self, text: str, words: List[str]) -> dict:
        text_lower = text.lower()
        word_counts = Counter(words)
        unique_words = len(word_counts)
        total_words = len(words)

        # Common word ratio (humans: 85-90%, AI: 60-70%)
        common_word_count = sum(1 for w in words if w in COMMON_WORDS_SAMPLE)
        common_word_ratio = common_word_count / total_words

        # Synonym variety score: AI avoids repeating words
        # High hapax ratio (words used only once) = AI avoiding repetition
        hapax_count = sum(1 for w, c in word_counts.items() if c == 1 and len(w) > 4)
        hapax_ratio = hapax_count / max(unique_words, 1)

        # AI transition word frequency
        ai_transitions = sum(1 for phrase in AI_TRANSITION_WORDS if phrase in text_lower)
        human_transitions = sum(1 for phrase in HUMAN_TRANSITION_WORDS if phrase in text_lower)

        # Sentence rhythm: length variation (AI produces mathematically varied lengths)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        sentence_lengths = [len(s.split()) for s in sentences]
        sentence_length_cv = 0.0
        if len(sentence_lengths) > 2:
            mean_len = sum(sentence_lengths) / len(sentence_lengths)
            std_len = math.sqrt(sum((l - mean_len) ** 2 for l in sentence_lengths) / len(sentence_lengths))
            sentence_length_cv = std_len / (mean_len + 1e-9)

        # Type-token ratio (vocabulary richness) — low = repetitive human, high = AI
        ttr = unique_words / total_words

        # Personal pronoun usage (humans reference themselves; AI often writes impersonally)
        personal_pronouns = {"i", "i'm", "i've", "i'd", "i'll", "my", "me", "myself", "we", "our"}
        pronoun_count = sum(word_counts.get(p, 0) for p in personal_pronouns)
        pronoun_ratio = pronoun_count / total_words

        return {
            "word_count": total_words,
            "common_word_ratio": round(common_word_ratio, 3),
            "hapax_ratio": round(hapax_ratio, 3),
            "ai_transition_count": ai_transitions,
            "human_transition_count": human_transitions,
            "sentence_length_cv": round(sentence_length_cv, 3),
            "type_token_ratio": round(ttr, 3),
            "pronoun_ratio": round(pronoun_ratio, 3),
            "sentence_count": len(sentence_lengths),
        }

    def _score_features(self, f: dict) -> float:
        score_components = []

        # Common word ratio (humans use more everyday words)
        cwr = f["common_word_ratio"]
        if cwr >= 0.80:
            score_components.append(0.90)   # High common word use = human
        elif cwr >= 0.65:
            score_components.append(0.60)
        else:
            score_components.append(0.15)   # Low common word use = AI

        # Hapax ratio (AI avoids repetition by using varied vocabulary)
        hr = f["hapax_ratio"]
        if hr > 0.70:
            score_components.append(0.15)   # Too many unique words = AI
        elif hr > 0.50:
            score_components.append(0.55)
        else:
            score_components.append(0.85)   # Repeating words = human

        # Transition word balance
        ai_t = f["ai_transition_count"]
        human_t = f["human_transition_count"]
        if ai_t == 0 and human_t > 0:
            score_components.append(0.90)
        elif ai_t > human_t:
            score_components.append(0.20)
        elif ai_t == 0 and human_t == 0:
            score_components.append(0.50)
        else:
            score_components.append(0.65)

        # Sentence rhythm (AI has smooth mathematical variation)
        slcv = f["sentence_length_cv"]
        if slcv > 0.4:
            score_components.append(0.85)   # Irregular = human
        elif slcv > 0.2:
            score_components.append(0.60)
        else:
            score_components.append(0.25)   # Smooth = AI

        # Personal pronouns (humans write about themselves)
        pr = f["pronoun_ratio"]
        if pr > 0.03:
            score_components.append(0.80)
        elif pr > 0.01:
            score_components.append(0.55)
        else:
            score_components.append(0.30)

        return round(sum(score_components) / len(score_components), 3)

    def _generate_flags(self, f: dict) -> List[str]:
        flags = []
        if f["common_word_ratio"] < 0.70:
            flags.append("text_vocabulary_too_advanced")
        if f["hapax_ratio"] > 0.70:
            flags.append("text_synonym_variety_too_high")
        if f["ai_transition_count"] >= 3:
            flags.append("text_ai_transition_phrases_detected")
        if f["sentence_length_cv"] < 0.15 and f["sentence_count"] > 4:
            flags.append("text_sentence_rhythm_too_uniform")
        if f["pronoun_ratio"] < 0.005:
            flags.append("text_no_personal_pronouns")
        return flags
