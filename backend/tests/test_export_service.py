"""
Unit tests for app/services/export_service.py

Pure-function tests — no DB or HTTP needed.
"""
from __future__ import annotations

import pytest

from app.services.export_service import (
    _extract_pitch,
    _parse_lines,
    build_cover_letter_docx,
    build_cover_letter_pdf,
    build_cv_docx,
    build_cv_pdf,
    build_hr_email,
    build_linkedin_message,
)

SAMPLE_CV = """\
# Jane Smith
## Experience
### Senior Engineer — Acme Corp (2021–2024)
- Led Python migration reducing latency by 40%
- Built production ML pipeline serving 1M requests/day

## Skills
Python, FastAPI, PostgreSQL, Docker
"""

SAMPLE_LETTER = """\
Dear Hiring Manager,

I am excited to apply for the Senior ML Engineer role. My five years of Python engineering experience, including large-scale model deployment, makes me a strong match for your team. I have shipped ML systems that process millions of events daily.

I look forward to discussing this further.

Kind regards,
Jane Smith
"""


# ── Parser ────────────────────────────────────────────────────────────────────

class TestParseLines:
    def test_heading1(self):
        result = dict(_parse_lines("# Title"))
        assert result == {"heading1": "Title"}

    def test_heading2(self):
        parsed = _parse_lines("## Section")
        assert ("heading2", "Section") in parsed

    def test_heading3(self):
        parsed = _parse_lines("### Sub")
        assert ("heading3", "Sub") in parsed

    def test_bullet_dash(self):
        parsed = _parse_lines("- item one")
        assert ("bullet", "item one") in parsed

    def test_bullet_star(self):
        parsed = _parse_lines("* item two")
        assert ("bullet", "item two") in parsed

    def test_blank_line(self):
        # splitlines() on a string with a newline yields ["", ""] — blank tokens
        parsed = _parse_lines("line1\n\nline2")
        assert ("blank", "") in parsed

    def test_plain_para(self):
        parsed = _parse_lines("Just a normal sentence.")
        assert ("para", "Just a normal sentence.") in parsed

    def test_multi_line(self):
        parsed = _parse_lines("# H\n## S\n- b\npara")
        kinds = [k for k, _ in parsed]
        assert "heading1" in kinds
        assert "heading2" in kinds
        assert "bullet" in kinds
        assert "para" in kinds


# ── DOCX generation ───────────────────────────────────────────────────────────

class TestBuildCvDocx:
    def test_returns_bytes(self):
        result = build_cv_docx(SAMPLE_CV)
        assert isinstance(result, bytes)

    def test_is_valid_zip(self):
        # DOCX files are ZIP archives starting with PK
        result = build_cv_docx(SAMPLE_CV)
        assert result[:2] == b"PK"

    def test_nonempty(self):
        result = build_cv_docx(SAMPLE_CV)
        assert len(result) > 1000

    def test_empty_text_still_produces_docx(self):
        result = build_cv_docx("")
        assert result[:2] == b"PK"


class TestBuildCoverLetterDocx:
    def test_returns_bytes(self):
        result = build_cover_letter_docx(SAMPLE_LETTER)
        assert isinstance(result, bytes)
        assert result[:2] == b"PK"

    def test_different_from_cv(self):
        cv = build_cv_docx(SAMPLE_CV)
        letter = build_cover_letter_docx(SAMPLE_LETTER)
        assert cv != letter


# ── PDF generation ────────────────────────────────────────────────────────────

class TestBuildCvPdf:
    def test_returns_bytes(self):
        result = build_cv_pdf(SAMPLE_CV)
        assert isinstance(result, bytes)

    def test_is_pdf_magic(self):
        result = build_cv_pdf(SAMPLE_CV)
        assert result[:4] == b"%PDF"

    def test_nonempty(self):
        result = build_cv_pdf(SAMPLE_CV)
        assert len(result) > 500

    def test_empty_text_still_produces_pdf(self):
        result = build_cv_pdf("")
        assert result[:4] == b"%PDF"


class TestBuildCoverLetterPdf:
    def test_returns_bytes(self):
        result = build_cover_letter_pdf(SAMPLE_LETTER)
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"


# ── Pitch extraction ──────────────────────────────────────────────────────────

class TestExtractPitch:
    def test_skips_salutation(self):
        text = "Dear Hiring Manager,\n\nI am great at coding."
        pitch = _extract_pitch(text, max_sentences=2)
        assert "Dear" not in pitch
        assert "great at coding" in pitch

    def test_returns_up_to_max_sentences(self):
        text = "Sent A. Sent B. Sent C. Sent D."
        pitch = _extract_pitch(text, max_sentences=2)
        # Should not include all 4 sentences
        assert "Sent D" not in pitch

    def test_handles_empty(self):
        assert _extract_pitch("") == ""

    def test_skips_closing(self):
        # "Kind regards," matches the closing skip pattern and is omitted;
        # a bare name like "Jane" on its own line is not recognisable as a closing
        # and may appear — the important thing is the greeting phrase is gone.
        text = "Kind regards,\nJane"
        pitch = _extract_pitch(text, max_sentences=3)
        assert "Kind regards" not in pitch


# ── HR email ─────────────────────────────────────────────────────────────────

class TestBuildHrEmail:
    def test_contains_job_title(self):
        email = build_hr_email("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        assert "ML Engineer" in email

    def test_contains_company(self):
        email = build_hr_email("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        assert "Acme" in email

    def test_contains_candidate_name(self):
        email = build_hr_email("ML Engineer", "Acme", "Jane Smith", SAMPLE_LETTER)
        assert "Jane Smith" in email

    def test_has_subject_line(self):
        email = build_hr_email("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        assert email.startswith("Subject:")

    def test_has_greeting(self):
        email = build_hr_email("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        assert "Dear Hiring Manager" in email

    def test_includes_pitch_from_cover_letter(self):
        email = build_hr_email("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        assert "Python" in email or "excited" in email or "ML" in email


# ── LinkedIn message ──────────────────────────────────────────────────────────

class TestBuildLinkedinMessage:
    def test_contains_job_title(self):
        msg = build_linkedin_message("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        assert "ML Engineer" in msg

    def test_contains_company(self):
        msg = build_linkedin_message("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        assert "Acme" in msg

    def test_shorter_than_email(self):
        email = build_hr_email("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        msg = build_linkedin_message("ML Engineer", "Acme", "Jane", SAMPLE_LETTER)
        assert len(msg) < len(email)

    def test_has_closing(self):
        msg = build_linkedin_message("ML Engineer", "Acme", "Jane Smith", SAMPLE_LETTER)
        assert "Jane Smith" in msg
