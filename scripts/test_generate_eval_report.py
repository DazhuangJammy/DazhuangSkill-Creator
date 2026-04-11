#!/usr/bin/env python3
"""Regression test: report.html should expose plan, prompts, answers, and scoring."""

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


def seed_eval_fixture(root: Path) -> tuple[Path, Path]:
    workspace = root / "frontend-workspace" / "iteration-1"
    eval_dir = workspace / "eval-0"
    write_json(
        eval_dir / "eval_metadata.json",
        {
            "eval_id": 0,
            "eval_name": "落地案例 A",
            "prompt": "请把这个首页改得更有产品感，同时保证移动端可用。",
            "dimension_ids": ["task_completion"],
            "dimension_labels": ["任务完成度"],
        },
    )

    for config, answer, pass_rate, note in (
        ("with_skill", "with answer: intentional layout and complete mobile states", 1.0, "状态补齐完整。"),
        ("without_skill", "without answer: generic cards and weak hierarchy", 0.5, "视觉层级偏弱。"),
    ):
        run_dir = eval_dir / config / "run-1"
        outputs_dir = run_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        (outputs_dir / "answer.txt").write_text(answer, encoding="utf-8")
        write_json(
            run_dir / "grading.json",
            {
                "expectations": [
                    {
                        "text": "移动端状态补齐",
                        "passed": pass_rate >= 1.0,
                        "evidence": note,
                    }
                ],
                "summary": {
                    "passed": 1 if pass_rate >= 1.0 else 0,
                    "failed": 0 if pass_rate >= 1.0 else 1,
                    "total": 1,
                    "pass_rate": pass_rate,
                },
                "execution_metrics": {
                    "total_tool_calls": 6,
                    "errors_encountered": 0,
                    "output_chars": 3200,
                },
                "timing": {
                    "total_duration_seconds": 15.0 if config == "with_skill" else 20.0,
                },
                "user_notes_summary": {
                    "uncertainties": [],
                    "needs_review": [],
                    "workarounds": [note],
                },
            },
        )

    benchmark_path = workspace / "benchmark.json"
    write_json(
        benchmark_path,
        {
            "metadata": {
                "skill_name": "frontend-design2",
                "timestamp": "2026-04-11T10:00:00Z",
                "evals_run": [0],
                "runs_per_configuration": 1,
                "evaluation_plan": {
                    "comparison_mode": "with-vs-without",
                    "variants": ["with_skill", "without_skill"],
                    "primary_direction": {
                        "id": "delivery_effect",
                        "label": "落地效果",
                        "weight": 1.0,
                    },
                    "dimensions": [
                        {
                            "id": "task_completion",
                            "label": "任务完成度",
                            "weight": 1.0,
                            "notes": "看页面有没有真正做完整。",
                        }
                    ],
                    "out_of_scope": ["tone_similarity"],
                    "case_plan": {
                        "sample_types": ["真实前端改版题"],
                        "sample_count": 1,
                        "blind_review": False,
                    },
                    "report_requirements": {
                        "must_include": ["总判断", "分维度判断", "证据"],
                    },
                },
                "dimension_coverage": {
                    "total_dimensions": 1,
                    "covered_dimension_ids": ["task_completion"],
                    "covered_dimension_labels": ["任务完成度"],
                    "evals": [
                        {
                            "eval_id": 0,
                            "eval_name": "落地案例 A",
                            "dimension_ids": ["task_completion"],
                            "dimension_labels": ["任务完成度"],
                        }
                    ],
                },
            },
            "runs": [
                {
                    "eval_id": 0,
                    "eval_name": "落地案例 A",
                    "dimension_ids": ["task_completion"],
                    "dimension_labels": ["任务完成度"],
                    "configuration": "with_skill",
                    "run_number": 1,
                    "result": {
                        "pass_rate": 1.0,
                        "passed": 1,
                        "failed": 0,
                        "total": 1,
                        "time_seconds": 15.0,
                        "tokens": 1800,
                        "tool_calls": 6,
                        "errors": 0,
                    },
                    "expectations": [
                        {
                            "text": "移动端状态补齐",
                            "passed": True,
                            "evidence": "状态补齐完整。",
                        }
                    ],
                    "notes": ["状态补齐完整。"],
                },
                {
                    "eval_id": 0,
                    "eval_name": "落地案例 A",
                    "dimension_ids": ["task_completion"],
                    "dimension_labels": ["任务完成度"],
                    "configuration": "without_skill",
                    "run_number": 1,
                    "result": {
                        "pass_rate": 0.5,
                        "passed": 0,
                        "failed": 1,
                        "total": 1,
                        "time_seconds": 20.0,
                        "tokens": 2200,
                        "tool_calls": 5,
                        "errors": 0,
                    },
                    "expectations": [
                        {
                            "text": "移动端状态补齐",
                            "passed": False,
                            "evidence": "视觉层级偏弱。",
                        }
                    ],
                    "notes": ["视觉层级偏弱。"],
                },
            ],
            "run_summary": {
                "with_skill": {
                    "pass_rate": {"mean": 1.0, "stddev": 0.0, "min": 1.0, "max": 1.0},
                    "time_seconds": {"mean": 15.0, "stddev": 0.0, "min": 15.0, "max": 15.0},
                    "tokens": {"mean": 1800.0, "stddev": 0.0, "min": 1800.0, "max": 1800.0},
                },
                "without_skill": {
                    "pass_rate": {"mean": 0.5, "stddev": 0.0, "min": 0.5, "max": 0.5},
                    "time_seconds": {"mean": 20.0, "stddev": 0.0, "min": 20.0, "max": 20.0},
                    "tokens": {"mean": 2200.0, "stddev": 0.0, "min": 2200.0, "max": 2200.0},
                },
                "delta": {
                    "pass_rate": "+0.50",
                    "time_seconds": "-5.0",
                    "tokens": "-400",
                },
            },
            "notes": ["这次只测一题，先看结构。"],
        },
    )

    return workspace, benchmark_path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable

    with tempfile.TemporaryDirectory(prefix="generate_eval_report_test_") as tmp:
        tmp_path = Path(tmp)
        workspace, benchmark_path = seed_eval_fixture(tmp_path)
        report_path = workspace / "report.html"
        generated = run(
            [
                python_cmd,
                str(root / "eval-viewer" / "generate_report.py"),
                str(workspace),
                "--benchmark",
                str(benchmark_path),
                "--output",
                str(report_path),
            ],
            cwd=root,
        )
        output = generated.stdout + generated.stderr
        assert_true(generated.returncode == 0, f"generate_report should pass: {output}")
        assert_true(report_path.exists(), "report.html should be created")
        companion_review = workspace / "review.html"
        assert_true(companion_review.exists(), "direct report generation should auto-create companion review.html")

        html = report_path.read_text(encoding="utf-8")
        review_html = companion_review.read_text(encoding="utf-8")
        assert_true("本次测评计划" in html, "report should include evaluation plan section")
        assert_true("综合评分总览" in html, "report should include score overview")
        assert_true("请把这个首页改得更有产品感" in html, "report should include eval prompt")
        assert_true("with answer: intentional layout" in html, "report should include with-skill answer")
        assert_true("without answer: generic cards" in html, "report should include without-skill answer")
        assert_true("任务完成度" in html, "report should include dimension label")
        assert_true("review.html" in html, "report should mention review companion file")
        assert_true('"evaluation_plan"' in review_html, "companion review should still embed evaluation_plan")

    print("PASS: generate eval report regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
