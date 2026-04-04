#!/usr/bin/env python3
"""
Skill 初始化器：用精简的“核心规则 / 默认工作流”脚手架创建新 skill。

用法：
    init_skill.py <skill-name> --path <path> [--resources scripts,references,assets] [--examples] [--config-file] [--openai-yaml] [--interface key=value]
    init_skill.py <skill-name> [--config ./config.yaml]

示例：
    init_skill.py my-new-skill --path skills/public
    init_skill.py my-new-skill --path skills/public --resources references
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

SKILL_TEMPLATE = """---
name: {skill_name}
description: [TODO: 说明这个 skill 帮用户解决什么问题、什么时候应该触发、什么情况下不要触发。]
---

# {skill_title}

# 核心规则

- 把当前 `SKILL.md` 所在目录视为 `<skill-base>`。所有 bundled resources 都从这里解析，不要依赖调用方当前工作目录。
- 先判断每一块内容值不值得存在。如果拿掉它，skill 仍然成立，就优先删掉或不要加进去。
- 主 `SKILL.md` 只保留耐久规则、默认工作流、工作流内嵌指针。
- 如果某些参数会被人频繁修改，再把它们放进 `<skill-base>/config.yaml`。机器写入的运行产物、缓存、严格交换格式才用 JSON。
- 当工作流要运行 bundled script 时，优先写成显式命令，例如 `cd "<skill-base>" && python3 scripts/...`。
- 默认不要创建额外目录、评测资产或界面元数据，除非它们真的对当前 skill 有价值。
- [TODO: 只补充真正耐久、真正承重的规则。]
- [TODO: 删除泛泛建议，只保留任务专属约束。]
- [TODO: 如果默认交付物应该极简（例如单行、单命令、单标题），把“默认只输出这一项”写成硬规则，并把允许扩写的条件写成窄的闭集。]
- [TODO: 如果这个 skill 属于 Conventional Commit、标题压缩、单行摘要这类高压缩判型输出，把高代价边界写死；例如旧 public CLI flag 被拒绝且由新 flag 替代时，要按 breaking interface change 处理，不要误写成普通 fix。]

# 默认工作流

## Step 1：先判断任务

- [TODO: 提取任务类型、输入、约束、缺失信息。]
- 只有当流程真的依赖可调参数时，才读取 `<skill-base>/config.yaml`。
- 如果需要示例，读取 `<skill-base>/references/examples.md`。
- 如果需要较长的输出规格，读取 `<skill-base>/references/output-spec.md`。
- 如果需要更深的领域说明，读取 `<skill-base>/references/` 下的对应文件。
- 如果需要可直接复用的模板或文件，使用 `<skill-base>/assets/` 下的对应文件。
- 如果需要确定性或重复性执行，运行 `cd "<skill-base>" && python3 scripts/...`。

## Step 2：先定结构，再决定怎么做

- [TODO: 判断这次请求的主路径、主结构、主策略。]
- [TODO: 明确指出哪些内容留在 body，哪些内容应该下沉到 references / assets / scripts。]
- [TODO: 明确写出哪些额外文件不需要创建，避免顺手把 skill 做重。]
- [TODO: 只指向当前步骤真正需要的 bundled resource，避免到处乱读。]

## Step 3：产出结果

- [TODO: 生成最终交付物。]
- [TODO: 只有在需要时才遵循对应 output spec 或模板。]
- [TODO: 如果本步骤调用脚本，把完整命令写出来，不要假设当前 cwd。]
- [TODO: 如果默认输出应该很短，只有在满足明确条件时才允许加 body、解释或备选项；不要用“有帮助时可加”这类宽条件。]

## Step 4：最后检查

- [TODO: 检查结果是否满足规则、任务约束和主策略。]
- [TODO: 检查交付物里有没有混入不必要的 config、界面元数据、评测资产或绝对路径。]
- [TODO: 如果默认输出应该极简，删除所有不必要的 body、解释、备选项。]
- [TODO: 如果这类任务存在高代价误判边界（例如 breaking change 会被错判成 fix），确认你已经用规则或一个极短 canonical example 把它封死。]
- [TODO: 再问一次：有没有哪一块内容拿掉也不会垮？如果有，删掉。]
"""

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

EXAMPLE_REFERENCE_EXAMPLES = """# 示例

只有在你真的需要模式参考、示例输入或边界写法时，才读取这份文件。

## 示例 1

用户请求：

```text
[请替换成真实、自然、像用户会说的话的请求]
```

这个示例应该教会 Claude：

- [可以复用的切入角度或结构]
- [需要避免的失败方式]
"""

EXAMPLE_REFERENCE_OUTPUT_SPEC = """# 输出规格

只有当你需要决定最终交付物长什么样时，才读取这份文件。

## 默认行为

- [描述默认输出行为]

## 模板 A

在什么情况下使用：

- [条件]

推荐结构：

```md
[把这里替换成输出骨架]
```
"""

EXAMPLE_ASSET = """# 可复用模板

只有当最终输出需要这个确切结构时，才复制或使用这份文件。
如果它没有真实价值，就删掉它。
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


def title_case_skill_name(skill_name):
    """Convert hyphenated skill name to Title Case for display."""
    return " ".join(word.capitalize() for word in skill_name.split("-"))


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
                output_spec_file = resource_dir / "output-spec.md"
                examples_file.write_text(EXAMPLE_REFERENCE_EXAMPLES)
                output_spec_file.write_text(EXAMPLE_REFERENCE_OUTPUT_SPEC)
                print("[OK] 已创建 references/examples.md")
                print("[OK] 已创建 references/output-spec.md")
            else:
                print("[OK] 已创建 references/")
        elif resource == "assets":
            if include_examples:
                example_asset = resource_dir / "template.md"
                example_asset.write_text(EXAMPLE_ASSET)
                print("[OK] 已创建 assets/template.md")
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
    include_examples,
    interface_overrides,
    interface_defaults,
    create_config,
    create_openai_yaml,
):
    """Initialize a new skill directory with a lean SKILL.md template."""
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

    skill_title = title_case_skill_name(skill_name)
    skill_content = SKILL_TEMPLATE.format(
        skill_name=skill_name,
        skill_title=skill_title,
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
    print("1. 先替换 SKILL.md 里的 TODO，再把主 body 压到只剩核心规则、默认工作流、内嵌指针。")
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
    print("4. 把长示例、长规格、长解释移出 SKILL.md，下沉到 references/ 或 assets/。")
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
        description="创建一个新的 skill 目录，并生成精简的 SKILL.md 模板。",
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
    print(f"   创建 config.yaml：{'是' if create_config else '否'}")
    print(f"   创建 agents/openai.yaml：{'是' if create_openai_yaml else '否'}")
    print()

    result = init_skill(
        skill_name,
        path,
        resources,
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
