"""
Model Evaluator
Tests detector accuracy, generates performance reports, and tracks model drift.

Run this before every production deployment.
Usage: python -m ml_engine.evaluation.model_evaluator
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class EvalMetrics:
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    false_positive_rate: float   # Bot classified as human (dangerous — lets bots through)
    false_negative_rate: float   # Human classified as bot (bad UX — blocks real users)
    sample_count: int
    threshold_used: float


class ModelEvaluator:
    """
    Evaluates any detector model against a labeled dataset.
    Dataset format: List of {"signals": ..., "label": "human" | "bot"}
    """

    HUMAN_SCORE_THRESHOLD = 0.5   # Score >= this = predicted human

    def evaluate_detector(
        self,
        model,
        test_samples: List[Dict[str, Any]],
        model_name: str,
    ) -> EvalMetrics:
        """
        Run evaluation on a labeled test set.

        Args:
            model: Any detector with a predict() or analyze() or score() method
            test_samples: [{"input": <model-specific input>, "label": "human"|"bot"}]
            model_name: Name for logging and reporting
        """
        tp = fp = tn = fn = 0

        for sample in test_samples:
            true_label = sample["label"]  # "human" or "bot"
            input_data = sample["input"]

            # Call the model's main method (different detectors use different names)
            result = self._call_model(model, input_data)
            predicted_human = result.score >= self.HUMAN_SCORE_THRESHOLD

            if true_label == "human" and predicted_human:
                tp += 1
            elif true_label == "bot" and predicted_human:
                fp += 1   # Bot slipped through — most dangerous error
            elif true_label == "bot" and not predicted_human:
                tn += 1
            elif true_label == "human" and not predicted_human:
                fn += 1   # Human blocked — bad UX

        total = tp + fp + tn + fn
        accuracy = (tp + tn) / max(total, 1)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)
        fpr = fp / max(fp + tn, 1)
        fnr = fn / max(fn + tp, 1)

        metrics = EvalMetrics(
            model_name=model_name,
            accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            false_positive_rate=round(fpr, 4),
            false_negative_rate=round(fnr, 4),
            sample_count=total,
            threshold_used=self.HUMAN_SCORE_THRESHOLD,
        )

        logger.info(f"Eval [{model_name}]: acc={accuracy:.3f} f1={f1:.3f} fpr={fpr:.3f} fnr={fnr:.3f}")
        return metrics

    def _call_model(self, model, input_data):
        """Dispatch to whichever method the model exposes."""
        if hasattr(model, "predict"):
            return model.predict(input_data)
        elif hasattr(model, "analyze"):
            return model.analyze(input_data)
        elif hasattr(model, "score"):
            return model.score(input_data)
        elif hasattr(model, "classify"):
            return model.classify(input_data)
        else:
            raise ValueError(f"Model {model} has no predict/analyze/score/classify method")

    def generate_report(self, metrics_list: List[EvalMetrics]) -> str:
        """Generate a human-readable evaluation report."""
        lines = ["=" * 60, "HumanEye ML Evaluation Report", "=" * 60]
        for m in metrics_list:
            lines += [
                f"\nModel: {m.model_name}",
                f"  Accuracy:          {m.accuracy:.1%}",
                f"  F1 Score:          {m.f1:.1%}",
                f"  False Positive Rate (bot-as-human): {m.false_positive_rate:.1%}  {'⚠ HIGH' if m.false_positive_rate > 0.05 else '✓ OK'}",
                f"  False Negative Rate (human-as-bot): {m.false_negative_rate:.1%}  {'⚠ HIGH' if m.false_negative_rate > 0.10 else '✓ OK'}",
                f"  Sample count:      {m.sample_count}",
            ]
        lines.append("=" * 60)
        return "\n".join(lines)

    def save_metrics(self, metrics_list: List[EvalMetrics], path: str):
        """Save metrics to JSON for MLflow logging."""
        data = [asdict(m) for m in metrics_list]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Metrics saved to {path}")
