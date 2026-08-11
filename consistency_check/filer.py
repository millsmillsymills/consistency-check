"""GitHub-issue filer. Wraps `gh` CLI with idempotent create/update logic."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

from consistency_check.report import (
    child_issue_title,
    render_child_issue,
    render_umbrella,
    umbrella_issue_title,
)
from consistency_check.stage import declared_stage
from consistency_check.types import FindingStatus, Tier

if TYPE_CHECKING:
    from consistency_check.types import Finding, Repo

_GH_TIMEOUT_SECONDS = 30


def _gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run `gh` under a bounded wait, raising RuntimeError if it cannot complete."""
    label = " ".join(args[:2])
    try:
        return subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        msg = (
            f"gh {label} timed out after {_GH_TIMEOUT_SECONDS}s. "
            f"Check network access; an outbound firewall prompt on a newly "
            f"installed gh binary can block it indefinitely."
        )
        raise RuntimeError(msg) from exc
    except OSError as exc:
        msg = f"gh {label} could not be executed: {exc}"
        raise RuntimeError(msg) from exc


def gh_auth_ok() -> bool:
    """Return True iff `gh auth status` reports an authenticated user.

    Raises:
        RuntimeError: if `gh` could not be run at all, so that a hung or
            missing binary is reported as such rather than as a stale login.

    """
    return _gh(["auth", "status"]).returncode == 0


def file_repo_findings(repo: Repo, findings: list[Finding], *, apply: bool) -> None:
    """File or update issues for `repo` based on its findings.

    Dry-run by default; pass ``apply=True`` to actually call `gh`.
    """
    failures = [f for f in findings if f.status == FindingStatus.FAIL]
    if not failures:
        print(f"[{repo.name}] no failures — nothing to file.")  # noqa: T201
        return

    if not apply:
        _print_dry_run(repo, findings)
        return

    if not gh_auth_ok():
        msg = "gh auth status failed; run `gh auth login` first."
        raise RuntimeError(msg)

    umbrella_body = render_umbrella(repo.name, findings, declared_stage=declared_stage(repo))
    _upsert_issue(
        repo.github_slug,
        umbrella_issue_title(repo.name),
        umbrella_body,
        labels=("consistency",),
        edit_if_exists=True,
    )

    for f in failures:
        if f.tier == Tier.MAY:
            continue
        body = render_child_issue(repo.name, f)
        if body is None:
            continue
        _upsert_issue(
            repo.github_slug,
            child_issue_title(repo.name, f.rule_id),
            body,
            labels=("consistency", f"consistency:{f.tier.value.lower()}"),
            edit_if_exists=False,
        )


def _print_dry_run(repo: Repo, findings: list[Finding]) -> None:
    failures = [f for f in findings if f.status == FindingStatus.FAIL]
    print(  # noqa: T201
        f"[{repo.name}] dry-run: would call: gh issue create --repo {repo.github_slug} "
        f'--title "{umbrella_issue_title(repo.name)}" --body-file <umbrella>.md '
        f"--label consistency"
    )
    for f in failures:
        if f.tier == Tier.MAY:
            continue
        print(  # noqa: T201
            f"[{repo.name}] dry-run: would call: gh issue create --repo {repo.github_slug} "
            f'--title "{child_issue_title(repo.name, f.rule_id)}" '
            f"--body-file <{f.rule_id}>.md "
            f"--label consistency --label consistency:{f.tier.value.lower()}"
        )


# GitHub rejects an issue body over 65,536 characters. Bounding it here rather
# than at render time is what makes the bound an invariant: the per-finding cap
# in `report` scales with the rule count, and `render_umbrella` also serves
# stdout and `--out`, where no API limit applies and truncating is just loss.
_BODY_LIMIT = 65_000
_BODY_TRUNCATED = "\n\n_Body truncated to fit the GitHub API limit. Re-run locally for the rest._\n"


def _fit_body(body: str) -> str:
    """Trim an oversized body at a line boundary.

    Cutting at a fixed offset can land inside an evidence code span and drop its
    closing backtick, and the surviving prefix is then unfenced: an ``@name`` or
    ``#12`` in it posts as a live mention or a cross-reference. Evidence is
    single-line, so no line boundary sits inside a span.
    """
    if len(body) <= _BODY_LIMIT:
        return body
    head = body[: _BODY_LIMIT - len(_BODY_TRUNCATED)]
    return head[: head.rfind("\n") + 1] + _BODY_TRUNCATED


def _upsert_issue(
    slug: str,
    title: str,
    body: str,
    labels: tuple[str, ...],
    *,
    edit_if_exists: bool,
) -> None:
    body = _fit_body(body)
    existing = _list_issues_by_title(slug, title)
    open_existing = [i for i in existing if i["state"] == "OPEN"]
    if len(open_existing) > 1:
        print(  # noqa: T201
            f"WARNING: multiple open issues match {title!r}; refusing to update. "
            f"Numbers: {[i['number'] for i in open_existing]}",
            file=sys.stderr,
        )
        return
    if open_existing:
        if edit_if_exists:
            number = open_existing[0]["number"]
            _run_gh(["issue", "edit", str(number), "--repo", slug, "--body", body])
        return

    cmd = ["issue", "create", "--repo", slug, "--title", title, "--body", body]
    for label in labels:
        cmd += ["--label", label]
    result = _run_gh(cmd)
    print(f"created: {result.stdout.strip()}")  # noqa: T201


def _list_issues_by_title(slug: str, title: str) -> list[dict[str, object]]:
    result = _run_gh(
        [
            "issue",
            "list",
            "--repo",
            slug,
            "--state",
            "all",
            "--search",
            f'in:title "{title}"',
            "--json",
            "number,title,state",
        ]
    )
    return [i for i in json.loads(result.stdout or "[]") if i["title"] == title]


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = _gh(args)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {result.stderr}")
    return result
