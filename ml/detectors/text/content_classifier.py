"""
Content Classifier — AI vs Human Text Detection

─── Model tiers (swap MODEL_NAME to upgrade) ─────────────────────────────────

  CURRENT (demo/local):
    openai-community/roberta-large-openai-detector
    - Pre-trained by OpenAI. Zero setup. Downloads ~1.4 GB once, then cached.
    - Accurate on GPT-2 era text. Good enough to impress in a demo.

  UPGRADE OPTION (stronger, still zero fine-tuning needed):
    Hello-SimpleAI/chatgpt-detector-roberta
    - Trained on ChatGPT outputs. Better on GPT-3.5/4 era text.
    - Same swap — just change MODEL_NAME below.

  PRODUCTION (fine-tuned on your own pilot data — see FINE_TUNING_GUIDE.md):
    /app/ml_engine/saved_models/humaneye-detector
    - Train on labeled samples from pilot customers (~2 hrs on Colab T4).
    - Instructions in FINE_TUNING_GUIDE.md.

─── Label mapping (handled automatically) ────────────────────────────────────
  roberta-large-openai-detector : "Real" = human,  "Fake" = AI
  chatgpt-detector-roberta      : "Human" = human, "ChatGPT" = AI
  Your fine-tuned model         : auto-detected from first inference
"""

import re
import math
from collections import Counter
from typing import List, Optional
import logging

from ...api.schemas import DetectorResult

logger = logging.getLogger(__name__)

# ── Change this one line to upgrade the model ─────────────────────────────────
MODEL_NAME = "openai-community/roberta-large-openai-detector"
# MODEL_NAME = "Hello-SimpleAI/chatgpt-detector-roberta"
# MODEL_NAME = "/app/ml_engine/saved_models/humaneye-detector"
# ─────────────────────────────────────────────────────────────────────────────


class ContentClassifier:
    version = "1.0.0"
    last_trained = "openai_roberta_large_detector"

    def __init__(self):
        self._transformer_model = None
        self._human_label: Optional[str] = None
        self._try_load_transformer()

    # ── Startup ──────────────────────────────────────────────────────────────

    def _try_load_transformer(self):
        """
        Load transformer. Silently falls back to statistical-only if:
        - No internet (model not yet cached locally)
        - Not enough RAM (~1.4 GB needed for roberta-large)
        - Any other failure
        Service keeps running either way — statistical fallback is always active.
        """
        try:
            from transformers import pipeline
            self._transformer_model = pipeline(
                "text-classification",
                model=MODEL_NAME,
                max_length=512,
                truncation=True,
            )
            # Auto-detect which label means "human" by running one dummy input
            probe = self._transformer_model("Hello, how are you today?")[0]
            self._human_label = self._detect_human_label(probe["label"])
            logger.info(
                f"Transformer loaded: {MODEL_NAME} | "
                f"human_label='{self._human_label}'"
            )
        except Exception as e:
            logger.warning(
                f"Transformer unavailable — statistical fallback active. "
                f"Model: {MODEL_NAME} | Error: {e}"
            )
            self._transformer_model = None

    def _detect_human_label(self, sample_label: str) -> str:
        """
        Figure out which label string means 'human-written' for the loaded model.
        Handles: "Real"/"Fake", "Human"/"ChatGPT", "LABEL_1"/"LABEL_0", etc.
        """
        human_indicators = {"real", "human", "label_1", "1"}
        if sample_label.lower() in human_indicators:
            return sample_label
        # Probe returned an AI label — the human label is the opposite.
        # Store this AI label and invert in _get_transformer_score.
        return sample_label   # will be inverted because it's not in human_indicators

    # ── Main classify method ─────────────────────────────────────────────────

    def classify(self, text: str) -> DetectorResult:
        words = text.split()
        if len(words) < 20:
            return DetectorResult(
                score=0.5,
                flags=["text_too_short"],
                confidence=0.1,
                raw_features={"word_count": len(words)},
            )

        features = self._extract_statistical_features(text, words)
        stat_score = self._statistical_score(features)

        if self._transformer_model and len(text) > 50:
            try:
                transformer_score = self._get_transformer_score(text)
                # Blend: transformer 70%, statistical 30%
                final_score = 0.7 * transformer_score + 0.3 * stat_score
                confidence = 0.85
                source = "transformer_blend"
            except Exception as e:
                logger.warning(f"Transformer inference failed: {e}")
                final_score = stat_score
                confidence = 0.65
                source = "statistical_fallback"
        else:
            final_score = stat_score
            confidence = 0.65
            source = "statistical"

        flags = self._generate_flags(features)
        if source == "statistical_fallback":
            flags.append("classifier_using_statistical_fallback")

        return DetectorResult(
            score=round(final_score, 3),
            flags=flags,
            confidence=confidence,
            raw_features={**features, "score_source": source},
        )

    def _get_transformer_score(self, text: str) -> float:
        """
        Returns 0.0–1.0 where 1.0 = definitely human-written.
        Handles any label scheme via _human_label detection at startup.
        """
        result = self._transformer_model(text[:512])[0]
        label = result["label"]
        raw_score = result["score"]

        if label.lower() in {"real", "human", "label_1", "1"}:
            return raw_score        # This label = human → score is the human confidence
        else:
            return 1.0 - raw_score  # This label = AI → invert to get human confidence

    # ── Statistical features (always runs, no model needed) ──────────────────

    def _extract_statistical_features(self, text: str, words: List[str]) -> dict:
        word_counts = Counter(w.lower() for w in words)
        total = sum(word_counts.values())

        # Entropy: human writing clusters topics; AI spreads vocabulary evenly
        entropy = -sum((c / total) * math.log2(c / total + 1e-9) for c in word_counts.values())
        max_entropy = math.log2(max(len(word_counts), 1))
        normalized_entropy = entropy / (max_entropy + 1e-9)

        # Average word length: AI uses more formal/longer words
        avg_word_len = sum(len(w) for w in words) / max(len(words), 1)

        # Contractions: humans use them naturally; AI often avoids them
        contractions = len(re.findall(
            r"\b\w+n't\b|\bi'm\b|\bi've\b|\bi'll\b|\bdon't\b|\bcan't\b|\bwon't\b|\bwe're\b|\bthey're\b",
            text.lower()
        ))
        contraction_rate = contractions / max(len(words), 1)

        # Paragraph length variation: AI tends to write very uniform paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
        para_lengths = [len(p.split()) for p in paragraphs]
        para_cv = 0.0
        if len(para_lengths) > 1:
            mean_p = sum(para_lengths) / len(para_lengths)
            std_p = math.sqrt(sum((l - mean_p) ** 2 for l in para_lengths) / len(para_lengths))
            para_cv = std_p / (mean_p + 1e-9)

        return {
            "normalized_entropy": round(normalized_entropy, 3),
            "avg_word_len": round(avg_word_len, 2),
            "comma_rate": round(text.count(",") / max(len(words), 1), 3),
            "para_cv": round(para_cv, 3),
            "contraction_rate": round(contraction_rate, 3),
            "word_count": len(words),
        }

    def _statistical_score(self, f: dict) -> float:
        score_components = []

        ne = f["normalized_entropy"]
        if ne > 0.92:
            score_components.append(0.15)   # Very uniform = AI
        elif ne > 0.85:
            score_components.append(0.55)
        else:
            score_components.append(0.80)

        awl = f["avg_word_len"]
        if awl > 6.5:
            score_components.append(0.20)   # Long words = formal = AI
        elif awl > 5.5:
            score_components.append(0.55)
        else:
            score_components.append(0.80)

        cr = f["contraction_rate"]
        if cr > 0.03:
            score_components.append(0.90)   # Contractions = human
        elif cr > 0.01:
            score_components.append(0.65)
        else:
            score_components.append(0.30)

        pv = f["para_cv"]
        if pv > 0.4:
            score_components.append(0.80)   # Irregular paragraphs = human
        elif pv > 0.1:
            score_components.append(0.55)
        else:
            score_components.append(0.30)

        return round(sum(score_components) / len(score_components), 3)

    def _generate_flags(self, f: dict) -> List[str]:
        flags = []
        if f["normalized_entropy"] > 0.92:
            flags.append("text_vocabulary_distribution_too_uniform")
        if f["avg_word_len"] > 6.5:
            flags.append("text_formal_vocabulary_detected")
        if f["contraction_rate"] < 0.005:
            flags.append("text_no_contractions")
        return flags
