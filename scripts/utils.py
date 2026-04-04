"""Shared utilities for dazhuangskill-creator scripts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


def get_repo_root() -> Path:
    """Return the dazhuangskill-creator project root."""
    return REPO_ROOT


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text()
    lines = content.split("\n")

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
    text = target.read_text()

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
