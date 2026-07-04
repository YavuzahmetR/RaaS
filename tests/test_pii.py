"""PII redaction tests (OWASP LLM02/LLM06): emails, phones, IBANs, cards, IDs."""

from __future__ import annotations

import pytest

from app.guardrails.pii import contains_pii, redact


@pytest.mark.parametrize(
    ("raw", "must_disappear", "placeholder"),
    [
        ("Contact hr@acme.example for details.", "hr@acme.example", "[REDACTED_EMAIL]"),
        ("Call +90 532 123 45 67 anytime.", "532 123 45 67", "[REDACTED_PHONE]"),
        ("Wire to TR33 0006 1005 1978 6457 8413 26 today.", "0006 1005", "[REDACTED_IBAN]"),
        ("Card: 4111 1111 1111 1111 exp 12/29.", "4111 1111", "[REDACTED_CREDIT_CARD]"),
        ("TC no 10000000146 is on file.", "10000000146", "[REDACTED_TC_KIMLIK]"),
        ("SSN 078-05-1120 must stay private.", "078-05-1120", "[REDACTED_SSN]"),
    ],
)
def test_pii_is_redacted(raw: str, must_disappear: str, placeholder: str) -> None:
    result = redact(raw)
    assert must_disappear not in result
    assert placeholder in result


def test_clean_text_untouched() -> None:
    text = "Employees accrue 22 days of leave per year; reviews happen in June."
    assert redact(text) == text
    assert not contains_pii(text)


def test_multiple_pii_in_one_text() -> None:
    text = "Mail jane.doe@corp.io or call +90 555 111 22 33."
    result = redact(text)
    assert "jane.doe@corp.io" not in result
    assert "555 111 22 33" not in result
    assert result.count("[REDACTED_") >= 2
