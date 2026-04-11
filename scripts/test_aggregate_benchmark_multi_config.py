#!/usr/bin/env python3
"""Regression test: benchmark aggregation should render all peer configs."""

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

    with tempfile.TemporaryDirectory(prefix="aggregate_benchmark_multi_config_test_") as tmp:
        tmp_path = Path(tmp)
        skill_dir = tmp_path / "peer-skill"
        benchmark_dir = tmp_path / "workspace" / "iteration-1"

        write_json(
            skill_dir / "evals" / "eval-plan.json",
            {
                "target": {
                    "skill_name": "peer-skill",
                    "comparison_mode": "peer-vs-peer",
                    "variants": ["skill_a", "skill_b", "skill_c"],
                },
                "confirmed_plan": {
                    "primary_direction": {"id": "delivery_effect", "label": "落地效果", "weight": 1.0},
                    "dimensions": [
                        {"id": "task_completion", "label": "任务完成度", "weight": 1.0},
                    ],
                    "report_requirements": {
                        "must_include": ["总判断", "分维度判断"],
                    },
                },
            },
        )

        write_json(
            benchmark_dir / "eval-0" / "eval_metadata.json",
            {
                "eval_id": 0,
                "eval_name": "同题对比 A",
                "dimension_ids": ["task_completion"],
                "dimension_labels": ["任务完成度"],
            },
        )

        for config, pass_rate in (("skill_a", 1.0), ("skill_b", 0.75), ("skill_c", 0.5)):
            write_json(
                benchmark_dir / "eval-0" / config / "run-1" / "grading.json",
                {
                    "summary": {"pass_rate": pass_rate, "passed": int(pass_rate * 4), "failed": 4 - int(pass_rate * 4), "total": 4},
                    "expectations": [],
                    "execution_metrics": {"total_tool_calls": 5, "errors_encountered": 0},
                    "timing": {"total_duration_seconds": 10.0 + (1.0 - pass_rate) * 4},
                    "user_notes_summary": {"uncertainties": [], "needs_review": [], "workarounds": []},
                },
            )

        aggregated = run(
            [
                python_cmd,
                str(root / "scripts" / "aggregate_benchmark.py"),
                str(benchmark_dir),
                "--skill-name",
                "peer-skill",
                "--skill-path",
                str(skill_dir),
            ],
            cwd=root,
        )
        output = aggregated.stdout + aggregated.stderr
        assert_true(aggregated.returncode == 0, f"aggregate_benchmark should pass: {output}")

        benchmark_json = json.loads((benchmark_dir / "benchmark.json").read_text(encoding="utf-8"))
        run_summary = benchmark_json.get("run_summary", {})
        assert_true("skill_a" in run_summary and "skill_b" in run_summary and "skill_c" in run_summary, "run_summary should keep all peer configs")
        assert_true("delta" not in run_summary, "multi-config peer comparison should not invent a two-way delta")

        benchmark_md = (benchmark_dir / "benchmark.md").read_text(encoding="utf-8")
        assert_true("| 指标 | Skill A | Skill B | Skill C |" in benchmark_md, "markdown should render all peer config columns")
        assert_true("比较方式：peer-vs-peer（skill_a, skill_b, skill_c）" in benchmark_md, "markdown should show peer comparison mode")

    print("PASS: aggregate benchmark multi-config regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
