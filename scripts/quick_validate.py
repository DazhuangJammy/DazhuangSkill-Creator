#!/usr/bin/env python3
"""用于快速校验 skill 结构的脚本。"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


ALLOWED_PROPERTIES = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "compatibility",
}
ALLOWED_TOP_LEVEL_SECTIONS = ["角色", "规则", "工作流程", "例子", "输出格式", "索引"]
REQUIRED_TOP_LEVEL_SECTIONS = {"规则", "工作流程"}
SECTION_ORDER = {name: index for index, name in enumerate(ALLOWED_TOP_LEVEL_SECTIONS)}
INLINE_SECTION_LIMITS = {
    "例子": 18,
    "输出格式": 18,
}
INLINE_COMBINED_LIMIT = 30
RESOURCE_ANCHOR_IGNORE_DIRS = {"__pycache__", "node_modules", ".git"}


def skill_root_has_bundled_resources(skill_path):
    """Return whether the skill root contains bundled resources that need anchoring."""
    for child in skill_path.iterdir():
        if child.name == "SKILL.md":
            continue
        if child.is_dir() and child.name not in RESOURCE_ANCHOR_IGNORE_DIRS:
            return True
        if child.is_file() and child.name == "config.yaml":
            return True
    return False


def has_skill_base_rule(section_lines):
    """Check whether the rules section defines <skill-base> explicitly."""
    section_text = "\n".join(section_lines)
    if "<skill-base>" not in section_text:
        return False
    normalized = section_text.replace("`", "")
    return "当前 SKILL.md 所在目录" in normalized or "当前SKILL.md所在目录" in normalized


def parse_frontmatter(frontmatter_text):
    """优先用 PyYAML 解析 frontmatter，没有 PyYAML 时退回到简易解析。"""
    if yaml is not None:
        try:
            parsed = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            return None, f"frontmatter 里的 YAML 无效：{exc}"
        if not isinstance(parsed, dict):
            return None, "frontmatter 必须是一个 YAML 字典"
        return parsed, None

    parsed = {}
    for raw_line in frontmatter_text.splitlines():
        if not raw_line.strip():
            continue
        if raw_line[:1].isspace():
            continue
        if ":" not in raw_line:
            return None, f"当前回退解析不支持这行 frontmatter：{raw_line}"
        key, value = raw_line.split(":", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    if not isinstance(parsed, dict):
        return None, "frontmatter 必须是一个 YAML 字典"
    return parsed, None


def parse_top_level_sections(body_text):
    """Parse level-1 markdown headings and their bodies."""
    sections = []
    stray_lines = []
    current = None

    for line in body_text.splitlines():
        heading_match = re.match(r"^#\s+(.+?)\s*$", line)
        if heading_match:
            current = {"name": heading_match.group(1).strip(), "lines": []}
            sections.append(current)
            continue
        if current is None:
            if line.strip():
                stray_lines.append(line.strip())
            continue
        current["lines"].append(line)

    return stray_lines, sections


def validate_skill(skill_path):
    """对 skill 做基础结构校验。"""
    skill_path = Path(skill_path)

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "找不到 SKILL.md"

    content = skill_md.read_text()
    if not content.startswith("---"):
        return False, "没有找到 YAML frontmatter"

    match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if not match:
        return False, "frontmatter 格式无效"

    frontmatter_text = match.group(1)
    frontmatter, error = parse_frontmatter(frontmatter_text)
    if error:
        return False, error

    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"SKILL.md frontmatter 中出现了未允许的字段：{', '.join(sorted(unexpected_keys))}。"
            f"允许的字段只有：{', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    if "name" not in frontmatter:
        return False, "frontmatter 缺少 name"
    if "description" not in frontmatter:
        return False, "frontmatter 缺少 description"

    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return False, f"name 必须是字符串，当前得到的是 {type(name).__name__}"
    name = name.strip()
    if name:
        if not re.match(r"^[a-z0-9-]+$", name):
            return False, f"name '{name}' 应该是 kebab-case（只允许小写字母、数字和连字符）"
        if name.startswith("-") or name.endswith("-") or "--" in name:
            return False, f"name '{name}' 不能以连字符开头或结尾，也不能出现连续连字符"
        if len(name) > 64:
            return False, f"name 过长（{len(name)} 个字符）。最大允许 64 个字符。"

    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return False, f"description 必须是字符串，当前得到的是 {type(description).__name__}"
    description = description.strip()
    if description:
        if "<" in description or ">" in description:
            return False, "description 不能包含尖括号（< 或 >）"
        if len(description) > 1024:
            return False, f"description 过长（{len(description)} 个字符）。最大允许 1024 个字符。"

    compatibility = frontmatter.get("compatibility", "")
    if compatibility:
        if not isinstance(compatibility, str):
            return False, f"compatibility 必须是字符串，当前得到的是 {type(compatibility).__name__}"
        if len(compatibility) > 500:
            return False, f"compatibility 过长（{len(compatibility)} 个字符）。最大允许 500 个字符。"

    body_text = content[match.end():]
    stray_lines, sections = parse_top_level_sections(body_text)

    if stray_lines:
        return False, (
            "frontmatter 之后只能直接进入固定顶级 section；"
            f"当前发现了游离正文：{stray_lines[0]}"
        )

    if not sections:
        return False, "SKILL.md 正文缺少顶级 section。至少需要 `# 规则` 和 `# 工作流程`。"

    seen = {}
    previous_order = -1
    inline_lengths = {}

    for section in sections:
        section_name = section["name"]
        if section_name not in ALLOWED_TOP_LEVEL_SECTIONS:
            allowed = "、".join(ALLOWED_TOP_LEVEL_SECTIONS)
            return False, f"发现未允许的顶级 section：`# {section_name}`。允许的只有：{allowed}"
        if section_name in seen:
            return False, f"顶级 section `# {section_name}` 只能出现一次。"

        current_order = SECTION_ORDER[section_name]
        if current_order < previous_order:
            expected = " -> ".join(ALLOWED_TOP_LEVEL_SECTIONS)
            return False, (
                f"顶级 section 顺序不合法：`# {section_name}` 出现得太早。"
                f"请按这个顺序组织：{expected}"
            )
        previous_order = current_order
        seen[section_name] = section

        nonempty_lines = [line.strip() for line in section["lines"] if line.strip()]
        if section_name in REQUIRED_TOP_LEVEL_SECTIONS and not nonempty_lines:
            return False, f"顶级 section `# {section_name}` 不能为空。"
        if section_name in INLINE_SECTION_LIMITS:
            inline_lengths[section_name] = len(nonempty_lines)

    missing_sections = [name for name in ALLOWED_TOP_LEVEL_SECTIONS if name in REQUIRED_TOP_LEVEL_SECTIONS and name not in seen]
    if missing_sections:
        joined = "、".join(f"`# {name}`" for name in missing_sections)
        return False, f"缺少必选的顶级 section：{joined}"

    if skill_root_has_bundled_resources(skill_path):
        rules_section = seen.get("规则", {})
        if not has_skill_base_rule(rules_section.get("lines", [])):
            return False, (
                "skill 根目录里已经有 bundled resources（如 references/、assets/、scripts/、agents/、evals/ 或 config.yaml），"
                "因此 `# 规则` 里必须明确把当前 `SKILL.md` 所在目录定义为 `<skill-base>`。"
            )

    if (skill_path / "references").exists() and "例子" in seen:
        return False, "已经存在 references/，不要再把 `# 例子` 留在主 SKILL.md；请下沉到 references/examples.md。"
    if (skill_path / "assets").exists() and "输出格式" in seen:
        return False, "已经存在 assets/，不要再把 `# 输出格式` 留在主 SKILL.md；请下沉到 assets/output-format.md。"

    for section_name, limit in INLINE_SECTION_LIMITS.items():
        if inline_lengths.get(section_name, 0) > limit:
            return False, (
                f"`# {section_name}` 过长（{inline_lengths[section_name]} 行非空内容）。"
                "这类低频或长内容应该下沉到 bundled resources。"
            )

    inline_total = sum(inline_lengths.values())
    if inline_total > INLINE_COMBINED_LIMIT:
        return False, (
            f"内联的 `# 例子` + `# 输出格式` 总长度过大（{inline_total} 行非空内容）。"
            "请把它们下沉到 references/ 或 assets/。"
        )

    return True, "Skill 结构有效！"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法：python quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
