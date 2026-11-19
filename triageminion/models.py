"""Typed models for triage verdicts.

The Judge agent returns a ``TriageReport`` via OpenMinion's ``output_type``
mechanism, so verdicts are Pydantic-validated instead of free text. A
validation failure raises ``AgentOutputValidationError`` with the raw model
text preserved — we never silently invent a valid object.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class IssueTriage(BaseModel):
    """One issue's triage verdict."""

    number: int = Field(description="GitHub issue number.")
    title: str = Field(description="Issue title, copied from the issue.")
    category: str = Field(
        description="One of: bug, feature, docs, question, chore."
    )
    severity: str = Field(
        description="One of: critical, high, medium, low."
    )
    priority: str = Field(description="One of: P0, P1, P2, P3.")
    suggested_labels: list[str] = Field(
        default_factory=list,
        description="Labels a maintainer could apply, e.g. ['bug', 'needs-repro'].",
    )
    duplicate_of: int | None = Field(
        default=None,
        description="Issue number this duplicates, or null when it is not a duplicate.",
    )
    needs_info: bool = Field(
        default=False,
        description="True when the issue lacks the information needed to act on it.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Judge's confidence in this verdict, 0.0-1.0.",
    )
    rationale: str = Field(
        description="One or two sentences justifying the verdict, quoting evidence from the issue."
    )


class TriageReport(BaseModel):
    """The Judge's validated verdict for a whole triage run."""

    repo: str = Field(description="Repository triaged, as 'owner/name'.")
    issues: list[IssueTriage] = Field(
        default_factory=list, description="One verdict per issue, same order as fetched."
    )
    summary: str = Field(
        description="Two or three sentences summarising the state of the open queue."
    )
