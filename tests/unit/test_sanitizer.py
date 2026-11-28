"""Unit tests for query data sanitization."""

from src.utils.sanitizer import sanitize_text


def test_sanitize_aws_key_and_token():
    raw_query = "What caused the error with AKIAIOSFODNN7EXAMPLE and Bearer eyJhbGciOiJ..."
    sanitized, redactions = sanitize_text(raw_query)

    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
    assert "[REDACTED_AWS_KEY]" in sanitized
    assert "Bearer [REDACTED_TOKEN]" in sanitized
    assert redactions["aws_access_key"] == 1
    assert redactions["bearer_token"] == 1


def test_sanitize_private_ip():
    raw_query = "Cannot connect to node at 10.0.4.15 and 192.168.1.100"
    sanitized, redactions = sanitize_text(raw_query)

    assert "10.0.4.15" not in sanitized
    assert "192.168.1.100" not in sanitized
    assert "[INTERNAL_IP]" in sanitized
    assert redactions["private_ip"] == 2
