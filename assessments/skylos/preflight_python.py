"""Verify a new Python environment identity; never collect scanner observations."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from assessments.skylos.environment import file_hash, verify_python_preflight


def main(argv: list[str] | None = None) -> int:
    """Read hashes and package metadata only, with no scanner or target invocation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", required=True, type=Path)
    parser.add_argument("--environment", required=True, type=Path)
    parser.add_argument("--lock", type=Path, default=Path("assessments/skylos/requirements.lock"))
    args = parser.parse_args(argv)
    try:
        verify_python_preflight(args.identity, args.environment, args.lock)
        result = {
            "state": "python_identity_verified",
            "identity_sha256": file_hash(args.identity),
            "go_evaluation": "deferred",
            "collection_authorized": False,
        }
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({"state": "preflight_failed", "error": str(exc)}))  # noqa: T201
        return 2
    print(json.dumps(result))  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
