# TriageMinion — GitHub Issue Triage Agent on OpenMinion 0.1

> **Cortensor Hackathon #5 entry** (prep skeleton — full build after 9 Dec 2026).
> TriageMinion reads a public GitHub repository's open issues and produces a
> maintainer-ready triage report: every issue classified by type, severity, and
> priority, with suggested labels, likely duplicates called out, and evidence
> quoted from the issue itself.

**The rule: the model never fetches, the judge never writes.**

- **Scout** — read-only tools only (`list_open_issues`, `read_issue`,
  `search_issues`). Gathers facts from the live GitHub API, returns facts only.
- **Judge** — no tools at all, so it cannot invent data. Returns a
  Pydantic-validated `TriageReport`. Complex issues get a bounded deep-dive
  subagent before the verdict.
- **Publisher** — writes `triage_report.md` through a dangerous tool gated by
  OpenMinion's human approval flow. If the operator says no, nothing is
  written.

## Quick start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Configure one real provider (guided setup), then verify it:
openminion setup --no-chat
openminion doctor --check-turn

# Triage a repo (no GitHub token needed for public repos):
python -m triageminion OpenMinion/openminion --limit 5
```

The report is written to `triage_report.md` in the current directory — after
you approve the write at the prompt. Pass `--auto-approve yes` only for
non-interactive runs where you have already reviewed what the agent will do.

## Provider switching

The same agent runs on any configured provider — no code changes:

```bash
# Free OpenAI-compatible model via OpenRouter (demo default)
openminion setup --provider openrouter --no-chat

# Cortensor Portal (experimental hosted path; access may be limited)
export CORTENSOR_API_KEY=<your-key>
openminion setup --provider cortensor-portal --model oss-20b --no-chat

# Then select the agent profile:
python -m triageminion OpenMinion/openminion --limit 5 --agent default
```

The provider and model used are recorded in the report header.

## Options

```
python -m triageminion OWNER/REPO [--limit N] [--agent ID]
    [--model PROVIDER:MODEL] [--fresh-session]
    [--auto-approve yes|no] [--out PATH] [--timeout SECONDS]
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `OWNER/REPO` | (required) | Public GitHub repository to triage |
| `--limit` | `5` | Max open issues to triage (keep small on free tiers) |
| `--agent` | default profile | Configured OpenMinion agent id |
| `--model` | profile default | Explicit `provider:model` override |
| `--fresh-session` | off | Start a new session instead of resuming the repo's remembered triage session |
| `--auto-approve` | prompt | `yes`/`no` for non-interactive runs |
| `--out` | `triage_report.md` | Report path |
| `--timeout` | `120` | Per-turn deadline in seconds |

## How the OpenMinion SDK is used

See [`docs/BUILDING_BLOCKS.md`](docs/BUILDING_BLOCKS.md) for the full
building-blocks note, and [`docs/WHAT_WE_LEARNED.md`](docs/WHAT_WE_LEARNED.md)
for findings and feedback. In short:

| Building block | Where |
| --- | --- |
| Run-scoped decorated tools | `triageminion/tools.py` (`@tool`, `min_scope`, `idempotent`) |
| Forced first tool call | Scout run, `forced_tools=["list_open_issues"]` |
| Typed structured output | `triageminion/models.py` (`output_type=TriageReport`) |
| Durable sessions + memory | `session_id=f"triage:{owner}/{repo}"`, remembered decisions |
| Human approval | `save_report` (dangerous tool) + `approval_callback` / `thread_id` resume |
| Bounded delegation | Deep-dive `subagent()` for complex issues |
| Streaming progress | `run_stream(..., on_delta=...)` |
| Typed errors | `ProviderError`, `TurnTimeoutError`, `AgentOutputValidationError` |
| Provider switching | `--agent` / `--model`, no code change |

## Tests

```bash
python -m pytest tests/ -v
```

Unit tests cover the pure logic (GitHub response parsing, report rendering,
verdict validation) and need no model and no network. A credential-free
wiring check uses the echo provider:

```bash
openminion config init --provider echo --force
python -m triageminion --smoke-test
```

Echo proves configuration and runtime wiring only — it cannot prove
model-selected tool use. The real demo always uses a tool-capable model.

## Status

Skeleton (prep, 19 Nov 2026): CLI, GitHub client, tools, models, report
renderer, and tests are in place; the agent wiring in `agent.py` follows the
documented OpenMinion 0.1.22 API. Full build (live model runs, demo video,
findings notes) lands after 9 Dec 2026, ahead of the 19 Dec 2026 14:59 WIB
submission deadline.

## License

MIT — see [LICENSE](LICENSE).
