"""Command-line entrypoint for consistency-check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from consistency_check import repos as repos_mod
from consistency_check.audit import audit_repo
from consistency_check.filer import file_repo_findings
from consistency_check.report import render_umbrella
from consistency_check.types import FindingStatus, Tier


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="consistency-check")
    sub = parser.add_subparsers(dest="cmd", required=True)

    audit = sub.add_parser("audit", help="Audit one or all repos.")
    audit.add_argument("--repo", help="Audit only this repo (default: all).")
    audit.add_argument("--apply", action="store_true", help="File issues via gh CLI.")
    audit.add_argument(
        "--out",
        type=Path,
        help="Write per-repo umbrella markdown to this directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the requested subcommand; return an exit code."""
    args = _build_parser().parse_args(argv)
    if args.cmd != "audit":
        return 2

    repos = repos_mod.REGISTRY
    if args.repo:
        repos = tuple(r for r in repos if r.name == args.repo)
        if not repos:
            print(f"unknown repo: {args.repo}", file=sys.stderr)  # noqa: T201
            return 2

    exit_code = 0
    for repo in repos:
        findings = audit_repo(repo)
        body = render_umbrella(repo.name, findings)
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"{repo.name}.md").write_text(body, encoding="utf-8")
        else:
            print(body)  # noqa: T201

        if any(f.status == FindingStatus.ERROR for f in findings):
            exit_code = max(exit_code, 2)
        if any(f.status == FindingStatus.FAIL and f.tier == Tier.MUST for f in findings):
            exit_code = max(exit_code, 1)

        try:
            file_repo_findings(repo, findings, apply=args.apply)
        except RuntimeError as exc:
            print(f"filer error: {exc}", file=sys.stderr)  # noqa: T201
            exit_code = max(exit_code, 3)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
