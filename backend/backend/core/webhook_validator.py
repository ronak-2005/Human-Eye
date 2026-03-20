"""Security-owned. Call validate_webhook_url(url) before storing any webhook URL."""
from urllib.parse import urlparse
from core.errors import bad_request

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal",
                 "169.254.169.254"}


def validate_webhook_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        bad_request("Webhook URL must use HTTPS", "WEBHOOK_NOT_HTTPS")
    host = parsed.hostname or ""
    if host in BLOCKED_HOSTS or host.endswith(".internal") or host.endswith(".local"):
        bad_request("Webhook URL points to a blocked host", "WEBHOOK_BLOCKED_HOST")
    return url
