"""
security/ml-security/adversarial-samples/generate_adversarial_samples.py

ADVERSARIAL SAMPLE GENERATOR
Owner: Security Engineer (maintains) | Used by: ML Engineer (monthly tests)

PURPOSE:
  Generates synthetic adversarial input samples for monthly model testing.
  These are crafted inputs designed to evade detection — bots that
  mimic human timing, voices, and text patterns.

  Security Engineer updates this file when new evasion techniques are discovered.
  ML Engineer runs it to get fresh test samples each month.

USAGE:
  python security/ml-security/adversarial-samples/generate_adversarial_samples.py
  
  Outputs to: security/ml-security/adversarial-samples/generated/
  Run from project root.
"""

import json
import random
import math
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict

OUTPUT_DIR = Path("security/ml-security/adversarial-samples/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# BEHAVIORAL BIOMETRICS — ADVERSARIAL KEYSTROKE SAMPLES
# ─────────────────────────────────────────────────────────────────────────────

def generate_naive_bot_keystrokes(n_events: int = 100) -> List[Dict]:
    """
    TYPE A: Naive bot — constant timing. Should score very low (easy to catch).
    Human detection rate should be ~99%.
    """
    events = []
    t = 0.0
    for _ in range(n_events):
        dwell = 50.0   # Perfectly constant — immediate flag
        flight = 30.0
        events.append({
            "code": f"Key{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}",
            "down_time": round(t, 3),
            "up_time": round(t + dwell, 3)
        })
        t += dwell + flight
    return events


def generate_randomized_bot_keystrokes(n_events: int = 100) -> List[Dict]:
    """
    TYPE B: Bot with injected uniform randomness.
    Timing in human range (80-200ms) but uniformly distributed.
    Real humans have log-normal distribution — not uniform.
    Human detection rate should be ~85-90%.
    """
    events = []
    t = 0.0
    for _ in range(n_events):
        # Bot uses uniform random — humans use log-normal
        dwell = random.uniform(80, 200)
        flight = random.uniform(50, 180)
        events.append({
            "code": f"Key{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}",
            "down_time": round(t, 3),
            "up_time": round(t + dwell, 3)
        })
        t += dwell + flight
    return events


def generate_sophisticated_bot_keystrokes(n_events: int = 100) -> List[Dict]:
    """
    TYPE C: Sophisticated bot — log-normal timing matching human statistics.
    This is the hardest evasion. Tests whether model detects deeper patterns
    (micro-tremor, error rates, cognitive load variation) beyond basic timing.
    Human detection rate should be ≥80%.
    
    Uses human statistics:
      dwell:  log-normal(mu=4.8, sigma=0.4) → mean ~130ms
      flight: log-normal(mu=4.5, sigma=0.5) → mean ~90ms
    """
    events = []
    t = 0.0
    
    # Simulate cognitive load variation (humans slow down mid-task)
    # Bot does this perfectly periodically — real humans do it irregularly
    phase = 0
    
    for i in range(n_events):
        # Log-normal timing (matches human population statistics)
        dwell = np.random.lognormal(mean=4.8, sigma=0.4)
        dwell = np.clip(dwell, 60, 400)
        
        flight = np.random.lognormal(mean=4.5, sigma=0.5)
        flight = np.clip(flight, 30, 500)
        
        # Fake "cognitive load" — perfectly sinusoidal (bot artifact)
        # Real humans: irregular, event-driven slowdowns
        load_factor = 1.0 + 0.2 * math.sin(i / 15)
        dwell *= load_factor
        flight *= load_factor
        
        # No genuine errors and corrections (key bot artifact)
        # Real humans: ~5-8% error rate with specific correction patterns
        
        events.append({
            "code": f"Key{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}",
            "down_time": round(t, 3),
            "up_time": round(t + dwell, 3)
        })
        t += dwell + flight
    
    return events


def generate_replay_attack_keystrokes(genuine_sample: List[Dict]) -> List[Dict]:
    """
    TYPE D: Replay attack — exact timing from a captured genuine human session.
    Tests whether model detects session-level consistency anomalies.
    In a real session: same exact timing used 3 times in a row.
    Human detection rate should be ~95%.
    """
    # Repeat the genuine sample 3x with small time offset
    replayed = []
    offset = 0.0
    for repetition in range(3):
        for event in genuine_sample:
            replayed.append({
                "code": event["code"],
                "down_time": round(event["down_time"] + offset, 3),
                "up_time": round(event["up_time"] + offset, 3)
            })
        if genuine_sample:
            offset += genuine_sample[-1]["up_time"] + 500  # 500ms gap between replays
    return replayed


# ─────────────────────────────────────────────────────────────────────────────
# TEXT ANALYSIS — ADVERSARIAL TEXT SAMPLES
# ─────────────────────────────────────────────────────────────────────────────

ADVERSARIAL_COVER_LETTERS = [
    # Type A: Clean AI-generated text — should detect as AI
    {
        "type": "clean_ai",
        "label": "ai",
        "expected_detection": True,
        "text": """I am writing to express my strong interest in the Software Engineer position 
        at your esteemed organization. With a proven track record of delivering high-quality 
        software solutions, I am confident that my skills and experience align perfectly with 
        your requirements. Throughout my career, I have demonstrated exceptional proficiency 
        in developing scalable applications. I am enthusiastic about the opportunity to 
        contribute to your team and leverage my expertise to drive innovation. Furthermore, 
        my strong communication skills and collaborative nature enable me to work effectively 
        with cross-functional teams to achieve organizational objectives."""
    },
    # Type B: AI text with injected typos and informal phrases — harder to detect
    {
        "type": "ai_with_imperfections",
        "label": "ai",
        "expected_detection": True,  # Model should still detect this
        "text": """hey so im really excited about this role tbh. I've been coding for like 
        5 years and stuff and I think I'd be really good at it lol. I have strong skills 
        in Python and I've built some really cool projects. Furthermore, my demonstrated 
        proficiency in leveraging cutting-edge technologies to architect robust and scalable 
        solutions has been consistently recognized throughout my career journey. I think 
        this would be a great fit and I look forward to the opportunity to discuss further 
        how my expertise aligns with your organizational objectives."""
        # Note: sudden switch to AI register is a detectable artifact
    },
    # Type C: Specific, genuine-seeming text — tests false positive rate
    {
        "type": "specific_genuine",
        "label": "human",
        "expected_detection": False,  # Should NOT detect as AI
        "text": """Last month I broke prod at 2am because I deployed a migration without 
        checking if the foreign key constraints would cascade. Lost 3 hours of sleep and 
        learned to always use --dry-run first. That's actually why I got obsessed with 
        automated testing — I wrote a migration validator that's now used across our team. 
        I noticed your job post mentions the same Postgres version we use. Is the team 
        still on Alembic or have you moved to something else? I'm asking because I hit 
        an edge case with autogenerate last quarter that took me two days to debug."""
    },
    # Type D: Generic human-sounding but actually AI-generated
    {
        "type": "generic_ai_human_style",
        "label": "ai",
        "expected_detection": True,
        "text": """I've always been passionate about technology and problem-solving. 
        Growing up, I loved taking things apart to see how they worked. This curiosity 
        led me to pursue a degree in computer science, where I discovered my love for 
        building things that matter. In my current role, I work with a great team on 
        challenging problems every day. I believe in writing clean code and communicating 
        clearly with my colleagues. I'm excited about the possibility of bringing my 
        skills and enthusiasm to your company."""
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE GENERATION AND EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def generate_all_samples(n_per_type: int = 50) -> Dict:
    """Generate complete adversarial sample set for monthly testing."""
    
    # Genuine human timing (used as baseline and for replay attack)
    def genuine_human_sample():
        events = []
        t = 0.0
        for _ in range(80):
            # Real human: log-normal with irregular cognitive load bursts
            base_dwell = np.random.lognormal(mean=4.8, sigma=0.4)
            # Random genuine slowdowns — not periodic
            if random.random() < 0.08:  # 8% chance of hesitation
                base_dwell *= random.uniform(2, 5)
            dwell = np.clip(base_dwell, 60, 800)
            flight = np.clip(np.random.lognormal(mean=4.5, sigma=0.6), 25, 600)
            # Genuine errors: ~6% rate with realistic backspace patterns
            if random.random() < 0.06:
                events.append({"code": "Backspace", "down_time": round(t, 3), "up_time": round(t + 85, 3)})
                t += 85 + 45
            events.append({
                "code": f"Key{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}",
                "down_time": round(t, 3),
                "up_time": round(t + dwell, 3)
            })
            t += dwell + flight
        return events

    sample_genuine = genuine_human_sample()

    samples = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "security/ml-security/adversarial-samples/generate_adversarial_samples.py",
        "purpose": "Monthly adversarial testing — provided by Security Engineer to ML Engineer",
        "threshold": 0.80,
        "behavioral": {
            "naive_bot": {
                "description": "Constant timing bot — should be detected ~99% of the time",
                "label": "bot",
                "expected_detection_rate": 0.99,
                "samples": [generate_naive_bot_keystrokes() for _ in range(n_per_type)]
            },
            "randomized_bot": {
                "description": "Bot with uniform random timing — should be detected ~85-90%",
                "label": "bot",
                "expected_detection_rate": 0.87,
                "samples": [generate_randomized_bot_keystrokes() for _ in range(n_per_type)]
            },
            "sophisticated_bot": {
                "description": "Log-normal timing bot — hardest evasion, must detect ≥80%",
                "label": "bot",
                "expected_detection_rate": 0.80,
                "samples": [generate_sophisticated_bot_keystrokes() for _ in range(n_per_type)]
            },
            "replay_attack": {
                "description": "Replayed genuine human session — should detect ~95%",
                "label": "bot",
                "expected_detection_rate": 0.95,
                "samples": [generate_replay_attack_keystrokes(genuine_human_sample()) for _ in range(n_per_type)]
            },
            "genuine_human_baseline": {
                "description": "Genuine human samples — false positive check, should NOT be flagged",
                "label": "human",
                "expected_false_positive_rate": 0.05,
                "samples": [genuine_human_sample() for _ in range(n_per_type)]
            }
        },
        "text": {
            "samples": ADVERSARIAL_COVER_LETTERS,
            "description": "Cover letter samples for text classifier adversarial testing"
        }
    }
    
    return samples


if __name__ == "__main__":
    print("Generating adversarial samples...")
    samples = generate_all_samples(n_per_type=50)
    
    output_file = OUTPUT_DIR / f"adversarial_samples_{datetime.now().strftime('%Y%m')}.json"
    output_file.write_text(json.dumps(samples, indent=2))
    
    print(f"\n✅ Samples generated: {output_file}")
    print(f"\nSample counts:")
    for category, data in samples["behavioral"].items():
        key = "samples" if "samples" in data else "count"
        count = len(data.get("samples", []))
        print(f"  {category}: {count} samples")
    print(f"  text: {len(samples['text']['samples'])} samples")
    print(f"\nSend this file to ML Engineer for monthly adversarial testing.")
    print(f"Expected detection rates are in each category's 'expected_detection_rate' field.")
