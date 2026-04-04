#!/usr/bin/env python3
"""
Skill 打包器：把一个 skill 目录打成可分发的 .skill 文件。

用法：
    python utils/package_skill.py <path/to/skill-folder> [output-directory]

示例：
    python utils/package_skill.py skills/public/my-skill
    python utils/package_skill.py skills/public/my-skill ./dist
"""

import fnmatch
import sys
import zipfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quick_validate import validate_skill
from scripts.utils import coalesce, get_config_value, load_dazhuangskill_creator_config

# 打包时需要排除的目录和文件模式。
EXCLUDE_DIRS = {"__pycache__", "node_modules"}
EXCLUDE_GLOBS = {"*.pyc"}
EXCLUDE_FILES = {".DS_Store"}
# 只在 skill 根目录层级排除的目录（更深层不受影响）。
ROOT_EXCLUDE_DIRS = {"evals"}


def should_exclude(rel_path: Path) -> bool:
    """判断某个路径是否应该在打包时被排除。"""
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    # rel_path 相对 skill_path.parent，因此 parts[0] 是 skill 目录名，
    # parts[1]（如果存在）才是 skill 根目录下的第一层子目录。
    if len(parts) > 1 and parts[1] in ROOT_EXCLUDE_DIRS:
        return True
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_GLOBS)


def package_skill(skill_path, output_dir=None):
    """
    把一个 skill 目录打成 .skill 文件。

    Args:
        skill_path: skill 目录路径
        output_dir: .skill 输出目录；不传则默认当前目录

    Returns:
        返回生成出的 .skill 路径；失败时返回 None
    """
    skill_path = Path(skill_path).resolve()

    # 校验 skill 目录是否存在
    if not skill_path.exists():
        print(f"❌ 错误：找不到 skill 目录：{skill_path}")
        return None

    if not skill_path.is_dir():
        print(f"❌ 错误：路径不是目录：{skill_path}")
        return None

    # 校验 SKILL.md 是否存在
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"❌ 错误：在 {skill_path} 中找不到 SKILL.md")
        return None

    # 打包前先跑一次校验
    print("🔍 正在校验 skill...")
    valid, message = validate_skill(skill_path)
    if not valid:
        print(f"❌ 校验失败：{message}")
        print("   请先修复这些问题，再继续打包。")
        return None
    print(f"✅ {message}\n")

    # 决定输出目录
    skill_name = skill_path.name
    if output_dir:
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path.cwd()

    skill_filename = output_path / f"{skill_name}.skill"

    # 生成 .skill 文件（本质上是 zip）
    try:
        with zipfile.ZipFile(skill_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 遍历 skill 目录，同时排除构建垃圾和缓存文件
            for file_path in skill_path.rglob('*'):
                if not file_path.is_file():
                    continue
                arcname = file_path.relative_to(skill_path.parent)
                if should_exclude(arcname):
                    print(f"  已跳过：{arcname}")
                    continue
                zipf.write(file_path, arcname)
                print(f"  已加入：{arcname}")

        print(f"\n✅ 已成功打包到：{skill_filename}")
        return skill_filename

    except Exception as e:
        print(f"❌ 生成 .skill 文件时出错：{e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("用法：python utils/package_skill.py <path/to/skill-folder> [output-directory]")
        print("\n示例：")
        print("  python utils/package_skill.py skills/public/my-skill")
        print("  python utils/package_skill.py skills/public/my-skill ./dist")
        sys.exit(1)

    config = load_dazhuangskill_creator_config()
    skill_path = sys.argv[1]
    output_dir = coalesce(sys.argv[2] if len(sys.argv) > 2 else None, get_config_value(config, "package_skill.output_dir"))

    print(f"📦 正在打包 skill：{skill_path}")
    if output_dir:
        print(f"   输出目录：{output_dir}")
    print()

    result = package_skill(skill_path, output_dir)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
