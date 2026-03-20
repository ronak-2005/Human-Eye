"""
HumanEye — Backend Test Suite
Run: pytest tests/ -v --cov=. --cov-report=term-missing
"""
import pytest
from unittest.mock import patch, AsyncMock


# ── Verification service ──────────────────────────────────────────────────────

class TestScoreToVerdict:
    def test_80_plus_is_human(self):
        from services.verification_service import score_to_verdict
        assert score_to_verdict(100) == ("human", "high")
        assert score_to_verdict(80)  == ("human", "high")

    def test_65_to_79_likely_human(self):
        from services.verification_service import score_to_verdict
        verdict, conf = score_to_verdict(72)
        assert verdict == "likely_human" and conf == "high"

    def test_50_to_64_uncertain(self):
        from services.verification_service import score_to_verdict
        verdict, conf = score_to_verdict(55)
        assert verdict == "uncertain" and conf == "medium"

    def test_25_to_49_suspicious(self):
        from services.verification_service import score_to_verdict
        verdict, _ = score_to_verdict(30)
        assert verdict == "suspicious"

    def test_under_25_synthetic(self):
        from services.verification_service import score_to_verdict
        assert score_to_verdict(10) == ("synthetic", "high")

    def test_none_is_unavailable(self):
        from services.verification_service import score_to_verdict
        assert score_to_verdict(None) == ("unavailable", "none")


class TestFloatToScore:
    def test_1_0_is_100(self):
        from services.verification_service import float_to_score
        assert float_to_score(1.0) == 100

    def test_0_0_is_0(self):
        from services.verification_service import float_to_score
        assert float_to_score(0.0) == 0

    def test_clamps_above_100(self):
        from services.verification_service import float_to_score
        assert float_to_score(1.5) == 100

    def test_none_stays_none(self):
        from services.verification_service import float_to_score
        assert float_to_score(None) is None


# ── Security ──────────────────────────────────────────────────────────────────

class TestSecurity:
    def test_key_has_prefix(self):
        from core.security import generate_api_key
        plaintext, _ = generate_api_key()
        assert plaintext.startswith("he_")

    def test_verify_correct_key(self):
        from core.security import generate_api_key, verify_api_key
        plaintext, hashed = generate_api_key()
        assert verify_api_key(plaintext, hashed) is True

    def test_verify_wrong_key(self):
        from core.security import generate_api_key, verify_api_key
        _, hashed = generate_api_key()
        assert verify_api_key("wrong", hashed) is False

    def test_log_hash_not_plaintext(self):
        from core.security import generate_api_key, hash_for_log
        plaintext, _ = generate_api_key()
        assert hash_for_log(plaintext) != plaintext
        assert len(hash_for_log(plaintext)) == 16

    def test_bearer_extraction(self):
        from core.security import extract_bearer_token
        assert extract_bearer_token("Bearer he_abc") == "he_abc"
        assert extract_bearer_token(None) is None
        assert extract_bearer_token("Token abc") is None
        assert extract_bearer_token("he_abc") is None

    def test_make_request_log_no_sensitive(self):
        from core.security import make_request_log
        log = make_request_log(
            session_id="s1",
            customer_id="c1",
            api_key_plaintext="he_secret123",
            signal_data={"keystrokes": [1, 2, 3]},  # should be stripped
        )
        assert "signal_data" not in log
        assert "he_secret123" not in str(log)


# ── ML client ─────────────────────────────────────────────────────────────────

class TestMLClient:
    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        import httpx
        from services.ml_client import MLClient
        client = MLClient()
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("t")):
            result = await client.analyze("s1", {}, {})
        assert result["human_trust_score"] is None
        assert result["verdict"] == "unavailable"
        assert any("timeout" in f for f in result["flags"])

    @pytest.mark.asyncio
    async def test_health_when_unreachable(self):
        from services.ml_client import MLClient
        client = MLClient()
        with patch("httpx.AsyncClient.get", side_effect=Exception("refused")):
            result = await client.health()
        assert result["status"] == "unavailable"
        assert result["phase1_ready"] is False


class TestTimestampNormalization:
    def test_normalizes_to_relative(self):
        from services.ml_client import _normalize_timestamps
        signals = {
            "keystrokes": [
                {"key": "a", "keydown_time": 1000.0, "keyup_time": 1050.0},
                {"key": "b", "keydown_time": 1200.0, "keyup_time": 1250.0},
            ]
        }
        result = _normalize_timestamps(signals)
        assert result["keystrokes"][0]["keydown_time"] == 0.0
        assert result["keystrokes"][1]["keydown_time"] == 200.0

    def test_empty_signals_ok(self):
        from services.ml_client import _normalize_timestamps
        result = _normalize_timestamps({})
        assert result == {}


# ── Webhook ───────────────────────────────────────────────────────────────────

class TestWebhookSigning:
    def test_signature_format(self):
        from tasks.webhook_tasks import _sign
        sig = _sign('{"test":true}', "mysecret")
        assert sig.startswith("sha256=")
        assert len(sig) == 71  # "sha256=" + 64 hex chars

    def test_deterministic(self):
        from tasks.webhook_tasks import _sign
        assert _sign("payload", "secret") == _sign("payload", "secret")

    def test_different_secret_different_sig(self):
        from tasks.webhook_tasks import _sign
        assert _sign("payload", "s1") != _sign("payload", "s2")


# ── Webhook validator ─────────────────────────────────────────────────────────

class TestWebhookValidator:
    def test_https_passes(self):
        from core.webhook_validator import validate_webhook_url
        assert validate_webhook_url("https://example.com/hook") == "https://example.com/hook"

    def test_http_blocked(self):
        from fastapi import HTTPException
        from core.webhook_validator import validate_webhook_url
        with pytest.raises(HTTPException):
            validate_webhook_url("http://example.com/hook")

    def test_localhost_blocked(self):
        from fastapi import HTTPException
        from core.webhook_validator import validate_webhook_url
        with pytest.raises(HTTPException):
            validate_webhook_url("https://localhost/hook")
