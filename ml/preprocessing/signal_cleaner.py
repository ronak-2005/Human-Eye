"""
Signal Cleaner — Preprocessing for all incoming raw signals.

Cleans, validates, and normalizes raw behavioral data before it reaches detectors.
Bad data in → bad scores out. This is the first line of defense.

Handles:
- Timestamp normalization (relative, not absolute)
- Outlier filtering (tab-away events, extreme values)
- Sequence deduplication
- Minimum quality checks
"""

import logging
from typing import List, Optional
from ...api.schemas import KeystrokeEvent, MouseEvent, ScrollEvent

logger = logging.getLogger(__name__)


class SignalCleaner:
    """
    Preprocesses raw signals before they reach detector models.
    All methods return cleaned lists; empty list = signal unusable.
    """

    # ─── Keystroke cleaning ──────────────────────────────────────────────────

    MAX_DWELL_MS = 2000       # Longer than this = user tabbed away, not a real keypress
    MIN_DWELL_MS = 1          # Shorter than this = hardware artifact
    MAX_FLIGHT_MS = 5000      # Gap this large = user paused thinking, not a digraph

    def clean_keystrokes(self, events: List[KeystrokeEvent]) -> List[KeystrokeEvent]:
        if not events:
            return []

        cleaned = []
        for ev in events:
            dwell = ev.keyup_time - ev.keydown_time
            if self.MIN_DWELL_MS <= dwell <= self.MAX_DWELL_MS:
                cleaned.append(ev)
            else:
                logger.debug(f"Dropped keystroke: dwell={dwell:.1f}ms key={ev.key}")

        # Sort by timestamp (browser events can arrive out of order)
        cleaned.sort(key=lambda e: e.keydown_time)

        # Deduplicate exact duplicates (double-fire events)
        deduped = []
        seen = set()
        for ev in cleaned:
            key = (ev.key, round(ev.keydown_time, 1))
            if key not in seen:
                seen.add(key)
                deduped.append(ev)

        # Normalize timestamps to be relative to first event
        if deduped:
            t0 = deduped[0].keydown_time
            deduped = [
                KeystrokeEvent(
                    key=ev.key,
                    keydown_time=round(ev.keydown_time - t0, 3),
                    keyup_time=round(ev.keyup_time - t0, 3),
                )
                for ev in deduped
            ]

        logger.debug(f"Keystrokes: {len(events)} raw → {len(deduped)} clean")
        return deduped

    # ─── Mouse cleaning ──────────────────────────────────────────────────────

    MAX_COORDINATE = 10000    # Unlikely screen coordinate; hardware artifact
    MAX_VELOCITY = 10000      # px/ms — physically impossible
    MOUSE_SAMPLE_RATE_MS = 20 # 50Hz max sampling

    def clean_mouse_events(self, events: List[MouseEvent]) -> List[MouseEvent]:
        if not events:
            return []

        # Filter impossible coordinates
        cleaned = [
            ev for ev in events
            if 0 <= ev.x <= self.MAX_COORDINATE and 0 <= ev.y <= self.MAX_COORDINATE
        ]

        # Sort by timestamp
        cleaned.sort(key=lambda e: e.timestamp)

        # Downsample move events to 50Hz (SDK should enforce this, but double-check)
        downsampled = self._downsample_moves(cleaned)

        # Normalize timestamps
        if downsampled:
            t0 = downsampled[0].timestamp
            downsampled = [
                MouseEvent(
                    x=ev.x, y=ev.y,
                    timestamp=round(ev.timestamp - t0, 3),
                    event_type=ev.event_type,
                    button=ev.button,
                )
                for ev in downsampled
            ]

        logger.debug(f"Mouse: {len(events)} raw → {len(downsampled)} clean")
        return downsampled

    def _downsample_moves(self, events: List[MouseEvent]) -> List[MouseEvent]:
        """Keep clicks always; downsample moves to max 50Hz."""
        result = []
        last_move_ts = -999
        for ev in events:
            if ev.event_type != "move":
                result.append(ev)
            elif ev.timestamp - last_move_ts >= self.MOUSE_SAMPLE_RATE_MS:
                result.append(ev)
                last_move_ts = ev.timestamp
        return result

    # ─── Scroll cleaning ─────────────────────────────────────────────────────

    MAX_SCROLL_VELOCITY = 10000  # px/ms — physically impossible

    def clean_scroll_events(self, events: List[ScrollEvent]) -> List[ScrollEvent]:
        if not events:
            return []

        cleaned = [
            ev for ev in events
            if abs(ev.velocity) <= self.MAX_SCROLL_VELOCITY and ev.scroll_y >= 0
        ]

        cleaned.sort(key=lambda e: e.timestamp)

        # Normalize timestamps
        if cleaned:
            t0 = cleaned[0].timestamp
            cleaned = [
                ScrollEvent(
                    scroll_y=ev.scroll_y,
                    timestamp=round(ev.timestamp - t0, 3),
                    direction=ev.direction,
                    velocity=ev.velocity,
                )
                for ev in cleaned
            ]

        logger.debug(f"Scroll: {len(events)} raw → {len(cleaned)} clean")
        return cleaned

    # ─── Text cleaning ───────────────────────────────────────────────────────

    def clean_text(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        # Strip excessive whitespace, normalize line endings
        lines = text.splitlines()
        lines = [line.strip() for line in lines]
        cleaned = "\n".join(line for line in lines if line)
        return cleaned if len(cleaned) >= 20 else None
