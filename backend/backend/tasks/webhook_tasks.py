"""
Webhook delivery — idempotent per DevOps spec.
Celery retries 3× with exponential backoff.
Duplicate deliveries are safe — customer must deduplicate on verification_id.
"""
import hmac
import hashlib
import json
import httpx
import logging
from datetime import datetime
from core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _sign(payload: str, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.webhook_tasks.deliver_webhook",
)
def deliver_webhook(self, verification_id: str, customer_url: str, secret: str | None, payload: dict):
    """
    POST verification result to customer URL.
    Signs with HMAC-SHA256 if secret provided.
    Header: X-HumanEye-Signature: sha256=<hex>
    Idempotent — verification_id in payload allows customer deduplication.
    """
    body = json.dumps(payload, default=str)
    headers = {
        "Content-Type": "application/json",
        "X-HumanEye-Verification-Id": verification_id,
    }
    if secret:
        headers["X-HumanEye-Signature"] = _sign(body, secret)

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(customer_url, content=body, headers=headers)

        logger.info(
            "webhook_delivered",
            extra={"verification_id": verification_id, "url": customer_url, "status": resp.status_code},
        )

        if not resp.is_success:
            raise Exception(f"Webhook returned {resp.status_code}")

    except Exception as exc:
        logger.warning(
            "webhook_failed attempt=%s verification_id=%s: %s",
            self.request.retries + 1, verification_id, exc,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
