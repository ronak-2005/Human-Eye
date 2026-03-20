"""
HumanEye — Verification Service
Orchestrates the full pipeline:
  1. Create pending record
  2. Call ML engine (Phase 1: behavioral+text, Phase 2: face+voice)
  3. Compute final human_trust_score
  4. Persist result
  5. Upsert persistent trust score
  6. Enqueue webhook
"""
import time
import logging
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.verification import Verification, VerificationStatus
from models.score import Score
from models.webhook import WebhookEndpoint
from services.ml_client import MLClient
from schemas import VerifyRequest, VerifyResponse

logger = logging.getLogger(__name__)

HIGH_STAKES_ACTIONS = {"financial_transaction", "hiring", "legal", "medical", "voting"}


# ── Score → verdict ──────────────────────────────────────────────────────────

def score_to_verdict(score: int | None) -> tuple[str, str]:
    if score is None:
        return "unavailable", "none"
    if score >= 80: return "human",        "high"
    if score >= 65: return "likely_human", "high"
    if score >= 50: return "uncertain",    "medium"
    if score >= 25: return "suspicious",   "medium"
    return "synthetic", "high"


def float_to_score(v: float | None) -> int | None:
    if v is None:
        return None
    return max(0, min(100, int(round(v * 100))))


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_verification(
    request: VerifyRequest,
    customer_id: UUID,
    api_key_id: UUID,
    db: AsyncSession,
    ml: MLClient,
) -> VerifyResponse:
    start_ms = time.time() * 1000

    # ── Step 1: create pending record ────────────────────────────────────────
    verification = Verification(
        session_id=request.session_id,
        user_id=customer_id,
        api_key_id=api_key_id,
        action_type=request.context.action_type,
        platform_user_id=request.context.platform_user_id,
        ip_address=request.context.ip_address,
        user_agent=request.context.user_agent,
        status="pending",
    )
    db.add(verification)
    await db.flush()

    try:
        # ── Step 2a: Phase 1 — behavioral + text ─────────────────────────────
        signals_dict = {
            "keystrokes":   [k.dict() for k in (request.signals.keystrokes or [])],
            "mouse_events": [m.dict() for m in (request.signals.mouse_events or [])],
            "scroll_events":[s.dict() for s in (request.signals.scroll_events or [])],
            "text_content": request.signals.text_content,
        }
        context_dict = {
            "action_type":         request.context.action_type,
            "platform_user_id":    request.context.platform_user_id,
            "ip_address":          request.context.ip_address,
            "user_agent":          request.context.user_agent,
            "session_duration_ms": request.context.session_duration_ms,
        }

        ml_result = await ml.analyze(request.session_id, signals_dict, context_dict)

        flags            = list(ml_result.get("flags", []))
        signals_analyzed = list(ml_result.get("signals_analyzed", []))

        # human_trust_score from ML (0-100 int) or fallback from combined_score
        trust_score: int | None = ml_result.get("human_trust_score")
        if trust_score is None and ml_result.get("combined_score") is not None:
            trust_score = float_to_score(ml_result["combined_score"])

        # ── Step 2b: Phase 2 — face (if video present) ───────────────────────
        liveness_score       = None
        deepfake_probability = None

        if request.signals.video_frame_data:
            face_result = await ml.analyze_face(
                session_id=request.session_id,
                video_frames=request.signals.video_frame_data,
                context=context_dict,
            )
            liveness_score       = face_result.get("liveness_score")
            deepfake_probability = face_result.get("deepfake_probability")
            face_flags           = face_result.get("flags", [])
            flags.extend(face_flags)
            signals_analyzed.append("face")

            # High deepfake probability overrides behavioral score
            if deepfake_probability and deepfake_probability > 0.7:
                flags.append("deepfake_high_probability")
                trust_score = min(trust_score or 100, 20)

        # ── Step 2c: Phase 2 — voice (if audio present) ──────────────────────
        clone_probability = None

        if request.signals.audio_data:
            voice_result = await ml.analyze_voice(
                session_id=request.session_id,
                audio_data=request.signals.audio_data,
                context=context_dict,
            )
            clone_probability = voice_result.get("clone_probability")
            voice_flags       = voice_result.get("flags", [])
            flags.extend(voice_flags)
            signals_analyzed.append("voice")

            if clone_probability and clone_probability > 0.7:
                flags.append("voice_clone_high_probability")
                trust_score = min(trust_score or 100, 20)

        # ── Step 3: verdict ───────────────────────────────────────────────────
        verdict, confidence = score_to_verdict(trust_score)
        elapsed = int(time.time() * 1000 - start_ms)

        # High-stakes unavailable — flag for manual review
        if verdict == "unavailable" and request.context.action_type in HIGH_STAKES_ACTIONS:
            flags.append("manual_review_required_high_stakes_unavailable")

        # ── Step 4: persist ───────────────────────────────────────────────────
        verification.human_trust_score   = trust_score
        verification.combined_score      = str(ml_result.get("combined_score", ""))
        verification.behavioral_score    = str(ml_result.get("behavioral_score", ""))
        verification.text_score          = str(ml_result.get("text_score", ""))
        verification.liveness_score      = str(liveness_score) if liveness_score is not None else None
        verification.deepfake_probability= str(deepfake_probability) if deepfake_probability is not None else None
        verification.clone_probability   = str(clone_probability) if clone_probability is not None else None
        verification.verdict             = verdict
        verification.confidence          = confidence
        verification.flags               = flags
        verification.signals_analyzed    = signals_analyzed
        verification.status              = "complete" if verdict != "unavailable" else "unavailable"
        verification.processing_time_ms  = elapsed
        verification.completed_at        = datetime.utcnow()

        # ── Step 5: upsert trust score (skip if unavailable) ─────────────────
        if trust_score is not None:
            await _upsert_score(db, customer_id, request.context.platform_user_id, trust_score)

        await db.commit()
        await db.refresh(verification)

        # ── Step 6: async webhook ─────────────────────────────────────────────
        await _trigger_webhooks(db, customer_id, verification)

        logger.info(
            "verification_complete",
            extra={
                "verification_id": str(verification.id),
                "score": trust_score,
                "verdict": verdict,
                "elapsed_ms": elapsed,
                "action_type": request.context.action_type,
            },
        )

        return VerifyResponse(
            verification_id=str(verification.id),
            human_trust_score=trust_score,
            verdict=verdict,
            confidence=confidence,
            flags=flags,
            processing_time_ms=elapsed,
            signals_analyzed=signals_analyzed,
            liveness_score=liveness_score,
            deepfake_probability=deepfake_probability,
            clone_probability=clone_probability,
        )

    except Exception as e:
        verification.status = "failed"
        await db.commit()
        logger.exception("verification_failed id=%s: %s", verification.id, e)
        raise


# ── Score upsert ──────────────────────────────────────────────────────────────

async def _upsert_score(db, user_id, platform_user_id, new_score: int):
    """Exponential moving average: 70% old + 30% new."""
    result = await db.execute(
        select(Score).where(
            Score.user_id == user_id,
            Score.platform_user_id == platform_user_id,
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.current_score      = round(0.7 * record.current_score + 0.3 * new_score, 2)
        record.verification_count += 1
        record.last_verified_at   = datetime.utcnow()
    else:
        db.add(Score(
            user_id=user_id,
            platform_user_id=platform_user_id,
            current_score=float(new_score),
            verification_count=1,
            last_verified_at=datetime.utcnow(),
        ))


# ── Webhook trigger ───────────────────────────────────────────────────────────

async def _trigger_webhooks(db, user_id, verification: Verification):
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.user_id == user_id,
            WebhookEndpoint.is_active == True,  # noqa: E712
        )
    )
    for endpoint in result.scalars().all():
        from tasks.webhook_tasks import deliver_webhook
        deliver_webhook.delay(
            verification_id=str(verification.id),
            customer_url=endpoint.url,
            secret=endpoint.secret,
            payload={
                "event":             "verification.complete",
                "verification_id":   str(verification.id),
                "human_trust_score": verification.human_trust_score,
                "verdict":           verification.verdict,
                "confidence":        verification.confidence,
                "flags":             verification.flags,
                "platform_user_id":  verification.platform_user_id,
                "timestamp":         datetime.utcnow().isoformat(),
            },
        )
