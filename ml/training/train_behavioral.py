"""
Behavioral Model Training Script
Generates synthetic training data and trains baseline behavioral classifiers.

Phase 1 uses synthetic data (rule-based human simulation vs deterministic bots).
Phase 2 will replace with real labeled data from pilot customers.

Usage: python -m ml_engine.training.train_behavioral
"""

import random
import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


# ─── Synthetic data generation ───────────────────────────────────────────────

def generate_human_keystrokes(n_keys: int = 150) -> List[Dict]:
    """
    Simulate realistic human keystroke patterns.
    Real humans: variable dwell 50-180ms, flight 60-250ms, ~5% backspace rate.
    """
    events = []
    t = 0.0
    common_keys = list("abcdefghijklmnopqrstuvwxyz ,.!?")

    for i in range(n_keys):
        key = random.choice(common_keys)

        # Human-like: occasional fast burst (typing a common word), occasional slow (thinking)
        if random.random() < 0.15:
            flight = random.gauss(200, 80)    # Thinking pause
        else:
            flight = random.gauss(90, 35)     # Normal typing rhythm

        dwell = random.gauss(95, 30)          # Key hold time

        # Occasionally insert a backspace (human error)
        if i > 5 and random.random() < 0.05:
            events.append({
                "key": "Backspace",
                "keydown_time": round(t, 3),
                "keyup_time": round(t + random.gauss(80, 20), 3),
            })
            t += abs(random.gauss(70, 15))

        t += abs(flight)
        events.append({
            "key": f"Key{key.upper()}" if key.isalpha() else "Space",
            "keydown_time": round(t, 3),
            "keyup_time": round(t + abs(dwell), 3),
        })
        t += abs(dwell)

    return events


def generate_bot_keystrokes(n_keys: int = 150) -> List[Dict]:
    """
    Simulate bot keystroke patterns.
    Bots: near-constant timing, zero backspaces, no personal rhythm.
    """
    events = []
    t = 0.0

    for i in range(n_keys):
        key = f"Key{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"
        # Bot: almost perfectly constant timing with tiny noise
        flight = 80.0 + random.uniform(-1, 1)
        dwell = 50.0 + random.uniform(-0.5, 0.5)

        events.append({
            "key": key,
            "keydown_time": round(t, 3),
            "keyup_time": round(t + dwell, 3),
        })
        t += flight + dwell

    return events


def generate_human_mouse(n_points: int = 200) -> List[Dict]:
    """Simulate human mouse movement: curved paths, variable speed, micro-tremor."""
    events = []
    x, y = 400.0, 300.0
    t = 0.0

    for i in range(n_points):
        # Human-like: gradual direction changes, variable speed
        dx = random.gauss(0, 15) + random.uniform(-3, 3)
        dy = random.gauss(0, 10) + random.uniform(-3, 3)

        # Micro-tremor: small high-frequency noise
        dx += random.gauss(0, 2)
        dy += random.gauss(0, 2)

        x = max(0, min(1920, x + dx))
        y = max(0, min(1080, y + dy))
        dt = abs(random.gauss(20, 8))

        events.append({
            "x": round(x, 1), "y": round(y, 1),
            "timestamp": round(t, 3),
            "event_type": "move",
        })
        t += dt

        # Occasional click with deceleration before it
        if i > 20 and random.random() < 0.02:
            events.append({
                "x": round(x, 1), "y": round(y, 1),
                "timestamp": round(t, 3),
                "event_type": "click", "button": 0,
            })

    return events


def generate_bot_mouse(n_points: int = 200) -> List[Dict]:
    """Simulate bot mouse: linear paths, constant velocity, no tremor."""
    events = []
    x, y = 100.0, 100.0
    target_x, target_y = 800.0, 600.0
    t = 0.0

    for i in range(n_points):
        # Bot: perfectly linear interpolation toward target
        progress = i / n_points
        x = 100 + (target_x - 100) * progress
        y = 100 + (target_y - 100) * progress
        dt = 20.0  # Perfectly constant 50Hz

        events.append({
            "x": round(x, 2), "y": round(y, 2),
            "timestamp": round(t, 3),
            "event_type": "move",
        })
        t += dt

    # One click at the end, perfectly on target
    events.append({
        "x": target_x, "y": target_y,
        "timestamp": round(t, 3),
        "event_type": "click", "button": 0,
    })
    return events


def generate_training_dataset(
    n_human: int = 500,
    n_bot: int = 500,
) -> List[Dict[str, Any]]:
    """Generate a balanced labeled training dataset."""
    dataset = []

    for _ in range(n_human):
        dataset.append({
            "label": "human",
            "keystrokes": generate_human_keystrokes(),
            "mouse_events": generate_human_mouse(),
        })

    for _ in range(n_bot):
        dataset.append({
            "label": "bot",
            "keystrokes": generate_bot_keystrokes(),
            "mouse_events": generate_bot_mouse(),
        })

    # Shuffle
    random.shuffle(dataset)
    return dataset


def save_dataset(dataset: List[Dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(dataset, f)
    logger.info(f"Saved {len(dataset)} samples to {path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Generating synthetic behavioral training data...")
    dataset = generate_training_dataset(n_human=1000, n_bot=1000)
    save_dataset(dataset, "ml_engine/training/data/behavioral_synthetic_v1.json")
    logger.info("Done. Run evaluation to check baseline accuracy.")
