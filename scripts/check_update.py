#!/usr/bin/env python3
"""轻量版本检查器：在 skill 启用时检查 GitHub 上是否有新版本。"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import (
    coalesce,
    configure_utf8_stdio,
    get_config_value,
    get_repo_root,
    load_dazhuangskill_creator_config,
    read_utf8_text,
    write_utf8_text,
)

configure_utf8_stdio()

DEFAULT_REPO = "DazhuangJammy/DazhuangSkill-Creator"
DEFAULT_BRANCH = "main"
DEFAULT_VERSION_FILE = "VERSION"
DEFAULT_INTERVAL_HOURS = 24
DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = "dazhuangskill-creator-update-check/1.0"
VERSION_RE = re.compile(r"^[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+.]?([0-9A-Za-z.-]+))?$")


@dataclass
class UpdateSettings:
    enabled: bool
    repo: str
    branch: str
    version_file: str
    version_url: str
    interval_hours: float
    timeout_seconds: int
    auto_update: bool
    remind_once_per_version: bool
    manual_update_command: str
    manual_update_url: str
    changelog_url: str
    state_file: Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso8601(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def default_state_file() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "dazhuangskill-creator" / "update-state.json"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(read_utf8_text(path))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_text(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def normalize_version(raw_value: str) -> str:
    return raw_value.strip()


def parse_version(raw_value: str) -> tuple[int, int, int, str] | None:
    value = normalize_version(raw_value)
    match = VERSION_RE.match(value)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)
    suffix = match.group(4) or ""
    return major, minor, patch, suffix


def compare_versions(left: str, right: str) -> int:
    parsed_left = parse_version(left)
    parsed_right = parse_version(right)
    if parsed_left and parsed_right:
        for left_value, right_value in zip(parsed_left[:3], parsed_right[:3]):
            if left_value != right_value:
                return (left_value > right_value) - (left_value < right_value)
        left_suffix = parsed_left[3]
        right_suffix = parsed_right[3]
        if left_suffix == right_suffix:
            return 0
        if not left_suffix and right_suffix:
            return 1
        if left_suffix and not right_suffix:
            return -1
        return (left_suffix > right_suffix) - (left_suffix < right_suffix)

    normalized_left = left.lstrip("vV")
    normalized_right = right.lstrip("vV")
    return (normalized_left > normalized_right) - (normalized_left < normalized_right)


def read_local_version(version_path: Path) -> str:
    return normalize_version(read_utf8_text(version_path))


def fetch_text(url: str, timeout_seconds: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/plain, application/json;q=0.9, */*;q=0.1",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8").strip()


def run_git_command(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def inspect_git_install(repo_root: Path, expected_repo: str) -> dict[str, Any]:
    top_level = run_git_command(repo_root, ["rev-parse", "--show-toplevel"])
    if top_level.returncode != 0:
        return {
            "mode": "manual",
            "remote_matches": False,
            "is_dirty": False,
            "branch": "",
            "remote_url": "",
            "reason": "当前安装不是 git clone 的工作区。",
        }

    remote = run_git_command(repo_root, ["remote", "get-url", "origin"])
    remote_url = remote.stdout.strip() if remote.returncode == 0 else ""
    branch = run_git_command(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch_name = branch.stdout.strip() if branch.returncode == 0 else ""
    status = run_git_command(repo_root, ["status", "--porcelain"])
    is_dirty = bool(status.stdout.strip()) if status.returncode == 0 else True

    return {
        "mode": "git",
        "remote_matches": expected_repo.lower() in remote_url.lower(),
        "is_dirty": is_dirty,
        "branch": branch_name,
        "remote_url": remote_url,
        "reason": "",
    }


def derive_default_version_url(repo: str, branch: str, version_file: str) -> str:
    safe_version_file = version_file.lstrip("/")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{safe_version_file}"


def derive_github_api_version_url(repo: str, branch: str, version_file: str) -> str:
    safe_version_file = version_file.lstrip("/")
    return f"https://api.github.com/repos/{repo}/contents/{safe_version_file}?ref={branch}"


def derive_repo_url(repo: str) -> str:
    return f"https://github.com/{repo}"


def derive_changelog_url(repo: str, branch: str) -> str:
    return f"https://github.com/{repo}/blob/{branch}/CHANGELOG.md"


def build_settings(args: argparse.Namespace, config: dict[str, Any]) -> UpdateSettings:
    update_config = get_config_value(config, "update_check", {})
    if update_config and not isinstance(update_config, dict):
        raise ValueError("config.yaml 里的 update_check 必须是一个 YAML 字典。")

    repo = str(coalesce(args.repo, get_config_value(config, "update_check.repo", DEFAULT_REPO)))
    branch = str(coalesce(args.branch, get_config_value(config, "update_check.branch", DEFAULT_BRANCH)))
    version_file = str(coalesce(getattr(args, "version_file", None), get_config_value(config, "update_check.version_file", DEFAULT_VERSION_FILE)))
    version_url = str(coalesce(args.version_url, get_config_value(config, "update_check.version_url", ""), "") or "")
    manual_update_url = str(
        coalesce(
            get_config_value(config, "update_check.manual_update_url", ""),
            derive_repo_url(repo),
        )
    )
    changelog_url = str(
        coalesce(
            get_config_value(config, "update_check.changelog_url", ""),
            derive_changelog_url(repo, branch),
        )
    )
    state_file = Path(coalesce(args.state_file, get_config_value(config, "update_check.state_file", ""), default_state_file())).expanduser()

    return UpdateSettings(
        enabled=bool(coalesce(getattr(args, "enabled", None), get_config_value(config, "update_check.enabled", True))),
        repo=repo,
        branch=branch,
        version_file=version_file,
        version_url=version_url,
        interval_hours=float(coalesce(args.interval_hours, get_config_value(config, "update_check.interval_hours", DEFAULT_INTERVAL_HOURS))),
        timeout_seconds=int(coalesce(args.timeout, get_config_value(config, "update_check.timeout_seconds", DEFAULT_TIMEOUT_SECONDS))),
        auto_update=bool(coalesce(args.auto_update, get_config_value(config, "update_check.auto_update", False))),
        remind_once_per_version=bool(coalesce(getattr(args, "remind_once_per_version", None), get_config_value(config, "update_check.remind_once_per_version", True))),
        manual_update_command=str(coalesce(get_config_value(config, "update_check.manual_update_command", ""), "") or ""),
        manual_update_url=manual_update_url,
        changelog_url=changelog_url,
        state_file=state_file,
    )


def should_skip_remote_check(state: dict[str, Any], interval_hours: float, force: bool) -> bool:
    if force or interval_hours <= 0:
        return False
    last_checked = parse_timestamp(str(state.get("last_checked_at", "")))
    if last_checked is None:
        return False
    return utc_now() - last_checked < timedelta(hours=interval_hours)


def resolve_update_command(settings: UpdateSettings, git_info: dict[str, Any]) -> str:
    if settings.manual_update_command:
        return settings.manual_update_command
    if git_info.get("mode") == "git" and git_info.get("remote_matches"):
        return "git pull --ff-only"
    return ""


def candidate_version_urls(settings: UpdateSettings) -> list[str]:
    if settings.version_url:
        return [settings.version_url]
    return [
        derive_github_api_version_url(settings.repo, settings.branch, settings.version_file),
        derive_default_version_url(settings.repo, settings.branch, settings.version_file),
    ]


def extract_version_payload(payload: str) -> str:
    stripped = payload.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped

    if isinstance(parsed, dict):
        encoded_content = parsed.get("content")
        encoding = parsed.get("encoding")
        if isinstance(encoded_content, str) and encoding == "base64":
            return base64.b64decode(encoded_content).decode("utf-8").strip()
        if isinstance(parsed.get("version"), str):
            return parsed["version"].strip()

    return stripped


def fetch_remote_version(settings: UpdateSettings) -> str:
    last_error: Exception | None = None
    for url in candidate_version_urls(settings):
        try:
            return normalize_version(extract_version_payload(fetch_text(url, settings.timeout_seconds)))
        except (HTTPError, URLError, OSError, ValueError) as exc:
            last_error = exc
    if last_error is None:
        raise OSError("没有可用的远端版本地址。")
    raise last_error


def attempt_auto_update(
    repo_root: Path,
    settings: UpdateSettings,
    git_info: dict[str, Any],
    latest_version: str,
) -> tuple[bool, str, str]:
    if git_info.get("mode") != "git":
        return False, "当前 skill 是手动复制安装，自动更新暂时只支持 git clone 方式。", ""
    if not git_info.get("remote_matches"):
        return False, "当前 git remote 不是官方仓库，已跳过自动更新。", resolve_update_command(settings, git_info)
    if git_info.get("branch") in {"", "HEAD"}:
        return False, "当前处于 detached HEAD 或无法识别分支，已跳过自动更新。", resolve_update_command(settings, git_info)
    if git_info.get("is_dirty"):
        return False, "当前 skill 目录有未提交改动，已跳过自动更新以避免覆盖本地修改。", resolve_update_command(settings, git_info)

    pull_result = run_git_command(repo_root, ["pull", "--ff-only"])
    if pull_result.returncode != 0:
        details = (pull_result.stderr or pull_result.stdout).strip()
        suffix = f" 详情：{details}" if details else ""
        return False, f"自动更新失败，已继续使用当前版本。{suffix}", resolve_update_command(settings, git_info)

    local_version = read_local_version(repo_root / settings.version_file)
    if compare_versions(local_version, latest_version) >= 0:
        return True, "已自动拉取最新版本；新版本会在下次调用这个 skill 时完整生效。", resolve_update_command(settings, git_info)

    return False, "已执行 git pull，但本地版本号没有追上远端 VERSION，建议手动检查分支和远端配置。", resolve_update_command(settings, git_info)


def build_result(status: str, current_version: str, latest_version: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "checked": False,
        "should_notify": False,
        "auto_updated": False,
        "current_version": current_version,
        "latest_version": latest_version or current_version,
        "cached_remote_version": "",
        "message": "",
        "update_command": "",
        "manual_update_url": "",
        "changelog_url": "",
    }


def evaluate_update(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = get_repo_root()
    config = load_dazhuangskill_creator_config(args.config)
    settings = build_settings(args, config)

    version_path = repo_root / settings.version_file
    current_version = read_local_version(version_path)
    git_info = inspect_git_install(repo_root, settings.repo)
    state = load_state(settings.state_file)

    result = build_result("skipped", current_version)
    result["update_command"] = resolve_update_command(settings, git_info)
    result["manual_update_url"] = settings.manual_update_url
    result["changelog_url"] = settings.changelog_url
    result["state_file"] = str(settings.state_file)

    if not settings.enabled:
        result["status"] = "disabled"
        result["message"] = "更新检查已在 config.yaml 中关闭。"
        return result

    if should_skip_remote_check(state, settings.interval_hours, args.force):
        result["status"] = "throttled"
        result["message"] = "最近已经检查过更新，当前跳过联网检测。"
        cached_remote = str(state.get("last_seen_remote_version", "")).strip()
        if cached_remote:
            result["cached_remote_version"] = cached_remote
            if compare_versions(cached_remote, current_version) >= 0:
                result["latest_version"] = cached_remote
                result["message"] = (
                    "最近已经检查过更新，当前跳过联网检测。"
                    f"上次远端缓存版本：v{cached_remote}。"
                )
            else:
                # Cache can be stale; do not surface a lower cached value as "latest".
                result["message"] = (
                    "最近已经检查过更新，当前跳过联网检测。"
                    f"上次远端缓存版本 v{cached_remote} 低于当前本地 v{current_version}，"
                    "本次按本地版本展示 latest。"
                )
        return result

    try:
        latest_version = fetch_remote_version(settings)
    except HTTPError as exc:
        result["status"] = "error"
        result["message"] = f"更新检查失败：远端 VERSION 不可用（HTTP {exc.code}）。"
        return result
    except URLError as exc:
        result["status"] = "error"
        result["message"] = f"更新检查失败：无法访问远端版本信息（{exc.reason}）。"
        return result
    except OSError as exc:
        result["status"] = "error"
        result["message"] = f"更新检查失败：{exc}"
        return result

    result["checked"] = True
    result["latest_version"] = latest_version
    state["last_checked_at"] = to_iso8601(utc_now())
    state["last_seen_remote_version"] = latest_version

    version_cmp = compare_versions(current_version, latest_version)
    if version_cmp == 0:
        result["status"] = "up_to_date"
        result["message"] = f"当前已是最新版本：v{current_version}。"
        save_state(settings.state_file, state)
        return result

    if version_cmp > 0:
        result["status"] = "ahead"
        result["message"] = f"当前本地版本 v{current_version} 高于远端 v{latest_version}，继续使用本地版本。"
        save_state(settings.state_file, state)
        return result

    if settings.auto_update:
        updated, message, command = attempt_auto_update(repo_root, settings, git_info, latest_version)
        result["update_command"] = command or result["update_command"]
        result["auto_updated"] = updated
        result["should_notify"] = True
        result["message"] = (
            f"检测到新版本：当前 v{current_version}，最新 v{latest_version}。{message}"
        )
        if updated:
            state["last_notified_version"] = latest_version
            result["status"] = "updated"
        else:
            result["status"] = "update_available"
            if settings.remind_once_per_version and state.get("last_notified_version") == latest_version:
                result["should_notify"] = False
            else:
                state["last_notified_version"] = latest_version
        save_state(settings.state_file, state)
        return result

    result["status"] = "update_available"
    result["message"] = (
        f"检测到新版本：当前 v{current_version}，最新 v{latest_version}。"
        "本次继续使用当前版本。"
    )
    if settings.remind_once_per_version and state.get("last_notified_version") == latest_version:
        result["should_notify"] = False
    else:
        result["should_notify"] = True
        state["last_notified_version"] = latest_version

    save_state(settings.state_file, state)
    return result


def print_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
        return

    print(result.get("message", ""))
    latest_version = result.get("latest_version")
    current_version = result.get("current_version")
    if result.get("should_notify") and latest_version and current_version and latest_version != current_version:
        if result.get("update_command"):
            print(f"建议更新命令：{result['update_command']}")
        if result.get("changelog_url"):
            print(f"更新日志：{result['changelog_url']}")
        elif result.get("manual_update_url"):
            print(f"项目地址：{result['manual_update_url']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查 dazhuangskill-creator 是否有新版本，并按配置决定是否自动更新。",
    )
    parser.add_argument("--config", default=None, help="config.yaml 路径（默认使用 dazhuangskill-creator/config.yaml）")
    parser.add_argument("--repo", default=None, help="覆盖 GitHub 仓库名，格式 owner/repo（CLI > config.yaml）")
    parser.add_argument("--branch", default=None, help="覆盖远端分支（CLI > config.yaml）")
    parser.add_argument("--version-file", default=None, help="覆盖本地/远端版本文件名（CLI > config.yaml）")
    parser.add_argument("--version-url", default=None, help="覆盖远端 VERSION 地址；主要用于测试或镜像源")
    parser.add_argument("--state-file", default=None, help="覆盖本地状态文件路径；主要用于测试")
    parser.add_argument("--interval-hours", type=float, default=None, help="覆盖检测间隔小时数（CLI > config.yaml）")
    parser.add_argument("--timeout", type=int, default=None, help="覆盖网络超时秒数（CLI > config.yaml）")
    parser.add_argument("--force", action="store_true", help="忽略检测间隔，强制联网检查")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果，便于 skill workflow 消费")
    parser.add_argument("--auto-update", dest="auto_update", action="store_true", default=None, help="强制开启自动更新（CLI > config.yaml）")
    parser.add_argument("--no-auto-update", dest="auto_update", action="store_false", help="强制关闭自动更新（CLI > config.yaml）")
    args = parser.parse_args()

    try:
        result = evaluate_update(args)
    except FileNotFoundError as exc:
        result = {
            "status": "error",
            "checked": False,
            "should_notify": False,
            "auto_updated": False,
            "current_version": "",
            "latest_version": "",
            "cached_remote_version": "",
            "message": f"更新检查失败：找不到必要文件（{exc}）。",
            "update_command": "",
            "manual_update_url": "",
            "changelog_url": "",
        }
    except ValueError as exc:
        result = {
            "status": "error",
            "checked": False,
            "should_notify": False,
            "auto_updated": False,
            "current_version": "",
            "latest_version": "",
            "cached_remote_version": "",
            "message": f"更新检查失败：{exc}",
            "update_command": "",
            "manual_update_url": "",
            "changelog_url": "",
        }

    print_result(result, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
