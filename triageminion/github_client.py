"""Minimal read-only GitHub REST client (stdlib only, no auth required).

Public repository data needs no token: the unauthenticated rate limit is
60 requests/hour, and a demo run uses roughly one request per issue plus one
for the listing. Set ``GITHUB_TOKEN`` to raise the limit to 5,000/hour — the
token is read from the environment only, never from source or config files.
"""

from __future__ import annotations

import http.client
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.github.com"
TIMEOUT_SECONDS = 15
USER_AGENT = "triageminion/0.1.0 (Cortensor Hackathon #5)"


def _drop_connection_close_header() -> None:
    """Stop urllib from sending ``Connection: close``.

    ``urllib`` forces that header, and some egress proxies respond by
    truncating the response (we hit read timeouts / cut-off bodies against
    api.github.com from this VM until the header was dropped; curl, which
    keeps the connection alive, worked fine). Dropping it is harmless on a
    normal network — it just leaves the default keep-alive behaviour in
    place.
    """
    original_putheader = http.client.HTTPConnection.putheader

    def patched_putheader(self, header, *values):  # type: ignore[no-untyped-def]
        if header.lower() == "connection":
            return
        return original_putheader(self, header, *values)

    http.client.HTTPConnection.putheader = patched_putheader


_drop_connection_close_header()


class GitHubError(RuntimeError):
    """Raised when the GitHub API call fails (network, rate limit, 404, ...)."""


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(path: str, params: dict[str, str] | None = None) -> object:
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise GitHubError(f"GitHub API {exc.code} for {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"GitHub API unreachable ({path}): {exc}") from exc


def parse_issue(raw: dict) -> dict:
    """Reduce a GitHub issue payload to the fields triage needs.

    Pull requests also appear in the issues listing; they carry a
    ``pull_request`` key and are filtered out by :func:`list_open_issues`.
    """
    return {
        "number": raw["number"],
        "title": raw.get("title", ""),
        "body": (raw.get("body") or "")[:2000],
        "labels": [label["name"] for label in raw.get("labels", [])],
        "comments": raw.get("comments", 0),
        "created_at": raw.get("created_at", ""),
        "html_url": raw.get("html_url", ""),
        "author": (raw.get("user") or {}).get("login", ""),
    }


def list_open_issues(repo: str, limit: int = 5) -> list[dict]:
    """Return up to ``limit`` open issues (not pull requests) for ``repo``."""
    raw = _get(f"/repos/{repo}/issues", {"state": "open", "per_page": str(max(limit * 2, limit))})
    issues = [parse_issue(item) for item in raw if "pull_request" not in item]
    return issues[:limit]


def read_issue(repo: str, number: int) -> dict:
    """Return one issue in full."""
    return parse_issue(_get(f"/repos/{repo}/issues/{number}"))


def search_issues(repo: str, query: str, limit: int = 5) -> list[dict]:
    """Keyword-search issues in ``repo`` (used for duplicate detection)."""
    raw = _get("/search/issues", {"q": f"repo:{repo} {query} in:title,body", "per_page": str(limit)})
    return [parse_issue(item) for item in raw.get("items", [])]
