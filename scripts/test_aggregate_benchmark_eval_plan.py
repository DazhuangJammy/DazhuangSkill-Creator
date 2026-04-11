#!/usr/bin/env python3
"""Regression test: benchmark aggregation should carry eval-plan.json into outputs."""

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

    with tempfile.TemporaryDirectory(prefix="aggregate_benchmark_eval_plan_test_") as tmp:
        tmp_path = Path(tmp)
        skill_dir = tmp_path / "musk-skill"
        benchmark_dir = tmp_path / "workspace" / "iteration-1"

        write_json(
            skill_dir / "evals" / "eval-plan.json",
            {
                "target": {
                    "skill_name": "musk-skill",
                    "comparison_mode": "with-vs-without",
                    "variants": ["with_skill", "without_skill"],
                },
                "initial_judgement": {
                    "skill_type": "mixed",
                    "recommended_primary_direction": "delivery_effect",
                    "reasoning": "先看 agent 干活效果，再看思维味道。",
                },
                "confirmed_plan": {
                    "primary_direction": {
                        "id": "delivery_effect",
                        "label": "落地效果",
                        "weight": 0.7,
                    },
                    "secondary_direction": {
                        "id": "thinking_imitation",
                        "label": "思维方式模仿",
                        "weight": 0.3,
                    },
                    "dimensions": [
                        {"id": "task_completion", "label": "任务完成度", "weight": 0.4},
                        {"id": "solution_effectiveness", "label": "方案有效性", "weight": 0.3},
                    ],
                    "out_of_scope": ["tone_similarity"],
                    "case_plan": {
                        "sample_types": ["真实业务决策题"],
                        "sample_count": 3,
                        "blind_review": True,
                    },
                    "report_requirements": {
                        "must_include": ["总判断", "分维度判断", "证据"],
                    },
                },
            },
        )

        write_json(
            benchmark_dir / "eval-0" / "eval_metadata.json",
            {
                "eval_id": 0,
                "eval_name": "真实案例 A",
                "dimension_labels": ["任务完成度", "方案有效性"],
            },
        )

        grading_template = {
            "summary": {"pass_rate": 1.0, "passed": 4, "failed": 0, "total": 4},
            "expectations": [],
            "execution_metrics": {"total_tool_calls": 9, "errors_encountered": 0},
            "timing": {"total_duration_seconds": 18.2},
            "user_notes_summary": {"uncertainties": [], "needs_review": [], "workarounds": []},
        }
        write_json(
            benchmark_dir / "eval-0" / "with_skill" / "run-1" / "grading.json",
            grading_template,
        )
        write_json(
            benchmark_dir / "eval-0" / "without_skill" / "run-1" / "grading.json",
            {
                **grading_template,
                "summary": {"pass_rate": 0.5, "passed": 2, "failed": 2, "total": 4},
                "timing": {"total_duration_seconds": 21.4},
            },
        )

        aggregated = run(
            [
                python_cmd,
                str(root / "scripts" / "aggregate_benchmark.py"),
                str(benchmark_dir),
                "--skill-name",
                "musk-skill",
                "--skill-path",
                str(skill_dir),
            ],
            cwd=root,
        )
        output = aggregated.stdout + aggregated.stderr
        assert_true(aggregated.returncode == 0, f"aggregate_benchmark should pass: {output}")

        benchmark_json = json.loads((benchmark_dir / "benchmark.json").read_text(encoding="utf-8"))
        metadata = benchmark_json.get("metadata", {})
        plan = metadata.get("evaluation_plan", {})
        runs = benchmark_json.get("runs", [])

        assert_true(
            plan.get("primary_direction", {}).get("label") == "落地效果",
            "benchmark metadata should carry eval-plan primary direction",
        )
        assert_true(
            metadata.get("evaluation_plan_path", "").endswith("evals/eval-plan.json"),
            "benchmark metadata should record eval-plan path",
        )
        assert_true(
            metadata.get("evaluation_plan", {}).get("report_requirements", {}).get("must_include") == ["总判断", "分维度判断", "证据"],
            "benchmark metadata should carry report requirements",
        )
        assert_true(
            metadata.get("dimension_coverage", {}).get("covered_dimension_ids") == ["solution_effectiveness", "task_completion"],
            "benchmark metadata should record dimension coverage",
        )
        assert_true(runs and runs[0].get("eval_name") == "真实案例 A", "run entries should carry eval_name")
        assert_true(
            "任务完成度" in runs[0].get("dimension_labels", []),
            "run entries should carry dimension labels from eval_metadata",
        )

        benchmark_md = (benchmark_dir / "benchmark.md").read_text(encoding="utf-8")
        assert_true("## 本次怎么评" in benchmark_md, "markdown summary should include evaluation scope")
        assert_true("这次不看：tone_similarity" in benchmark_md, "markdown should show out_of_scope items")
        assert_true("结论必须包含：总判断、分维度判断、证据" in benchmark_md, "markdown should show report requirements")
        assert_true("维度覆盖：已覆盖 2/2 个维度" in benchmark_md, "markdown should show dimension coverage")

    print("PASS: aggregate benchmark eval-plan regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
