"""CLI entry point: python -m triageminion OWNER/REPO [--limit N] ...

Exit codes:
  0  triage complete (report written, or write denied by the operator)
  1  provider failure / GitHub failure / unexpected error
  2  typed-output validation failure (raw model text printed, nothing invented)
  3  turn deadline exceeded
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid

from openminion import (
    AgentOutputValidationError,
    ProviderError,
    TurnTimeoutError,
)

from . import __version__, agent as agent_mod
from .github_client import GitHubError


def _progress(event) -> None:
    """Streaming progress callback: one dot per delta, no log spam."""
    sys.stdout.write(".")
    sys.stdout.flush()


def _smoke_test() -> int:
    """Credential-free wiring check (echo provider).

    Proves the SDK imports, the config loads, and the runtime answers. It
    does NOT prove model-selected tool use — use a real model for that.
    """
    import openminion

    print(f"triageminion {__version__} · openminion {openminion.__version__}")
    from openminion import Agent

    with Agent(session_id=f"smoke-{uuid.uuid4().hex[:8]}") as smoke:
        result = smoke.run("Reply with the single word: ok", timeout_seconds=60)
    print(f"runtime answered: {result.text!r}")
    print("smoke test passed (wiring only — echo proves no model behavior)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="triageminion",
        description="Triage a public GitHub repo's open issues with OpenMinion.",
    )
    parser.add_argument("repo", nargs="?", help="Repository as OWNER/REPO")
    parser.add_argument("--limit", type=int, default=5, help="Max issues (default 5)")
    parser.add_argument("--agent", default=None, help="Configured OpenMinion agent id")
    parser.add_argument("--model", default=None, help="Explicit provider:model override")
    parser.add_argument(
        "--fresh-session",
        action="store_true",
        help="Start a new session instead of resuming the repo's remembered triage session",
    )
    parser.add_argument(
        "--auto-approve",
        choices=["yes", "no"],
        default=None,
        help="Decide the save_report approval non-interactively (CI use)",
    )
    parser.add_argument("--out", default="triage_report.md", help="Report path")
    parser.add_argument("--timeout", type=int, default=120, help="Per-turn deadline (seconds)")
    parser.add_argument("--smoke-test", action="store_true", help="Credential-free wiring check")
    parser.add_argument("--version", action="version", version=f"triageminion {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.smoke_test:
        try:
            return _smoke_test()
        except (ProviderError, TurnTimeoutError) as exc:
            print(f"smoke test failed: {exc}", file=sys.stderr)
            return 1

    if not args.repo or "/" not in args.repo:
        print("error: give a repository as OWNER/REPO", file=sys.stderr)
        return 2

    session_id = None
    if args.fresh_session:
        session_id = f"triage:{args.repo}:{uuid.uuid4().hex[:8]}"

    print(f"TriageMinion: triaging {args.repo} (limit {args.limit})")
    try:
        outcome = agent_mod.run_triage(
            args.repo,
            limit=args.limit,
            agent_id=args.agent,
            model=args.model,
            session_id=session_id,
            auto_approve=args.auto_approve,
            out_path=args.out,
            timeout_seconds=args.timeout,
            on_delta=_progress,
        )
    except AgentOutputValidationError as exc:
        print("ERROR: the model reply failed schema validation.", file=sys.stderr)
        print(f"raw model text:\n{exc.raw_text}", file=sys.stderr)
        return 2
    except TurnTimeoutError as exc:
        print(f"ERROR: turn timed out after {args.timeout}s: {exc}", file=sys.stderr)
        return 3
    except ProviderError as exc:
        print(f"ERROR: provider failed: {exc.code}: {exc.message}", file=sys.stderr)
        return 1
    except GitHubError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print()  # end the progress-dot line
    print(f"\n{outcome.report.summary}\n")
    for issue in outcome.report.issues:
        dup = f" (dup of #{issue.duplicate_of})" if issue.duplicate_of else ""
        print(
            f"  #{issue.number} [{issue.category}/{issue.severity}/{issue.priority}] "
            f"{issue.title}{dup} — conf {issue.confidence:.2f}"
        )

    # Facts next to the report, for auditability.
    with open("facts.json", "w", encoding="utf-8") as f:
        json.dump({"repo": args.repo, "facts": outcome.facts_text}, f, indent=2)

    if outcome.written_path:
        print(f"\nReport written to {outcome.written_path} (facts in facts.json)")
    else:
        print("\nWrite denied by the operator — no report file was created.")
        print("The verdicts above are still shown; re-run to save them.")
    print(f"session={outcome.session_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
