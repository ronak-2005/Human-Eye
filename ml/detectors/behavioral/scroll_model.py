"""
Scroll Behavior Model
Analyzes scroll patterns to distinguish humans from bots.

Real humans: natural deceleration, pauses at content boundaries (end of paragraphs),
             backscroll (rereading), irregular momentum.
Bots:        linear/programmatic scrolling, no pauses, no backscroll.
"""

import numpy as np
from typing import List
import logging

from ...api.schemas import ScrollEvent, DetectorResult

logger = logging.getLogger(__name__)


class ScrollModel:

    version = "1.0.0"
    last_trained = "synthetic_baseline_v1"

    MIN_EVENTS_FOR_SCORING = 15

    def predict(self, events: List[ScrollEvent]) -> DetectorResult:
        if len(events) < self.MIN_EVENTS_FOR_SCORING:
            return DetectorResult(
                score=0.5,
                flags=["insufficient_scroll_data"],
                confidence=0.2,
                raw_features={"event_count": len(events)},
            )

        features = self._extract_features(events)
        score = self._score_features(features)
        flags = self._generate_flags(features)
        confidence = min(0.85, len(events) / 150)

        return DetectorResult(
            score=score,
            flags=flags,
            confidence=round(confidence, 3),
            raw_features=features,
        )

    def _extract_features(self, events: List[ScrollEvent]) -> dict:
        positions = np.array([e.scroll_y for e in events])
        timestamps = np.array([e.timestamp for e in events])
        velocities = np.array([e.velocity for e in events])

        # Backscroll: direction changes (up scrolls after downward progress)
        directions = np.sign(np.diff(positions))
        direction_changes = np.sum(np.abs(np.diff(directions)) > 0)
        backscroll_rate = direction_changes / max(len(events) - 1, 1)

        # Pause detection: time gaps > 500ms between scroll events
        time_gaps = np.diff(timestamps)
        pause_count = int(np.sum(time_gaps > 500))
        pause_rate = pause_count / max(len(time_gaps), 1)

        # Velocity deceleration pattern: compute how often velocity drops after a peak
        vel_diff = np.diff(velocities)
        decel_events = np.sum(vel_diff < -0.5)
        decel_rate = decel_events / max(len(vel_diff), 1)

        # Scroll step uniformity: bots often scroll in fixed pixel increments
        position_diffs = np.abs(np.diff(positions))
        nonzero_diffs = position_diffs[position_diffs > 0]
        step_cv = float(np.std(nonzero_diffs) / (np.mean(nonzero_diffs) + 1e-9)) if len(nonzero_diffs) > 0 else 0

        # Velocity coefficient of variation
        vel_cv = float(np.std(velocities) / (np.mean(np.abs(velocities)) + 1e-9))

        return {
            "backscroll_rate": float(backscroll_rate),
            "pause_rate": float(pause_rate),
            "pause_count": pause_count,
            "decel_rate": float(decel_rate),
            "step_cv": float(step_cv),
            "velocity_cv": float(vel_cv),
            "event_count": len(events),
            "total_scroll_distance": float(np.sum(np.abs(np.diff(positions)))),
        }

    def _score_features(self, f: dict) -> float:
        score_components = []

        # Backscroll (humans reread content)
        if f["backscroll_rate"] > 0.05:
            score_components.append(0.85)
        elif f["backscroll_rate"] > 0.01:
            score_components.append(0.65)
        else:
            score_components.append(0.20)   # Zero backscroll = suspicious

        # Pause rate (humans pause to read)
        if f["pause_rate"] > 0.10:
            score_components.append(0.90)
        elif f["pause_rate"] > 0.03:
            score_components.append(0.65)
        else:
            score_components.append(0.15)

        # Deceleration rate (human scroll momentum decays naturally)
        if f["decel_rate"] > 0.30:
            score_components.append(0.85)
        elif f["decel_rate"] > 0.10:
            score_components.append(0.60)
        else:
            score_components.append(0.20)

        # Step uniformity (bots often scroll fixed increments)
        if f["step_cv"] > 0.5:
            score_components.append(0.85)   # Variable steps = human
        elif f["step_cv"] > 0.2:
            score_components.append(0.60)
        else:
            score_components.append(0.10)   # Uniform steps = bot

        return round(float(np.mean(score_components)), 3)

    def _generate_flags(self, f: dict) -> List[str]:
        flags = []
        if f["backscroll_rate"] == 0.0:
            flags.append("scroll_no_backscroll")
        if f["pause_rate"] < 0.02:
            flags.append("scroll_no_reading_pauses")
        if f["step_cv"] < 0.1:
            flags.append("scroll_uniform_step_size")
        if f["velocity_cv"] < 0.1:
            flags.append("scroll_constant_velocity")
        return flags
