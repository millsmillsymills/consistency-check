"""Rules: CI / release (MCP-014, 015, 016, 017, 018, 025, 026)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.types import Rule, Stage, Tier

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo

# Documents the desired SHA-pinned-with-comment pattern for reference.
_SHA_PINNED = re.compile(r"uses:\s*([a-z0-9_.\-]+/[a-z0-9_.\-]+)@([a-f0-9]{40})\s*(#\s*v\d|$)")
_TAG_USED = re.compile(r"uses:\s*([a-z0-9_.\-]+/[a-z0-9_.\-]+)@(?!([a-f0-9]{40}\b))[^\s]+")


def _read_workflows(repo: Repo) -> list[Path]:
    wf_dir = repo.path / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    return [p for p in wf_dir.iterdir() if p.suffix in {".yml", ".yaml"}]


def _check_ci_workflow(repo: Repo) -> str | None:
    ci = repo.path / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():
        return ".github/workflows/ci.yml missing"
    text = ci.read_text(encoding="utf-8", errors="replace")
    if "push" not in text or "pull_request" not in text:
        return "ci.yml does not trigger on both push and pull_request"
    return None


def _check_security_workflow(repo: Repo) -> str | None:
    wf = repo.path / ".github" / "workflows"
    if (wf / "codeql.yml").is_file() or (wf / "security.yml").is_file():
        return None
    return "no codeql.yml / security.yml workflow"


def _check_dependabot(repo: Repo) -> str | None:
    db = repo.path / ".github" / "dependabot.yml"
    if not db.is_file():
        return ".github/dependabot.yml missing"
    return None


def _check_actions_pinned(repo: Repo) -> str | None:
    offenders: list[str] = []
    for wf in _read_workflows(repo):
        text = wf.read_text(encoding="utf-8", errors="replace")
        offenders.extend(f"{wf.name}: {m.group(0).strip()}" for m in _TAG_USED.finditer(text))
    if offenders:
        return f"unpinned action references: {offenders[:5]}"
    return None


# A bare ``-coverprofile`` / ``-covermode`` only emits a report; it does not
# gate the build. Require a real coverage floor: pytest-cov's
# ``--cov-fail-under`` (Python), a Go coverage-gate (``go-test-coverage`` / a
# ``threshold-total`` check), or a project ``coverage-check`` target/script that
# exits non-zero below a floor.
_COVERAGE_GATE = re.compile(
    r"(?i)cov-fail-under|fail_under|go-test-coverage"
    r"|threshold[-_]?(?:total|file|package)|coverage-check"
)
_VULN_SCAN = re.compile(
    r"(?i)pip-audit|govulncheck|osv-scanner|\btrivy\b|\bgrype\b|dependency-review|\bsnyk\b"
)
# ``safety check`` is two ordinary words, so a comment like ``# improve safety
# check`` must not clear this MUST. Count it only inside a workflow ``run:``
# command body — the inline form or an indented ``run: |`` block scalar — never
# in a YAML/shell comment or a sibling step.
_RUN_KEY = re.compile(r"^([ \t]*-?[ \t]*)run:[ \t]*([|>][+-]?)?[ \t]*(.*)$")
_SAFETY_CHECK = re.compile(r"(?i)\bsafety\s+check\b")
# ``make <target>`` and ``./scripts/x.sh`` in a run: body name the file that
# actually holds the gate. Only these two shapes are followed, one hop deep.
_MAKE_CALL = re.compile(r"(?:^|[\s;&|])make\b([^\n;&|]*)")
_SCRIPT_CALL = re.compile(r"(?:^|[\s;&|])(?:(?:ba)?sh\s+)?([\w./-]+\.(?:sh|bash))\b")
_MAX_FOLLOWED_FILES = 20
_MAX_MAKE_DEPTH = 2


def _strip_comment(line: str) -> str:
    line = re.sub(r"\s#.*$", "", line)
    return "" if line.lstrip().startswith("#") else line


def _run_command_bodies(corpus: str) -> list[str]:
    lines = corpus.splitlines()
    bodies: list[str] = []
    i = 0
    while i < len(lines):
        m = _RUN_KEY.match(lines[i])
        i += 1
        if not m:
            continue
        key_indent, block = len(m.group(1)), m.group(2) is not None
        parts = [] if block else [_strip_comment(m.group(3))]
        while block and i < len(lines):
            line = lines[i]
            if line.strip() and len(line) - len(line.lstrip()) <= key_indent:
                break
            parts.append(_strip_comment(line))
            i += 1
        bodies.append("\n".join(parts))
    return bodies


def _make_targets(body: str) -> list[str]:
    targets: list[str] = []
    for m in _MAKE_CALL.finditer(body):
        targets.extend(w for w in m.group(1).split() if not w.startswith("-") and "=" not in w)
    return targets


def _make_recipe(makefile: str, target: str) -> tuple[str, list[str]]:
    """Return the commands of ``target`` and the prerequisite targets it depends on."""
    recipe: list[str] = []
    prereqs: list[str] = []
    collecting = False
    for line in makefile.splitlines():
        m = re.match(rf"^{re.escape(target)}\s*:=?(.*)$", line)
        if m:
            collecting = True
            prereqs = m.group(1).split()
        elif collecting:
            if line.strip() and not line.startswith((" ", "\t")):
                break
            recipe.append(_strip_comment(line))
    return "\n".join(recipe), prereqs


def _read_makefile(repo: Repo) -> str:
    for name in ("Makefile", "makefile", "GNUmakefile"):
        p = repo.path / name
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    return ""


def _expand_make_targets(makefile: str, targets: list[str]) -> tuple[list[str], list[str]]:
    """Recipes for ``targets`` and their prerequisites, following one extra level."""
    recipes: list[str] = []
    scripts: list[str] = []
    seen: set[str] = set()
    pending = list(targets)
    for _ in range(_MAX_MAKE_DEPTH):
        following, pending = [t for t in pending if t not in seen], []
        seen.update(following)
        for target in following:
            recipe, prereqs = _make_recipe(makefile, target)
            pending.extend(prereqs)
            if recipe.strip():
                recipes.append(recipe)
                scripts.extend(_SCRIPT_CALL.findall(recipe))
    return recipes, scripts


def _indirect_refs(workflows: str, makefile: str) -> tuple[list[str], list[str]]:
    """Recipes and script paths the workflow ``run:`` steps reach."""
    recipes: list[str] = []
    scripts: list[str] = []
    for body in _run_command_bodies(workflows):
        scripts.extend(_SCRIPT_CALL.findall(body))
        target_recipes, target_scripts = _expand_make_targets(makefile, _make_targets(body))
        recipes.extend(target_recipes)
        scripts.extend(target_scripts)
    return recipes, scripts


def _script_text(repo: Repo, rel: str) -> str:
    root = repo.path.resolve()
    candidate = (repo.path / rel).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return ""
    text = candidate.read_text(encoding="utf-8", errors="replace")
    return "\n".join(_strip_comment(line) for line in text.splitlines())


def _ci_corpus(repo: Repo) -> str:
    parts = [wf.read_text(encoding="utf-8", errors="replace") for wf in _read_workflows(repo)]
    pyproject = repo.path / "pyproject.toml"
    if pyproject.is_file():
        parts.append(pyproject.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _coverage_corpus(repo: Repo) -> str:
    """Return the CI corpus plus the Makefile recipes and scripts a ``run:`` step calls.

    A coverage floor is routinely held in the target a workflow shells out to
    rather than in the YAML. Comments are stripped from everything followed, so
    a mention of a gate cannot stand in for one. Scoped to MCP-025: widening the
    corpus for MCP-026 would let an unreached line in an unrelated script clear
    a MUST.
    """
    workflows = "\n".join(
        wf.read_text(encoding="utf-8", errors="replace") for wf in _read_workflows(repo)
    )
    recipes, scripts = _indirect_refs(workflows, _read_makefile(repo))
    followed = [*recipes, *(_script_text(repo, rel) for rel in dict.fromkeys(scripts))]
    return "\n".join([_ci_corpus(repo), *followed[:_MAX_FOLLOWED_FILES]])


def _check_coverage_threshold(repo: Repo) -> str | None:
    if _COVERAGE_GATE.search(_coverage_corpus(repo)):
        return None
    return "CI does not enforce a coverage threshold (cov-fail-under / -covermode)"


def _runs_safety_check(corpus: str) -> bool:
    return any(_SAFETY_CHECK.search(body) for body in _run_command_bodies(corpus))


def _check_vuln_scan(repo: Repo) -> str | None:
    corpus = _ci_corpus(repo)
    if _VULN_SCAN.search(corpus) or _runs_safety_check(corpus):
        return None
    return "CI runs no dependency vulnerability scan (pip-audit / govulncheck)"


# Coarse "any publish step" gate; see rules/deployment.py for archetype-specific patterns.
_PUBLISH_MARKER = re.compile(
    r"docker/build-push-action|docker push|ghcr\.io|wrangler (deploy|publish)"
    r"|softprops/action-gh-release|gh release upload|upload-release-asset|\.mcpb"
)


def _check_release_workflow(repo: Repo) -> str | None:
    release = repo.path / ".github" / "workflows" / "release.yml"
    if not release.is_file():
        return "no .github/workflows/release.yml"
    text = release.read_text(encoding="utf-8", errors="replace")
    if not _PUBLISH_MARKER.search(text):
        return (
            "release.yml publishes no recognizable distribution artifact "
            "(no image push, wrangler deploy, or release-asset upload)"
        )
    return None


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-014",
        tier=Tier.MUST,
        statement="ci.yml triggers on push and pull_request",
        check=_check_ci_workflow,
        min_stage=Stage.S2,
    ),
    Rule(
        id="MCP-015",
        tier=Tier.SHOULD,
        statement="Security workflow present",
        check=_check_security_workflow,
    ),
    Rule(
        id="MCP-016",
        tier=Tier.SHOULD,
        statement="Dependabot configuration present",
        check=_check_dependabot,
    ),
    Rule(
        id="MCP-017",
        tier=Tier.MUST,
        statement="GitHub Actions pinned to SHA",
        check=_check_actions_pinned,
        min_stage=Stage.S2,
    ),
    Rule(
        id="MCP-018",
        tier=Tier.MUST,
        statement="Release workflow builds and publishes the distribution artifact",
        check=_check_release_workflow,
        min_stage=Stage.S4,
    ),
    Rule(
        id="MCP-025",
        tier=Tier.SHOULD,
        statement="CI enforces a coverage threshold",
        check=_check_coverage_threshold,
    ),
    Rule(
        id="MCP-026",
        tier=Tier.MUST,
        statement="CI runs a dependency vulnerability scan",
        check=_check_vuln_scan,
    ),
)
