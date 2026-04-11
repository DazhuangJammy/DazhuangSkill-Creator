#!/usr/bin/env python3
"""Regression test: benchmark aggregation should require eval-plan.json by default."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable

    with tempfile.TemporaryDirectory(prefix="aggregate_benchmark_requires_plan_test_") as tmp:
        tmp_path = Path(tmp)
        benchmark_dir = tmp_path / "workspace" / "iteration-1"

        write_json(
            benchmark_dir / "eval-0" / "eval_metadata.json",
            {
                "eval_id": 0,
                "eval_name": "真实案例 A",
            },
        )
        write_json(
            benchmark_dir / "eval-0" / "with_skill" / "run-1" / "grading.json",
            {
                "summary": {"pass_rate": 1.0, "passed": 2, "failed": 0, "total": 2},
                "expectations": [],
                "execution_metrics": {"total_tool_calls": 3, "errors_encountered": 0},
                "timing": {"total_duration_seconds": 4.2},
                "user_notes_summary": {"uncertainties": [], "needs_review": [], "workarounds": []},
            },
        )
        write_json(
            benchmark_dir / "eval-0" / "without_skill" / "run-1" / "grading.json",
            {
                "summary": {"pass_rate": 0.5, "passed": 1, "failed": 1, "total": 2},
                "expectations": [],
                "execution_metrics": {"total_tool_calls": 4, "errors_encountered": 0},
                "timing": {"total_duration_seconds": 5.7},
                "user_notes_summary": {"uncertainties": [], "needs_review": [], "workarounds": []},
            },
        )

        blocked = run(
            [
                python_cmd,
                str(root / "scripts" / "aggregate_benchmark.py"),
                str(benchmark_dir),
                "--skill-name",
                "musk-skill",
            ],
            cwd=root,
        )
        blocked_output = blocked.stdout + blocked.stderr
        assert_true(blocked.returncode != 0, "aggregate_benchmark should fail without eval-plan by default")
        assert_true("正式评估计划" in blocked_output, "missing-plan error should mention 正式评估计划")

        allowed = run(
            [
                python_cmd,
                str(root / "scripts" / "aggregate_benchmark.py"),
                str(benchmark_dir),
                "--skill-name",
                "musk-skill",
                "--allow-missing-eval-plan",
            ],
            cwd=root,
        )
        allowed_output = allowed.stdout + allowed.stderr
        assert_true(allowed.returncode == 0, f"aggregate_benchmark should allow legacy mode: {allowed_output}")

        benchmark_json = json.loads((benchmark_dir / "benchmark.json").read_text(encoding="utf-8"))
        metadata = benchmark_json.get("metadata", {})
        assert_true("evaluation_plan" not in metadata, "legacy benchmark should not invent evaluation_plan metadata")

    print("PASS: aggregate benchmark requires eval-plan regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
