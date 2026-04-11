#!/usr/bin/env python3
"""
把单次运行结果聚合成 benchmark 汇总统计。

读取各个运行目录中的 grading.json，并产出：
- 每个指标的 run_summary（均值、标准差、最小值、最大值）
- 不同配置之间的差值

用法：
    python aggregate_benchmark.py <benchmark_dir>

示例：
    python aggregate_benchmark.py benchmarks/2026-01-15T10-30-00/

脚本支持两种目录布局：

    工作区布局（来自 dazhuangskill-creator 的迭代流程）：
    <benchmark_dir>/
    └── eval-N/
        ├── with_skill/
        │   ├── run-1/grading.json
        │   └── run-2/grading.json
        └── without_skill/
            ├── run-1/grading.json
            └── run-2/grading.json

    旧布局（带 runs/ 子目录）：
    <benchmark_dir>/
    └── runs/
        └── eval-N/
            ├── with_skill/
            │   └── run-1/grading.json
            └── without_skill/
                └── run-1/grading.json
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import (
    configure_utf8_stdio,
    load_structured_data,
    summarize_evaluation_plan,
)

configure_utf8_stdio()


def resolve_evaluation_plan_path(
    benchmark_dir: Path,
    skill_path: str = "",
    explicit_path: Path | None = None,
) -> Path | None:
    """Find the most likely eval-plan.json for this benchmark run."""
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(explicit_path)

    if skill_path:
        skill_dir = Path(skill_path)
        candidates.extend(
            [
                skill_dir / "evals" / "eval-plan.json",
                skill_dir / "eval-plan.json",
            ]
        )

    candidates.extend(
        [
            benchmark_dir / "evals" / "eval-plan.json",
            benchmark_dir / "eval-plan.json",
            benchmark_dir.parent / "eval-plan.json",
        ]
    )

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    return None


def load_evaluation_plan_summary(
    benchmark_dir: Path,
    skill_path: str = "",
    explicit_path: Path | None = None,
) -> tuple[dict, str]:
    """Load and normalize eval-plan.json when available."""
    plan_path = resolve_evaluation_plan_path(benchmark_dir, skill_path, explicit_path)
    if not plan_path:
        return {}, ""

    try:
        payload = load_structured_data(plan_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}, ""

    summary = summarize_evaluation_plan(payload)
    if not summary:
        return {}, ""

    try:
        display_path = str(plan_path.relative_to(benchmark_dir))
    except ValueError:
        display_path = str(plan_path)
    return summary, display_path


def format_config_label(config: str) -> str:
    labels = {
        "with_skill": "使用当前 skill",
        "without_skill": "不使用 skill",
        "new_skill": "新版 skill",
        "old_skill": "旧版 skill",
    }
    if config in labels:
        return labels[config]

    if config.startswith("skill_"):
        suffix = config[len("skill_") :].strip()
        if suffix:
            return f"Skill {suffix.upper()}"

    return config.replace("_", " ")


def calculate_stats(values: list[float]) -> dict:
    """Calculate mean, stddev, min, max for a list of values."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4)
    }


def load_run_results(benchmark_dir: Path) -> dict:
    """
    Load all run results from a benchmark directory.

    Returns dict keyed by config name (e.g. "with_skill"/"without_skill",
    or "new_skill"/"old_skill"), each containing a list of run results.
    """
    # Support both layouts: eval dirs directly under benchmark_dir, or under runs/
    runs_dir = benchmark_dir / "runs"
    if runs_dir.exists():
        search_dir = runs_dir
    elif list(benchmark_dir.glob("eval-*")):
        search_dir = benchmark_dir
    else:
        print(f"No eval directories found in {benchmark_dir} or {benchmark_dir / 'runs'}")
        return {}

    results: dict[str, list] = {}

    for eval_idx, eval_dir in enumerate(sorted(search_dir.glob("eval-*"))):
        metadata_path = eval_dir / "eval_metadata.json"
        eval_metadata: dict = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, encoding="utf-8-sig") as mf:
                    eval_metadata = json.load(mf)
                    eval_id = eval_metadata.get("eval_id", eval_idx)
            except (json.JSONDecodeError, OSError):
                eval_id = eval_idx
        else:
            try:
                eval_id = int(eval_dir.name.split("-")[1])
            except ValueError:
                eval_id = eval_idx

        eval_name = ""
        if isinstance(eval_metadata, dict):
            for key in ("eval_name", "name", "title"):
                value = eval_metadata.get(key)
                if isinstance(value, str) and value.strip():
                    eval_name = value.strip()
                    break

        dimension_ids: list[str] = []
        dimension_labels: list[str] = []
        if isinstance(eval_metadata, dict):
            raw_dimension_ids = eval_metadata.get("dimension_ids", [])
            if isinstance(raw_dimension_ids, list):
                dimension_ids = [
                    item.strip() for item in raw_dimension_ids
                    if isinstance(item, str) and item.strip()
                ]

            raw_dimension_labels = eval_metadata.get("dimension_labels", [])
            if isinstance(raw_dimension_labels, list):
                dimension_labels = [
                    item.strip() for item in raw_dimension_labels
                    if isinstance(item, str) and item.strip()
                ]

            raw_dimensions = eval_metadata.get("dimensions", [])
            if isinstance(raw_dimensions, list):
                for item in raw_dimensions:
                    if not isinstance(item, dict):
                        continue
                    identifier = item.get("id")
                    label = item.get("label") or identifier
                    if isinstance(identifier, str) and identifier.strip() and identifier.strip() not in dimension_ids:
                        dimension_ids.append(identifier.strip())
                    if isinstance(label, str) and label.strip() and label.strip() not in dimension_labels:
                        dimension_labels.append(label.strip())

        # Discover config directories dynamically rather than hardcoding names
        for config_dir in sorted(eval_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            # Skip non-config directories (inputs, outputs, etc.)
            if not list(config_dir.glob("run-*")):
                continue
            config = config_dir.name
            if config not in results:
                results[config] = []

            for run_dir in sorted(config_dir.glob("run-*")):
                run_number = int(run_dir.name.split("-")[1])
                grading_file = run_dir / "grading.json"

                if not grading_file.exists():
                    print(f"Warning: grading.json not found in {run_dir}")
                    continue

                try:
                    with open(grading_file, encoding="utf-8-sig") as f:
                        grading = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON in {grading_file}: {e}")
                    continue

                # Extract metrics
                result = {
                    "eval_id": eval_id,
                    "run_number": run_number,
                    "pass_rate": grading.get("summary", {}).get("pass_rate", 0.0),
                    "passed": grading.get("summary", {}).get("passed", 0),
                    "failed": grading.get("summary", {}).get("failed", 0),
                    "total": grading.get("summary", {}).get("total", 0),
                }
                if eval_name:
                    result["eval_name"] = eval_name
                if dimension_ids:
                    result["dimension_ids"] = dimension_ids
                if dimension_labels:
                    result["dimension_labels"] = dimension_labels

                # Extract timing — check grading.json first, then sibling timing.json
                timing = grading.get("timing", {})
                result["time_seconds"] = timing.get("total_duration_seconds", 0.0)
                timing_file = run_dir / "timing.json"
                if result["time_seconds"] == 0.0 and timing_file.exists():
                    try:
                        with open(timing_file, encoding="utf-8-sig") as tf:
                            timing_data = json.load(tf)
                        result["time_seconds"] = timing_data.get("total_duration_seconds", 0.0)
                        result["tokens"] = timing_data.get("total_tokens", 0)
                    except json.JSONDecodeError:
                        pass

                # Extract metrics if available
                metrics = grading.get("execution_metrics", {})
                result["tool_calls"] = metrics.get("total_tool_calls", 0)
                if not result.get("tokens"):
                    result["tokens"] = metrics.get("output_chars", 0)
                result["errors"] = metrics.get("errors_encountered", 0)

                # Extract expectations — viewer requires fields: text, passed, evidence
                raw_expectations = grading.get("expectations", [])
                for exp in raw_expectations:
                    if "text" not in exp or "passed" not in exp:
                        print(f"Warning: expectation in {grading_file} missing required fields (text, passed, evidence): {exp}")
                result["expectations"] = raw_expectations

                # Extract notes from user_notes_summary
                notes_summary = grading.get("user_notes_summary", {})
                notes = []
                notes.extend(notes_summary.get("uncertainties", []))
                notes.extend(notes_summary.get("needs_review", []))
                notes.extend(notes_summary.get("workarounds", []))
                result["notes"] = notes

                results[config].append(result)

    return results


def aggregate_results(results: dict) -> dict:
    """
    Aggregate run results into summary statistics.

    Returns run_summary with stats for each configuration.
    If and only if there are exactly 2 configurations, also include delta.
    """
    run_summary = {}
    configs = list(results.keys())

    for config in configs:
        runs = results.get(config, [])

        if not runs:
            run_summary[config] = {
                "pass_rate": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "time_seconds": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "tokens": {"mean": 0, "stddev": 0, "min": 0, "max": 0}
            }
            continue

        pass_rates = [r["pass_rate"] for r in runs]
        times = [r["time_seconds"] for r in runs]
        tokens = [r.get("tokens", 0) for r in runs]

        run_summary[config] = {
            "pass_rate": calculate_stats(pass_rates),
            "time_seconds": calculate_stats(times),
            "tokens": calculate_stats(tokens)
        }

    # Delta only makes sense for strict A/B comparisons.
    if len(configs) == 2:
        primary = run_summary.get(configs[0], {})
        baseline = run_summary.get(configs[1], {})
        delta_pass_rate = (
            primary.get("pass_rate", {}).get("mean", 0)
            - baseline.get("pass_rate", {}).get("mean", 0)
        )
        delta_time = (
            primary.get("time_seconds", {}).get("mean", 0)
            - baseline.get("time_seconds", {}).get("mean", 0)
        )
        delta_tokens = (
            primary.get("tokens", {}).get("mean", 0)
            - baseline.get("tokens", {}).get("mean", 0)
        )

        run_summary["delta"] = {
            "pass_rate": f"{delta_pass_rate:+.2f}",
            "time_seconds": f"{delta_time:+.1f}",
            "tokens": f"{delta_tokens:+.0f}"
        }

    return run_summary


def build_dimension_coverage_report(runs: list[dict], evaluation_plan: dict) -> tuple[dict, list[str]]:
    """Validate that eval runs are mapped back to plan dimensions."""
    plan_dimensions = evaluation_plan.get("dimensions", [])
    if not isinstance(plan_dimensions, list) or not plan_dimensions:
        return {}, []

    by_id: dict[str, dict] = {}
    by_label: dict[str, dict] = {}
    ordered_dimension_ids: list[str] = []
    for item in plan_dimensions:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("id", "")).strip()
        label = str(item.get("label") or identifier).strip()
        canonical_id = identifier or label
        if not canonical_id:
            continue
        normalized = {
            "id": canonical_id,
            "label": label or canonical_id,
        }
        by_id[canonical_id] = normalized
        if label:
            by_label[label] = normalized
        if canonical_id not in ordered_dimension_ids:
            ordered_dimension_ids.append(canonical_id)

    if not ordered_dimension_ids:
        return {}, []

    eval_groups: dict[str, dict] = {}
    for run in runs:
        eval_id = run.get("eval_id")
        eval_key = str(eval_id)
        group = eval_groups.setdefault(
            eval_key,
            {
                "eval_id": eval_id,
                "eval_name": run.get("eval_name") or "",
                "raw_dimension_ids": set(),
                "raw_dimension_labels": set(),
            },
        )
        if run.get("eval_name") and not group["eval_name"]:
            group["eval_name"] = run["eval_name"]
        group["raw_dimension_ids"].update(
            item.strip()
            for item in run.get("dimension_ids", [])
            if isinstance(item, str) and item.strip()
        )
        group["raw_dimension_labels"].update(
            item.strip()
            for item in run.get("dimension_labels", [])
            if isinstance(item, str) and item.strip()
        )

    covered_dimension_ids: set[str] = set()
    missing_dimension_tags: list[str] = []
    unknown_dimension_refs: list[str] = []
    coverage_entries: list[dict] = []

    def eval_display_name(group: dict) -> str:
        if group.get("eval_name"):
            return str(group["eval_name"])
        return f"评测 {group.get('eval_id', '?')}"

    for eval_key in sorted(eval_groups, key=lambda item: (str(eval_groups[item].get("eval_id", item)))):
        group = eval_groups[eval_key]
        raw_ids = sorted(group["raw_dimension_ids"])
        raw_labels = sorted(group["raw_dimension_labels"])
        display_name = eval_display_name(group)

        if not raw_ids and not raw_labels:
            missing_dimension_tags.append(display_name)
            coverage_entries.append(
                {
                    "eval_id": group.get("eval_id"),
                    "eval_name": group.get("eval_name") or display_name,
                    "dimension_ids": [],
                    "dimension_labels": [],
                }
            )
            continue

        matched_ids: list[str] = []
        unknown_refs_for_eval: list[str] = []

        for identifier in raw_ids:
            matched = by_id.get(identifier)
            if matched:
                canonical_id = matched["id"]
                if canonical_id not in matched_ids:
                    matched_ids.append(canonical_id)
                continue
            unknown_refs_for_eval.append(identifier)

        for label in raw_labels:
            matched = by_label.get(label)
            if matched:
                canonical_id = matched["id"]
                if canonical_id not in matched_ids:
                    matched_ids.append(canonical_id)
                continue
            unknown_refs_for_eval.append(label)

        matched_labels = [by_id[item]["label"] for item in matched_ids if item in by_id]
        covered_dimension_ids.update(matched_ids)

        coverage_entries.append(
            {
                "eval_id": group.get("eval_id"),
                "eval_name": group.get("eval_name") or display_name,
                "dimension_ids": matched_ids,
                "dimension_labels": matched_labels,
            }
        )

        if unknown_refs_for_eval:
            unknown_dimension_refs.append(
                f"{display_name}：{'、'.join(unknown_refs_for_eval)}"
            )

    missing_dimensions = [
        by_id[identifier]["label"]
        for identifier in ordered_dimension_ids
        if identifier not in covered_dimension_ids
    ]

    errors: list[str] = []
    if missing_dimension_tags:
        errors.append(
            "这些 eval 题还没在 eval_metadata.json 里标明对应维度："
            + "、".join(missing_dimension_tags)
        )
    if unknown_dimension_refs:
        errors.append(
            "这些 eval 题写了正式评估计划里没有的维度："
            + "；".join(unknown_dimension_refs)
        )
    if missing_dimensions:
        errors.append(
            "正式评估计划里的这些维度还没被任何题覆盖："
            + "、".join(missing_dimensions)
        )

    report = {
        "total_dimensions": len(ordered_dimension_ids),
        "covered_dimension_ids": sorted(covered_dimension_ids),
        "covered_dimension_labels": [
            by_id[item]["label"]
            for item in ordered_dimension_ids
            if item in covered_dimension_ids
        ],
        "evals": coverage_entries,
    }
    if missing_dimensions:
        report["missing_dimensions"] = missing_dimensions

    return report, errors


def generate_benchmark(
    benchmark_dir: Path,
    skill_name: str = "",
    skill_path: str = "",
    eval_plan_path: Path | None = None,
) -> dict:
    """
    Generate complete benchmark.json from run results.
    """
    results = load_run_results(benchmark_dir)
    run_summary = aggregate_results(results)
    evaluation_plan, evaluation_plan_display_path = load_evaluation_plan_summary(
        benchmark_dir,
        skill_path=skill_path,
        explicit_path=eval_plan_path,
    )

    # Build runs array for benchmark.json
    runs = []
    for config in results:
        for result in results[config]:
            run_record = {
                "eval_id": result["eval_id"],
                "configuration": config,
                "run_number": result["run_number"],
                "result": {
                    "pass_rate": result["pass_rate"],
                    "passed": result["passed"],
                    "failed": result["failed"],
                    "total": result["total"],
                    "time_seconds": result["time_seconds"],
                    "tokens": result.get("tokens", 0),
                    "tool_calls": result.get("tool_calls", 0),
                    "errors": result.get("errors", 0)
                },
                "expectations": result["expectations"],
                "notes": result["notes"]
            }
            if result.get("eval_name"):
                run_record["eval_name"] = result["eval_name"]
            if result.get("dimension_ids"):
                run_record["dimension_ids"] = result["dimension_ids"]
            if result.get("dimension_labels"):
                run_record["dimension_labels"] = result["dimension_labels"]
            runs.append(run_record)

    # Determine eval IDs from results
    eval_ids = sorted(set(
        r["eval_id"]
        for config in results.values()
        for r in config
    ))

    metadata = {
        "skill_name": skill_name or "<skill-name>",
        "skill_path": skill_path or "<path/to/skill>",
        "executor_model": "<model-name>",
        "analyzer_model": "<model-name>",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evals_run": eval_ids,
        "runs_per_configuration": 3,
    }
    if evaluation_plan:
        metadata["evaluation_plan"] = evaluation_plan
    if evaluation_plan_display_path:
        metadata["evaluation_plan_path"] = evaluation_plan_display_path

    if evaluation_plan:
        dimension_coverage, coverage_errors = build_dimension_coverage_report(
            runs,
            evaluation_plan,
        )
        if dimension_coverage:
            metadata["dimension_coverage"] = dimension_coverage
        if coverage_errors:
            raise ValueError(
                "正式评估计划和当前 eval 题还没对齐好：\n- "
                + "\n- ".join(coverage_errors)
            )

    benchmark = {
        "metadata": metadata,
        "runs": runs,
        "run_summary": run_summary,
        "notes": []  # To be filled by analyzer
    }

    return benchmark


def generate_markdown(benchmark: dict) -> str:
    """Generate human-readable benchmark.md from benchmark data."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]
    evaluation_plan = metadata.get("evaluation_plan", {}) if isinstance(metadata, dict) else {}
    dimension_coverage = metadata.get("dimension_coverage", {}) if isinstance(metadata, dict) else {}

    # Determine config names (excluding "delta")
    configs = [k for k in run_summary if k != "delta"]
    has_delta = len(configs) == 2 and isinstance(run_summary.get("delta"), dict)

    lines = [
        f"# Skill 基准结果：{metadata['skill_name']}",
        "",
        f"**模型**：{metadata['executor_model']}",
        f"**日期**：{metadata['timestamp']}",
        f"**评测项**：{', '.join(map(str, metadata['evals_run']))}（每个配置各运行 {metadata['runs_per_configuration']} 次）",
        "",
    ]

    if evaluation_plan:
        primary = evaluation_plan.get("primary_direction", {})
        secondary = evaluation_plan.get("secondary_direction", {})
        dimensions = evaluation_plan.get("dimensions", [])
        out_of_scope = evaluation_plan.get("out_of_scope", [])
        case_plan = evaluation_plan.get("case_plan", {})
        report_requirements = evaluation_plan.get("report_requirements", {})
        lines.extend([
            "## 本次怎么评",
            "",
        ])
        if metadata.get("evaluation_plan_path"):
            lines.append(f"- 评估计划：`{metadata['evaluation_plan_path']}`")
        if metadata.get("evaluation_plan_path") or primary:
            lines.append("")
        if primary:
            weight = primary.get("weight")
            suffix = f"（权重 {weight:.2f}）" if isinstance(weight, (int, float)) else ""
            lines.append(f"- 主方向：{primary.get('label', primary.get('id', '未命名方向'))}{suffix}")
        if secondary:
            weight = secondary.get("weight")
            suffix = f"（权重 {weight:.2f}）" if isinstance(weight, (int, float)) else ""
            lines.append(f"- 次方向：{secondary.get('label', secondary.get('id', '未命名方向'))}{suffix}")
        if evaluation_plan.get("comparison_mode"):
            variants = ", ".join(evaluation_plan.get("variants", []))
            variant_suffix = f"（{variants}）" if variants else ""
            lines.append(f"- 比较方式：{evaluation_plan['comparison_mode']}{variant_suffix}")
        if dimensions:
            dimension_chunks = []
            for item in dimensions:
                label = item.get("label", item.get("id", "未命名维度"))
                weight = item.get("weight")
                if isinstance(weight, (int, float)):
                    label = f"{label}（{weight:.2f}）"
                dimension_chunks.append(label)
            lines.append(f"- 重点维度：{'、'.join(dimension_chunks)}")
        if out_of_scope:
            lines.append(f"- 这次不看：{'、'.join(out_of_scope)}")
        if case_plan:
            sample_types = case_plan.get("sample_types", [])
            sample_count = case_plan.get("sample_count")
            blind_review = case_plan.get("blind_review")
            case_chunks = []
            if sample_types:
                case_chunks.append(f"样本类型：{'、'.join(sample_types)}")
            if isinstance(sample_count, int):
                case_chunks.append(f"样本数：{sample_count}")
            if isinstance(blind_review, bool):
                case_chunks.append("盲评：是" if blind_review else "盲评：否")
            if case_chunks:
                lines.append(f"- 案例计划：{'；'.join(case_chunks)}")
        must_include = report_requirements.get("must_include", [])
        if must_include:
            lines.append(f"- 结论必须包含：{'、'.join(must_include)}")
        if dimension_coverage:
            covered_count = len(dimension_coverage.get("covered_dimension_labels", []))
            total_count = dimension_coverage.get("total_dimensions", covered_count)
            lines.append(f"- 维度覆盖：已覆盖 {covered_count}/{total_count} 个维度")
            coverage_chunks = []
            for item in dimension_coverage.get("evals", []):
                if not isinstance(item, dict):
                    continue
                eval_name = item.get("eval_name") or f"评测 {item.get('eval_id', '?')}"
                labels = item.get("dimension_labels", [])
                if labels:
                    coverage_chunks.append(f"{eval_name} -> {'、'.join(labels)}")
            if coverage_chunks:
                lines.append(f"- 题目映射：{'；'.join(coverage_chunks)}")
        lines.extend([
            "",
        ])

    summary_headers = ["指标", *[format_config_label(config) for config in configs]]
    if has_delta:
        summary_headers.append("差值")
    lines.extend([
        "## 汇总",
        "",
        "| " + " | ".join(summary_headers) + " |",
        "|" + "|".join(["------"] * len(summary_headers)) + "|",
    ])

    def format_stat(config: str, metric_key: str, *, pct: bool = False, unit: str = "") -> str:
        stat = run_summary.get(config, {}).get(metric_key, {})
        mean = stat.get("mean", 0)
        stddev = stat.get("stddev", 0)
        if pct:
            return f"{mean*100:.0f}% ± {stddev*100:.0f}%"
        return f"{mean:.1f}{unit} ± {stddev:.1f}{unit}"

    delta = run_summary.get("delta", {}) if has_delta else {}
    metric_rows = [
        ("通过率", "pass_rate", True, ""),
        ("耗时", "time_seconds", False, "s"),
        ("Token 数", "tokens", False, ""),
    ]
    for label, metric_key, pct, unit in metric_rows:
        row = [label]
        for config in configs:
            if metric_key == "tokens":
                stat = run_summary.get(config, {}).get(metric_key, {})
                row.append(
                    f"{stat.get('mean', 0):.0f} ± {stat.get('stddev', 0):.0f}"
                )
            else:
                row.append(format_stat(config, metric_key, pct=pct, unit=unit))
        if has_delta:
            delta_value = delta.get(metric_key, "—")
            if metric_key == "time_seconds" and delta_value != "—":
                delta_value = f"{delta_value}s"
            row.append(delta_value)
        lines.append("| " + " | ".join(row) + " |")

    # Notes section
    if benchmark.get("notes"):
        lines.extend([
            "",
            "## 说明",
            ""
        ])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="把 benchmark 运行结果聚合成汇总统计"
    )
    parser.add_argument(
        "benchmark_dir",
        type=Path,
        help="benchmark 目录路径"
    )
    parser.add_argument(
        "--skill-name",
        default="",
        help="当前正在评测的 skill 名称"
    )
    parser.add_argument(
        "--skill-path",
        default="",
        help="当前正在评测的 skill 路径"
    )
    parser.add_argument(
        "--eval-plan",
        type=Path,
        default=None,
        help="正式评估计划路径（默认尝试从 --skill-path/evals/eval-plan.json 自动发现）",
    )
    parser.add_argument(
        "--allow-missing-eval-plan",
        action="store_true",
        help="允许在没有正式评估计划的情况下继续聚合（仅兼容旧数据，默认会直接拦住）",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="benchmark.json 的输出路径（默认：<benchmark_dir>/benchmark.json）"
    )

    args = parser.parse_args()

    if not args.benchmark_dir.exists():
        print(f"未找到目录：{args.benchmark_dir}")
        sys.exit(1)

    evaluation_plan, evaluation_plan_path = load_evaluation_plan_summary(
        args.benchmark_dir,
        skill_path=args.skill_path,
        explicit_path=args.eval_plan,
    )
    if not evaluation_plan and not args.allow_missing_eval_plan:
        print(
            "错误：还没找到正式评估计划。"
            " 先完成前置对齐，并准备好 evals/eval-plan.json，"
            "再运行 aggregate_benchmark.py；如果你只是在兼容旧 benchmark，"
            "请显式加 --allow-missing-eval-plan。",
            file=sys.stderr,
        )
        sys.exit(1)

    # Generate benchmark
    try:
        benchmark = generate_benchmark(
            args.benchmark_dir,
            args.skill_name,
            args.skill_path,
            args.eval_plan,
        )
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        sys.exit(1)

    # Determine output paths
    output_json = args.output or (args.benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    # Write benchmark.json
    with open(output_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(benchmark, f, indent=2)
    print(f"已生成：{output_json}")

    # Write benchmark.md
    markdown = generate_markdown(benchmark)
    with open(output_md, "w", encoding="utf-8", newline="\n") as f:
        f.write(markdown)
    print(f"已生成：{output_md}")

    # Print summary
    run_summary = benchmark["run_summary"]
    configs = [k for k in run_summary if k != "delta"]
    delta = run_summary.get("delta", {})

    print(f"\n汇总：")
    if evaluation_plan_path:
        print(f"  评估计划：   {evaluation_plan_path}")
    for config in configs:
        pr = run_summary[config]["pass_rate"]["mean"]
        label = format_config_label(config)
        print(f"  {label}：{pr*100:.1f}% 通过率")
    if delta:
        print(f"  差值：         {delta.get('pass_rate', '—')}")


if __name__ == "__main__":
    main()
