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
            # 简易回退模式下忽略嵌套行；对当前轻量校验来说只看顶层字段就够了。
            continue
        if ":" not in raw_line:
            return None, f"当前回退解析不支持这行 frontmatter：{raw_line}"
        key, value = raw_line.split(":", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    if not isinstance(parsed, dict):
        return None, "frontmatter 必须是一个 YAML 字典"
    return parsed, None

def validate_skill(skill_path):
    """对 skill 做基础结构校验。"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "找不到 SKILL.md"

    # Read and validate frontmatter
    content = skill_md.read_text()
    if not content.startswith('---'):
        return False, "没有找到 YAML frontmatter"

    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "frontmatter 格式无效"

    frontmatter_text = match.group(1)

    frontmatter, error = parse_frontmatter(frontmatter_text)
    if error:
        return False, error

    # Check for unexpected properties (excluding nested keys under metadata)
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"SKILL.md frontmatter 中出现了未允许的字段：{', '.join(sorted(unexpected_keys))}。"
            f"允许的字段只有：{', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    # Check required fields
    if 'name' not in frontmatter:
        return False, "frontmatter 缺少 name"
    if 'description' not in frontmatter:
        return False, "frontmatter 缺少 description"

    # Extract name for validation
    name = frontmatter.get('name', '')
    if not isinstance(name, str):
        return False, f"name 必须是字符串，当前得到的是 {type(name).__name__}"
    name = name.strip()
    if name:
        # 检查命名规范（kebab-case：小写字母、数字、连字符）
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"name '{name}' 应该是 kebab-case（只允许小写字母、数字和连字符）"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"name '{name}' 不能以连字符开头或结尾，也不能出现连续连字符"
        # 检查 name 长度（规范上限 64）
        if len(name) > 64:
            return False, f"name 过长（{len(name)} 个字符）。最大允许 64 个字符。"

    # Extract and validate description
    description = frontmatter.get('description', '')
    if not isinstance(description, str):
        return False, f"description 必须是字符串，当前得到的是 {type(description).__name__}"
    description = description.strip()
    if description:
        # 检查 angle brackets
        if '<' in description or '>' in description:
            return False, "description 不能包含尖括号（< 或 >）"
        # 检查 description 长度（规范上限 1024）
        if len(description) > 1024:
            return False, f"description 过长（{len(description)} 个字符）。最大允许 1024 个字符。"

    # 如果存在 compatibility，则顺手校验
    compatibility = frontmatter.get('compatibility', '')
    if compatibility:
        if not isinstance(compatibility, str):
            return False, f"compatibility 必须是字符串，当前得到的是 {type(compatibility).__name__}"
        if len(compatibility) > 500:
            return False, f"compatibility 过长（{len(compatibility)} 个字符）。最大允许 500 个字符。"

    return True, "Skill 结构有效！"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法：python quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
