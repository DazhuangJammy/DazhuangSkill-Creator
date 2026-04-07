# Changelog / 更新日志

按版本记录主要更新，保持简洁，方便后续追踪。

## v1.4.0 - 2026-04-07

1. 补齐 macOS / Windows 双端兼容层，不改 skill 架构、不改 validator 判型标准，也不改 benchmark / trigger optimization 的方法论。
2. 统一仓库内文本文件读写为 UTF-8，并在读取时兼容 BOM，修复 Windows 上 `SKILL.md`、`config.yaml`、JSON / HTML / Markdown 因默认编码或 BOM 导致的失败。
3. 修复 `scripts/check_update.py`、`scripts/init_skill.py`、`scripts/quick_validate.py`、`scripts/generate_openai_yaml.py`、`eval-viewer/generate_review.py` 等脚本在 Windows 上的编码脆弱点。
4. 重写 `scripts/run_eval.py` 的子进程输出读取方式，去掉对 Unix 风格 `select + pipe` 的依赖，让触发评测和描述优化链路在 Windows 上可运行。
5. 更新 `README.md`、`README.zh-CN.md`、主 `SKILL.md` 与多份 `references/`，把关键命令改成跨平台写法：统一使用 `<python-cmd>` 概念，Windows 默认优先 `py -3`。
6. 版本号提升到 `1.4.0`，让现有更新检查链路把这次双端兼容更新识别成一个新版本。

## v1.3.1 - 2026-04-06

1. 把 `config.yaml` 的 `update_check.auto_update` 默认值改成 `true`，让干净的 git clone 安装默认尝试自动更新。
2. 更新 `README.md` 与 `README.zh-CN.md`，明确要求用户和安装型 AI 用 `git clone https://github.com/DazhuangJammy/DazhuangSkill-Creator.git` 安装，而不是手动复制文件夹，并补充可直接复制给 Claude / Codex 的标准安装提示词。
3. 同步更新主 `SKILL.md` 的自更新规则，明确当前 creator 的推荐安装方式是 git clone，并把默认更新策略改成“默认自动更新，可显式关闭”。
4. 版本号提升到 `1.3.1`，让现有更新检查链路能把这次行为调整识别成一个新版本。

## v1.3.0 - 2026-04-06

1. 新增根目录 `VERSION` 和 `scripts/check_update.py`，让 creator 在启用时能读取 GitHub 上的远端版本号并做轻量更新检查。
2. 扩充 `config.yaml` 的 `update_check` 配置块，支持开关、检测频率、远端仓库、提醒频率和可选自动更新。
3. 更新主 `SKILL.md` 的 Step 1，把“启用即检查更新”接进默认工作流，并明确更新失败不阻断主任务。
4. 自动更新默认仍关闭；只有在显式开启 `update_check.auto_update` 且当前安装是干净的 git clone 工作区时，才尝试 `git pull --ff-only`。
5. 更新 `README.md` 与 `README.zh-CN.md`，补充运行时更新检查、手动检查命令和自动更新的适用边界。
6. 把更新检查的默认网络超时放宽到 `10` 秒，降低首次访问 GitHub Raw 时的误报概率。
7. 远端版本读取改成优先 GitHub Contents API、失败再回退 GitHub Raw，提升不同网络环境下的可用性。

## v1.2.0 - 2026-04-06

1. 收紧单文件 skill 的结构规范，明确顶级 section 白名单只允许 `角色`、`规则`、`工作流程`、`例子`、`输出格式`、`索引`，并补充各 section 的使用边界。
2. 更新 `scripts/init_skill.py`，新增 `--sections` 参数和 `init_skill.sections` 配置，支持按需生成 `角色`、`例子`、`输出格式`、`索引` 这些可选 section。
3. 调整初始化脚手架与示例资源，统一把长例子下沉到 `references/examples.md`，把输出模板下沉到 `assets/output-format.md`，避免主 `SKILL.md` 继续膨胀。
4. 强化 `scripts/quick_validate.py`，新增对顶级 section 名称、顺序、必选项、内联长度和 `<skill-base>` 资源锚点的校验。
5. 更新 `SKILL.md`、`references/skill-architecture.md`、`README.md` 和 `README.zh-CN.md`，同步说明单文件闭集、下沉阈值以及新脚手架用法。
6. 扩充 `config.yaml` 初始化项，为新脚手架提供默认 `sections` 配置入口。

## v1.1.0 - 2026-04-05

1. 补充改已有 skill 的默认策略，明确 `轻优化`、`结构重构`、`完整改造` 三档力度。
2. 更新 `SKILL.md` 主流程，强调先做结构判断，再做触发优化和评测。
3. 扩写 `references/skill-architecture.md` 与 `references/description-optimization.md`，补齐重构边界。
4. 新增 `references/openai-yaml.md`，整理 OpenAI YAML 的最小字段说明和示例。
5. 更新 `README.md` 与 `README.zh-CN.md`，补充重构说明、使用建议和资料入口。
6. 补充 benchmark 展示材料与截图，方便直接在仓库里查看结果。
7. 新增本更新日志，后续版本继续在这里追加。

## v1.0.0 - 2026-04-04

1. 补齐中英文 README，正式说明项目定位、评测方法、核心结果和使用方式。
2. 整理仓库结构说明，方便用户快速浏览 `SKILL.md`、`references/`、`scripts/` 和 `测评报告/`。
3. 公开 benchmark 归档内容，让项目主页就能直接看到主要结论。

## v0.1.0 - 2026-04-03

1. 初始化仓库并完成首版项目导入。
2. 建立基础目录结构，放入核心 skill、参考资料和脚本骨架。
3. 完成远程仓库初始同步，作为后续迭代起点。
