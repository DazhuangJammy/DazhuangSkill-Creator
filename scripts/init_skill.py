#!/usr/bin/env python3
"""
Skill 初始化器：用固定的单文件/多文件脚手架创建新 skill。

用法：
    init_skill.py <skill-name> --path <path> [--resources scripts,references,assets] [--sections role,examples,output-format,index] [--examples] [--config-file] [--openai-yaml] [--interface key=value]
    init_skill.py <skill-name> [--config ./config.yaml]

示例：
    init_skill.py my-new-skill --path skills/public
    init_skill.py my-new-skill --path skills/public --resources references
    init_skill.py my-judge-skill --path skills/public --sections role,output-format
    init_skill.py my-api-helper --path skills/private --resources scripts,references,assets --examples
    init_skill.py custom-skill --path /custom/location
    init_skill.py my-skill --path skills/public --openai-yaml --interface short_description="中文界面说明"
    init_skill.py my-skill --config ./config.yaml
"""

import argparse
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_openai_yaml import write_openai_yaml
from scripts.utils import coalesce, get_config_value, load_dazhuangskill_creator_config

MAX_SKILL_NAME_LENGTH = 64
ALLOWED_RESOURCES = {"scripts", "references", "assets"}
ALLOWED_SECTIONS = {"role", "examples", "output-format", "index"}
SECTION_ORDER = ["role", "rules", "workflow", "examples", "output-format", "index"]

EXAMPLE_SCRIPT = '''#!/usr/bin/env python3
"""
{skill_name} 的示例辅助脚本

当某个确定性步骤每次都要重复写一遍时，才应该把它正式收进 scripts/。
如果这个占位脚本没有真实价值，就删掉它。
"""


def main():
    print("请把 scripts/example_task.py 替换成真正有价值的辅助脚本，或者直接删除它。")


if __name__ == "__main__":
    main()
'''

EXAMPLE_REFERENCE_EXAMPLES = """# 例子

只有在你真的需要给模型补 canonical case、边界判断样本或 few-shot 参考时，才读取这份文件。
这里放的是给 skill / 模型看的内部参考材料，不是教用户怎么提问的示例。

## 例子 1： [场景名]

场景：

```text
[描述模型会遇到的任务场景、输入材料或冲突点；不要只写一句用户问句]
```

在这个例子里，模型应该学到：

- [遇到什么信号时，优先采用哪种判断框架]
- [应该如何取舍、如何组织答案]
- [哪些常见误判或跑偏方式必须避免]

推荐输出落点：

```md
[只保留关键结构、关键句型或关键判断，不要写成冗长成品]
```
"""

EXAMPLE_ASSET_OUTPUT_FORMAT = """# 输出格式

只有当最终输出需要稳定结构时，才读取这份文件。
这里放的是给 skill / 模型直接遵循的模板、骨架或字段约束，不是给用户看的说明文字。
如果这个 skill 的输出天然开放，就不要保留这份文件。

## 默认行为

- [描述默认输出行为]

## 推荐结构

```md
[把这里替换成输出骨架]
```

## 扩写边界

- [只有在什么条件下才允许多写]

## 禁止项

- [哪些解释、备选项或 body 不应该出现]
"""

EXAMPLE_CONFIG = """# 人工可编辑的 skill 参数
# 经常要调的值放这里，不要另外发明一份手写 JSON。
# 机器写入的运行产物、缓存、API payload 再继续用 JSON。

defaults:
  # 在这里补具体参数。
"""


def normalize_skill_name(skill_name):
    """Normalize a skill name to lowercase hyphen-case."""
    normalized = skill_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized


def parse_resources(raw_resources):
    if not raw_resources:
        return []
    resources = [item.strip() for item in raw_resources.split(",") if item.strip()]
    invalid = sorted({item for item in resources if item not in ALLOWED_RESOURCES})
    if invalid:
        allowed = ", ".join(sorted(ALLOWED_RESOURCES))
        print(f"[ERROR] 未知资源类型：{', '.join(invalid)}")
        print(f"   可选值：{allowed}")
        sys.exit(1)
    deduped = []
    seen = set()
    for resource in resources:
        if resource not in seen:
            deduped.append(resource)
            seen.add(resource)
    return deduped


def parse_sections(raw_sections):
    if not raw_sections:
        return []
    sections = [item.strip() for item in raw_sections.split(",") if item.strip()]
    invalid = sorted({item for item in sections if item not in ALLOWED_SECTIONS})
    if invalid:
        allowed = ", ".join(sorted(ALLOWED_SECTIONS))
        print(f"[ERROR] 未知 section：{', '.join(invalid)}")
        print(f"   可选值：{allowed}")
        sys.exit(1)
    deduped = []
    seen = set()
    for section in SECTION_ORDER:
        if section in sections and section not in seen:
            deduped.append(section)
            seen.add(section)
    return deduped


def validate_structure_choices(resources, sections):
    if "references" in resources and "examples" in sections:
        print("[ERROR] 启用 references/ 时，不要再把 `# 例子` 内联到主 SKILL.md。")
        print("   二选一：要么用单文件 `# 例子`，要么把例子下沉到 references/examples.md。")
        sys.exit(1)
    if "assets" in resources and "output-format" in sections:
        print("[ERROR] 启用 assets/ 时，不要再把 `# 输出格式` 内联到主 SKILL.md。")
        print("   二选一：要么用单文件 `# 输出格式`，要么把输出格式下沉到 assets/output-format.md。")
        sys.exit(1)


def needs_skill_base_rule(resources, create_config, create_openai_yaml):
    return bool(resources or create_config or create_openai_yaml)


def render_skill_template(skill_name, sections, resources, create_config, create_openai_yaml):
    require_skill_base = needs_skill_base_rule(resources, create_config, create_openai_yaml)
    blocks = [
        "---",
        f"name: {skill_name}",
        "description: [TODO: 说明这个 skill 帮用户解决什么问题、什么时候应该触发、什么情况下不要触发。]",
        "---",
        "",
    ]

    if "role" in sections:
        blocks.extend(
            [
                "# 角色",
                "",
                "- [TODO: 先判断这是“扮演角色”还是“借用视角”，只选一个主方向。]",
                "- [TODO: 定义这个 skill 的判断视角、身份边界或表达姿态。]",
                "- [TODO: 如果借用某个人物或方法论，默认写成“借用其判断框架，不模仿口吻”。]",
                "",
            ]
        )

    blocks.extend(
        [
            "# 规则",
            "",
            "- 顶级 section 只在 `角色`、`规则`、`工作流程`、`例子`、`输出格式`、`索引` 这套闭集里组合；不需要的模块不要加。",
            "- 这里只保留对当前 skill 真正承重的规则；能交给 creator、validator 或 bundled resources 保证的通用结构说明，不要原封不动塞进最终版。",
            "- [TODO: 只补充真正耐久、真正承重的规则。]",
        ]
    )

    if require_skill_base:
        blocks.insert(
            len(blocks) - 1,
            "- 把当前 `SKILL.md` 所在目录视为 `<skill-base>`。所有 bundled resources 都从这里解析，不要依赖调用方当前工作目录。",
        )
    if "scripts" in resources:
        blocks.insert(
            len(blocks) - 1,
            "- 当工作流要运行 bundled script 时，优先写成显式命令，例如 `cd \"<skill-base>\" && python3 scripts/...`。",
        )
    if create_config:
        blocks.insert(
            len(blocks) - 1,
            "- 这个 skill 已启用 `<skill-base>/config.yaml`；只有当流程真的依赖可调参数时才读取它。",
        )

    if "references" in resources:
        blocks.append("- 已启用 `references/` 时，只在需要低频边界、内部参考例子或 few-shot 材料时读取 `<skill-base>/references/examples.md`。")
    if "assets" in resources:
        blocks.append("- 已启用 `assets/` 时，只在需要稳定交付模板、固定骨架或字段约束时读取 `<skill-base>/assets/output-format.md`。")

    blocks.extend(
        [
            "- [TODO: 删除泛泛建议，只保留任务专属约束。]",
            "",
            "# 工作流程",
            "",
            "## Step 1：先判断任务",
            "",
            "- [TODO: 提取任务类型、输入、约束、缺失信息。]",
            "- 先判断这个 skill 需不需要 `角色`、`例子`、`输出格式`、`索引`；不需要就不要加。",
        ]
    )

    if require_skill_base:
        blocks.append("- 如果这个 skill 带有本地资源，统一沿 `<skill-base>` 解析，不要依赖当前工作目录。")
    if create_config:
        blocks.append("- 只有当流程真的依赖可调参数时，才读取 `<skill-base>/config.yaml`。")
    if "references" in resources:
        blocks.append("- 如果需要下沉的例子，读取 `<skill-base>/references/examples.md`；这里的例子是给模型看的内部参考，不是用户问句示例。")
    if "assets" in resources:
        blocks.append("- 如果需要下沉的输出格式，读取 `<skill-base>/assets/output-format.md`；这里放的是模型应直接遵循的模板或骨架。")
    if "scripts" in resources:
        blocks.append("- 如果需要确定性或重复性执行，运行 `cd \"<skill-base>\" && python3 scripts/...`。")

    blocks.extend(
        [
            "",
            "## Step 2：先定结构，再决定怎么做",
            "",
            "- [TODO: 判断这次请求的主路径、主结构、主策略。]",
            "- [TODO: 明确指出哪些内容留在主 `SKILL.md`，哪些内容应该下沉到 `references/`、`assets/`、`scripts/`。]",
            "- [TODO: 如果 `例子` 或 `输出格式` 已经变长、变多，改下沉，不要把主文件写胖。]",
            "- [TODO: 把 creator 的通用架构说明压到最小，只留下这个 skill 真正会用到的结构规则。]",
            "",
            "## Step 3：产出结果",
            "",
            "- [TODO: 生成最终交付物。]",
            "- [TODO: 如果本步骤调用脚本，把完整命令写出来，不要假设当前 cwd。]",
            "- [TODO: 如果默认输出应该很短，只有在满足明确条件时才允许加 body、解释或备选项。]",
            "",
            "## Step 4：最后检查",
            "",
            "- [TODO: 检查结果是否满足规则、任务约束和主策略。]",
            "- [TODO: 检查 `SKILL.md` 有没有长出未允许的顶级 section。]",
            "- [TODO: 如果 `例子` 或 `输出格式` 已经过长，改下沉到 `references/` 或 `assets/`。]",
            "- [TODO: 再问一次：有没有哪一块内容拿掉也不会垮？如果有，删掉。]",
            "",
        ]
    )

    if "examples" in sections:
        blocks.extend(
            [
                "# 例子",
                "",
                "- [TODO: 只放高代价边界或最关键的 canonical example；这是给模型看的内部参考，不是给用户看的提问示例。]",
                "",
            ]
        )

    if "output-format" in sections:
        blocks.extend(
            [
                "# 输出格式",
                "",
                "- [TODO: 写清模型应遵循的默认输出结构、允许扩写的条件和禁止项；这里是模板，不是面向用户的解释。]",
                "",
            ]
        )

    if "index" in sections:
        blocks.extend(
            [
                "# 索引",
                "",
                "- [TODO: 只有当单文件已经复杂到容易漂移时才保留这个 section。]",
                "- [TODO: 这个索引只负责恢复方向，不替代工作流程。]",
                "",
            ]
        )

    return "\n".join(blocks)


def create_resource_dirs(skill_dir, skill_name, resources, include_examples):
    for resource in resources:
        resource_dir = skill_dir / resource
        resource_dir.mkdir(exist_ok=True)
        if resource == "scripts":
            if include_examples:
                example_script = resource_dir / "example_task.py"
                example_script.write_text(EXAMPLE_SCRIPT.format(skill_name=skill_name))
                example_script.chmod(0o755)
                print("[OK] 已创建 scripts/example_task.py")
            else:
                print("[OK] 已创建 scripts/")
        elif resource == "references":
            if include_examples:
                examples_file = resource_dir / "examples.md"
                examples_file.write_text(EXAMPLE_REFERENCE_EXAMPLES)
                print("[OK] 已创建 references/examples.md")
            else:
                print("[OK] 已创建 references/")
        elif resource == "assets":
            if include_examples:
                output_format_file = resource_dir / "output-format.md"
                output_format_file.write_text(EXAMPLE_ASSET_OUTPUT_FORMAT)
                print("[OK] 已创建 assets/output-format.md")
            else:
                print("[OK] 已创建 assets/")


def create_config_file(skill_dir):
    config_path = skill_dir / "config.yaml"
    config_path.write_text(EXAMPLE_CONFIG)
    print("[OK] 已创建 config.yaml")


def init_skill(
    skill_name,
    path,
    resources,
    sections,
    include_examples,
    interface_overrides,
    interface_defaults,
    create_config,
    create_openai_yaml,
):
    """Initialize a new skill directory with a fixed scaffold."""
    skill_dir = Path(path).resolve() / skill_name

    if skill_dir.exists():
        print(f"[ERROR] Skill 目录已存在：{skill_dir}")
        return None

    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
        print(f"[OK] 已创建 skill 目录：{skill_dir}")
    except Exception as exc:
        print(f"[ERROR] 创建目录失败：{exc}")
        return None

    skill_content = render_skill_template(
        skill_name,
        sections,
        resources,
        create_config,
        create_openai_yaml,
    )

    skill_md_path = skill_dir / "SKILL.md"
    try:
        skill_md_path.write_text(skill_content)
        print("[OK] 已创建 SKILL.md")
    except Exception as exc:
        print(f"[ERROR] 创建 SKILL.md 失败：{exc}")
        return None

    try:
        if create_config:
            create_config_file(skill_dir)
        if create_openai_yaml:
            result = write_openai_yaml(
                skill_dir,
                skill_name,
                interface_overrides,
                interface_defaults,
            )
            if not result:
                return None
    except Exception as exc:
        print(f"[ERROR] 创建可选文件失败：{exc}")
        return None

    if resources:
        try:
            create_resource_dirs(skill_dir, skill_name, resources, include_examples)
        except Exception as exc:
            print(f"[ERROR] 创建资源目录失败：{exc}")
            return None

    print(f"\n[OK] Skill '{skill_name}' 已在 {skill_dir} 初始化完成")
    print("\n下一步建议：")
    print("1. 先替换 SKILL.md 里的 TODO，并确认顶级 section 只来自固定白名单。")
    if create_config:
        print("2. 经常要调的参数放进 config.yaml，不要额外发明一份手写 JSON。")
    else:
        print("2. 只有当人会频繁调参数时，才补 config.yaml。")
    if resources:
        if include_examples:
            print("3. 把 scripts/、references/、assets/ 里的示例文件替换成真实内容，没价值的就删掉。")
        else:
            print("3. 只往 scripts/、references/、assets/ 里补真正需要的文件。")
    else:
        print("3. 只有当 skill 真的需要时，才创建资源目录。")
    print("4. 如果 `# 例子` 或 `# 输出格式` 已经变长、变多，就把它们下沉到 references/ 或 assets/。")
    print("5. bundled file 指针保持精确，默认写成 <skill-base>/...，不要把本次运行的绝对路径写进最终交付物。")
    if create_openai_yaml:
        print("6. 如果界面元数据需要变化，重新生成 agents/openai.yaml。")
    else:
        print("6. 只有目标环境真的需要时，才补 agents/openai.yaml。")
    print("7. 如果默认输出应该极简，最后再专门删一遍不必要的 body、解释和备选项。")
    print("8. 结构写完后，跑 validator 检查 skill 是否成立。")

    return skill_dir


def main():
    parser = argparse.ArgumentParser(
        description="创建一个新的 skill 目录，并生成固定的 SKILL.md 脚手架。",
    )
    parser.add_argument("skill_name", help="Skill 名称（会规范化为 kebab-case）")
    parser.add_argument("--config", default=None, help="config.yaml 路径（默认使用 dazhuangskill-creator/config.yaml）")
    parser.add_argument("--path", required=False, help="skill 输出目录（CLI > config.yaml）")
    parser.add_argument(
        "--resources",
        default=None,
        help="逗号分隔：scripts,references,assets（CLI > config.yaml）",
    )
    parser.add_argument(
        "--sections",
        default=None,
        help="逗号分隔：role,examples,output-format,index（CLI > config.yaml）",
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        default=None,
        help="在所选资源目录里创建示例文件（CLI > config.yaml）",
    )
    parser.add_argument(
        "--config-file",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="是否创建 config.yaml（CLI > config.yaml；默认关闭）",
    )
    parser.add_argument(
        "--openai-yaml",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="是否创建 agents/openai.yaml（CLI > config.yaml；默认关闭）",
    )
    parser.add_argument(
        "--interface",
        action="append",
        default=[],
        help="界面字段覆盖，格式 key=value，可重复传入；只有生成 agents/openai.yaml 时才需要",
    )
    args = parser.parse_args()

    config = load_dazhuangskill_creator_config(args.config)
    raw_skill_name = args.skill_name
    skill_name = normalize_skill_name(raw_skill_name)
    if not skill_name:
        print("[ERROR] Skill 名称里至少要有一个字母或数字。")
        sys.exit(1)
    if len(skill_name) > MAX_SKILL_NAME_LENGTH:
        print(
            f"[ERROR] Skill 名称 '{skill_name}' 过长（{len(skill_name)} 个字符）。最大允许 {MAX_SKILL_NAME_LENGTH} 个字符。"
        )
        sys.exit(1)
    if skill_name != raw_skill_name:
        print(f"提示：已把 skill 名从 '{raw_skill_name}' 规范化为 '{skill_name}'。")

    if args.resources is not None:
        resources = parse_resources(args.resources)
    else:
        configured_resources = get_config_value(config, "init_skill.resources", [])
        if not isinstance(configured_resources, list):
            print("[ERROR] config.yaml 里的 init_skill.resources 必须是 YAML 列表。")
            sys.exit(1)
        resources = parse_resources(",".join(str(item) for item in configured_resources))

    if args.sections is not None:
        sections = parse_sections(args.sections)
    else:
        configured_sections = get_config_value(config, "init_skill.sections", [])
        if not isinstance(configured_sections, list):
            print("[ERROR] config.yaml 里的 init_skill.sections 必须是 YAML 列表。")
            sys.exit(1)
        sections = parse_sections(",".join(str(item) for item in configured_sections))

    validate_structure_choices(resources, sections)

    include_examples = (
        args.examples
        if args.examples is not None
        else bool(get_config_value(config, "init_skill.include_examples", False))
    )
    if include_examples and not resources:
        print("[ERROR] 使用 --examples 时，必须同时提供 --resources。")
        sys.exit(1)

    path = coalesce(args.path, get_config_value(config, "init_skill.output_path"))
    if not path:
        print("[ERROR] 必须提供 --path，除非 config.yaml 已设置 init_skill.output_path。")
        sys.exit(1)

    interface_defaults = get_config_value(config, "openai_yaml.interface_defaults", {})
    create_config = (
        args.config_file
        if args.config_file is not None
        else bool(get_config_value(config, "init_skill.create_config", False))
    )
    create_openai_yaml = (
        args.openai_yaml
        if args.openai_yaml is not None
        else bool(get_config_value(config, "init_skill.create_openai_yaml", False))
    )
    if args.interface and not create_openai_yaml:
        print("[ERROR] 只有在启用 --openai-yaml 时，才应该传 --interface 覆盖。")
        sys.exit(1)

    print(f"准备初始化 skill：{skill_name}")
    print(f"   位置：{path}")
    if resources:
        print(f"   资源目录：{', '.join(resources)}")
        if include_examples:
            print("   示例文件：开启")
    else:
        print("   资源目录：无（按需再建）")
    print(f"   内联 section：{', '.join(sections) if sections else '无（只保留规则 + 工作流程）'}")
    print(f"   创建 config.yaml：{'是' if create_config else '否'}")
    print(f"   创建 agents/openai.yaml：{'是' if create_openai_yaml else '否'}")
    print()

    result = init_skill(
        skill_name,
        path,
        resources,
        sections,
        include_examples,
        args.interface,
        interface_defaults,
        create_config,
        create_openai_yaml,
    )

    if result:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
