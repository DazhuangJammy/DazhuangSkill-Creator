#!/usr/bin/env python3
"""生成给人看的正式评估报告 HTML。"""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aggregate_benchmark import calculate_stats, format_config_label
from scripts.utils import (
    configure_utf8_stdio,
    load_structured_data,
    read_utf8_text,
    summarize_evaluation_plan,
    write_utf8_text,
)

configure_utf8_stdio()

METADATA_FILES = {"transcript.md", "user_notes.md", "metrics.json"}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".yaml", ".yml", ".xml", ".html", ".css", ".sh", ".rb", ".go", ".rs",
    ".java", ".c", ".cpp", ".h", ".hpp", ".sql", ".r", ".toml",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MIME_OVERRIDES = {
    ".svg": "image/svg+xml",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def default_companion_path(primary_output: Path, companion_name: str) -> Path:
    """Choose a stable sibling path for the companion HTML artifact."""
    if primary_output.name == companion_name:
        return primary_output
    return primary_output.with_name(companion_name)


def run_companion_review(
    workspace: Path,
    *,
    skill_name: str,
    benchmark_path: Path | None,
    eval_plan_path: Path | None,
    allow_missing_eval_plan: bool,
    output_path: Path,
) -> None:
    """Generate review.html so report/review stay paired by default."""
    command = [
        sys.executable,
        str(Path(__file__).with_name("generate_review.py")),
        str(workspace),
        "--static",
        str(output_path),
        "--skill-name",
        skill_name,
        "--skip-companion-report",
    ]
    if benchmark_path:
        command.extend(["--benchmark", str(benchmark_path)])
    if eval_plan_path:
        command.extend(["--eval-plan", str(eval_plan_path)])
    if allow_missing_eval_plan:
        command.append("--allow-missing-eval-plan")

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise RuntimeError(output.strip() or "generate_review.py failed")


def get_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in MIME_OVERRIDES:
        return MIME_OVERRIDES[ext]
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def embed_file(path: Path) -> dict:
    ext = path.suffix.lower()
    mime = get_mime_type(path)

    if ext in TEXT_EXTENSIONS:
        try:
            content = read_utf8_text(path, errors="replace")
        except OSError:
            content = "(读取文件失败)"
        return {
            "name": path.name,
            "type": "text",
            "content": content,
        }

    try:
        raw = path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
    except OSError:
        return {"name": path.name, "type": "error", "content": "(读取文件失败)"}

    if ext in IMAGE_EXTENSIONS:
        return {
            "name": path.name,
            "type": "image",
            "mime": mime,
            "data_uri": f"data:{mime};base64,{b64}",
        }
    if ext == ".pdf":
        return {
            "name": path.name,
            "type": "pdf",
            "mime": mime,
            "data_uri": f"data:{mime};base64,{b64}",
        }
    if ext == ".xlsx":
        return {
            "name": path.name,
            "type": "xlsx",
            "mime": mime,
            "data_uri": f"data:{mime};base64,{b64}",
        }
    return {
        "name": path.name,
        "type": "binary",
        "mime": mime,
        "data_uri": f"data:{mime};base64,{b64}",
    }


def _find_runs_recursive(root: Path, current: Path, runs: list[dict]) -> None:
    if not current.is_dir():
        return

    outputs_dir = current / "outputs"
    if outputs_dir.is_dir():
        run = collect_run(root, current)
        if run:
            runs.append(run)
        return

    skip = {"node_modules", ".git", "__pycache__", "skill", "inputs"}
    for child in sorted(current.iterdir()):
        if child.is_dir() and child.name not in skip:
            _find_runs_recursive(root, child, runs)


def find_runs(workspace: Path) -> list[dict]:
    runs: list[dict] = []
    _find_runs_recursive(workspace, workspace, runs)
    runs.sort(key=lambda item: (sort_eval_id(item.get("eval_id")), item.get("configuration", ""), item.get("run_number", 0), item.get("id", "")))
    return runs


def _load_json_candidates(candidates: list[Path]) -> dict:
    for candidate in candidates:
        if not candidate or not candidate.exists() or not candidate.is_file():
            continue
        try:
            payload = json.loads(read_utf8_text(candidate))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _extract_prompt_from_transcript(candidates: list[Path]) -> str:
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            text = read_utf8_text(candidate, errors="replace")
        except OSError:
            continue
        match = re.search(r"## Eval Prompt\n\n([\s\S]*?)(?=\n##|$)", text)
        if match:
            prompt = match.group(1).strip()
            if prompt:
                return prompt
    return ""


def _parse_dimension_lists(metadata: dict) -> tuple[list[str], list[str]]:
    dimension_ids: list[str] = []
    dimension_labels: list[str] = []

    raw_dimension_ids = metadata.get("dimension_ids", [])
    if isinstance(raw_dimension_ids, list):
        for item in raw_dimension_ids:
            if isinstance(item, str) and item.strip() and item.strip() not in dimension_ids:
                dimension_ids.append(item.strip())

    raw_dimension_labels = metadata.get("dimension_labels", [])
    if isinstance(raw_dimension_labels, list):
        for item in raw_dimension_labels:
            if isinstance(item, str) and item.strip() and item.strip() not in dimension_labels:
                dimension_labels.append(item.strip())

    raw_dimensions = metadata.get("dimensions", [])
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

    return dimension_ids, dimension_labels


def collect_run(root: Path, run_dir: Path) -> dict | None:
    output_dir = run_dir / "outputs"
    if not output_dir.is_dir():
        return None

    metadata_candidates = [run_dir / "eval_metadata.json"]
    for parent in run_dir.parents:
        metadata_candidates.append(parent / "eval_metadata.json")
        if parent == root:
            break
    metadata = _load_json_candidates(metadata_candidates)

    prompt = ""
    if metadata:
        raw_prompt = metadata.get("prompt")
        if isinstance(raw_prompt, str) and raw_prompt.strip():
            prompt = raw_prompt.strip()
    if not prompt:
        prompt = _extract_prompt_from_transcript([
            run_dir / "transcript.md",
            output_dir / "transcript.md",
        ])
    if not prompt:
        prompt = "(未找到提示词)"

    eval_name = ""
    for key in ("eval_name", "name", "title"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            eval_name = value.strip()
            break

    configuration = run_dir.parent.name if run_dir.parent != root else ""
    run_number = 0
    if run_dir.name.startswith("run-"):
        try:
            run_number = int(run_dir.name.split("-", 1)[1])
        except ValueError:
            run_number = 0

    outputs: list[dict] = []
    for item in sorted(output_dir.iterdir()):
        if item.is_file() and item.name not in METADATA_FILES:
            outputs.append(embed_file(item))

    grading = _load_json_candidates([
        run_dir / "grading.json",
        run_dir.parent / "grading.json",
    ])

    dimension_ids, dimension_labels = _parse_dimension_lists(metadata)

    run_id = str(run_dir.relative_to(root)).replace("/", "-").replace("\\", "-")
    return {
        "id": run_id,
        "run_dir": str(run_dir),
        "eval_id": metadata.get("eval_id"),
        "eval_name": eval_name,
        "prompt": prompt,
        "configuration": configuration,
        "run_number": run_number,
        "dimension_ids": dimension_ids,
        "dimension_labels": dimension_labels,
        "outputs": outputs,
        "grading": grading,
    }


def sort_eval_id(value: object) -> tuple[int, int | str]:
    if isinstance(value, int):
        return (0, value)
    text = str(value).strip()
    if not text:
        return (2, "")
    if text.isdigit():
        return (0, int(text))
    return (1, text)


def normalize_eval_key(value: object, fallback: str = "") -> str:
    if isinstance(value, int):
        return f"int:{value}"
    text = str(value).strip()
    if text:
        return f"str:{text}"
    return f"fallback:{fallback}"


def infer_result_from_run(run: dict) -> dict:
    grading = run.get("grading") or {}
    summary = grading.get("summary") if isinstance(grading.get("summary"), dict) else {}
    timing = grading.get("timing") if isinstance(grading.get("timing"), dict) else {}
    metrics = grading.get("execution_metrics") if isinstance(grading.get("execution_metrics"), dict) else {}
    return {
        "pass_rate": float(summary.get("pass_rate", 0.0) or 0.0),
        "passed": int(summary.get("passed", 0) or 0),
        "failed": int(summary.get("failed", 0) or 0),
        "total": int(summary.get("total", 0) or 0),
        "time_seconds": float(timing.get("total_duration_seconds", 0.0) or 0.0),
        "tokens": int(metrics.get("output_chars", 0) or 0),
        "tool_calls": int(metrics.get("total_tool_calls", 0) or 0),
        "errors": int(metrics.get("errors_encountered", 0) or 0),
    }


def extract_notes_from_grading(grading: dict) -> list[str]:
    notes: list[str] = []
    if not isinstance(grading, dict):
        return notes
    summary = grading.get("user_notes_summary")
    if isinstance(summary, dict):
        for key in ("uncertainties", "needs_review", "workarounds"):
            values = summary.get(key, [])
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, str) and item.strip() and item.strip() not in notes:
                        notes.append(item.strip())
    feedback = grading.get("eval_feedback")
    if isinstance(feedback, dict):
        overall = feedback.get("overall")
        if isinstance(overall, str) and overall.strip() and overall.strip() not in notes:
            notes.append(overall.strip())
    return notes


def load_evaluation_plan(benchmark: dict | None, eval_plan_path: Path | None) -> dict:
    evaluation_plan = {}
    if benchmark and isinstance(benchmark.get("metadata"), dict):
        evaluation_plan = summarize_evaluation_plan(benchmark["metadata"].get("evaluation_plan"))
    if evaluation_plan:
        return evaluation_plan
    if not eval_plan_path:
        return {}
    try:
        return summarize_evaluation_plan(load_structured_data(eval_plan_path))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def determine_config_order(benchmark: dict, evaluation_plan: dict, runs: list[dict]) -> list[str]:
    config_order: list[str] = []

    variants = evaluation_plan.get("variants", []) if isinstance(evaluation_plan, dict) else []
    if isinstance(variants, list):
        for item in variants:
            if isinstance(item, str) and item.strip() and item.strip() not in config_order:
                config_order.append(item.strip())

    run_summary = benchmark.get("run_summary", {}) if isinstance(benchmark, dict) else {}
    if isinstance(run_summary, dict):
        for item in run_summary:
            if item == "delta":
                continue
            if item not in config_order:
                config_order.append(item)

    benchmark_runs = benchmark.get("runs", []) if isinstance(benchmark, dict) else []
    if isinstance(benchmark_runs, list):
        for item in benchmark_runs:
            if not isinstance(item, dict):
                continue
            config = item.get("configuration")
            if isinstance(config, str) and config and config not in config_order:
                config_order.append(config)

    for run in runs:
        config = run.get("configuration")
        if isinstance(config, str) and config and config not in config_order:
            config_order.append(config)

    return config_order


def build_dimension_lookup(evaluation_plan: dict) -> tuple[dict[str, dict], dict[str, dict], list[dict]]:
    by_id: dict[str, dict] = {}
    by_label: dict[str, dict] = {}
    ordered: list[dict] = []
    for item in evaluation_plan.get("dimensions", []):
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("id", "")).strip()
        label = str(item.get("label") or identifier).strip()
        if not identifier and not label:
            continue
        canonical_id = identifier or label
        normalized = {
            "id": canonical_id,
            "label": label or canonical_id,
            "weight": item.get("weight") if isinstance(item.get("weight"), (int, float)) else None,
            "notes": item.get("notes") if isinstance(item.get("notes"), str) else "",
        }
        by_id[canonical_id] = normalized
        if label:
            by_label[label] = normalized
        ordered.append(normalized)
    return by_id, by_label, ordered


def match_dimensions(raw_ids: list[str], raw_labels: list[str], by_id: dict[str, dict], by_label: dict[str, dict]) -> tuple[list[str], list[str]]:
    matched_ids: list[str] = []
    matched_labels: list[str] = []
    for identifier in raw_ids:
        if identifier in by_id and identifier not in matched_ids:
            matched_ids.append(identifier)
            matched_labels.append(by_id[identifier]["label"])
    for label in raw_labels:
        if label in by_label:
            identifier = by_label[label]["id"]
            if identifier not in matched_ids:
                matched_ids.append(identifier)
                matched_labels.append(by_label[label]["label"])
    return matched_ids, matched_labels


def calculate_dimension_scores(benchmark: dict, evaluation_plan: dict, config_order: list[str]) -> list[dict]:
    benchmark_runs = benchmark.get("runs", []) if isinstance(benchmark, dict) else []
    by_id, by_label, dimensions = build_dimension_lookup(evaluation_plan)
    if not dimensions or not isinstance(benchmark_runs, list):
        return []

    rows: list[dict] = []
    for dimension in dimensions:
        dimension_id = dimension["id"]
        row_scores: dict[str, float | None] = {}
        for config in config_order:
            values: list[float] = []
            for run in benchmark_runs:
                if not isinstance(run, dict) or run.get("configuration") != config:
                    continue
                raw_ids = [item for item in run.get("dimension_ids", []) if isinstance(item, str)]
                raw_labels = [item for item in run.get("dimension_labels", []) if isinstance(item, str)]
                matched_ids, _ = match_dimensions(raw_ids, raw_labels, by_id, by_label)
                if dimension_id not in matched_ids:
                    continue
                result = run.get("result") if isinstance(run.get("result"), dict) else {}
                values.append(float(result.get("pass_rate", 0.0) or 0.0) * 100.0)
            row_scores[config] = round(sum(values) / len(values), 2) if values else None
        rows.append(
            {
                "id": dimension_id,
                "label": dimension["label"],
                "weight": dimension.get("weight"),
                "notes": dimension.get("notes") or "",
                "scores": row_scores,
            }
        )
    return rows


def resolve_config_metrics(benchmark: dict, config_order: list[str]) -> dict[str, dict]:
    run_summary = benchmark.get("run_summary", {}) if isinstance(benchmark, dict) else {}
    benchmark_runs = benchmark.get("runs", []) if isinstance(benchmark, dict) else []
    metrics: dict[str, dict] = {}

    for config in config_order:
        if isinstance(run_summary, dict) and isinstance(run_summary.get(config), dict):
            metrics[config] = run_summary[config]
            continue

        relevant_runs = [
            item for item in benchmark_runs
            if isinstance(item, dict) and item.get("configuration") == config
        ]
        pass_rates = [float(item.get("result", {}).get("pass_rate", 0.0) or 0.0) for item in relevant_runs]
        times = [float(item.get("result", {}).get("time_seconds", 0.0) or 0.0) for item in relevant_runs]
        tokens = [int(item.get("result", {}).get("tokens", 0) or 0) for item in relevant_runs]
        metrics[config] = {
            "pass_rate": calculate_stats(pass_rates),
            "time_seconds": calculate_stats(times),
            "tokens": calculate_stats(tokens),
        }
    return metrics


def calculate_overall_scores(metrics: dict[str, dict], dimension_rows: list[dict], config_order: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}

    if dimension_rows:
        for config in config_order:
            weighted_total = 0.0
            weight_sum = 0.0
            for row in dimension_rows:
                score = row.get("scores", {}).get(config)
                if score is None:
                    continue
                weight = row.get("weight")
                numeric_weight = float(weight) if isinstance(weight, (int, float)) else 1.0
                weighted_total += float(score) * numeric_weight
                weight_sum += numeric_weight
            if weight_sum > 0:
                scores[config] = round(weighted_total / weight_sum, 2)
                continue
            pass_rate = metrics.get(config, {}).get("pass_rate", {}).get("mean", 0.0)
            scores[config] = round(float(pass_rate) * 100.0, 2)
        return scores

    for config in config_order:
        pass_rate = metrics.get(config, {}).get("pass_rate", {}).get("mean", 0.0)
        scores[config] = round(float(pass_rate) * 100.0, 2)
    return scores


def build_score_cards(metrics: dict[str, dict], overall_scores: dict[str, float], config_order: list[str]) -> list[dict]:
    cards: list[dict] = []
    for config in config_order:
        metric = metrics.get(config, {})
        cards.append(
            {
                "id": config,
                "label": format_config_label(config),
                "overall_score": overall_scores.get(config, 0.0),
                "pass_rate": float(metric.get("pass_rate", {}).get("mean", 0.0) or 0.0) * 100.0,
                "time_seconds": float(metric.get("time_seconds", {}).get("mean", 0.0) or 0.0),
                "tokens": float(metric.get("tokens", {}).get("mean", 0.0) or 0.0),
            }
        )
    cards.sort(key=lambda item: (-item["overall_score"], item["time_seconds"], item["tokens"], item["label"]))
    return cards


def build_conclusion(score_cards: list[dict], dimension_rows: list[dict], benchmark: dict) -> list[str]:
    if not score_cards:
        return ["当前没有足够的数据来下结论。"]

    bullets: list[str] = []
    best = score_cards[0]
    bullets.append(
        f"按这次已经对齐好的正式评估计划看，{best['label']} 的综合评分最高，当前是 {best['overall_score']:.1f} / 100。"
    )

    if len(score_cards) > 1:
        runner_up = score_cards[1]
        gap = best["overall_score"] - runner_up["overall_score"]
        if gap >= 0.1:
            bullets.append(
                f"它比第二名 {runner_up['label']} 高 {gap:.1f} 分，所以这次不是模糊领先，而是有清楚差距。"
            )
        else:
            bullets.append(
                f"第一名和第二名只差 {gap:.1f} 分，说明这次更像接近打平，需要重点看分维度证据。"
            )

    fastest = min(score_cards, key=lambda item: item["time_seconds"])
    cheapest = min(score_cards, key=lambda item: item["tokens"])
    bullets.append(
        f"速度最快的是 {fastest['label']}（平均 {fastest['time_seconds']:.1f}s），最省 token 的是 {cheapest['label']}（平均 {cheapest['tokens']:.0f}）。"
    )

    if dimension_rows and len(score_cards) > 1:
        best_id = best["id"]
        runner_up_id = score_cards[1]["id"]
        better_dims: list[str] = []
        weaker_dims: list[str] = []
        for row in dimension_rows:
            best_score = row.get("scores", {}).get(best_id)
            other_score = row.get("scores", {}).get(runner_up_id)
            if best_score is None or other_score is None:
                continue
            if best_score > other_score:
                better_dims.append(row["label"])
            elif best_score < other_score:
                weaker_dims.append(row["label"])
        if better_dims:
            bullets.append(f"它领先最明显的维度是：{'、'.join(better_dims)}。")
        if weaker_dims:
            bullets.append(f"它没有占优的维度是：{'、'.join(weaker_dims)}。")

    delta = benchmark.get("run_summary", {}).get("delta", {}) if isinstance(benchmark, dict) else {}
    if isinstance(delta, dict) and delta:
        pass_delta = delta.get("pass_rate")
        time_delta = delta.get("time_seconds")
        token_delta = delta.get("tokens")
        parts: list[str] = []
        if isinstance(pass_delta, str):
            parts.append(f"通过率差值 {pass_delta}")
        if isinstance(time_delta, str):
            parts.append(f"耗时差值 {time_delta}s")
        if isinstance(token_delta, str):
            parts.append(f"Token 差值 {token_delta}")
        if parts:
            bullets.append("benchmark 给出的主对比差值是：" + "，".join(parts) + "。")

    return bullets


def build_case_map(runs: list[dict], benchmark: dict, evaluation_plan: dict, config_order: list[str]) -> list[dict]:
    benchmark_runs = benchmark.get("runs", []) if isinstance(benchmark, dict) else []
    benchmark_runs = benchmark_runs if isinstance(benchmark_runs, list) else []
    dimension_lookup = {}
    metadata = benchmark.get("metadata", {}) if isinstance(benchmark, dict) else {}
    dimension_coverage = metadata.get("dimension_coverage", {}) if isinstance(metadata, dict) else {}
    coverage_items = dimension_coverage.get("evals", []) if isinstance(dimension_coverage, dict) else []
    if isinstance(coverage_items, list):
        for item in coverage_items:
            if not isinstance(item, dict):
                continue
            dimension_lookup[normalize_eval_key(item.get("eval_id"), str(item.get("eval_name", "")))] = item

    by_id, by_label, _ = build_dimension_lookup(evaluation_plan)
    cases: dict[str, dict] = {}

    def get_case(eval_id: object, fallback_name: str = "") -> dict:
        key = normalize_eval_key(eval_id, fallback_name)
        case = cases.get(key)
        if case:
            return case
        case = {
            "key": key,
            "eval_id": eval_id,
            "eval_name": fallback_name or f"评测 {eval_id if eval_id is not None else '?'}",
            "prompt": "",
            "dimension_ids": [],
            "dimension_labels": [],
            "configurations": {},
        }
        cases[key] = case
        coverage = dimension_lookup.get(key)
        if isinstance(coverage, dict):
            raw_ids = [item for item in coverage.get("dimension_ids", []) if isinstance(item, str)]
            raw_labels = [item for item in coverage.get("dimension_labels", []) if isinstance(item, str)]
            matched_ids, matched_labels = match_dimensions(raw_ids, raw_labels, by_id, by_label)
            case["dimension_ids"] = matched_ids or raw_ids
            case["dimension_labels"] = matched_labels or raw_labels
            if isinstance(coverage.get("eval_name"), str) and coverage["eval_name"].strip():
                case["eval_name"] = coverage["eval_name"].strip()
        return case

    def get_case_config(case: dict, config: str) -> dict:
        configurations = case["configurations"]
        if config in configurations:
            return configurations[config]
        entry = {
            "id": config,
            "label": format_config_label(config),
            "runs": [],
        }
        configurations[config] = entry
        return entry

    bench_index: dict[tuple[str, str, int], dict] = {}
    for item in benchmark_runs:
        if not isinstance(item, dict):
            continue
        config = item.get("configuration")
        if not isinstance(config, str) or not config:
            continue
        run_number = item.get("run_number")
        if not isinstance(run_number, int):
            continue
        eval_id = item.get("eval_id")
        case = get_case(eval_id, str(item.get("eval_name") or ""))
        case_config = get_case_config(case, config)
        raw_ids = [value for value in item.get("dimension_ids", []) if isinstance(value, str)]
        raw_labels = [value for value in item.get("dimension_labels", []) if isinstance(value, str)]
        matched_ids, matched_labels = match_dimensions(raw_ids, raw_labels, by_id, by_label)
        if matched_ids and not case["dimension_ids"]:
            case["dimension_ids"] = matched_ids
        if matched_labels and not case["dimension_labels"]:
            case["dimension_labels"] = matched_labels
        run_entry = {
            "run_number": run_number,
            "result": item.get("result") if isinstance(item.get("result"), dict) else {},
            "expectations": item.get("expectations") if isinstance(item.get("expectations"), list) else [],
            "notes": item.get("notes") if isinstance(item.get("notes"), list) else [],
            "outputs": [],
            "grading": None,
            "missing_outputs": True,
        }
        case_config["runs"].append(run_entry)
        bench_index[(case["key"], config, run_number)] = run_entry

    for run in runs:
        config = run.get("configuration")
        if not isinstance(config, str) or not config:
            continue
        case = get_case(run.get("eval_id"), run.get("eval_name") or "")
        if not case.get("prompt") and isinstance(run.get("prompt"), str):
            case["prompt"] = run["prompt"]
        if not case.get("eval_name") and isinstance(run.get("eval_name"), str) and run["eval_name"]:
            case["eval_name"] = run["eval_name"]
        if run.get("dimension_ids") and not case["dimension_ids"]:
            case["dimension_ids"] = list(run["dimension_ids"])
        if run.get("dimension_labels") and not case["dimension_labels"]:
            case["dimension_labels"] = list(run["dimension_labels"])

        run_number = int(run.get("run_number", 0) or 0)
        key = (case["key"], config, run_number)
        case_config = get_case_config(case, config)
        entry = bench_index.get(key)
        if not entry:
            entry = {
                "run_number": run_number,
                "result": infer_result_from_run(run),
                "expectations": [],
                "notes": [],
                "outputs": [],
                "grading": None,
                "missing_outputs": True,
            }
            case_config["runs"].append(entry)
            bench_index[key] = entry

        if not entry.get("result"):
            entry["result"] = infer_result_from_run(run)
        if not entry.get("expectations") and isinstance(run.get("grading"), dict):
            expectations = run["grading"].get("expectations")
            if isinstance(expectations, list):
                entry["expectations"] = expectations
        if isinstance(run.get("grading"), dict):
            grading_notes = extract_notes_from_grading(run["grading"])
            for note in grading_notes:
                if note not in entry["notes"]:
                    entry["notes"].append(note)
        entry["outputs"] = run.get("outputs", [])
        entry["grading"] = run.get("grading") if isinstance(run.get("grading"), dict) else None
        entry["missing_outputs"] = False
        entry["prompt"] = run.get("prompt")
        if case.get("prompt") in {"", "(未找到提示词)"} and isinstance(run.get("prompt"), str):
            case["prompt"] = run["prompt"]

    ordered_cases: list[dict] = []
    for case in cases.values():
        config_entries: list[dict] = []
        observed_configs = set(case["configurations"])
        for config in config_order:
            if config in observed_configs:
                config_entries.append(case["configurations"][config])
        for config in sorted(observed_configs):
            if config not in config_order:
                config_entries.append(case["configurations"][config])

        for config_entry in config_entries:
            config_entry["runs"].sort(key=lambda item: item.get("run_number", 0))
            pass_rates = [float(item.get("result", {}).get("pass_rate", 0.0) or 0.0) for item in config_entry["runs"]]
            times = [float(item.get("result", {}).get("time_seconds", 0.0) or 0.0) for item in config_entry["runs"]]
            tokens = [int(item.get("result", {}).get("tokens", 0) or 0) for item in config_entry["runs"]]
            config_entry["aggregate"] = {
                "pass_rate": round(sum(pass_rates) / len(pass_rates) * 100.0, 2) if pass_rates else 0.0,
                "time_seconds": round(sum(times) / len(times), 2) if times else 0.0,
                "tokens": round(sum(tokens) / len(tokens), 2) if tokens else 0.0,
                "runs": len(config_entry["runs"]),
            }
        case["config_entries"] = config_entries
        if not case.get("prompt"):
            case["prompt"] = "(未找到提示词)"
        ordered_cases.append(case)

    ordered_cases.sort(key=lambda item: (sort_eval_id(item.get("eval_id")), item.get("eval_name", "")))
    return ordered_cases


def fmt_weight(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    return "-"


def fmt_percent(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}%"


def fmt_seconds(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}s"


def fmt_tokens(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.0f}"


def render_direction(direction: dict) -> str:
    if not isinstance(direction, dict) or not direction:
        return "<div class='empty'>这次没有写这个方向。</div>"
    label = html.escape(direction.get("label", direction.get("id", "未命名方向")))
    notes = html.escape(direction.get("notes", ""))
    weight = direction.get("weight")
    chips = [f"<span class='chip'>{label}</span>"]
    if isinstance(weight, (int, float)):
        chips.append(f"<span class='chip chip-muted'>权重 {float(weight):.2f}</span>")
    body = "".join(chips)
    if notes:
        body += f"<div class='mini-note'>{notes}</div>"
    return body


def render_list(items: list[str], *, empty_text: str) -> str:
    cleaned = [html.escape(item) for item in items if isinstance(item, str) and item.strip()]
    if not cleaned:
        return f"<div class='empty'>{html.escape(empty_text)}</div>"
    return "<ul class='plain-list'>" + "".join(f"<li>{item}</li>" for item in cleaned) + "</ul>"


def render_dimensions(dimensions: list[dict]) -> str:
    if not dimensions:
        return "<div class='empty'>这次没有显式写维度，综合评分会退回总体通过率。</div>"
    rows = []
    for item in dimensions:
        label = html.escape(item.get("label", item.get("id", "未命名维度")))
        weight = item.get("weight")
        notes = html.escape(item.get("notes", ""))
        rows.append(
            "<tr>"
            f"<td>{label}</td>"
            f"<td>{fmt_weight(weight)}</td>"
            f"<td>{notes or '<span class=\'muted\'>未补说明</span>'}</td>"
            "</tr>"
        )
    return (
        "<table class='grid-table'>"
        "<thead><tr><th>维度</th><th>权重</th><th>说明</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_output_file(file_info: dict) -> str:
    name = html.escape(file_info.get("name", "output"))
    kind = file_info.get("type")
    if kind == "text":
        content = file_info.get("content", "")
        preview = content[:1200]
        preview_html = html.escape(preview)
        full_html = html.escape(content)
        truncated = len(content) > len(preview)
        if truncated:
            return (
                "<details class='output-block' open>"
                f"<summary>{name}</summary>"
                f"<pre>{preview_html}</pre>"
                f"<div class='mini-note'>内容较长，下面放完整版本。</div>"
                f"<pre>{full_html}</pre>"
                "</details>"
            )
        return (
            "<details class='output-block' open>"
            f"<summary>{name}</summary>"
            f"<pre>{full_html}</pre>"
            "</details>"
        )
    if kind == "image":
        data_uri = file_info.get("data_uri", "")
        return (
            "<details class='output-block' open>"
            f"<summary>{name}</summary>"
            f"<img class='output-image' src='{data_uri}' alt='{name}'>"
            "</details>"
        )
    if kind in {"pdf", "xlsx", "binary"}:
        data_uri = file_info.get("data_uri", "")
        return (
            "<details class='output-block' open>"
            f"<summary>{name}</summary>"
            f"<a class='download-link' href='{data_uri}' download='{name}'>下载 {name}</a>"
            "</details>"
        )
    content = html.escape(file_info.get("content", "(读取文件失败)"))
    return (
        "<details class='output-block' open>"
        f"<summary>{name}</summary>"
        f"<pre>{content}</pre>"
        "</details>"
    )


def render_expectations(expectations: list[dict]) -> str:
    if not expectations:
        return "<div class='empty'>这轮没有 expectation 细项。</div>"
    rows = []
    for item in expectations:
        if not isinstance(item, dict):
            continue
        text = html.escape(str(item.get("text", "(未写断言)")))
        evidence = html.escape(str(item.get("evidence", "(未写证据)")))
        passed = item.get("passed") is True
        badge = "通过" if passed else "未通过"
        badge_class = "pass" if passed else "fail"
        rows.append(
            "<tr>"
            f"<td>{text}</td>"
            f"<td><span class='status {badge_class}'>{badge}</span></td>"
            f"<td>{evidence}</td>"
            "</tr>"
        )
    return (
        "<table class='grid-table'>"
        "<thead><tr><th>检查点</th><th>结果</th><th>证据</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_case_run(run: dict, open_by_default: bool) -> str:
    result = run.get("result", {}) if isinstance(run.get("result"), dict) else {}
    outputs = run.get("outputs", []) if isinstance(run.get("outputs"), list) else []
    notes = run.get("notes", []) if isinstance(run.get("notes"), list) else []
    expectations = run.get("expectations", []) if isinstance(run.get("expectations"), list) else []
    summary_bits = [
        f"通过率 {fmt_percent(float(result.get('pass_rate', 0.0) or 0.0) * 100.0)}",
        f"耗时 {fmt_seconds(result.get('time_seconds', 0.0))}",
        f"Token {fmt_tokens(result.get('tokens', 0))}",
    ]
    if result.get("total"):
        summary_bits.insert(1, f"断言 {int(result.get('passed', 0))}/{int(result.get('total', 0))}")
    details_attr = " open" if open_by_default else ""
    body_parts = [
        f"<div class='run-metrics'>{''.join(f'<span class=\'chip chip-muted\'>{html.escape(part)}</span>' for part in summary_bits)}</div>",
        "<div class='subsection-title'>输出</div>",
    ]
    if outputs:
        body_parts.append("".join(render_output_file(item) for item in outputs))
    elif run.get("missing_outputs"):
        body_parts.append("<div class='empty'>没找到这轮的 outputs 目录，基础结果还在 review.html 里更容易排查。</div>")
    else:
        body_parts.append("<div class='empty'>这轮没有输出文件。</div>")

    body_parts.extend([
        "<div class='subsection-title'>评分细项</div>",
        render_expectations(expectations),
        "<div class='subsection-title'>补充说明</div>",
        render_list(notes, empty_text="这轮没有额外备注。"),
    ])

    return (
        f"<details class='run-block'{details_attr}>"
        f"<summary>Run {int(run.get('run_number', 0) or 0)} · {' · '.join(html.escape(bit) for bit in summary_bits)}</summary>"
        f"{''.join(body_parts)}"
        "</details>"
    )


def render_case(case: dict) -> str:
    case_title = html.escape(case.get("eval_name") or f"评测 {case.get('eval_id', '?')}")
    prompt = html.escape(case.get("prompt", "(未找到提示词)"))
    dimension_labels = case.get("dimension_labels", []) if isinstance(case.get("dimension_labels"), list) else []
    dimension_html = "".join(f"<span class='chip'>{html.escape(item)}</span>" for item in dimension_labels)
    if not dimension_html:
        dimension_html = "<span class='chip chip-muted'>这题还没标维度</span>"

    config_blocks = []
    for config in case.get("config_entries", []):
        aggregate = config.get("aggregate", {})
        metric_chips = [
            f"<span class='chip chip-muted'>平均通过率 {fmt_percent(aggregate.get('pass_rate'))}</span>",
            f"<span class='chip chip-muted'>平均耗时 {fmt_seconds(aggregate.get('time_seconds'))}</span>",
            f"<span class='chip chip-muted'>平均 Token {fmt_tokens(aggregate.get('tokens'))}</span>",
            f"<span class='chip chip-muted'>运行次数 {int(aggregate.get('runs', 0) or 0)}</span>",
        ]
        run_blocks = []
        for index, run in enumerate(config.get("runs", [])):
            run_blocks.append(render_case_run(run, open_by_default=index == 0))
        if not run_blocks:
            run_blocks.append("<div class='empty'>这个对象在这道题上没有可展示的运行结果。</div>")
        config_blocks.append(
            "<article class='config-card'>"
            f"<div class='config-head'><h4>{html.escape(config.get('label', config.get('id', '未命名对象')))}</h4>{''.join(metric_chips)}</div>"
            f"{''.join(run_blocks)}"
            "</article>"
        )

    return (
        "<section class='case-card'>"
        f"<div class='case-head'><h3>{case_title}</h3><div class='chip-row'>{dimension_html}</div></div>"
        "<div class='subsection-title'>案例提示词</div>"
        f"<pre class='prompt-box'>{prompt}</pre>"
        "<div class='config-grid'>"
        f"{''.join(config_blocks)}"
        "</div>"
        "</section>"
    )


def generate_html(
    workspace: Path,
    skill_name: str,
    benchmark: dict,
    evaluation_plan: dict,
    cases: list[dict],
    score_cards: list[dict],
    dimension_rows: list[dict],
) -> str:
    metadata = benchmark.get("metadata", {}) if isinstance(benchmark, dict) else {}
    comparison_mode = evaluation_plan.get("comparison_mode") or metadata.get("comparison_mode") or "(未写)"
    timestamp = metadata.get("timestamp", "") if isinstance(metadata.get("timestamp", ""), str) else ""
    plan_dimensions = evaluation_plan.get("dimensions", []) if isinstance(evaluation_plan.get("dimensions"), list) else []
    case_plan = evaluation_plan.get("case_plan", {}) if isinstance(evaluation_plan.get("case_plan"), dict) else {}
    report_requirements = evaluation_plan.get("report_requirements", {}) if isinstance(evaluation_plan.get("report_requirements"), dict) else {}
    out_of_scope = evaluation_plan.get("out_of_scope", []) if isinstance(evaluation_plan.get("out_of_scope"), list) else []
    notes = benchmark.get("notes", []) if isinstance(benchmark.get("notes"), list) else []
    conclusion = build_conclusion(score_cards, dimension_rows, benchmark)

    plan_summary_rows = [
        ("比较方式", html.escape(comparison_mode)),
        ("评测对象", html.escape(" / ".join(format_config_label(item) for item in evaluation_plan.get("variants", []) if isinstance(item, str)) or "(未写)")),
        ("实际案例数", str(len(cases))),
        ("计划案例数", html.escape(str(case_plan.get("sample_count"))) if isinstance(case_plan.get("sample_count"), int) else "(未写)"),
        ("盲评", "是" if case_plan.get("blind_review") is True else "否" if case_plan.get("blind_review") is False else "(未写)"),
        ("生成时间", html.escape(timestamp or "(未写)")),
    ]

    score_rows = []
    for card in score_cards:
        score_rows.append(
            "<tr>"
            f"<td>{html.escape(card['label'])}</td>"
            f"<td>{card['overall_score']:.1f}</td>"
            f"<td>{card['pass_rate']:.1f}%</td>"
            f"<td>{card['time_seconds']:.1f}s</td>"
            f"<td>{card['tokens']:.0f}</td>"
            "</tr>"
        )

    dimension_table = "<div class='empty'>这次没有足够的维度数据，所以分维度评分表暂时留空。</div>"
    if dimension_rows:
        head = "".join(f"<th>{html.escape(card['label'])}</th>" for card in score_cards)
        body_rows = []
        for row in dimension_rows:
            scores = "".join(
                f"<td>{fmt_percent(row.get('scores', {}).get(card['id']))}</td>"
                for card in score_cards
            )
            notes_html = html.escape(row.get("notes", "")) or "<span class='muted'>未补说明</span>"
            body_rows.append(
                "<tr>"
                f"<td>{html.escape(row['label'])}</td>"
                f"<td>{fmt_weight(row.get('weight'))}</td>"
                f"{scores}"
                f"<td>{notes_html}</td>"
                "</tr>"
            )
        dimension_table = (
            "<table class='grid-table'>"
            f"<thead><tr><th>维度</th><th>权重</th>{head}<th>说明</th></tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody>"
            "</table>"
        )

    must_include = report_requirements.get("must_include", []) if isinstance(report_requirements.get("must_include"), list) else []

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(skill_name)} - 评估报告</title>
  <style>
    :root {{
      --bg: #f6f3ec;
      --paper: #fffdf8;
      --panel: #ffffff;
      --border: #ddd4c4;
      --text: #1b1a17;
      --muted: #736f67;
      --accent: #875c3b;
      --accent-soft: #efe4d6;
      --good: #2f6b46;
      --good-bg: #ebf5ee;
      --bad: #a44131;
      --bad-bg: #fdeeea;
      --shadow: 0 14px 40px rgba(79, 58, 33, 0.08);
      --radius: 18px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: "SF Pro Text", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(135, 92, 59, 0.10), transparent 32%),
        linear-gradient(180deg, #faf7f2 0%, var(--bg) 100%);
      line-height: 1.6;
    }}
    a {{ color: var(--accent); }}
    .page {{ max-width: 1380px; margin: 0 auto; padding: 32px 24px 80px; }}
    .hero {{
      background: linear-gradient(140deg, rgba(255,255,255,0.94), rgba(249,244,235,0.96));
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 32px;
      box-shadow: var(--shadow);
    }}
    .eyebrow {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.18em; color: var(--muted); }}
    h1 {{ margin: 10px 0 12px; font-size: clamp(28px, 4vw, 44px); line-height: 1.1; }}
    .hero p {{ margin: 0; color: var(--muted); max-width: 820px; }}
    .hero-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-top: 24px; }}
    .hero-card {{ background: var(--paper); border: 1px solid var(--border); border-radius: 18px; padding: 16px; }}
    .hero-card .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
    .hero-card .value {{ font-size: 28px; font-weight: 700; margin-top: 8px; }}
    .hero-card .hint {{ font-size: 13px; color: var(--muted); margin-top: 6px; }}
    .hero-links {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 22px; }}
    .hero-links a {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
      background: var(--text);
      color: #fff;
      padding: 10px 14px;
      border-radius: 999px;
      font-weight: 600;
    }}
    .hero-links a.secondary {{ background: var(--accent-soft); color: var(--accent); }}
    .toc {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0 0; }}
    .toc a {{
      display: inline-flex;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--border);
      text-decoration: none;
      color: var(--text);
      font-size: 14px;
    }}
    .section {{
      background: rgba(255,255,255,0.92);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
      margin-top: 20px;
      box-shadow: var(--shadow);
    }}
    .section h2 {{ margin: 0 0 10px; font-size: 24px; }}
    .section-intro {{ color: var(--muted); margin: 0 0 18px; }}
    .chip-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 13px;
      font-weight: 600;
    }}
    .chip-muted {{ background: #f4efe6; color: var(--muted); }}
    .mini-note {{ color: var(--muted); font-size: 13px; margin-top: 8px; }}
    .plain-list {{ margin: 0; padding-left: 18px; }}
    .plain-list li + li {{ margin-top: 6px; }}
    .two-col {{ display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr); gap: 18px; }}
    .panel {{ background: var(--paper); border: 1px solid var(--border); border-radius: 18px; padding: 18px; }}
    .grid-table {{ width: 100%; border-collapse: collapse; background: var(--paper); border-radius: 18px; overflow: hidden; }}
    .grid-table th, .grid-table td {{ padding: 12px 14px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
    .grid-table th {{ background: #f0e8dc; font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
    .grid-table tr:last-child td {{ border-bottom: none; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .muted {{ color: var(--muted); }}
    .status {{ display: inline-flex; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .status.pass {{ color: var(--good); background: var(--good-bg); }}
    .status.fail {{ color: var(--bad); background: var(--bad-bg); }}
    .score-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }}
    .score-card {{ background: var(--paper); border: 1px solid var(--border); border-radius: 18px; padding: 18px; }}
    .score-card h3 {{ margin: 0; font-size: 18px; }}
    .score-main {{ font-size: 34px; font-weight: 800; margin-top: 10px; }}
    .score-meta {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }}
    .score-meta .cell {{ background: rgba(255,255,255,0.8); border: 1px solid var(--border); border-radius: 14px; padding: 10px; }}
    .score-meta .cell span {{ display: block; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }}
    .score-meta .cell strong {{ display: block; margin-top: 6px; font-size: 17px; }}
    .case-list {{ display: grid; gap: 18px; }}
    .case-card {{ background: var(--paper); border: 1px solid var(--border); border-radius: 20px; padding: 22px; }}
    .case-head {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 12px; }}
    .case-head h3 {{ margin: 0; font-size: 22px; }}
    .prompt-box {{ background: #171512; color: #f7f0e7; border-radius: 16px; padding: 16px; white-space: pre-wrap; overflow-x: auto; margin: 0; font-size: 14px; }}
    .subsection-title {{ margin: 18px 0 10px; font-weight: 800; font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }}
    .config-grid {{ display: grid; gap: 14px; margin-top: 18px; }}
    .config-card {{ background: rgba(255,255,255,0.9); border: 1px solid var(--border); border-radius: 18px; padding: 18px; }}
    .config-head {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .config-head h4 {{ margin: 0 auto 0 0; font-size: 18px; }}
    .run-block {{ margin-top: 14px; border: 1px solid var(--border); border-radius: 16px; background: #fff; overflow: hidden; }}
    .run-block > summary {{ cursor: pointer; list-style: none; padding: 14px 16px; font-weight: 700; background: #fbf8f2; }}
    .run-block > summary::-webkit-details-marker {{ display: none; }}
    .run-block[open] > summary {{ border-bottom: 1px solid var(--border); }}
    .run-metrics {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 14px 16px 0; }}
    .run-block pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font-family: "SFMono-Regular", Menlo, Monaco, Consolas, monospace; font-size: 13px; }}
    .output-block {{ margin: 12px 16px 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }}
    .output-block > summary {{ cursor: pointer; list-style: none; padding: 10px 12px; font-weight: 700; background: #f8f3ea; }}
    .output-block > summary::-webkit-details-marker {{ display: none; }}
    .output-block pre, .output-block img, .output-block a, .output-block .mini-note {{ display: block; margin: 0; padding: 14px; }}
    .output-image {{ width: 100%; height: auto; object-fit: contain; background: #fff; }}
    .download-link {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
    @media (max-width: 960px) {{
      .page {{ padding: 18px 14px 48px; }}
      .hero, .section {{ padding: 20px; border-radius: 20px; }}
      .two-col {{ grid-template-columns: 1fr; }}
      .score-meta {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 640px) {{
      .score-meta {{ grid-template-columns: 1fr; }}
      .hero-grid {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="hero">
      <div class="eyebrow">Formal Eval Report</div>
      <h1>{html.escape(skill_name)} 评估报告</h1>
      <p>这份是给人看的完整报告：会把本次到底测了什么、按什么标准测、每道题的提示词、各对象的回答、评分证据和最后结论放到一处。基础证据工作台仍然保留在 <code>review.html</code>。</p>
      <div class="hero-grid">
        <div class="hero-card"><div class="label">比较方式</div><div class="value">{html.escape(comparison_mode)}</div><div class="hint">这次不是随便比，是按正式计划锁定的比较拓扑。</div></div>
        <div class="hero-card"><div class="label">实际案例数</div><div class="value">{len(cases)}</div><div class="hint">每个案例都在下面展示提示词与回答。</div></div>
        <div class="hero-card"><div class="label">主维度数</div><div class="value">{len(plan_dimensions)}</div><div class="hint">综合分优先按这些维度折算。</div></div>
        <div class="hero-card"><div class="label">输出标准</div><div class="value">2 HTML</div><div class="hint">评估完成 = review.html + report.html 都要存在。</div></div>
      </div>
      <div class="hero-links">
        <a href="review.html">打开 review.html</a>
        <a class="secondary" href="#cases">直接看案例详情</a>
      </div>
      <nav class="toc">
        <a href="#conclusion">最终结论</a>
        <a href="#plan">测评计划</a>
        <a href="#scoreboard">综合评分</a>
        <a href="#dimensions">分维度评分</a>
        <a href="#cases">案例详情</a>
      </nav>
    </header>

    <section class="section" id="conclusion">
      <h2>最终结论</h2>
      <p class="section-intro">这里只说已经被数据支持的结论，不重新发明新的尺子。</p>
      {render_list(conclusion, empty_text="当前还没有足够的结论。")}
    </section>

    <section class="section" id="plan">
      <h2>本次测评计划</h2>
      <p class="section-intro">先把计划摆出来，再看结果。这样你能知道系统到底是在测什么，不会出现“测完了却不知道在测啥”。</p>
      <div class="two-col">
        <div class="panel">
          <div class="subsection-title">计划摘要</div>
          <table class="grid-table">
            <tbody>
              {''.join(f'<tr><th>{html.escape(label)}</th><td>{value}</td></tr>' for label, value in plan_summary_rows)}
            </tbody>
          </table>
          <div class="subsection-title">主方向</div>
          {render_direction(evaluation_plan.get('primary_direction', {}))}
          <div class="subsection-title">次方向</div>
          {render_direction(evaluation_plan.get('secondary_direction', {}))}
        </div>
        <div class="panel">
          <div class="subsection-title">本次明确不看什么</div>
          {render_list(out_of_scope, empty_text='这次没有显式写 out_of_scope。')}
          <div class="subsection-title">结论必须包含什么</div>
          {render_list(must_include, empty_text='这次没有额外写 report_requirements.must_include。')}
          <div class="subsection-title">案例类型计划</div>
          {render_list(case_plan.get('sample_types', []) if isinstance(case_plan.get('sample_types', []), list) else [], empty_text='这次没有显式写 sample_types。')}
        </div>
      </div>
      <div class="subsection-title">主维度</div>
      {render_dimensions(plan_dimensions)}
    </section>

    <section class="section" id="scoreboard">
      <h2>综合评分总览</h2>
      <p class="section-intro">综合分优先按正式评估计划里的维度权重折算；如果这次没写维度权重，就退回总体通过率。速度和 token 会单独展示，不会偷偷混进同一个黑箱分数。</p>
      <div class="score-strip">
        {''.join(
            f"<article class='score-card'><h3>{html.escape(card['label'])}</h3><div class='score-main'>{card['overall_score']:.1f}</div><div class='chip-row'><span class='chip'>综合评分</span></div><div class='score-meta'><div class='cell'><span>平均通过率</span><strong>{card['pass_rate']:.1f}%</strong></div><div class='cell'><span>平均耗时</span><strong>{card['time_seconds']:.1f}s</strong></div><div class='cell'><span>平均 Token</span><strong>{card['tokens']:.0f}</strong></div><div class='cell'><span>对象</span><strong>{html.escape(card['id'])}</strong></div></div></article>"
            for card in score_cards
        )}
      </div>
      <div class="subsection-title">量化表</div>
      <table class="grid-table">
        <thead><tr><th>对象</th><th>综合评分</th><th>平均通过率</th><th>平均耗时</th><th>平均 Token</th></tr></thead>
        <tbody>{''.join(score_rows)}</tbody>
      </table>
    </section>

    <section class="section" id="dimensions">
      <h2>分维度评分</h2>
      <p class="section-intro">这张表回答的是：每个对象到底赢在了哪些维度，哪些维度没有赢。维度分数来自该维度覆盖到的案例通过率均值。</p>
      {dimension_table}
    </section>

    <section class="section" id="cases">
      <h2>案例详情</h2>
      <p class="section-intro">这里是整份报告里最“有理有据”的部分：每道题的提示词、每个对象的回答、每轮评分细项和证据都在这里。</p>
      <div class="case-list">
        {''.join(render_case(case) for case in cases)}
      </div>
    </section>

    <section class="section">
      <h2>补充说明</h2>
      <p class="section-intro">如果你想回到基础证据工作台继续逐条检查，可以直接打开同目录下的 <code>review.html</code>。</p>
      <div class="two-col">
        <div class="panel">
          <div class="subsection-title">Benchmark 备注</div>
          {render_list(notes, empty_text='benchmark.json 里没有额外备注。')}
        </div>
        <div class="panel">
          <div class="subsection-title">这份 report 和 review 的分工</div>
          <ul class="plain-list">
            <li><strong>review.html</strong>：基础版证据工作台，方便你逐个 run 翻 transcript、outputs、formal grades。</li>
            <li><strong>report.html</strong>：给人看的完整版，把计划、案例、回答、评分和结论串起来。</li>
            <li>两者都必须有；缺一个，都不算这次正式评估完成。</li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="生成给人看的正式评估报告")
    parser.add_argument("workspace", type=Path, help="工作区目录路径")
    parser.add_argument("--skill-name", "-n", default=None, help="报告标题里显示的 skill 名")
    parser.add_argument("--benchmark", type=Path, default=None, help="benchmark.json 路径（默认尝试使用 <workspace>/benchmark.json）")
    parser.add_argument("--eval-plan", type=Path, default=None, help="正式评估计划路径；如果 benchmark 里已有计划摘要，可以不传")
    parser.add_argument("--allow-missing-eval-plan", action="store_true", help="允许在没有正式评估计划时继续生成 report（仅兼容旧数据，默认会直接拦住）")
    parser.add_argument("--output", "-o", type=Path, default=None, help="输出 HTML 路径（默认：<workspace>/report.html）")
    parser.add_argument("--skip-companion-review", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"错误：{workspace} 不是目录", file=sys.stderr)
        sys.exit(1)

    runs = find_runs(workspace)
    if not runs:
        print(f"错误：在 {workspace} 中未找到任何 run", file=sys.stderr)
        sys.exit(1)

    benchmark_path = (args.benchmark or (workspace / "benchmark.json")).resolve()
    if not benchmark_path.exists():
        print(
            "错误：还没找到 benchmark.json。"
            " 先跑 aggregate_benchmark.py，再生成 report.html。",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        benchmark = json.loads(read_utf8_text(benchmark_path))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"错误：benchmark.json 读取失败：{exc}", file=sys.stderr)
        sys.exit(1)

    evaluation_plan = load_evaluation_plan(benchmark, args.eval_plan.resolve() if args.eval_plan else None)
    if not evaluation_plan and not args.allow_missing_eval_plan:
        print(
            "错误：还没找到正式评估计划。"
            " 先完成前置对齐，并准备好 evals/eval-plan.json，"
            "再生成 report；如果你只是在兼容旧 benchmark，"
            "请显式加 --allow-missing-eval-plan。",
            file=sys.stderr,
        )
        sys.exit(1)

    skill_name = args.skill_name
    if not skill_name and isinstance(benchmark.get("metadata"), dict):
        raw_name = benchmark["metadata"].get("skill_name")
        if isinstance(raw_name, str) and raw_name.strip():
            skill_name = raw_name.strip()
    if not skill_name:
        skill_name = workspace.name.replace("-workspace", "")

    config_order = determine_config_order(benchmark, evaluation_plan, runs)
    metrics = resolve_config_metrics(benchmark, config_order)
    dimension_rows = calculate_dimension_scores(benchmark, evaluation_plan, config_order)
    overall_scores = calculate_overall_scores(metrics, dimension_rows, config_order)
    score_cards = build_score_cards(metrics, overall_scores, config_order)
    cases = build_case_map(runs, benchmark, evaluation_plan, config_order)

    html_output = generate_html(
        workspace,
        skill_name,
        benchmark,
        evaluation_plan,
        cases,
        score_cards,
        dimension_rows,
    )

    output_path = (args.output or (workspace / "report.html")).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_text(output_path, html_output)
    if not args.skip_companion_review:
        companion_review = default_companion_path(output_path, "review.html")
        try:
            run_companion_review(
                workspace,
                skill_name=skill_name,
                benchmark_path=benchmark_path,
                eval_plan_path=args.eval_plan.resolve() if args.eval_plan else None,
                allow_missing_eval_plan=args.allow_missing_eval_plan,
                output_path=companion_review,
            )
        except RuntimeError as exc:
            try:
                output_path.unlink()
            except OSError:
                pass
            print(
                "错误：report.html 已回滚，因为 companion review.html 生成失败。\n"
                + str(exc),
                file=sys.stderr,
            )
            sys.exit(1)
    print(f"\n  正式报告已写入：{output_path}\n")
    if not args.skip_companion_review:
        print(f"  companion review 已写入：{default_companion_path(output_path, 'review.html')}\n")


if __name__ == "__main__":
    main()
