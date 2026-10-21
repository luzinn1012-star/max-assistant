"""Reproducible synthetic benchmark: no real Windows, network or LLM calls."""

from __future__ import annotations

import argparse
import json
import logging
import math
import platform
import statistics
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import Settings
from core.assistant import Assistant
from core.normalizer import normalize
from skills.bootstrap import build_registry
from tests.phase2_doubles import FakeAudio, FakeWindows, SpyBrain


def distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min_ms": ordered[0],
        "median_ms": statistics.median(ordered),
        "mean_ms": statistics.mean(ordered),
        "p95_ms": ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)],
        "max_ms": ordered[-1],
    }


def measure(operation: Callable[[], Any], samples: int, warmup: int) -> dict[str, float]:
    for _ in range(warmup):
        operation()
    values = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        operation()
        values.append((time.perf_counter_ns() - start) / 1_000_000)
    return distribution(values)


def benchmark(samples: int = 5000, warmup: int = 200) -> dict[str, Any]:
    if samples < 1 or warmup < 0:
        raise ValueError("samples must be positive and warmup must be nonnegative")
    settings = Settings()
    backend, audio = FakeWindows(), FakeAudio()
    providers = {"codex": SpyBrain("codex"), "ollama": SpyBrain("ollama")}
    assistant = Assistant(settings, providers, build_registry(settings, backend, lambda: audio))
    logger = logging.getLogger("max")
    old_disabled = logger.disabled
    logger.disabled = True
    try:
        result = {
            "normalizer": measure(lambda: normalize("Max, abra a calculadora."), samples, warmup),
            "router": measure(
                lambda: assistant.local.router.route("abra a calculadora"), samples, warmup
            ),
            "local_dispatch": measure(
                lambda: assistant.ask("Max, abra a calculadora."), samples, warmup
            ),
        }
        assert all(
            not provider.ask_calls and provider.health_calls == 0 for provider in providers.values()
        )
    finally:
        logger.disabled = old_disabled
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "execution": "test_doubles",
        "python": platform.python_version(),
        "platform": platform.system(),
        "samples": samples,
        "warmup": warmup,
        "clock": "perf_counter_ns",
        "logging": "disabled for measurement",
        "metrics": result,
        "local_provider_calls": 0,
        "real_windows_launch_measured": False,
        "real_provider_latency_measured": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 1 or args.warmup < 0:
        parser.error("samples must be positive and warmup nonnegative")
    result = benchmark(args.samples, args.warmup)
    text = json.dumps(result, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
