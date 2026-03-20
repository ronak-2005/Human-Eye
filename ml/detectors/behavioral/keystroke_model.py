"""
Keystroke Dynamics Model
Detects bots by analyzing typing rhythm patterns.

Real humans: variable dwell/flight times, consistent personal digraph patterns,
             natural error/backspace sequences.
Bots:        unnaturally consistent timing, no personal fingerprint, no errors.
"""

import numpy as np
from typing import List, Optional
import logging

from ...api.schemas import KeystrokeEvent, DetectorResult

logger = logging.getLogger(__name__)


class KeystrokeModel:
    """
    Analyzes keystroke timing features to distinguish humans from bots.

    Features extracted:
    - Dwell time: how long each key is held (keyup - keydown)
    - Flight time: gap between keyup[n] and keydown[n+1]
    - Digraph timing: time between specific key pairs (e.g. 'th', 'ing')
    - Coefficient of variation: humans have high CV; bots have near-zero
    - Error + backspace rate: humans make consistent error types
    """

    version = "1.0.0"
    last_trained = "synthetic_baseline_v1"

    # Thresholds calibrated from human baseline studies
    BOT_CV_THRESHOLD = 0.05       # CV below this = suspiciously regular (bot)
    HUMAN_MIN_DWELL_MS = 40       # Real humans: 40–200ms dwell
    HUMAN_MAX_DWELL_MS = 400
    MIN_EVENTS_FOR_SCORING = 20   # Need at least 20 keystrokes to score reliably

    def predict(self, events: List[KeystrokeEvent]) -> DetectorResult:
        if len(events) < self.MIN_EVENTS_FOR_SCORING:
            return DetectorResult(
                score=0.5,
                flags=["insufficient_keystroke_data"],
                confidence=0.2,
                raw_features={"event_count": len(events)},
            )

        features = self._extract_features(events)
        score = self._score_features(features)
        flags = self._generate_flags(features)

        confidence = min(0.95, len(events) / 200)  # More data = more confidence

        return DetectorResult(
            score=score,
            flags=flags,
            confidence=round(confidence, 3),
            raw_features=features,
        )

    def _extract_features(self, events: List[KeystrokeEvent]) -> dict:
        dwell_times = []
        flight_times = []
        digraph_times = {}
        backspace_count = 0

        for i, ev in enumerate(events):
            dwell = ev.keyup_time - ev.keydown_time
            if 0 < dwell < 2000:  # Filter outliers (tabbing away etc.)
                dwell_times.append(dwell)

            if i > 0:
                flight = ev.keydown_time - events[i - 1].keyup_time
                if -50 < flight < 2000:  # Allow slight overlap (fast typists)
                    flight_times.append(flight)

                # Digraph: consecutive key pair timing
                pair = f"{events[i-1].key}_{ev.key}"
                digraph_times.setdefault(pair, []).append(flight)

            if ev.key in ("Backspace", "Delete"):
                backspace_count += 1

        dwell_arr = np.array(dwell_times) if dwell_times else np.array([100.0])
        flight_arr = np.array(flight_times) if flight_times else np.array([80.0])

        return {
            "dwell_mean": float(np.mean(dwell_arr)),
            "dwell_std": float(np.std(dwell_arr)),
            "dwell_cv": float(np.std(dwell_arr) / (np.mean(dwell_arr) + 1e-9)),
            "flight_mean": float(np.mean(flight_arr)),
            "flight_std": float(np.std(flight_arr)),
            "flight_cv": float(np.std(flight_arr) / (np.mean(flight_arr) + 1e-9)),
            "backspace_rate": backspace_count / max(len(events), 1),
            "unique_digraphs": len(digraph_times),
            "event_count": len(events),
            "digraph_cv_mean": float(np.mean([
                np.std(v) / (np.mean(v) + 1e-9)
                for v in digraph_times.values() if len(v) > 1
            ])) if digraph_times else 0.0,
        }

    def _score_features(self, f: dict) -> float:
        """
        Returns score 0–1 where 1 = likely human, 0 = likely bot.
        Higher CV = more human-like variation.
        """
        score_components = []

        # Dwell time variation (main signal)
        dwell_cv = f["dwell_cv"]
        if dwell_cv < 0.02:
            score_components.append(0.05)   # Near-zero variation = bot
        elif dwell_cv < self.BOT_CV_THRESHOLD:
            score_components.append(0.25)
        elif dwell_cv < 0.15:
            score_components.append(0.65)
        else:
            score_components.append(0.90)   # High variation = human

        # Flight time variation
        flight_cv = f["flight_cv"]
        if flight_cv < 0.03:
            score_components.append(0.05)
        elif flight_cv < 0.10:
            score_components.append(0.55)
        else:
            score_components.append(0.88)

        # Dwell time range (humans: 40–200ms; bots often outside this)
        dwell_mean = f["dwell_mean"]
        if self.HUMAN_MIN_DWELL_MS <= dwell_mean <= self.HUMAN_MAX_DWELL_MS:
            score_components.append(0.80)
        else:
            score_components.append(0.30)

        # Backspace rate (humans make mistakes; bots rarely do)
        bs_rate = f["backspace_rate"]
        if bs_rate == 0.0:
            score_components.append(0.20)   # Zero errors is suspicious
        elif bs_rate < 0.01:
            score_components.append(0.50)
        elif bs_rate <= 0.15:
            score_components.append(0.90)   # Natural error rate
        else:
            score_components.append(0.60)   # Very high — could be correcting AI text

        # Digraph consistency (humans have stable pair-specific timing)
        if f["digraph_cv_mean"] > 0.1:
            score_components.append(0.80)
        else:
            score_components.append(0.40)

        return round(float(np.mean(score_components)), 3)

    def _generate_flags(self, f: dict) -> List[str]:
        flags = []
        if f["dwell_cv"] < self.BOT_CV_THRESHOLD:
            flags.append("keystroke_dwell_unnaturally_consistent")
        if f["flight_cv"] < 0.05:
            flags.append("keystroke_flight_unnaturally_consistent")
        if f["backspace_rate"] == 0.0 and f["event_count"] > 50:
            flags.append("keystroke_zero_errors")
        if f["dwell_mean"] < self.HUMAN_MIN_DWELL_MS:
            flags.append("keystroke_dwell_too_fast")
        if f["dwell_mean"] > self.HUMAN_MAX_DWELL_MS:
            flags.append("keystroke_dwell_too_slow")
        return flags
