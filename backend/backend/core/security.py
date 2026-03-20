"""
Security-owned file. Backend reads functions here — never modifies.
Tag security engineer on any PR touching this file.
"""
import bcrypt
import secrets
import hashlib
import logging
from core.config import settings

logger = logging.getLogger(__name__)


def generate_api_key() -> tuple[str, str]:
    """Returns (plaintext, bcrypt_hash). Show plaintext once, store only hash."""
    raw = settings.API_KEY_PREFIX + secrets.token_urlsafe(32)
    hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode()
    return raw, hashed


def verify_api_key(plaintext: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode(), stored_hash.encode())
    except Exception:
        return False


def hash_for_log(api_key: str) -> str:
    """SHA-256 fingerprint for logging — never log the real key."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def make_request_log(
    session_id: str = "",
    customer_id: str = "",
    api_key_plaintext: str = "",
    path: str = "",
    ip: str = "",
    **kwargs,
) -> dict:
    """
    Use this for every inbound log line — per Security spec.
    Never log raw IPs, keys, signal arrays, or text content directly.
    """
    return {
        "session_id": session_id,
        "customer_id": customer_id,
        "api_key_fingerprint": hash_for_log(api_key_plaintext) if api_key_plaintext else "",
        "path": path,
        "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:12] if ip else "",
        **{k: v for k, v in kwargs.items() if k not in ("signal_data", "text_content", "audio", "video")},
    }
