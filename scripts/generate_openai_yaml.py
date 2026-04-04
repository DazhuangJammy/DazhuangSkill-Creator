#!/usr/bin/env python3
"""
OpenAI YAML 生成器：按需为某个 skill 目录创建 agents/openai.yaml。

用法：
    generate_openai_yaml.py <skill_dir> [--name <skill_name>] [--interface key=value]
"""

import argparse
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import get_config_value, load_dazhuangskill_creator_config

ACRONYMS = {
    "GH",
    "MCP",
    "API",
    "CI",
    "CLI",
    "LLM",
    "PDF",
    "PR",
    "UI",
    "URL",
    "SQL",
}

BRANDS = {
    "openai": "OpenAI",
    "openapi": "OpenAPI",
    "github": "GitHub",
    "pagerduty": "PagerDuty",
    "datadog": "DataDog",
    "sqlite": "SQLite",
    "fastapi": "FastAPI",
}

SMALL_WORDS = {"and", "or", "to", "up", "with"}

ALLOWED_INTERFACE_KEYS = {
    "display_name",
    "short_description",
    "icon_small",
    "icon_large",
    "brand_color",
    "default_prompt",
}


def yaml_quote(value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def format_display_name(skill_name):
    words = [word for word in skill_name.split("-") if word]
    formatted = []
    for index, word in enumerate(words):
        lower = word.lower()
        upper = word.upper()
        if upper in ACRONYMS:
            formatted.append(upper)
            continue
        if lower in BRANDS:
            formatted.append(BRANDS[lower])
            continue
        if index > 0 and lower in SMALL_WORDS:
            formatted.append(lower)
            continue
        formatted.append(word.capitalize())
    return " ".join(formatted)


def generate_short_description(display_name):
    description = f"帮助处理{display_name}相关任务、流程、执行与结果交付"

    if len(description) < 25:
        description = f"帮助处理{display_name}相关任务、流程、执行与常见结果交付"
    if len(description) < 25:
        description = f"帮助处理{display_name}相关任务、流程、执行、交付与使用说明"

    if len(description) > 64:
        description = f"帮助处理{display_name}相关任务"
    if len(description) > 64:
        description = f"{display_name}相关任务助手"
    if len(description) > 64:
        description = f"{display_name}相关工作助手"
    if len(description) > 64:
        suffix = "相关任务助手"
        max_name_length = 64 - len(suffix)
        trimmed = display_name[:max_name_length].rstrip()
        description = f"{trimmed}{suffix}"
    if len(description) > 64:
        description = description[:64].rstrip()

    if len(description) < 25:
        description = f"{description}支持"
        if len(description) > 64:
            description = description[:64].rstrip()

    return description


def read_frontmatter_name(skill_dir):
    skill_md = Path(skill_dir) / "SKILL.md"
    if not skill_md.exists():
        print(f"[ERROR] 在 {skill_dir} 中找不到 SKILL.md")
        return None

    content = skill_md.read_text()
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        print("[ERROR] SKILL.md frontmatter 格式无效。")
        return None

    frontmatter_text = match.group(1)
    name_match = re.search(r"^name:\s*(.+?)\s*$", frontmatter_text, re.MULTILINE)
    if not name_match:
        print("[ERROR] Frontmatter 里的 name 缺失或格式无效。")
        return None

    return name_match.group(1).strip().strip('"').strip("'")


def parse_interface_overrides(raw_overrides):
    overrides = {}
    optional_order = []
    for item in raw_overrides:
        if "=" not in item:
            print(f"[ERROR] 无效的 interface override：'{item}'。请使用 key=value。")
            return None, None
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            print(f"[ERROR] 无效的 interface override：'{item}'。key 不能为空。")
            return None, None
        if key not in ALLOWED_INTERFACE_KEYS:
            allowed = ", ".join(sorted(ALLOWED_INTERFACE_KEYS))
            print(f"[ERROR] 未知的 interface 字段：'{key}'。可选字段：{allowed}")
            return None, None
        overrides[key] = value
        if key not in ("display_name", "short_description") and key not in optional_order:
            optional_order.append(key)
    return overrides, optional_order


def _clean_interface_defaults(values):
    if not isinstance(values, dict):
        return {}
    cleaned = {}
    for key, value in values.items():
        if key not in ALLOWED_INTERFACE_KEYS:
            continue
        if value in (None, ""):
            continue
        cleaned[key] = str(value)
    return cleaned


def write_openai_yaml(skill_dir, skill_name, raw_overrides, config_defaults=None):
    overrides, optional_order = parse_interface_overrides(raw_overrides)
    if overrides is None:
        return None

    config_defaults = _clean_interface_defaults(config_defaults)
    optional_order = list(dict.fromkeys(
        [key for key in config_defaults if key not in ("display_name", "short_description")]
        + optional_order
    ))

    display_name = (
        overrides.get("display_name")
        or config_defaults.get("display_name")
        or format_display_name(skill_name)
    )
    short_description = (
        overrides.get("short_description")
        or config_defaults.get("short_description")
        or generate_short_description(display_name)
    )

    if not (25 <= len(short_description) <= 64):
        print(
            "[ERROR] short_description 长度必须在 25-64 个字符之间 "
            f"(当前为 {len(short_description)} 个字符)。"
        )
        return None

    interface_lines = [
        "interface:",
        f"  display_name: {yaml_quote(display_name)}",
        f"  short_description: {yaml_quote(short_description)}",
    ]

    for key in optional_order:
        value = overrides.get(key, config_defaults.get(key))
        if value is not None:
            interface_lines.append(f"  {key}: {yaml_quote(value)}")

    agents_dir = Path(skill_dir) / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    output_path = agents_dir / "openai.yaml"
    output_path.write_text("\n".join(interface_lines) + "\n")
    print("[OK] 已创建 agents/openai.yaml")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="为某个 skill 目录创建 agents/openai.yaml。",
    )
    parser.add_argument("skill_dir", help="skill 目录路径")
    parser.add_argument(
        "--config",
        default=None,
        help="config.yaml 路径（默认使用 dazhuangskill-creator/config.yaml）",
    )
    parser.add_argument(
        "--name",
        help="skill 名称覆盖值（默认取自 SKILL.md frontmatter）",
    )
    parser.add_argument(
        "--interface",
        action="append",
        default=[],
        help="界面字段覆盖，格式 key=value，可重复传入",
    )
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.exists():
        print(f"[ERROR] 找不到 skill 目录：{skill_dir}")
        sys.exit(1)
    if not skill_dir.is_dir():
        print(f"[ERROR] 路径不是目录：{skill_dir}")
        sys.exit(1)

    skill_name = args.name or read_frontmatter_name(skill_dir)
    if not skill_name:
        sys.exit(1)

    config = load_dazhuangskill_creator_config(args.config)
    config_defaults = get_config_value(config, "openai_yaml.interface_defaults", {})

    result = write_openai_yaml(skill_dir, skill_name, args.interface, config_defaults)
    if result:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
