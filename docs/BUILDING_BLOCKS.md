# Building Blocks Tested

> TEMPLATE — to be filled from real runs during the full build (after 9 Dec
> 2026). Nothing below is a finding yet; each row gets a verdict (worked /
> broke / rough edge) with evidence only after it is actually exercised.

## Environment

| Item | Value |
| --- | --- |
| OpenMinion version | `0.1.22` (pinned) |
| Python | 3.11+ |
| Provider / model (demo) | _to fill_ |
| Provider / model (Portal attempt) | _to fill, or "no access"_ |
| Repo triaged in the demo | `OpenMinion/openminion` |
| Date of runs | _to fill_ |

## Blocks exercised

| Building block | How TriageMinion uses it | Verdict | Evidence / notes |
| --- | --- | --- | --- |
| Agent execution | Scout / Judge / Publisher `Agent` runs | _pending_ | |
| Models | Provider switching (OpenRouter free ↔ Cortensor Portal) | _pending_ | |
| Tools | Run-scoped `@tool`: 3 read-only + 1 dangerous | _pending_ | |
| Permissions | `save_report` approval via `approval_callback` + `thread_id` resume | _pending_ | |
| Sessions | Stable `session_id` per repo; `--fresh-session` isolation | _pending_ | |
| Memory | Remembered triage decisions across runs in one session | _pending_ | |
| Typed output | `output_type=TriageReport` (Pydantic) | _pending_ | |
| Delegation | Bounded `subagent()` deep-dive for low-confidence issues | _pending_ | |
| Diagnostics | `doctor --check-turn`, run stats, error surfacing | _pending_ | |
| Streaming | `run_stream(..., on_delta=...)` progress | _pending_ | |
| Error handling | `ProviderError` / `TurnTimeoutError` / `AgentOutputValidationError` | _pending_ | |
| Tasks / scheduling | Not used — out of scope for this workflow | n/a | Deliberate: one-shot triage needs no scheduler |
| Skills | Not used — out of scope for this workflow | n/a | Deliberate |

## Bugs / rough edges found

_To fill during the full build. Each entry: what happened, repro steps,
expected vs actual, SDK version, safe evidence (log excerpt / screenshot /
request ID). Security-sensitive findings go privately to the team, not here._

## Leads to verify (reported by others — NOT our findings)

- Automatic memory extractor issuing the first request of every turn.
- Read-only tools still asking for confirmation under some configurations.
- SDK retry wait (~300 ms) vs free-tier rate windows (~60 s).

Each lead will be tested against 0.1.22 and only reported if reproduced.
