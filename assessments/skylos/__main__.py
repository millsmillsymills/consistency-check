"""Run only frozen synthetic pilot units with a verified isolated toolchain."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from assessments.skylos.corpus import load_corpus, materialize
from assessments.skylos.environment import verify_identity
from assessments.skylos.runner import Runner


def _failure(error: str) -> int:
    print(json.dumps({"state": "preflight_failed", "error": error}))  # noqa: T201
    return 2


def main(argv: list[str] | None = None) -> int:
    """Collect observations; noncomplete units exit 2 without discarding evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="One registered case ID; default: all 60.")
    parser.add_argument(
        "--language", choices=("python", "go"), help="Limit to one frozen language."
    )
    parser.add_argument("--environment", type=Path, default=Path(".scratch/skylos-env"))
    parser.add_argument("--engine", type=Path, default=Path(".scratch/skylos-go"))
    parser.add_argument(
        "--identity", type=Path, default=Path("assessments/skylos/environment-macos-arm64.json")
    )
    parser.add_argument("--input-root", type=Path, default=Path("audit-out/skylos/inputs"))
    parser.add_argument("--output", type=Path, default=Path("audit-out/skylos/observations"))
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument(
        "--sample", type=int, default=0, help="Distinct sampling unit (0 = warm-up)."
    )
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        corpus = load_corpus()
        identity = verify_identity(
            args.identity,
            args.environment,
            args.engine,
            Path("assessments/skylos/requirements.lock"),
        )
        cases = [
            case
            for case in corpus["cases"]
            if (args.case is None or case["id"] == args.case)
            and (args.language is None or case["language"] == args.language)
        ]
        if not cases or args.sample < 0:
            return _failure("unknown case or negative sample")
        runner = Runner(
            args.environment / "bin" / "skylos", args.engine, identity, args.output, args.timeout
        )
        records = []
        for case in cases:
            root = args.input_root / case["id"]
            if not root.exists():
                materialize(case, root)
            record = runner.run(case, root, sample=args.sample, resume=not args.no_resume)
            records.append(record)
            print(  # noqa: T201
                json.dumps(
                    {
                        key: record[key]
                        for key in ("case_id", "sample", "state", "valid_measurement", "resumed")
                    }
                )
            )
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        return _failure(str(exc))
    return 0 if all(record["valid_measurement"] for record in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
