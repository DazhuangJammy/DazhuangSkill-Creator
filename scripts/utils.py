"""Shared utilities for dazhuangskill-creator scripts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"
TEXT_READ_ENCODING = "utf-8-sig"
TEXT_WRITE_ENCODING = "utf-8"


def configure_utf8_stdio() -> None:
    """Prefer UTF-8 console output so localized messages survive on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except ValueError:
            # Some redirected streams do not allow reconfiguration.
            continue


def read_utf8_text(path: str | Path, *, errors: str = "strict") -> str:
    """Read repo-managed text files as UTF-8, tolerating an optional BOM."""
    return Path(path).read_text(encoding=TEXT_READ_ENCODING, errors=errors)


def write_utf8_text(path: str | Path, text: str) -> None:
    """Write repo-managed text files as UTF-8 with stable LF newlines."""
    Path(path).write_text(text, encoding=TEXT_WRITE_ENCODING, newline="\n")


def get_repo_root() -> Path:
    """Return the dazhuangskill-creator project root."""
    return REPO_ROOT


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = read_utf8_text(skill_path / "SKILL.md")
    lines = content.splitlines()

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            # Handle YAML multiline indicators (>, |, >-, |-)
            if value in (">", "|", ">-", "|-"):
                continuation_lines: list[str] = []
                i += 1
                while i < len(frontmatter_lines) and (
                    frontmatter_lines[i].startswith("  ")
                    or frontmatter_lines[i].startswith("\t")
                ):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content


def _strip_inline_comment(line: str) -> str:
    """Strip YAML-style comments while respecting quoted strings."""
    in_single = False
    in_double = False
    escaped = False

    for index, char in enumerate(line):
        if char == "\\" and in_double and not escaped:
            escaped = True
            continue
        if char == "'" and not in_double and not escaped:
            in_single = not in_single
        elif char == '"' and not in_single and not escaped:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or line[index - 1].isspace():
                return line[:index].rstrip()
        escaped = False

    return line.rstrip()


def _split_inline_yaml_sequence(value: str) -> list[str]:
    """Split a flow-style YAML sequence body into item strings."""
    items: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    bracket_depth = 0
    brace_depth = 0

    for char in value:
        if char == "\\" and in_double and not escaped:
            escaped = True
            current.append(char)
            continue
        if char == "'" and not in_double and not escaped:
            in_single = not in_single
        elif char == '"' and not in_single and not escaped:
            in_double = not in_double
        elif not in_single and not in_double:
            if char == "[":
                bracket_depth += 1
            elif char == "]":
                if bracket_depth == 0:
                    raise ValueError(f"Invalid inline YAML sequence: [{value}]")
                bracket_depth -= 1
            elif char == "{":
                brace_depth += 1
            elif char == "}":
                if brace_depth == 0:
                    raise ValueError(f"Invalid inline YAML sequence: [{value}]")
                brace_depth -= 1
            elif char == "," and bracket_depth == 0 and brace_depth == 0:
                item = "".join(current).strip()
                if not item:
                    raise ValueError(f"Empty item in inline YAML sequence: [{value}]")
                items.append(item)
                current = []
                continue
        current.append(char)
        escaped = False

    if in_single or in_double or bracket_depth != 0 or brace_depth != 0:
        raise ValueError(f"Unterminated inline YAML sequence: [{value}]")

    tail = "".join(current).strip()
    if not tail:
        raise ValueError(f"Empty item in inline YAML sequence: [{value}]")
    items.append(tail)
    return items


def _parse_scalar(value: str) -> Any:
    """Parse a scalar from a small YAML subset."""
    value = value.strip()
    if value == "":
        return ""

    if value[0] == value[-1] and value[0] in {"'", '"'} and len(value) >= 2:
        quote = value[0]
        inner = value[1:-1]
        if quote == '"':
            inner = bytes(inner, "utf-8").decode("unicode_escape")
        return inner

    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if inner == "":
            return []
        return [_parse_scalar(item) for item in _split_inline_yaml_sequence(inner)]

    lowered = value.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None

    if re.fullmatch(r"[+-]?\d+", value):
        try:
            return int(value)
        except ValueError:
            pass

    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)", value):
        try:
            return float(value)
        except ValueError:
            pass

    return value


def _prepare_yaml_lines(text: str) -> list[tuple[int, str]]:
    prepared: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.lstrip().startswith("#"):
            continue
        cleaned = _strip_inline_comment(raw_line)
        if not cleaned.strip():
            continue
        indent = len(cleaned) - len(cleaned.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(
                f"Unsupported indentation in config.yaml: {raw_line!r}. "
                "Use multiples of 2 spaces."
            )
        prepared.append((indent, cleaned.strip()))
    return prepared


def _parse_yaml_block(
    lines: list[tuple[int, str]],
    start_index: int,
    indent: int,
) -> tuple[Any, int]:
    if start_index >= len(lines):
        return {}, start_index

    first_indent, first_content = lines[start_index]
    if first_indent != indent:
        raise ValueError(
            f"Unexpected indentation: expected {indent} spaces, got {first_indent}"
        )

    if first_content.startswith("- "):
        items: list[Any] = []
        index = start_index
        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ValueError(
                    f"Unexpected indentation under list item: {content!r}"
                )
            if not content.startswith("- "):
                break

            remainder = content[2:].strip()
            index += 1

            if remainder:
                if re.match(r"^[A-Za-z0-9_.-]+\s*:(?:\s|$)", remainder):
                    key, raw_value = remainder.split(":", 1)
                    key = key.strip()
                    raw_value = raw_value.strip()
                    item: dict[str, Any] = {}

                    if raw_value:
                        item[key] = _parse_scalar(raw_value)
                    elif index < len(lines) and lines[index][0] > indent:
                        child, index = _parse_yaml_block(lines, index, lines[index][0])
                        item[key] = child
                    else:
                        item[key] = {}

                    if index < len(lines) and lines[index][0] > indent:
                        child, index = _parse_yaml_block(lines, index, lines[index][0])
                        if not isinstance(child, dict):
                            raise ValueError(
                                "Expected a mapping continuation under list item"
                            )
                        item.update(child)

                    items.append(item)
                    continue

                items.append(_parse_scalar(remainder))
                continue

            if index < len(lines) and lines[index][0] > indent:
                child, index = _parse_yaml_block(lines, index, lines[index][0])
                items.append(child)
            else:
                items.append(None)

        return items, index

    mapping: dict[str, Any] = {}
    index = start_index
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(
                f"Unexpected indentation under mapping entry: {content!r}"
            )
        if content.startswith("- "):
            raise ValueError(
                "Mixed list and mapping indentation is not supported in config.yaml"
            )
        if ":" not in content:
            raise ValueError(f"Invalid YAML line: {content!r}")

        key, remainder = content.split(":", 1)
        key = key.strip()
        remainder = remainder.strip()
        index += 1

        if remainder:
            mapping[key] = _parse_scalar(remainder)
            continue

        if index < len(lines) and lines[index][0] > indent:
            child, index = _parse_yaml_block(lines, index, lines[index][0])
            mapping[key] = child
        else:
            mapping[key] = {}

    return mapping, index


def parse_simple_yaml(text: str) -> Any:
    """Parse a small YAML subset used by dazhuangskill-creator config files."""
    lines = _prepare_yaml_lines(text)
    if not lines:
        return {}
    parsed, next_index = _parse_yaml_block(lines, 0, lines[0][0])
    if next_index != len(lines):
        raise ValueError("Could not parse the full YAML document")
    return parsed


def load_structured_data(path: str | Path) -> Any:
    """Load JSON or a small YAML subset based on file extension."""
    target = Path(path)
    suffix = target.suffix.lower()
    text = read_utf8_text(target)

    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        return parse_simple_yaml(text)

    raise ValueError(
        f"Unsupported file format for {target}. Use .json, .yaml, or .yml."
    )


def extract_eval_items(data: Any) -> list[dict[str, Any]]:
    """Accept either a raw eval list or a wrapper object with an evals key."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("evals"), list):
        return data["evals"]
    raise ValueError(
        "Eval data must be a list of eval items or a mapping with an 'evals' list."
    )


def _clean_optional_text(value: Any) -> str:
    """Normalize a possibly-empty scalar to a stripped string."""
    return value.strip() if isinstance(value, str) else ""


def _normalize_string_list(value: Any) -> list[str]:
    """Keep only non-empty strings from a list-like value."""
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = _clean_optional_text(item)
        if text:
            normalized.append(text)
    return normalized


def _normalize_direction(value: Any) -> dict[str, Any]:
    """Normalize a direction block from eval-plan.json."""
    if not isinstance(value, dict):
        return {}

    direction: dict[str, Any] = {}
    identifier = _clean_optional_text(value.get("id"))
    label = _clean_optional_text(value.get("label")) or identifier
    if identifier:
        direction["id"] = identifier
    if label:
        direction["label"] = label

    weight = value.get("weight")
    if isinstance(weight, (int, float)):
        direction["weight"] = round(float(weight), 4)

    notes = _clean_optional_text(value.get("notes"))
    if notes:
        direction["notes"] = notes

    return direction


def _normalize_dimensions(value: Any) -> list[dict[str, Any]]:
    """Normalize the dimensions block from eval-plan.json."""
    if not isinstance(value, list):
        return []

    dimensions: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized: dict[str, Any] = {}
        identifier = _clean_optional_text(item.get("id"))
        label = _clean_optional_text(item.get("label")) or identifier
        if identifier:
            normalized["id"] = identifier
        if label:
            normalized["label"] = label

        weight = item.get("weight")
        if isinstance(weight, (int, float)):
            normalized["weight"] = round(float(weight), 4)

        notes = _clean_optional_text(item.get("notes"))
        if notes:
            normalized["notes"] = notes

        if normalized:
            dimensions.append(normalized)
    return dimensions


def summarize_evaluation_plan(plan: Any) -> dict[str, Any]:
    """Return a compact, display-friendly summary for an eval-plan payload.

    Accepts either the full `eval-plan.json` shape or an already-summarized
    structure and normalizes the fields we want to carry through benchmark /
    review artifacts.
    """
    if not isinstance(plan, dict):
        return {}

    target = plan.get("target") if isinstance(plan.get("target"), dict) else plan
    confirmed = (
        plan.get("confirmed_plan")
        if isinstance(plan.get("confirmed_plan"), dict)
        else plan
    )
    initial = (
        plan.get("initial_judgement")
        if isinstance(plan.get("initial_judgement"), dict)
        else plan.get("initial_judgement", {})
    )

    summary: dict[str, Any] = {}

    skill_name = _clean_optional_text(target.get("skill_name"))
    if skill_name:
        summary["skill_name"] = skill_name

    comparison_mode = _clean_optional_text(target.get("comparison_mode") or plan.get("comparison_mode"))
    if comparison_mode:
        summary["comparison_mode"] = comparison_mode

    variants = _normalize_string_list(target.get("variants") or plan.get("variants"))
    if variants:
        summary["variants"] = variants

    if isinstance(initial, dict):
        initial_summary: dict[str, Any] = {}
        for key in (
            "skill_type",
            "recommended_primary_direction",
            "recommended_secondary_direction",
            "reasoning",
        ):
            text = _clean_optional_text(initial.get(key))
            if text:
                initial_summary[key] = text
        if initial_summary:
            summary["initial_judgement"] = initial_summary

    primary_direction = _normalize_direction(
        confirmed.get("primary_direction") if isinstance(confirmed, dict) else None
    ) or _normalize_direction(plan.get("primary_direction"))
    if primary_direction:
        summary["primary_direction"] = primary_direction

    secondary_direction = _normalize_direction(
        confirmed.get("secondary_direction") if isinstance(confirmed, dict) else None
    ) or _normalize_direction(plan.get("secondary_direction"))
    if secondary_direction:
        summary["secondary_direction"] = secondary_direction

    dimensions = _normalize_dimensions(
        confirmed.get("dimensions") if isinstance(confirmed, dict) else None
    ) or _normalize_dimensions(plan.get("dimensions"))
    if dimensions:
        summary["dimensions"] = dimensions

    out_of_scope = _normalize_string_list(
        confirmed.get("out_of_scope") if isinstance(confirmed, dict) else None
    ) or _normalize_string_list(plan.get("out_of_scope"))
    if out_of_scope:
        summary["out_of_scope"] = out_of_scope

    case_plan_source = (
        confirmed.get("case_plan") if isinstance(confirmed, dict) and isinstance(confirmed.get("case_plan"), dict) else {}
    )
    case_plan: dict[str, Any] = {}
    sample_types = _normalize_string_list(case_plan_source.get("sample_types"))
    if sample_types:
        case_plan["sample_types"] = sample_types

    sample_count = case_plan_source.get("sample_count")
    if isinstance(sample_count, int):
        case_plan["sample_count"] = sample_count

    blind_review = case_plan_source.get("blind_review")
    if isinstance(blind_review, bool):
        case_plan["blind_review"] = blind_review

    if case_plan:
        summary["case_plan"] = case_plan

    report_requirements_source = (
        confirmed.get("report_requirements")
        if isinstance(confirmed, dict) and isinstance(confirmed.get("report_requirements"), dict)
        else {}
    )
    report_requirements: dict[str, Any] = {}
    must_include = _normalize_string_list(report_requirements_source.get("must_include"))
    if must_include:
        report_requirements["must_include"] = must_include
    if report_requirements:
        summary["report_requirements"] = report_requirements

    return summary


def load_dazhuangskill_creator_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load dazhuangskill-creator defaults from config.yaml when present."""
    target = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not target.exists():
        return {}

    config = load_structured_data(target)
    if not isinstance(config, dict):
        raise ValueError(f"Config file must contain a mapping: {target}")
    return config


def get_config_value(config: dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    """Read a dotted path from a nested config mapping."""
    current: Any = config
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def coalesce(*values: Any) -> Any:
    """Return the first value that is not None and not an empty string."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        return value
    return None
