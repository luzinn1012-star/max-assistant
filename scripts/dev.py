"""Run development tools in the project venv, even from a plain git shell."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def interpreter(root: Path = ROOT) -> str:
    for relative in (".venv/Scripts/python.exe", ".venv/bin/python"):
        candidate = root / relative
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] not in {"ruff", "mypy", "pytest"}:
        print("Usage: python scripts/dev.py {ruff|mypy|pytest} [arguments]", file=sys.stderr)
        return 2
    return subprocess.run([interpreter(), "-m", *args], cwd=ROOT, shell=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
