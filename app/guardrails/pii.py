"""PII redaction — regex layer.

Applied at BOTH boundaries: document text at ingest (before it is embedded and
stored) and final answers at query time (before they leave the API). Covers
emails, phone numbers, IBANs, credit-card numbers, Turkish national IDs and
US SSNs. NER-based detection is a documented known limit (fallback ladder:
"PII NER → regex yeter"); the seam to add it is `redact()`.

OWASP LLM Top 10 mapping: LLM02 / LLM06 (Sensitive Information Disclosure).
"""

from __future__ import annotations

import re

# Order matters: more specific patterns run before broader ones.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[ ]?(?:[A-Z0-9][ ]?){10,30}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    # TR national ID: exactly 11 digits, first digit non-zero.
    ("TC_KIMLIK", re.compile(r"\b[1-9]\d{10}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    (
        "PHONE",
        re.compile(
            r"(?<![\d/])(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?\d{3}[ -]\d{2,4}[ -]\d{2,4}(?![\d/])"
        ),
    ),
]


def redact(text: str) -> str:
    """Replace every detected PII span with a typed placeholder."""
    result = text
    for label, pattern in _RULES:
        result = pattern.sub(f"[REDACTED_{label}]", result)
    return result


def contains_pii(text: str) -> bool:
    return any(pattern.search(text) for _, pattern in _RULES)
