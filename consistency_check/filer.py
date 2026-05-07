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
from consistency_check.types import FindingStatus, Tier

if TYPE_CHECKING:
    from consistency_check.types import Finding, Repo


def gh_auth_ok() -> bool:
    """Return True iff `gh auth status` reports an authenticated user."""
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


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

    umbrella_body = render_umbrella(repo.name, findings)
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


def _upsert_issue(
    slug: str,
    title: str,
    body: str,
    labels: tuple[str, ...],
    *,
    edit_if_exists: bool,
) -> None:
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
    result = _run_gh([
        "issue", "list", "--repo", slug, "--state", "all",
        "--search", f'in:title "{title}"',
        "--json", "number,title,state",
    ])
    return [i for i in json.loads(result.stdout or "[]") if i["title"] == title]


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {result.stderr}")
    return result
