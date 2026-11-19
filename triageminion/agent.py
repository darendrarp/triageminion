"""Agent wiring: Scout → Judge (+ deep-dive subagent) → Publisher.

Three roles, three power levels — the design that makes the agent trustworthy:

* Scout: read-only tools, gathers facts. It never judges.
* Judge: no tools at all, so it cannot invent data. It returns a
  Pydantic-validated ``TriageReport``.
* Publisher: one dangerous tool (``save_report``), gated by human approval.
  If the operator says no, nothing is written.

All three run on the same OpenMinion runtime through the public ``Agent``
facade (``openminion==0.1.22``). Provider selection is by configured agent
profile / ``model="provider:model"`` — the code never names a provider.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from openminion import (
    Agent,
    AgentOutputValidationError,
    ProviderError,
    TurnTimeoutError,
    subagent,
)

from . import report as report_mod
from . import tools
from .models import TriageReport

SCOUT_INSTRUCTIONS = (
    "You are the Scout for a GitHub issue triage run. Use list_open_issues "
    "to fetch the open issues, then read_issue for each one, and "
    "search_issues when an issue looks like a duplicate of another. "
    "Return ALL the facts you gathered as one JSON block, verbatim: issue "
    "numbers, titles, bodies, labels, comment counts, authors, dates. "
    "Do not judge, classify, or summarise — facts only."
)

JUDGE_INSTRUCTIONS = (
    "You are the Judge for a GitHub issue triage run. You receive facts "
    "gathered by the Scout. Return JSON matching the requested schema: one "
    "verdict per issue with category (bug/feature/docs/question/chore), "
    "severity (critical/high/medium/low), priority (P0-P3), suggested "
    "labels, duplicate_of (issue number or null), needs_info, confidence "
    "(0.0-1.0), and a rationale quoting evidence from the issue. "
    "Only call something a duplicate when the evidence clearly supports it. "
    "Set needs_info=true when the issue lacks the information a maintainer "
    "would need to act."
)

DEEP_DIVE_INSTRUCTIONS = (
    "You are a deep-dive reviewer. Read the issue carefully with read_issue "
    "and search_issues for related issues, then report in two or three "
    "sentences: what the issue is really about, whether it duplicates "
    "another issue (with the number), and what is still unclear."
)

PUBLISHER_INSTRUCTIONS = (
    "You are the Publisher. Call save_report exactly once with the report "
    "path and the Markdown content given to you, reproduced exactly. "
    "Do not edit, summarise, or reformat the content."
)

LOW_CONFIDENCE_THRESHOLD = 0.7


@dataclass
class TriageOutcome:
    """Everything a caller needs after a run."""

    report: TriageReport
    markdown: str
    facts_text: str
    session_id: str | None
    written_path: str | None  # None when the operator denied the write


def _approval_callback(auto_approve: str | None) -> Callable | None:
    """Build the approval callback for the Publisher's dangerous tool.

    ``auto_approve="yes"/"no"`` decides non-interactively (CI use).
    Otherwise the operator is asked on the terminal, after being shown the
    exact tool name and arguments.
    """
    if auto_approve == "yes":
        return lambda tool_name, args, approval_id: True
    if auto_approve == "no":
        return lambda tool_name, args, approval_id: False

    def decide(tool_name: str, args: dict, approval_id: str) -> bool:
        print(f"\n[approval requested] tool={tool_name} id={approval_id}")
        for key, value in args.items():
            shown = str(value)
            print(f"  {key} = {shown[:500]}{'...' if len(shown) > 500 else ''}")
        answer = input("Allow this exact action? [yes/no] ").strip().lower()
        return answer in ("y", "yes")

    return decide


def _scout_facts(
    repo: str,
    limit: int,
    *,
    agent_id: str | None,
    model: str | None,
    session_id: str,
    timeout_seconds: int,
    on_delta: Callable | None,
) -> str:
    """Run the Scout and return the facts text it gathered."""
    with Agent(
        name="scout",
        agent_id=agent_id,
        model=model,
        instructions=SCOUT_INSTRUCTIONS,
        tools=[tools.list_open_issues, tools.read_issue, tools.search_issues],
        forced_tools=["list_open_issues"],
        session_id=session_id,
    ) as scout:
        if on_delta is not None:
            result = scout.run_stream(
                f"Gather the facts for the {limit} most recent open issues of {repo}.",
                timeout_seconds=timeout_seconds,
                on_delta=on_delta,
            )
        else:
            result = scout.run(
                f"Gather the facts for the {limit} most recent open issues of {repo}.",
                timeout_seconds=timeout_seconds,
            )
    return result.text


def _judge(
    facts_text: str,
    repo: str,
    *,
    agent_id: str | None,
    model: str | None,
    session_id: str,
    timeout_seconds: int,
    extra_context: str = "",
) -> TriageReport:
    """Run the Judge and return the validated TriageReport."""
    prompt = (
        f"Triage the open issues of {repo} from these Scout facts:\n\n{facts_text}"
    )
    if extra_context:
        prompt += f"\n\nAdditional deep-dive findings:\n{extra_context}"
    with Agent(
        name="judge",
        agent_id=agent_id,
        model=model,
        instructions=JUDGE_INSTRUCTIONS,
        output_type=TriageReport,
        session_id=session_id,
    ) as judge:
        result = judge.run(prompt, timeout_seconds=timeout_seconds)
    return result.output


def _deep_dive(
    parent: Agent,
    repo: str,
    issue_numbers: list[int],
    *,
    timeout_seconds: int,
) -> str:
    """Bounded subagent investigation of the ambiguous issues."""
    reviewer = subagent(
        parent,
        name="deep-diver",
        instructions=DEEP_DIVE_INSTRUCTIONS,
        tools=[tools.read_issue, tools.search_issues],
        timeout_seconds=timeout_seconds,
    )
    findings = []
    for number in issue_numbers:
        findings.append(
            reviewer.run(f"Investigate issue #{number} of {repo}.").text
        )
    return "\n\n".join(findings)


def run_triage(
    repo: str,
    limit: int = 5,
    *,
    agent_id: str | None = None,
    model: str | None = None,
    session_id: str | None = None,
    auto_approve: str | None = None,
    out_path: str = "triage_report.md",
    timeout_seconds: int = 120,
    on_delta: Callable | None = None,
) -> TriageOutcome:
    """Run the full Scout → Judge → Publisher pipeline.

    Raises ``ProviderError``, ``TurnTimeoutError``, and
    ``AgentOutputValidationError`` for the caller to report visibly.
    """
    session_id = session_id or f"triage:{repo}"

    facts_text = _scout_facts(
        repo,
        limit,
        agent_id=agent_id,
        model=model,
        session_id=session_id,
        timeout_seconds=timeout_seconds,
        on_delta=on_delta,
    )

    try:
        verdict = _judge(
            facts_text,
            repo,
            agent_id=agent_id,
            model=model,
            session_id=session_id,
            timeout_seconds=timeout_seconds,
        )
    except AgentOutputValidationError:
        # One retry with a stricter instruction; then fail visibly with the
        # raw text on the exception — never silently invent a valid object.
        verdict = _judge(
            facts_text,
            repo,
            agent_id=agent_id,
            model=model,
            session_id=session_id,
            timeout_seconds=timeout_seconds,
            extra_context=(
                "Previous reply failed schema validation. Reply with ONLY "
                "the JSON object, no prose around it."
            ),
        )

    # Deep-dive the low-confidence verdicts, then re-judge with the findings.
    uncertain = [
        issue.number
        for issue in verdict.issues
        if issue.confidence < LOW_CONFIDENCE_THRESHOLD
    ]
    if uncertain:
        with Agent(
            name="coordinator",
            agent_id=agent_id,
            model=model,
            instructions="Coordinate a triage deep-dive.",
            session_id=session_id,
        ) as parent:
            extra = _deep_dive(
                parent, repo, uncertain, timeout_seconds=timeout_seconds
            )
        verdict = _judge(
            facts_text,
            repo,
            agent_id=agent_id,
            model=model,
            session_id=session_id,
            timeout_seconds=timeout_seconds,
            extra_context=extra,
        )

    markdown = report_mod.render_markdown(
        verdict, provider=agent_id or "default", model=model or "profile default"
    )

    # Publisher: the dangerous write goes through human approval.
    written_path = None
    with Agent(
        name="publisher",
        agent_id=agent_id,
        model=model,
        instructions=PUBLISHER_INSTRUCTIONS,
        tools=[tools.save_report],
        forced_tools=["save_report"],
        session_id=session_id,
    ) as publisher:
        result = publisher.run(
            f"Save this triage report to {out_path}:\n\n{markdown}",
            timeout_seconds=timeout_seconds,
            approval_callback=_approval_callback(auto_approve),
        )
        if result.metadata.get("respond_kind") == "policy_confirmation_prompt":
            # No callback was given and the policy paused: answer on the
            # waiting thread, while the Agent is still open. A plain later
            # run() would start a new thread and NOT answer the pause.
            decision = input(f"{result.text}\nAllow this exact action? [yes/no] ")
            resolved = publisher.run(decision, thread_id=result.thread_id)
            if "not run" not in resolved.text.lower():
                written_path = out_path
        elif "Confirmation denied" not in result.text:
            written_path = out_path

    return TriageOutcome(
        report=verdict,
        markdown=markdown,
        facts_text=facts_text,
        session_id=session_id,
        written_path=written_path,
    )


__all__ = [
    "AgentOutputValidationError",
    "ProviderError",
    "TriageOutcome",
    "TurnTimeoutError",
    "run_triage",
]
