"""
ML Engine Test Suite
Tests every detector and the fusion engine.
Run: pytest ml_engine/tests/ -v

Uses synthetic data — no external dependencies needed.
"""

import pytest
from ..detectors.behavioral.keystroke_model import KeystrokeModel
from ..detectors.behavioral.mouse_model import MouseModel
from ..detectors.behavioral.scroll_model import ScrollModel
from ..detectors.text.vocabulary_analyzer import VocabularyAnalyzer
from ..detectors.text.resume_scorer import ResumeScorer
from ..detectors.text.content_classifier import ContentClassifier
from ..fusion.score_combiner import ScoreCombiner
from ..preprocessing.signal_cleaner import SignalCleaner
from ..api.schemas import (
    KeystrokeEvent, MouseEvent, ScrollEvent, RequestContext
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def human_keystrokes():
    """Realistic human keystroke sequence."""
    import random
    random.seed(42)
    events = []
    t = 0.0
    for i in range(120):
        dwell = abs(random.gauss(95, 30))
        flight = abs(random.gauss(90, 35))
        key = f"Key{random.choice('ABCDEFGHIJ')}"
        if i > 10 and random.random() < 0.05:
            events.append(KeystrokeEvent(key="Backspace", keydown_time=t, keyup_time=t + 80))
            t += 70
        events.append(KeystrokeEvent(key=key, keydown_time=t, keyup_time=t + dwell))
        t += flight + dwell
    return events


@pytest.fixture
def bot_keystrokes():
    """Bot keystroke sequence — unnaturally constant timing."""
    events = []
    t = 0.0
    for i in range(120):
        events.append(KeystrokeEvent(
            key=f"Key{chr(65 + i % 26)}",
            keydown_time=round(t, 3),
            keyup_time=round(t + 50.0, 3),  # Perfectly constant 50ms
        ))
        t += 130.0  # Perfectly constant 130ms flight time
    return events


@pytest.fixture
def human_mouse():
    import random
    random.seed(42)
    events = []
    x, y, t = 400.0, 300.0, 0.0
    for i in range(150):
        x += random.gauss(0, 12) + random.gauss(0, 2)
        y += random.gauss(0, 8) + random.gauss(0, 2)
        x = max(0, min(1920, x))
        y = max(0, min(1080, y))
        events.append(MouseEvent(x=x, y=y, timestamp=t, event_type="move"))
        t += abs(random.gauss(20, 8))
        if i > 30 and i % 60 == 0:
            events.append(MouseEvent(x=x, y=y, timestamp=t, event_type="click", button=0))
    return events


@pytest.fixture
def bot_mouse():
    """Bot mouse — perfectly linear, constant velocity."""
    events = []
    t = 0.0
    for i in range(150):
        events.append(MouseEvent(
            x=float(100 + i * 5),
            y=float(100 + i * 3),
            timestamp=t,
            event_type="move",
        ))
        t += 20.0
    events.append(MouseEvent(x=850.0, y=550.0, timestamp=t, event_type="click", button=0))
    return events


@pytest.fixture
def human_scroll():
    import random
    random.seed(42)
    events = []
    pos, t = 0.0, 0.0
    for i in range(80):
        if random.random() < 0.12:
            delta = -random.uniform(50, 200)  # Backscroll
        else:
            delta = random.uniform(100, 400)
        vel = delta / max(random.gauss(150, 40), 10)
        pos += delta
        events.append(ScrollEvent(
            scroll_y=max(0, pos),
            timestamp=t,
            direction="down" if delta > 0 else "up",
            velocity=abs(vel),
        ))
        t += abs(random.gauss(200, 100))
        if random.random() < 0.15:
            t += random.uniform(600, 2000)  # Reading pause
    return events


@pytest.fixture
def bot_scroll():
    """Bot scroll — linear, constant velocity, no backscroll."""
    events = []
    t = 0.0
    for i in range(80):
        events.append(ScrollEvent(
            scroll_y=float(i * 100),
            timestamp=t,
            direction="down",
            velocity=5.0,  # Perfectly constant
        ))
        t += 100.0  # Perfectly constant intervals
    return events


HUMAN_TEXT = """
I remember the day I pushed my first real feature to production. It was March 2022 and
I'd spent three weeks debugging a race condition in our Redis cache that was causing
about 2% of users to see stale data. When I finally found it — a missing WATCH command
in a transaction — I literally called my teammate over to show him.

Since then I've shipped features used by our 40,000 daily active users, but that
debugging experience taught me more than anything. I don't just write code that works,
I write code I can reason about at 2am when it breaks.

I'd love to bring this to your team because I saw in your job post that you're dealing
with similar distributed systems challenges at a much larger scale. I've read about your
migration from PostgreSQL to CockroachDB and I have a lot of questions about how you
handled the transaction semantics.
"""

AI_TEXT = """
I am excited to apply for this software engineering position at your esteemed organization.
With my extensive experience in software development and my strong technical background,
I am confident that I would be an excellent addition to your team.

Furthermore, I possess exceptional problem-solving abilities and demonstrate strong
leadership qualities that would contribute meaningfully to your organization's objectives.
My proven track record of delivering results in fast-paced environments aligns perfectly
with your company's innovative culture.

Additionally, I am a highly motivated self-starter with outstanding communication skills.
I leverage cutting-edge technologies to drive synergistic outcomes and exceed expectations
consistently. In conclusion, I believe my skills and experience align perfectly with this
opportunity, and I am eager to contribute to your continued success.
"""


# ─── Keystroke Tests ─────────────────────────────────────────────────────────

class TestKeystrokeModel:
    def setup_method(self):
        self.model = KeystrokeModel()

    def test_human_scores_above_threshold(self, human_keystrokes):
        result = self.model.predict(human_keystrokes)
        assert result.score > 0.5, f"Human keystroke scored {result.score}, expected > 0.5"

    def test_bot_scores_below_threshold(self, bot_keystrokes):
        result = self.model.predict(bot_keystrokes)
        assert result.score < 0.5, f"Bot keystroke scored {result.score}, expected < 0.5"

    def test_insufficient_data_returns_neutral(self):
        result = self.model.predict([KeystrokeEvent(key="KeyA", keydown_time=0, keyup_time=80)])
        assert result.score == 0.5
        assert "insufficient_keystroke_data" in result.flags

    def test_bot_generates_flags(self, bot_keystrokes):
        result = self.model.predict(bot_keystrokes)
        assert len(result.flags) > 0

    def test_result_score_in_valid_range(self, human_keystrokes):
        result = self.model.predict(human_keystrokes)
        assert 0.0 <= result.score <= 1.0
        assert 0.0 <= result.confidence <= 1.0


# ─── Mouse Tests ─────────────────────────────────────────────────────────────

class TestMouseModel:
    def setup_method(self):
        self.model = MouseModel()

    def test_human_scores_above_threshold(self, human_mouse):
        result = self.model.predict(human_mouse)
        assert result.score > 0.5, f"Human mouse scored {result.score}"

    def test_bot_scores_below_threshold(self, bot_mouse):
        result = self.model.predict(bot_mouse)
        assert result.score < 0.5, f"Bot mouse scored {result.score}"

    def test_bot_flags_linear_paths(self, bot_mouse):
        result = self.model.predict(bot_mouse)
        assert any("linear" in f or "velocity" in f or "tremor" in f for f in result.flags)


# ─── Scroll Tests ─────────────────────────────────────────────────────────────

class TestScrollModel:
    def setup_method(self):
        self.model = ScrollModel()

    def test_human_scores_above_threshold(self, human_scroll):
        result = self.model.predict(human_scroll)
        assert result.score > 0.5, f"Human scroll scored {result.score}"

    def test_bot_scores_below_threshold(self, bot_scroll):
        result = self.model.predict(bot_scroll)
        assert result.score < 0.5, f"Bot scroll scored {result.score}"


# ─── Vocabulary Tests ─────────────────────────────────────────────────────────

class TestVocabularyAnalyzer:
    def setup_method(self):
        self.model = VocabularyAnalyzer()

    def test_human_text_scores_higher(self):
        human_result = self.model.analyze(HUMAN_TEXT)
        ai_result = self.model.analyze(AI_TEXT)
        assert human_result.score > ai_result.score, (
            f"Human text ({human_result.score}) should score higher than AI text ({ai_result.score})"
        )

    def test_ai_text_generates_transition_flag(self):
        result = self.model.analyze(AI_TEXT)
        assert "text_ai_transition_phrases_detected" in result.flags

    def test_short_text_returns_neutral(self):
        result = self.model.analyze("Short text.")
        assert result.score == 0.5
        assert "insufficient_text_length" in result.flags


# ─── Resume Scorer Tests ──────────────────────────────────────────────────────

class TestResumeScorer:
    def setup_method(self):
        self.model = ResumeScorer()

    def test_human_resume_scores_higher(self):
        human_result = self.model.score(HUMAN_TEXT)
        ai_result = self.model.score(AI_TEXT)
        assert human_result.score > ai_result.score

    def test_ai_resume_flags_buzzwords(self):
        result = self.model.score(AI_TEXT)
        assert "resume_high_buzzword_density" in result.flags or result.score < 0.5


# ─── Fusion Engine Tests ──────────────────────────────────────────────────────

class TestScoreCombiner:
    def setup_method(self):
        self.combiner = ScoreCombiner()
        self.context = RequestContext(action_type="job_application", platform_user_id="test123")

    def test_all_high_scores_produce_high_hts(self):
        scores = {"keystroke": 0.9, "mouse": 0.85, "resume": 0.88, "vocabulary": 0.82}
        result = self.combiner.combine(scores, self.context, [])
        assert result.human_trust_score >= 80
        assert result.verdict == "human"

    def test_all_low_scores_produce_low_hts(self):
        scores = {"keystroke": 0.1, "mouse": 0.15, "resume": 0.12, "vocabulary": 0.18}
        result = self.combiner.combine(scores, self.context, [])
        assert result.human_trust_score < 30
        assert result.verdict in ("bot", "suspicious")

    def test_conflict_detection(self):
        # High behavioral (human typing) + low text (AI content)
        scores = {"keystroke": 0.90, "mouse": 0.85, "resume": 0.15, "vocabulary": 0.12}
        result = self.combiner.combine(scores, self.context, [])
        assert result.conflict_detected
        assert "signal_conflict_detected" in self.combiner.combine(scores, self.context, []).signal_weights_used or result.conflict_detected

    def test_context_adjusts_weights_for_job_application(self):
        scores = {"keystroke": 0.5, "resume": 0.9, "vocabulary": 0.88}
        result = self.combiner.combine(scores, self.context, [])
        # Text signals should dominate for job_application context
        assert result.human_trust_score > 60

    def test_empty_scores_raises_error(self):
        with pytest.raises(ValueError):
            self.combiner.combine({}, self.context, [])

    def test_hts_always_in_valid_range(self):
        for score_val in [0.0, 0.25, 0.5, 0.75, 1.0]:
            scores = {"keystroke": score_val}
            result = self.combiner.combine(scores, self.context, [])
            assert 0 <= result.human_trust_score <= 100


# ─── Signal Cleaner Tests ─────────────────────────────────────────────────────

class TestSignalCleaner:
    def setup_method(self):
        self.cleaner = SignalCleaner()

    def test_filters_extreme_dwell_times(self):
        events = [
            KeystrokeEvent(key="KeyA", keydown_time=0, keyup_time=80),      # Normal
            KeystrokeEvent(key="KeyB", keydown_time=100, keyup_time=5000),   # Tab-away
            KeystrokeEvent(key="KeyC", keydown_time=5100, keyup_time=5180),  # Normal
        ]
        cleaned = self.cleaner.clean_keystrokes(events)
        assert len(cleaned) == 2
        assert all(ev.key != "KeyB" for ev in cleaned)

    def test_normalizes_timestamps_to_zero(self):
        events = [
            KeystrokeEvent(key="KeyA", keydown_time=1000, keyup_time=1080),
            KeystrokeEvent(key="KeyB", keydown_time=1200, keyup_time=1280),
        ]
        cleaned = self.cleaner.clean_keystrokes(events)
        assert cleaned[0].keydown_time == 0.0

    def test_empty_input_returns_empty(self):
        assert self.cleaner.clean_keystrokes([]) == []
        assert self.cleaner.clean_mouse_events([]) == []
        assert self.cleaner.clean_scroll_events([]) == []
