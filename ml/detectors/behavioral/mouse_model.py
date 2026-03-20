"""
Mouse Dynamics Model
Detects bots by analyzing mouse movement patterns.

Real humans: curved paths with micro-corrections, variable velocity,
             natural deceleration before clicks, involuntary micro-tremor.
Bots:        linear paths, constant velocity, perfectly timed clicks.
"""

import numpy as np
from typing import List
import logging

from ...api.schemas import MouseEvent, DetectorResult

logger = logging.getLogger(__name__)


class MouseModel:

    version = "1.0.0"
    last_trained = "synthetic_baseline_v1"

    MIN_EVENTS_FOR_SCORING = 30

    def predict(self, events: List[MouseEvent]) -> DetectorResult:
        move_events = [e for e in events if e.event_type == "move"]
        click_events = [e for e in events if e.event_type == "click"]

        if len(move_events) < self.MIN_EVENTS_FOR_SCORING:
            return DetectorResult(
                score=0.5,
                flags=["insufficient_mouse_data"],
                confidence=0.2,
                raw_features={"move_count": len(move_events)},
            )

        features = self._extract_features(move_events, click_events)
        score = self._score_features(features)
        flags = self._generate_flags(features)
        confidence = min(0.90, len(move_events) / 300)

        return DetectorResult(
            score=score,
            flags=flags,
            confidence=round(confidence, 3),
            raw_features=features,
        )

    def _extract_features(self, moves: List[MouseEvent], clicks: List[MouseEvent]) -> dict:
        xs = np.array([e.x for e in moves])
        ys = np.array([e.y for e in moves])
        ts = np.array([e.timestamp for e in moves])

        # Velocities between consecutive points
        dx = np.diff(xs)
        dy = np.diff(ys)
        dt = np.diff(ts) + 1e-9  # avoid division by zero
        distances = np.sqrt(dx**2 + dy**2)
        velocities = distances / dt

        # Curvature: angle change between consecutive movement vectors
        angles = np.arctan2(dy, dx)
        angle_changes = np.abs(np.diff(angles))
        # Normalize angles to [-pi, pi]
        angle_changes = np.where(angle_changes > np.pi, 2 * np.pi - angle_changes, angle_changes)

        # Micro-tremor: high-frequency small movements (< 5px) that humans produce involuntarily
        small_moves = distances[distances < 5.0]
        micro_tremor_rate = len(small_moves) / max(len(distances), 1)

        # Linearity: how straight are paths between click events?
        linearity_scores = self._compute_path_linearity(xs, ys, clicks, moves)

        # Pre-click deceleration: humans slow down before clicking
        pre_click_decel = self._compute_pre_click_deceleration(velocities, clicks, moves)

        return {
            "velocity_mean": float(np.mean(velocities)),
            "velocity_std": float(np.std(velocities)),
            "velocity_cv": float(np.std(velocities) / (np.mean(velocities) + 1e-9)),
            "curvature_mean": float(np.mean(angle_changes)),
            "curvature_std": float(np.std(angle_changes)),
            "micro_tremor_rate": float(micro_tremor_rate),
            "linearity_score": float(np.mean(linearity_scores)) if linearity_scores else 0.5,
            "pre_click_decel": float(pre_click_decel),
            "move_count": len(moves),
            "click_count": len(clicks),
        }

    def _compute_path_linearity(self, xs, ys, clicks, moves) -> List[float]:
        """
        For each segment between clicks, compute how linear the path is.
        Linear (straight line) = 1.0 (bot-like).
        Curved = closer to 0 (human-like).
        """
        if len(clicks) < 2:
            return []

        scores = []
        click_timestamps = [c.timestamp for c in clicks]
        move_timestamps = [m.timestamp for m in moves]

        for i in range(len(click_timestamps) - 1):
            t_start, t_end = click_timestamps[i], click_timestamps[i + 1]
            segment_indices = [
                j for j, t in enumerate(move_timestamps)
                if t_start <= t <= t_end
            ]
            if len(segment_indices) < 3:
                continue

            seg_xs = xs[segment_indices]
            seg_ys = ys[segment_indices]

            # Straight-line distance start→end vs actual path length
            direct_dist = np.sqrt((seg_xs[-1] - seg_xs[0])**2 + (seg_ys[-1] - seg_ys[0])**2)
            path_dist = np.sum(np.sqrt(np.diff(seg_xs)**2 + np.diff(seg_ys)**2))

            linearity = direct_dist / (path_dist + 1e-9)
            scores.append(float(linearity))

        return scores

    def _compute_pre_click_deceleration(self, velocities, clicks, moves) -> float:
        """
        Measure whether mouse decelerates in the 200ms before each click.
        Returns average deceleration ratio: < 1 = slowing down (human), ≈ 1 = constant (bot).
        """
        if len(clicks) == 0 or len(velocities) < 5:
            return 0.5

        move_timestamps = [m.timestamp for m in moves]
        decel_ratios = []

        for click in clicks:
            t_click = click.timestamp
            # Find moves in [t_click-300ms, t_click]
            near_indices = [
                i for i, t in enumerate(move_timestamps[:-1])
                if t_click - 300 <= t <= t_click
            ]
            if len(near_indices) < 4:
                continue

            near_vels = velocities[near_indices[0]:near_indices[-1]+1]
            if len(near_vels) < 2:
                continue

            # Compare first half vs second half velocity
            mid = len(near_vels) // 2
            avg_before = np.mean(near_vels[:mid]) + 1e-9
            avg_after = np.mean(near_vels[mid:]) + 1e-9
            decel_ratios.append(float(avg_after / avg_before))

        return float(np.mean(decel_ratios)) if decel_ratios else 0.5

    def _score_features(self, f: dict) -> float:
        score_components = []

        # Velocity variation (humans are irregular)
        vel_cv = f["velocity_cv"]
        if vel_cv < 0.1:
            score_components.append(0.10)
        elif vel_cv < 0.3:
            score_components.append(0.55)
        else:
            score_components.append(0.90)

        # Curvature (humans curve naturally)
        if f["curvature_mean"] > 0.05:
            score_components.append(0.85)
        else:
            score_components.append(0.15)

        # Micro-tremor (involuntary human movement)
        mt = f["micro_tremor_rate"]
        if mt > 0.15:
            score_components.append(0.90)
        elif mt > 0.05:
            score_components.append(0.65)
        else:
            score_components.append(0.20)

        # Path linearity (bots move in straight lines)
        linearity = f["linearity_score"]
        if linearity > 0.95:
            score_components.append(0.05)   # Near-perfect straight line = bot
        elif linearity > 0.85:
            score_components.append(0.40)
        else:
            score_components.append(0.85)

        # Pre-click deceleration (humans slow down before clicking)
        decel = f["pre_click_decel"]
        if decel < 0.6:
            score_components.append(0.90)   # Clear deceleration = human
        elif decel < 0.85:
            score_components.append(0.65)
        else:
            score_components.append(0.20)   # No deceleration = bot

        return round(float(np.mean(score_components)), 3)

    def _generate_flags(self, f: dict) -> List[str]:
        flags = []
        if f["velocity_cv"] < 0.1:
            flags.append("mouse_velocity_unnaturally_constant")
        if f["linearity_score"] > 0.95:
            flags.append("mouse_paths_too_linear")
        if f["micro_tremor_rate"] < 0.03:
            flags.append("mouse_no_micro_tremor")
        if f["pre_click_decel"] > 0.90:
            flags.append("mouse_no_pre_click_deceleration")
        if f["curvature_mean"] < 0.02:
            flags.append("mouse_movement_no_curvature")
        return flags
