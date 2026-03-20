"""
HumanEye Backend — ML Engine Client
The ONLY file in the backend that talks to the ML engine.
No other backend file imports or calls ML directly.

ML engine runs on: http://ml_engine:8001  (docker-compose)
                   http://ml-engine.humaneye.local:8001  (ECS)
Never exposed to the internet — backend is the only caller.
"""

import logging
import os
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

ML_ENGINE_URL = os.environ.get("ML_ENGINE_URL", "http://ml_engine:8001")
ML_TIMEOUT_MS = int(os.environ.get("ML_TIMEOUT_MS", "5000"))


class MLClient:

    def __init__(self):
        self._base    = ML_ENGINE_URL.rstrip("/")
        self._timeout = ML_TIMEOUT_MS / 1000   # httpx takes seconds

    # ── Phase 1: behavioral + text ────────────────────────────────────────────

    async def analyze(self, session_id: str, signals: dict, context: dict) -> dict:
        """
        Returns:
            human_trust_score  int     0-100
            combined_score     float   0.0-1.0
            behavioral_score   float   0.0-1.0  (None if no behavioral signals)
            text_score         float   0.0-1.0  (None if no text)
            flags              list
            signal_scores      dict
            confidence         str    "high"|"medium"|"low"
            processing_time_ms float

        Timestamps in signals must be RELATIVE to session start in ms.
        Normalize before calling:
            session_start = signals["keystrokes"][0]["keydown_time"]
            for e in signals["keystrokes"]:
                e["keydown_time"] -= session_start
                e["keyup_time"]   -= session_start
        """
        # Normalize timestamps
        signals = _normalize_timestamps(signals)

        payload = {"session_id": session_id, "signals": signals, "context": context}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base}/analyze", json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            logger.error("ML engine timeout session=%s", session_id)
            return self._unavailable_fallback("timeout")
        except httpx.HTTPStatusError as e:
            logger.error("ML engine HTTP %s session=%s", e.response.status_code, session_id)
            return self._unavailable_fallback(f"http_{e.response.status_code}")
        except Exception as e:
            logger.error("ML engine error session=%s: %s", session_id, e)
            return self._unavailable_fallback("connection_error")

    # ── Phase 2: face liveness ────────────────────────────────────────────────

    async def analyze_face(
        self,
        session_id: str,
        video_frames: list,    # list of base64 JPEG strings, min 90 frames
        context: dict,
        frame_rate: float = 30.0,
    ) -> dict:
        """
        Returns:
            liveness_score       float  0.0-1.0
            deepfake_probability float  0.0-1.0
            skin_physics_pass    bool   (None until Phase 2)
            rppg_bpm             float  (None until Phase 2)
            asymmetry_score      float  (None until Phase 2)
            flags                list
            phase                str
        """
        payload = {
            "session_id": session_id,
            "video_frames": video_frames,
            "frame_rate": frame_rate,
            "context": context,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base}/analyze/face", json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("ML face error session=%s: %s", session_id, e)
            return {
                "liveness_score": 0.5,
                "deepfake_probability": 0.0,
                "skin_physics_pass": None,
                "flags": ["face_analysis_unavailable"],
                "phase": "unavailable",
            }

    # ── Phase 2: voice forensics ──────────────────────────────────────────────

    async def analyze_voice(
        self,
        session_id: str,
        audio_data: str,       # base64 WAV, 16kHz mono, min 3 seconds
        context: dict,
        sample_rate: int = 16000,
    ) -> dict:
        """
        Returns:
            clone_probability  float  0.0-1.0
            jitter_score       float  (None until Phase 2)
            shimmer_score      float  (None until Phase 2)
            breathing_natural  bool   (None until Phase 2)
            flags              list
            phase              str
        """
        payload = {
            "session_id": session_id,
            "audio_data": audio_data,
            "sample_rate": sample_rate,
            "context": context,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base}/analyze/voice", json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("ML voice error session=%s: %s", session_id, e)
            return {
                "clone_probability": 0.0,
                "jitter_score": None,
                "shimmer_score": None,
                "breathing_natural": None,
                "flags": ["voice_analysis_unavailable"],
                "phase": "unavailable",
            }

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self) -> dict:
        """
        Returns full health payload. Key fields:
            status        "ok"|"degraded"|"starting"
            phase1_ready  bool  — check before sending requests
            phase2_ready  bool  — check before sending face/voice
        """
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base}/health")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("ML health check failed: %s", e)
            return {"status": "unavailable", "phase1_ready": False, "phase2_ready": False}

    async def is_ready(self) -> bool:
        health = await self.health()
        return health.get("phase1_ready", False)

    # ── Fallback ──────────────────────────────────────────────────────────────

    def _unavailable_fallback(self, reason: str) -> dict:
        """
        ML engine unreachable. Backend returns score=None with verdict="unavailable".
        Do NOT block the customer — flag for manual review on high-stakes action_types.
        """
        return {
            "human_trust_score": None,
            "combined_score": None,
            "behavioral_score": None,
            "text_score": None,
            "flags": [f"ml_engine_{reason}"],
            "confidence": "none",
            "verdict": "unavailable",
            "processing_time_ms": 0,
        }


# ── Timestamp normalization ───────────────────────────────────────────────────

def _normalize_timestamps(signals: dict) -> dict:
    """
    All timestamps must be RELATIVE to session start in ms.
    SDK sends absolute performance.now() — normalize here.
    """
    import copy
    s = copy.deepcopy(signals)

    keystrokes = s.get("keystrokes") or []
    if keystrokes:
        t0 = keystrokes[0].get("keydown_time", 0)
        for e in keystrokes:
            e["keydown_time"] = round(e.get("keydown_time", t0) - t0, 3)
            e["keyup_time"]   = round(e.get("keyup_time",   t0) - t0, 3)

    mouse = s.get("mouse_events") or []
    if mouse:
        t0 = mouse[0].get("timestamp", 0)
        for e in mouse:
            e["timestamp"] = round(e.get("timestamp", t0) - t0, 3)

    scroll = s.get("scroll_events") or []
    if scroll:
        t0 = scroll[0].get("timestamp", 0)
        for e in scroll:
            e["timestamp"] = round(e.get("timestamp", t0) - t0, 3)

    return s


# ── Singleton ─────────────────────────────────────────────────────────────────

_ml_client: Optional[MLClient] = None


def get_ml_client() -> MLClient:
    """FastAPI dependency — returns shared MLClient instance."""
    global _ml_client
    if _ml_client is None:
        _ml_client = MLClient()
    return _ml_client
