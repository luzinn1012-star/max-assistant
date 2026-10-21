"""Run the phase 2.5 quality gates without controlling Windows or live LLMs."""

from __future__ import annotations

import ast
import importlib.metadata
import io
import json
import platform
import re
import subprocess
import sys
import time
import unittest
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks.local import benchmark

ROOT = Path(__file__).resolve().parent.parent


def execute(name: str, arguments: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    command = [sys.executable, *arguments]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    row = {
        "command": ["python", *arguments],
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "duration_seconds": time.perf_counter() - started,
    }
    if name == "pytest":
        match = re.search(r"(\d+) passed(?:, (\d+) subtests passed)?", result.stdout)
        row["test_counts"] = (
            {"passed": int(match[1]), "subtests_passed": int(match[2] or 0)} if match else {}
        )
    print(json.dumps({"check": name, **row}), flush=True)
    if result.returncode:
        print(result.stdout[-6000:] + result.stderr[-6000:], file=sys.stderr)
    return row


def legacy_validation() -> dict[str, Any]:
    manifest = json.loads((ROOT / "tests/legacy_manifest.json").read_text(encoding="utf-8"))
    suite = unittest.TestSuite()
    preserved = 0
    for entry in manifest["files"]:
        path = ROOT / entry["current_path"]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = sorted(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        )
        if names != entry["test_methods"]:
            raise ValueError("Legacy test inventory changed: " + entry["current_path"])
        module = entry["current_path"].removesuffix(".py").replace("/", ".")
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
        preserved += len(names)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return {
        "count": result.testsRun,
        "original_methods_preserved": preserved,
        "passed": result.wasSuccessful() and result.testsRun == 142 and preserved == 142,
        "failures": len(result.failures),
        "errors": len(result.errors),
    }


def main() -> int:
    checks = {}
    for name, args in {
        "dependencies": ["-m", "pip", "check"],
        "ruff": ["-m", "ruff", "check", "."],
        "format": ["-m", "ruff", "format", "--check", "."],
        "type_check": ["-m", "mypy"],
        "pre_commit": ["-m", "pre_commit", "run", "--all-files"],
        "pytest": [
            "-m",
            "pytest",
            "--cov",
            "--cov-report=term-missing",
            "--cov-report=json",
            "--cov-report=xml",
            "--junitxml=data/hardening-tests.xml",
            "-q",
        ],
    }.items():
        checks[name] = execute(name, args)
    legacy = legacy_validation()
    coverage_path = ROOT / "data/coverage.json"
    totals = (
        json.loads(coverage_path.read_text(encoding="utf-8"))["totals"]
        if coverage_path.exists()
        else {}
    )
    junit = ROOT / "data/hardening-tests.xml"
    suites = list(ET.parse(junit).getroot().iter("testsuite")) if junit.exists() else []
    tests = {
        name: sum(int(suite.get(name, "0")) for suite in suites)
        for name in ("tests", "failures", "errors", "skipped")
    }
    tests["junit_cases"] = tests.pop("tests")
    tests.update(checks["pytest"].get("test_counts", {}))
    tests["count"] = tests.get("passed", 0) + tests["failures"] + tests["errors"] + tests["skipped"]
    report: dict[str, Any] = {
        "phase": "2.5",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.system(),
        "checks": checks,
        "tests": tests,
        "legacy_tests": legacy,
        "coverage": {
            "line_percent": 100
            * totals.get("covered_lines", 0)
            / max(1, totals.get("num_statements", 0)),
            "combined_line_branch_percent": totals.get("percent_covered"),
            "covered_lines": totals.get("covered_lines"),
            "statements": totals.get("num_statements"),
            "covered_branches": totals.get("covered_branches"),
            "branches": totals.get("num_branches"),
            "minimum_combined_percent": 80,
        },
        "tools": {
            name: importlib.metadata.version(name)
            for name in ("ruff", "mypy", "pytest", "pytest-cov", "pre-commit")
        },
        "benchmark": benchmark(),
        "windows_validation": {
            "execution": "adapters_and_mocks",
            "real_actions_executed": False,
            "prior_real_evidence": "real-windows-validation.json",
        },
        "providers": {
            "live_inference_executed": False,
            "fallback": "covered by preserved and new tests",
        },
        "ci": {
            "workflow": ".github/workflows/quality.yml",
            "platform": "windows-latest",
            "python": ["3.12", "3.13"],
            "remote_execution": "not measured by this local validator",
        },
        "pre_commit_hook_installed": (ROOT / ".git/hooks/pre-commit").is_file(),
        "test_groups": ["unit", "integration", "windows", "providers"],
        "result_contracts": ["IntentResult", "SkillResult", "ProviderResult"],
        "errors": [
            "ProviderUnavailable",
            "SkillExecutionError",
            "PermissionDenied",
            "ConfirmationRequired",
            "AppNotFound",
            "InvalidParameter",
        ],
        "scope": {"new_skills": False, "phase3_started": False},
    }
    report["passed"] = (
        all(row["passed"] for row in checks.values())
        and legacy["passed"]
        and tests.get("failures", 0) == tests.get("errors", 0) == 0
    )
    (ROOT / "phase2-hardening-validation.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "tests": tests,
                "legacy": legacy,
                "coverage": report["coverage"],
            }
        ),
        flush=True,
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
