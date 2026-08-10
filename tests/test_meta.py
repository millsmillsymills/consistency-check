"""Cross-check that documented rule IDs match implemented rule IDs."""

from __future__ import annotations

import re
from pathlib import Path

from consistency_check.audit import all_rules

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _REPO_ROOT / "docs" / "standards"
_RULE_HEADING = re.compile(r"(?m)^###\s+([A-Z]+-(?:\d{3}|STAGE-[A-Z]+))\b")


def _documented_ids() -> set[str]:
    ids: set[str] = set()
    for f in ("mcp.md", "python.md", "go.md", "mcp-protocol.md", "stages.md"):
        text = (_DOCS / f).read_text(encoding="utf-8")
        ids.update(m.group(1) for m in _RULE_HEADING.finditer(text))
    return ids


def _implemented_ids() -> set[str]:
    return {r.id for r in all_rules()}


def test_no_documented_rule_is_unimplemented() -> None:
    diff = _documented_ids() - _implemented_ids()
    assert not diff, f"documented but not implemented: {sorted(diff)}"


def test_no_implemented_rule_is_undocumented() -> None:
    diff = _implemented_ids() - _documented_ids()
    assert not diff, f"implemented but not documented: {sorted(diff)}"
