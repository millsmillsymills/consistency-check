"""Rules: security (MCP-019, 020)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo

_FORBIDDEN_NAMES = (".env", "credentials.json", "secrets.json", "id_rsa", "private.pem")


def _check_no_secrets(repo: Repo) -> str | None:
    offenders = [
        str(hit.relative_to(repo.path))
        for name in _FORBIDDEN_NAMES
        for hit in repo.path.rglob(name)
        if ".git" not in hit.parts
    ] + [
        str(hit.relative_to(repo.path))
        for hit in [*repo.path.rglob("*.pem"), *repo.path.rglob("*.key")]
        if ".git" not in hit.parts
    ]
    return f"secrets-shaped files in tree: {offenders[:5]}" if offenders else None


def _check_security_disclosure(repo: Repo) -> str | None:
    sec = repo.path / "SECURITY.md"
    if not sec.is_file():
        return "SECURITY.md missing"
    text = sec.read_text(encoding="utf-8", errors="replace").lower()
    if "@" not in text and "advisor" not in text and "disclosure" not in text:
        return "SECURITY.md does not describe a private disclosure path"
    return None


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-019",
        tier=Tier.MUST,
        statement="No secrets in tracked files",
        check=_check_no_secrets,
    ),
    Rule(
        id="MCP-020",
        tier=Tier.MUST,
        statement="SECURITY.md describes disclosure path",
        check=_check_security_disclosure,
    ),
)
