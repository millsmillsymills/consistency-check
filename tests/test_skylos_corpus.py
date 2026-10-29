"""The pilot corpus is balanced, frozen, contained, and never executed by materialization."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
from collections import Counter

import pytest
from assessments.skylos.corpus import input_digest, load_corpus, materialize


def test_corpus_has_fifteen_distinct_pairs_per_language() -> None:
    cases = load_corpus()["cases"]
    assert Counter((case["language"], case["kind"]) for case in cases) == {
        (language, kind): 15 for language in ("python", "go") for kind in ("defect", "control")
    }
    for language in ("python", "go"):
        families = Counter(case["family"] for case in cases if case["language"] == language)
        assert len(families) == 15
        assert set(families.values()) == {2}


def test_python_seeds_are_parseable_without_executing_subprocess_examples() -> None:
    for case in load_corpus()["cases"]:
        for name, source in case["files"].items():
            if name.endswith(".py"):
                ast.parse(source, filename=f"{case['id']}/{name}")


def test_materialization_refuses_overwrite_source_drift_and_links(tmp_path) -> None:
    case = load_corpus()["cases"][0]
    root = tmp_path / "case"
    materialize(case, root)
    marker = (root / ".pilot-unit.json").read_text()
    assert "def transform" not in marker
    assert case["id"] not in marker
    assert "main.py" not in marker
    top = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"], text=True
    )
    assert top.strip() == str(root)
    original = input_digest(root, case)
    with pytest.raises(FileExistsError):
        materialize(case, root)
    assert input_digest(root, case) == original
    (root / "extra.py").write_text("pass\n")
    with pytest.raises(ValueError, match="changed"):
        input_digest(root, case)
    (root / "extra.py").unlink()
    (root / "link.py").symlink_to(tmp_path / "outside.py")
    with pytest.raises(ValueError, match="symlink"):
        input_digest(root, case)


def test_mismatched_case_cannot_relabel_an_existing_input(tmp_path) -> None:
    case, other = load_corpus()["cases"][:2]
    root = tmp_path / "case"
    materialize(case, root)
    with pytest.raises(ValueError, match="registered case"):
        input_digest(root, other)


def test_line_ending_changes_invalidate_exact_input_bytes(tmp_path) -> None:
    case = load_corpus()["cases"][0]
    root = tmp_path / "case"
    materialize(case, root)
    source = root / case["target_file"]
    source.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="changed"):
        input_digest(root, case)


@pytest.mark.parametrize(
    "name", ["../outside.py", "/outside.py", "nested/../../outside.py", "a\\b.py"]
)
def test_case_paths_cannot_escape_materialization(tmp_path, name) -> None:
    case = copy.deepcopy(load_corpus()["cases"][0])
    case["files"][name] = "pass\n"
    with pytest.raises(ValueError, match="paths"):
        materialize(case, tmp_path / "case")
    assert not (tmp_path / "case").exists()


def test_duplicate_sources_cannot_inflate_the_benchmark(tmp_path) -> None:
    corpus = load_corpus()
    corpus["cases"][2]["files"] = corpus["cases"][0]["files"]
    corpus["cases"][2]["target_file"] = corpus["cases"][0]["target_file"]
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus))
    with pytest.raises(ValueError, match="duplicate source"):
        load_corpus(path)


def test_disposable_git_cannot_be_redirected_to_an_owner_checkout(tmp_path, monkeypatch) -> None:
    owner = tmp_path / "owner"
    monkeypatch.setenv("GIT_DIR", str(owner))
    root = tmp_path / "unit"
    materialize(load_corpus()["cases"][0], root)
    assert (root / ".git").is_dir()
    assert not owner.exists()
