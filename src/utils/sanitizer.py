"""
Data Sanitization & Secret Masking for GroundedOps.
Scans incoming user queries and logging payloads to redact sensitive secrets,
AWS access keys, bearer tokens, database credentials, and internal IP addresses.
"""

import re
from typing import Dict, Tuple

# Compiled security regex patterns
PATTERNS = {
    "aws_access_key": re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    "aws_secret_key": re.compile(r"\b([a-zA-Z0-9/+=]{40})\b"),
    "bearer_token": re.compile(r"Bearer\s+([a-zA-Z0-9\-\._~\+\/]+=*)", re.IGNORECASE),
    "db_uri_password": re.compile(r"://([^:]+):([^@]+)@"),
    "ipv4_private": re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b"),
    "generic_secret": re.compile(r"(password|secret|apikey|api_key|token)\s*[:=]\s*['\"]?([a-zA-Z0-9!@#$%^&*()_+=\-]{6,})['\"]?", re.IGNORECASE),
}


def sanitize_text(text: str) -> Tuple[str, Dict[str, int]]:
    """
    Sanitize sensitive information from a text string.
    Returns:
      (sanitized_text, redaction_counts)
    """
    if not text:
        return text, {}

    redaction_counts: Dict[str, int] = {}
    sanitized = text

    # Redact AWS Access Keys
    matches = PATTERNS["aws_access_key"].findall(sanitized)
    if matches:
        redaction_counts["aws_access_key"] = len(matches)
        sanitized = PATTERNS["aws_access_key"].sub("[REDACTED_AWS_KEY]", sanitized)

    # Redact Bearer Tokens
    matches = PATTERNS["bearer_token"].findall(sanitized)
    if matches:
        redaction_counts["bearer_token"] = len(matches)
        sanitized = PATTERNS["bearer_token"].sub("Bearer [REDACTED_TOKEN]", sanitized)

    # Redact DB passwords in connection URIs
    if PATTERNS["db_uri_password"].search(sanitized):
        sanitized = PATTERNS["db_uri_password"].sub(r"://\1:[REDACTED_PASSWORD]@", sanitized)
        redaction_counts["db_password"] = 1

    # Redact Private IP Addresses
    matches = PATTERNS["ipv4_private"].findall(sanitized)
    if matches:
        redaction_counts["private_ip"] = len(matches)
        sanitized = PATTERNS["ipv4_private"].sub("[INTERNAL_IP]", sanitized)

    # Redact generic password/secret assignments
    matches = PATTERNS["generic_secret"].findall(sanitized)
    if matches:
        redaction_counts["generic_secret"] = len(matches)
        sanitized = PATTERNS["generic_secret"].sub(r"\1=[REDACTED_SECRET]", sanitized)

    return sanitized, redaction_counts
