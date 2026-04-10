#!/usr/bin/env python3
"""用于快速校验 skill 结构的脚本。"""

import json
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import configure_utf8_stdio, read_utf8_text

configure_utf8_stdio()

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
MEMORY_GUARD_SCRIPT = Path("scripts") / "memory_mode_guard.py"
MEMORY_STATE_FILE = Path("references") / "memory-state.json"
MEMORY_EVENTS_FILE = Path("references") / "memory-events.jsonl"
MEMORY_LESSONS_FILE = Path("references") / "memory-lessons.md"
MEMORY_HARD_RULES_START = "<!-- MEMORY_HARD_RULES_START -->"
MEMORY_HARD_RULES_END = "<!-- MEMORY_HARD_RULES_END -->"
MEMORY_GUARD_INVOKE_RE = re.compile(r"memory_mode_guard\.py\"[^\n]*--event\s+invoke")
MEMORY_GUARD_RETRY_RE = re.compile(r"memory_mode_guard\.py\"[^\n]*--event\s+retry")
MEMORY_GUARD_FAILURE_RE = re.compile(r"memory_mode_guard\.py\"[^\n]*--event\s+failure")
MEMORY_INVOKE_CMD = (
    '`<python-cmd> "<skill-base>/scripts/memory_mode_guard.py" '
    '--skill-dir "<skill-base>" --event invoke`'
)
MEMORY_RETRY_CMD = (
    '`<python-cmd> "<skill-base>/scripts/memory_mode_guard.py" '
    '--skill-dir "<skill-base>" --event retry`'
)
MEMORY_FAILURE_CMD = (
    '`<python-cmd> "<skill-base>/scripts/memory_mode_guard.py" '
    '--skill-dir "<skill-base>" --event failure`'
)


def read_memory_state(path):
    """Read references/memory-state.json as a dict."""
    try:
        payload = json.loads(read_utf8_text(path))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def detect_memory_profile(skill_path, body_text):
    """Detect whether this skill uses memory runtime files or markers."""
    has_guard_script = (skill_path / MEMORY_GUARD_SCRIPT).exists()
    has_state_file = (skill_path / MEMORY_STATE_FILE).exists()
    has_events_file = (skill_path / MEMORY_EVENTS_FILE).exists()
    has_lessons_file = (skill_path / MEMORY_LESSONS_FILE).exists()
    has_markers = MEMORY_HARD_RULES_START in body_text or MEMORY_HARD_RULES_END in body_text
    references_guard = "memory_mode_guard.py" in body_text

    is_memory_skill = any(
        [
            has_guard_script,
            has_state_file,
            has_events_file,
            has_lessons_file,
            has_markers,
            references_guard,
        ]
    )
    return {
        "is_memory_skill": is_memory_skill,
        "has_guard_script": has_guard_script,
        "has_state_file": has_state_file,
        "has_events_file": has_events_file,
        "has_lessons_file": has_lessons_file,
        "has_markers": has_markers,
    }


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

    content = read_utf8_text(skill_md)
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

    memory_profile = detect_memory_profile(skill_path, body_text)
    if memory_profile["is_memory_skill"]:
        missing = []
        if not memory_profile["has_guard_script"]:
            missing.append(str(MEMORY_GUARD_SCRIPT))
        if not memory_profile["has_state_file"]:
            missing.append(str(MEMORY_STATE_FILE))
        if not memory_profile["has_events_file"]:
            missing.append(str(MEMORY_EVENTS_FILE))
        if missing:
            return False, (
                "检测到这是 memory skill，但缺少关键运行文件："
                f"{', '.join(missing)}"
            )

        rules_text = "\n".join(seen.get("规则", {}).get("lines", []))
        if MEMORY_HARD_RULES_START not in rules_text or MEMORY_HARD_RULES_END not in rules_text:
            return False, (
                "memory skill 的 `# 规则` 必须包含 MEMORY_HARD_RULES 标记块："
                f"{MEMORY_HARD_RULES_START} ... {MEMORY_HARD_RULES_END}"
            )
        if rules_text.find(MEMORY_HARD_RULES_START) > rules_text.find(MEMORY_HARD_RULES_END):
            return False, "MEMORY_HARD_RULES 标记顺序错误：start 必须出现在 end 前面。"

        workflow_text = "\n".join(seen.get("工作流程", {}).get("lines", []))
        if not MEMORY_GUARD_INVOKE_RE.search(workflow_text):
            return False, (
                "memory skill 的 Step 1 缺少 invoke 事件记录命令。"
                f"请把这行加到 Step 1：{MEMORY_INVOKE_CMD}"
            )
        if not MEMORY_GUARD_RETRY_RE.search(workflow_text):
            return False, (
                "memory skill 的 Step 4 缺少 retry 事件记录命令。"
                f"请把这行加到 Step 4：{MEMORY_RETRY_CMD}"
            )
        if not MEMORY_GUARD_FAILURE_RE.search(workflow_text):
            return False, (
                "memory skill 的 Step 4 缺少 failure 事件记录命令。"
                f"请把这行加到 Step 4：{MEMORY_FAILURE_CMD}"
            )

        memory_state = read_memory_state(skill_path / MEMORY_STATE_FILE)
        if memory_state is None:
            return False, "references/memory-state.json 不是有效 JSON 对象。"

        memory_mode = str(memory_state.get("mode", "")).strip().lower()
        if memory_mode not in {"adaptive", "lessons"}:
            return False, "references/memory-state.json 的 mode 必须是 adaptive 或 lessons。"

        memory_enabled = bool(memory_state.get("memory_enabled", False))
        if memory_mode == "lessons" and not memory_enabled:
            return False, "mode=lessons 的 memory skill 必须从创建时就满足 memory_enabled=true。"
        if memory_mode == "lessons" and not memory_profile["has_lessons_file"]:
            return False, "mode=lessons 的 memory skill 必须存在 references/memory-lessons.md。"
        if memory_mode == "adaptive" and memory_enabled and not memory_profile["has_lessons_file"]:
            return False, (
                "mode=adaptive 且 memory_enabled=true 时，"
                "必须存在 references/memory-lessons.md。"
            )

    return True, "Skill 结构有效！"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法：python quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
