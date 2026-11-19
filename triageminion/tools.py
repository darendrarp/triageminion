"""OpenMinion tools for TriageMinion.

Risk classification is deliberate and honest — it is what the approval policy
decides on:

- ``list_open_issues`` / ``read_issue`` / ``search_issues`` are
  ``min_scope="READ_ONLY"`` and ``idempotent=True``: pure reads, no side
  effects, run without confirmation under the default policy.
- ``save_report`` is ``dangerous=True`` and NOT idempotent: it writes a file
  on disk. The default policy requires confirmation, routed to the run's
  ``approval_callback`` (or the interactive prompt). If the operator denies,
  nothing is written.

The tools are plain Python functions; ``@tool`` exposes them to the model only
for the run that passes them in ``tools=[...]`` (run-scoped exposure).
"""

from __future__ import annotations

import json

from openminion import tool

from . import github_client


@tool(min_scope="READ_ONLY", idempotent=True)
def list_open_issues(repo: str, limit: int = 5) -> str:
    """List open GitHub issues (not pull requests) for a public repo.

    Returns a JSON list with number, title, labels, comment count, author,
    created date, URL, and the first 2000 characters of each body.
    """
    issues = github_client.list_open_issues(repo, limit=limit)
    return json.dumps(issues, indent=2)


@tool(min_scope="READ_ONLY", idempotent=True)
def read_issue(repo: str, number: int) -> str:
    """Read one GitHub issue in full: title, body, labels, comment count."""
    return json.dumps(github_client.read_issue(repo, number), indent=2)


@tool(min_scope="READ_ONLY", idempotent=True)
def search_issues(repo: str, query: str, limit: int = 5) -> str:
    """Keyword-search issues in a repo (title + body). Use it to check
    whether an issue duplicates one already filed."""
    return json.dumps(github_client.search_issues(repo, query, limit=limit), indent=2)


@tool(dangerous=True)
def save_report(path: str, markdown: str) -> str:
    """Write the triage report Markdown file to ``path``.

    This is the ONLY write in the whole workflow, and it requires human
    approval before it runs. Returns a confirmation line with the path and
    byte count.
    """
    with open(path, "w", encoding="utf-8") as f:
        written = f.write(markdown)
    return f"wrote {written} bytes to {path}"
