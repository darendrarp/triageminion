"""Unit tests for TriageMinion's pure logic.

No model and no network: these run in seconds in any checkout.
Run: python -m pytest tests/ -v
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from triageminion.github_client import parse_issue
from triageminion.models import IssueTriage, TriageReport
from triageminion.report import render_markdown

RAW_ISSUE = {
    "number": 42,
    "title": "Crash on empty config",
    "body": "Steps to reproduce: ...",
    "labels": [{"name": "bug"}, {"name": "needs-repro"}],
    "comments": 3,
    "created_at": "2026-11-01T10:00:00Z",
    "html_url": "https://github.com/acme/repo/issues/42",
    "user": {"login": "reporter"},
}


def _verdict(**overrides) -> IssueTriage:
    base = {
        "number": 42,
        "title": "Crash on empty config",
        "category": "bug",
        "severity": "high",
        "priority": "P1",
        "suggested_labels": ["bug"],
        "duplicate_of": None,
        "needs_info": False,
        "confidence": 0.9,
        "rationale": "The report includes repro steps and a stack trace.",
    }
    base.update(overrides)
    return IssueTriage(**base)


def test_parse_issue_keeps_triage_fields():
    parsed = parse_issue(RAW_ISSUE)
    assert parsed["number"] == 42
    assert parsed["labels"] == ["bug", "needs-repro"]
    assert parsed["author"] == "reporter"
    assert parsed["comments"] == 3


def test_parse_issue_truncates_long_body():
    raw = dict(RAW_ISSUE, body="x" * 5000)
    assert len(parse_issue(raw)["body"]) == 2000


def test_parse_issue_tolerates_missing_body():
    raw = dict(RAW_ISSUE, body=None)
    assert parse_issue(raw)["body"] == ""


def test_verdict_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        _verdict(confidence=1.5)


def test_report_serialises_to_json():
    report = TriageReport(
        repo="acme/repo",
        issues=[_verdict()],
        summary="One high-severity bug, ready to fix.",
    )
    data = json.loads(report.model_dump_json())
    assert data["issues"][0]["number"] == 42
    assert data["repo"] == "acme/repo"


def test_render_markdown_contains_verdicts_and_rationale():
    report = TriageReport(
        repo="acme/repo",
        issues=[_verdict(), _verdict(number=7, title="Docs typo", category="docs",
                                     severity="low", priority="P3",
                                     confidence=0.95, duplicate_of=42)],
        summary="One bug, one docs fix.",
    )
    md = render_markdown(report, provider="openrouter", model="demo-model")
    assert "# Triage report — acme/repo" in md
    assert "| #42 | Crash on empty config | bug |" in md
    assert "dup of #42" in md or "#42" in md
    assert "### #7 — Docs typo" in md
    assert "provider `openrouter`" in md
    assert "Reproduce:" in md
