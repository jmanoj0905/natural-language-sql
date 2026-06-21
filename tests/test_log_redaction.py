from app.utils.logger import redact_sensitive


def test_redacts_known_secret_fields():
    out = redact_sensitive(None, "info", {
        "event": "x", "api_key": "sk-123", "password": "p",
        "authorization": "Bearer t", "generated_key": "g", "safe": "keep",
    })
    assert out["api_key"] == "***REDACTED***"
    assert out["password"] == "***REDACTED***"
    assert out["authorization"] == "***REDACTED***"
    assert out["generated_key"] == "***REDACTED***"
    assert out["safe"] == "keep"


def test_leaves_empty_values_alone():
    out = redact_sensitive(None, "info", {"api_key": "", "event": "x"})
    assert out["api_key"] == ""
