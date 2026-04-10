---
name: dazhuangskill-creator
description: 用来创建、修改、重构、评估、打包和优化其他 skill。用户提到从零做 skill、把一段工作流程沉淀成 skill、改现有 skill、把别人的 skill 按当前这套架构重写、做轻优化或完整改造、设计评测、验证 skill 是否真的更好、优化触发描述，或打包交付 skill 时，都应使用这个 skill。
---

# 规则

- 把当前 `SKILL.md` 所在目录视为 `<skill-base>`。所有 bundled resources 都从这里解析，不要依赖调用方当前工作目录。
- 先判断这个 skill 或改动值不值得存在，再决定怎么写。如果拿掉一块不会伤筋动骨，就优先删掉或不要加进去。
- 执行过程中始终显式维护两个状态：`current_path` 和 `current_step`。
  - `current_path` 只能是：新建 / 修改 / 评估 / 优化 / 打包
  - `current_step` 只能是当前正在执行的 `Step N`
  - 每次切换分支或进入重型操作前，先复述：当前路径、当前步骤、下一动作
  - 如果对话变长、插入大量工具输出、或任务目标变化，先回到 Step 1 重新判路，不要凭惯性继续
- 维持层级分工：
  - 主 `SKILL.md`：只放耐久规则、工作流程，以及少量确实承重的可选 section
  - `references/`：长解释、内部例子、schema、低频模块说明
  - `assets/`：Claude 应该直接遵循、复制、填写的模板或文件
  - `scripts/`：确定性或重复性执行
  - `config.yaml`：人会频繁修改的参数
- 如果目标 skill 是单文件，主 `SKILL.md` 的顶级 section 只允许：`角色`、`规则`、`工作流程`、`例子`、`输出格式`、`索引`。其中必选只有 `规则` 和 `工作流程`。
- `角色`、`例子`、`输出格式`、`索引` 都不是默认必选项。只有拿掉它会明显降低稳定性时，才允许加入。
- `例子` 是给模型看的内部参考 / canonical case，不是给用户看的提问示例；用户入口示例属于 `description` 或触发层材料，不属于主 body 的 `例子`。
- `输出格式` 是给模型直接遵循的模板、骨架或字段约束，不是给用户解释“你会怎么输出”的说明文。
- 如果已经启用 `references/`，就不要再把长 `例子` 留在主 `SKILL.md`；如果已经启用 `assets/`，就不要再把长 `输出格式` 留在主 `SKILL.md`。
- 只要目标 skill 根目录下出现 bundled resources（例如 `references/`、`assets/`、`scripts/`、`agents/`、`evals/`、`config.yaml`），主 `SKILL.md` 就必须明确把当前 `SKILL.md` 所在目录定义为 `<skill-base>`，让模型知道所有本地资源相对谁解析。
- 单文件闭集、下沉阈值、校验规则这些“creator 级架构说明”，默认尽量留在 creator 和 validator；不要整段原封不动塞进每个目标 skill。目标 skill 只保留自己真正承重的最小结构规则。
- 默认路径要轻。不要一上来就跑重型 benchmark、blind comparison 或触发优化，除非用户真的需要这一级证据。
- 默认交付物也要轻。不要因为“以后可能有用”就顺手创建 `evals/`、workspace、`config.yaml`、`agents/openai.yaml`；只有当前任务真的需要，才把它们带进最终 skill。
- skill 内部文件指针默认写成可移植形式，例如 `<skill-base>/references/...`。不要把一次运行中的绝对路径写进最终交付物，除非用户明确要求做成只在当前机器使用的临时版本。
- 文件指针和命令都尽量写死、写全。把 `<python-cmd>` 视为当前环境可用的 Python 命令：macOS/Linux 通常是 `python3`，Windows 通常优先 `py -3`，其次 `python`。
- 当前 creator 的推荐安装方式是：把 `https://github.com/DazhuangJammy/DazhuangSkill-Creator.git` 用 `git clone` 放进 Claude Code / Codex / Open Claude 的 skill 目录；不要默认让用户或 AI 直接复制文件夹。
- 当前 creator 自带轻量更新检查。只要本地脚本可用且已经进入真实执行，不是纯讨论产品形态，就在 Step 1 开头运行 `<python-cmd> "<skill-base>/scripts/check_update.py" --json`。
- 更新检查、联网失败、或自动更新失败都不阻断当前任务；只有脚本返回 `should_notify = true` 时，才用 1-2 句告诉用户版本差异和下一动作。
- 自动更新默认开启；只要 `<skill-base>/config.yaml` 没有显式关闭 `update_check.auto_update`，并且当前安装是干净的 git clone 工作区，就允许脚本尝试 `git pull --ff-only`。
- 如果更新脚本返回 `status = updated`，说明本地文件已经拉到新版本，但这次调用仍沿当前已加载版本继续；新版本从下一次调用这个 skill 起完整生效。
- 根据用户技术水平调整术语密度；必要时简短解释，不要炫术语。
- 修改已有 skill 时，除非用户明确要求，否则保留原名。
- 给别人做优化时，默认先判断这次是同一套蓝图下的哪种力度：`轻优化`、`结构重构`、`完整改造`；不要把它们当成三套不同方法论。
- 新建 skill 和重构 skill 共用同一套架构目标：主 body 扛耐久规则和工作流程；单文件时按固定 section 白名单收；复杂到会漂移时才加紧凑 `# 索引`；长例子 / 长输出格式 / 长解释再按需要下沉。
- 重构现有 skill 时，把旧 skill 当作素材和脏输入，不当作格式约束；目标是按当前蓝图重新落盘，而不是尽量保留原写法。
- 这套蓝图强调对齐架构原则，不强调机械套模板；如果一个 skill 单文件就够稳，就不要为了形式统一硬拆目录。
- 修改 skill 后，要明确说明：主 body 留了什么、下沉了什么、删了什么。
- 不要把“记住流程”完全寄托在上下文残留上；要用状态播报主动刷新 workflow 锚点。
- 给新 skill 加 `# 索引` 不是默认强制项；只有当复杂度已经高到容易漂移时，才加入一个紧凑索引。
- 如果目标 skill 的默认产物本来就是单个极简结果（例如单行 commit、单条命令、单个标题），就把“默认只输出这一项”写成硬规则，并在最终检查里主动删掉不必要的 body、解释、备选项。
- 如果目标 skill 是 Conventional Commit、单行命令这类极简输出，不要把 body 触发条件写成“有帮助时可加”。要写成更窄的闭集：通常只有明确的 breaking change、迁移/弃用说明，或用户显式要求更多上下文时才允许 body；普通补充细节、测试更新、第二个子动作都不够构成扩写理由。
- 如果目标 skill 属于 Conventional Commit、PR 标题压缩、changelog 单行这类“高压缩判型”输出，而且某个边界误判代价很高，就允许保留 1 个极短 canonical example 或一条写死的边界规则来钉住它。尤其是公开接口变更：旧 public CLI flag / option / env var / config key / API field 只要被拒绝、移除、重命名，或被新名字替代，就按 breaking interface change 处理；默认倾向 `feat(scope)!`，必要时再补一行迁移 body，不要降成普通 `fix`。
- 新建 skill 时，“是否启用记忆层”是必做判断，不允许跳过。即使最后结论是 `off`，也要给出一句理由（例如：低风险、低变异、可确定性执行）。

# 工作流程

## Step 1：先判断当前是什么任务

- 判断当前请求属于哪条路径：
  - 新建 skill
  - 修改现有 skill（含 `轻优化` / `结构重构` / `完整改造` 的前半程）
  - 评估输出质量
  - 优化触发行为（只在 skill 本体结构已经站住时进入）
  - 打包或交付 skill
- 进入这一步时，先设置：
  - `current_path` = 上面五种路径之一
  - `current_step` = `Step 1`
  - `next_action` = 用一句话说明接下来要做什么
- 如果用户是在安装当前 creator，而不是在修改别的 skill，默认推荐 `git clone https://github.com/DazhuangJammy/DazhuangSkill-Creator.git` 到目标 skill 目录；不要默认走手动复制。
- 如果本地脚本可用且已经进入真实执行，先按需读取 `<skill-base>/config.yaml` 里的 `update_check`，再运行 `<python-cmd> "<skill-base>/scripts/check_update.py" --json`。
- 如果脚本返回 `should_notify = true`，只简短说明：当前版本、最新版本、是仅提醒还是已自动更新，然后继续当前任务。
- 如果脚本返回 `status = updated`，明确告诉用户“本地文件已更新，但这次调用继续沿当前已加载版本执行；下次调用会使用新版本”。
- 如果用户还在探索或讨论阶段，就停留在结构判断/评审模式，不要强行进入实现或重型评测。
- 如果路径不清楚，先做最轻的结构判断，再决定是否继续下钻。
- 如果用户说的是“优化一个现有 skill”，默认先停在 `修改现有 skill`，不要直接跳进 `优化触发行为`。
- 先判断这次更像哪一种：
  - `轻优化`：skill 本体结构基本站得住，只需要补 `description`、局部规则、边界、示例，或小的 workflow 修补
  - `结构重构`：skill 太胖、太散、太难恢复方向，需要把主 body 和 bundled resources 重排到当前这套架构里
  - `完整改造`：既要做结构重构，也要做触发优化或评测；顺序默认是先结构、后触发
- 这三档只是同一套蓝图下的干预力度，不代表三种不同的最终形状；最终都要回到当前这套架构目标。

## Step 2：先定结构，再动笔

- 先确认最小必要信息：
  1. 这个 skill 要让 Agent 做什么？
  2. 它应该在什么情况下触发？
  3. 它应该产出什么结果或文件？
  4. 哪些内容必须留在主 body，哪些应该进 `references/`、`assets/`、`scripts/`、`config.yaml`？
  5. 如果是改已有 skill，这次需要多大力度，才能把它拉回当前这套蓝图？
  6. 这个 skill 是否需要额外的 `# 索引` 来帮助恢复上下文？
- 进入这一步时，更新：
  - `current_step` = `Step 2`
  - `next_action` = 补齐最小必要信息，先定结构再写正文
- 主 body 默认只保留耐久规则和工作流程；只有 `角色`、`例子`、`输出格式`、`索引` 这四种可选 section 才允许额外出现。
- 如果是给别人做优化，先做轻量诊断：
  - 结构问题信号：主 body 混入长解释 / 长示例 / 低频模块；多路径却没有恢复入口；`references/` / `assets/` / `scripts/` 指针很多但缺少精确分流；长对话或大段工具输出后经常跑偏
  - 触发问题信号：边界本来清楚，但 skill 明显漏触发或误触发
  - 如果两类信号同时存在，默认先升到 `结构重构` 或 `完整改造`，不要先拿 `description` 顶着
- 如果目标是重构旧 skill，不要另外发明第二套主结构；直接用当前新建 skill 的蓝图判断哪些内容保留、下沉、删除、改写。
- 如果需要展开版写法指南，读 `<skill-base>/references/skill-architecture.md`。
- 如果只是想评审一个现有 skill 是否太胖、太散、太难执行，也先停在这一步，不要过早改写实现细节。
- 只有确认 skill 本体已经站住，才把 `<skill-base>/references/description-optimization.md` 当成下一步。
- 如果预计最终 skill 只是单文件、单产物，就先把“不创建额外目录/元数据/评测资产”视为默认方案，除非后面出现明确需求再加。
- 判断单文件 skill 要不要加可选 section 时，优先问：
  - 没有 `角色`，判断视角会不会明显跑偏？
  - 没有 `例子`，模型会不会缺少关键内部参考，导致高代价边界反复误判？
  - 没有 `输出格式`，模型会不会缺少稳定模板，导致交付结构明显不稳？
  - 没有 `索引`，长上下文里会不会经常丢主线？
- 需要 `角色` 时，再往下判断：这次更像“扮演角色”，还是“借用一个视角/判断框架”；两者可以都叫 `角色`，但正文里要明确主方向，不要混成半扮演半方法论。
- 判断新 skill 要不要加 `# 索引` 时，优先看是否至少满足下面两条：
  - 有 2 条以上路径分流
  - 有 3 个以上 `references/`、`agents/`、`scripts/` 指针
  - 会出现长工具输出、多轮迭代或批量运行
  - 有 Claude.ai / Codex / Cowork 之类的环境分支
  - 主 body 已经不是很短的单路径说明

## Step 3：起草或重写 skill

- 进入这一步时，更新：
  - `current_step` = `Step 3`
  - `next_action` = 起草或重写最小可用结构
- 新 skill 如果适合先搭脚手架，就执行：`<python-cmd> "<skill-base>/scripts/init_skill.py" ...`
- 新 skill 用 `init_skill.py` 时，默认先做记忆判型：优先用 `--memory-mode auto --intent "<任务语义>"`；如果明确要手动指定，也要说明为什么不是另外两种模式。
- 跑 `init_skill.py` 时，要么显式传 `--path <output-dir>`，要么提前在 `config.yaml` 里设置 `init_skill.output_path`；两边都没给会直接报错。
- 改已有 skill 时，不要把“保留原格式”当默认约束。把旧 skill 当作素材和脏输入，抽取承重内容后，按当前蓝图重新组织。
- 改已有 skill 时，优先保留真正承重的结构；把低频细节移到 bundled resources，而不是继续塞胖主 body。
- `轻优化`、`结构重构`、`完整改造` 只是在这套蓝图上的改动深浅不同；完成后都应该回到同一个目标形状。
- `轻优化` 也要朝当前蓝图收拢：修 `description`、边界或局部 Step 时，顺手删掉明显不承重的累赘。
- `结构重构` 的目标是：把主 body 压回耐久规则 + 工作流程，把低频内容下沉到 bundled resources。
- `完整改造` 的默认顺序：先让 skill 重新对齐这套蓝图并通过快速 sanity check，再决定要不要进入 trigger eval / description 优化。
- 长示例、长输出规格、长解释默认不要放在主 body，除非它们又短又关键。
- 如果任务属于“输入很脏、输出很稳”的结构化整理（例如访谈纪要、brief、研究总结），优先考虑补一份短而专的 `references/` 指南，而不是把抽取 heuristics 全塞进主 body。
- 如果这类结构化任务的最终输出本来就有固定章节或固定标题层级，把准确结构下沉到 `<skill-base>/assets/` 模板里，例如直接写死 `## Summary` 这类 heading level；不要只在正文里提章节名，让模型自己猜最终排版。
- 只有当目标交付环境真的需要 OpenAI 界面元数据时，才执行 `<python-cmd> "<skill-base>/scripts/generate_openai_yaml.py" ...`；不要把它当默认产物。字段说明和最小示例看 `<skill-base>/references/openai-yaml.md`。
- 改写时优先让每个 Step 都只回答一件事：现在在哪条路径、下一步做什么、需要读哪个精确文件。
- 如果目标 skill 需要 `# 索引`，就让它只承担“恢复方向”这一件事：
  - 先复述 `current_path`、`current_step`、`next_action`
  - 再按当前路径直达精确文件
  - 明确写出“索引不替代 workflow”
- 如果目标 skill 很短、单路径、资源很少，就不要为了形式统一硬加 `# 索引`。
- 如果目标 skill 仍然是单文件，就不要让模型自由发明新的顶级 section；只能在 `角色`、`规则`、`工作流程`、`例子`、`输出格式`、`索引` 里组合。
- 如果目标 skill 的默认交付物应该非常短，就把“什么时候允许扩写”写窄、写死；宁可偏保守，也不要让模型每次都顺手补一段解释或 body。优先写成明确条件列表，不要写成“有帮助时”“必要时补充更多背景”这种开放描述。
- 如果目标 skill 负责输出 Conventional Commit 这类高压缩结果，不要把高代价边界只留在脑补里；至少把反复出错的接口变更判型写死。旧 flag 被拒绝且新 flag 替代旧 flag，属于 breaking interface change，不是普通 `fix`。

## Step 4：选择最轻但有效的验证路径

- 进入这一步时，更新：
  - `current_step` = `Step 4`
  - `next_action` = 选一条最轻但仍可信的验证路径
- 只是讨论结构或架构：直接读文件并做判断。
- 快速体检：执行 `<python-cmd> "<skill-base>/scripts/quick_validate.py" <skill-dir>`，再配少量真实 prompt 做 sanity check。
- 如果 `quick_validate.py` 报 Step 4 缺少 `retry` / `failure` 事件命令，直接把 `memory_mode_guard.py --event retry` 和 `--event failure` 这两行补回目标 skill 的 Step 4。
- 优化现有 skill 的默认验证顺序是：先结构体检，再用少量真实 prompt 做 sanity check，最后才决定要不要跑 trigger eval。
- 标准输出质量迭代：读 `<skill-base>/references/eval-loop.md`；如果需要机器写入格式，再读 `<skill-base>/references/schemas.md`。
- 触发优化：读 `<skill-base>/references/description-optimization.md`。
- 不要拿 `<skill-base>/references/description-optimization.md` 去替代结构改造；description 只解决“会不会触发”，不解决“触发后会不会沿着正确主线执行”。
- Blind A/B 对比：读 `<skill-base>/agents/comparator.md` 和 `<skill-base>/agents/analyzer.md`。
- 打包或交付：读 `<skill-base>/references/package-and-present.md`。
- 运行环境不是标准本地 Codex：按需读 `<skill-base>/references/runtime-claude-ai.md` 或 `<skill-base>/references/runtime-cowork.md`。
- 如果只是做轻量 sanity check，不要顺手把 `evals/`、workspace、benchmark 资产写进最终 skill 目录；这些重资产只有在用户真的要评测闭环时才存在。
- 进入任何 benchmark、blind comparison、批量 eval 之前，先做一次状态播报，确认不是因为惯性把任务拉进重路径。

## Step 5：继续迭代，或者及时停下

- 进入这一步时，更新：
  - `current_step` = `Step 5`
  - `next_action` = 判断继续迭代还是停止，并说明理由
- 当 skill 已经足够好，继续加结构也买不来明显收益时，就停下。
- 不要因为“还有一种情况”就继续加规则。只有当新增结构能稳定避免重复失败或重复劳动时，才值得保留。
- 汇报时要说明：
  - 本轮用了哪种干预力度，为什么
  - 主 body 现在包含什么
  - 哪些内容被下沉
  - 哪些内容被删除
  - 为什么新结构更轻，但没有丢能力
- 如果目标 skill 的默认输出应该极简，停下前再专门检查一次：最终规则有没有把模型锁回单个结果，实际样例有没有偷偷长出 body、解释或多方案。
- 如果需要继续下一轮，先回到 Step 1 重判当前路径，而不是默认沿用上一轮的惯性路径。

# 索引

- 如果上下文变长、刚看完一大段工具输出、或需要重新找回方向，先复述一次：
  - `current_path`
  - `current_step`
  - `next_action`
- 然后按当前路径直达对应材料：
  - 结构起草或重写：`<skill-base>/references/skill-architecture.md`
  - 输出质量评测：`<skill-base>/references/eval-loop.md`
  - 触发描述优化：`<skill-base>/references/description-optimization.md`
  - 打包与交付：`<skill-base>/references/package-and-present.md`
  - 环境差异：`<skill-base>/references/runtime-claude-ai.md` 或 `<skill-base>/references/runtime-cowork.md`
  - 机器写入 schema：`<skill-base>/references/schemas.md`
  - 专用评测 agents：`<skill-base>/agents/grader.md`、`<skill-base>/agents/comparator.md`、`<skill-base>/agents/analyzer.md`
- 这个索引只用来快速恢复上下文，不替代 workflow；真正决定下一步的，仍然是 Step 1 到 Step 5。
