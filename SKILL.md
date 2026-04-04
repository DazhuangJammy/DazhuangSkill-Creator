---
name: dazhuangskill-creator
description: 用来创建、修改、评估、打包和优化其他 skill。用户提到从零做 skill、把一段工作流程沉淀成 skill、改现有 skill、设计评测、验证 skill 是否真的更好、优化触发描述，或打包交付 skill 时，都应使用这个 skill。
---

# Dazhuangskill Creator

用这个 skill 来创建、重塑、评估、打包其他 skill。把当前 `SKILL.md` 所在目录视为 `<skill-base>`，所有 bundled resources 都从这里解析，不要依赖调用方当前工作目录。

# 核心规则

- 先判断这个 skill 或改动值不值得存在，再决定怎么写。如果拿掉一块不会伤筋动骨，就优先删掉或不要加进去。
- 执行过程中始终显式维护两个状态：`current_path` 和 `current_step`。
  - `current_path` 只能是：新建 / 修改 / 评估 / 优化 / 打包
  - `current_step` 只能是当前正在执行的 `Step N`
  - 每次切换分支或进入重型操作前，先复述：当前路径、当前步骤、下一动作
  - 如果对话变长、插入大量工具输出、或任务目标变化，先回到 Step 1 重新判路，不要凭惯性继续
- 维持层级分工：
  - 主 `SKILL.md`：只放耐久规则、默认工作流、工作流内嵌指针
  - `references/`：长解释、示例、schema、低频模块说明
  - `assets/`：Claude 应该直接使用、复制、填写的模板或文件
  - `scripts/`：确定性或重复性执行
  - `config.yaml`：人会频繁修改的参数
- 默认路径要轻。不要一上来就跑重型 benchmark、blind comparison 或触发优化，除非用户真的需要这一级证据。
- 默认交付物也要轻。不要因为“以后可能有用”就顺手创建 `evals/`、workspace、`config.yaml`、`agents/openai.yaml`；只有当前任务真的需要，才把它们带进最终 skill。
- skill 内部文件指针默认写成可移植形式，例如 `<skill-base>/references/...`。不要把一次运行中的绝对路径写进最终交付物，除非用户明确要求做成只在当前机器使用的临时版本。
- 文件指针和命令都尽量写死、写全，例如 `cd "<skill-base>" && python3 scripts/...`。
- 根据用户技术水平调整术语密度；必要时简短解释，不要炫术语。
- 修改已有 skill 时，除非用户明确要求，否则保留原名。
- 修改 skill 后，要明确说明：主 body 留了什么、下沉了什么、删了什么。
- 不要把“记住流程”完全寄托在上下文残留上；要用状态播报主动刷新 workflow 锚点。
- 给新 skill 加 `# 索引` 不是默认强制项；只有当复杂度已经高到容易漂移时，才加入一个紧凑索引。
- 如果目标 skill 的默认产物本来就是单个极简结果（例如单行 commit、单条命令、单个标题），就把“默认只输出这一项”写成硬规则，并在最终检查里主动删掉不必要的 body、解释、备选项。
- 如果目标 skill 是 Conventional Commit、单行命令这类极简输出，不要把 body 触发条件写成“有帮助时可加”。要写成更窄的闭集：通常只有明确的 breaking change、迁移/弃用说明，或用户显式要求更多上下文时才允许 body；普通补充细节、测试更新、第二个子动作都不够构成扩写理由。
- 如果目标 skill 属于 Conventional Commit、PR 标题压缩、changelog 单行这类“高压缩判型”输出，而且某个边界误判代价很高，就允许保留 1 个极短 canonical example 或一条写死的边界规则来钉住它。尤其是公开接口变更：旧 public CLI flag / option / env var / config key / API field 只要被拒绝、移除、重命名，或被新名字替代，就按 breaking interface change 处理；默认倾向 `feat(scope)!`，必要时再补一行迁移 body，不要降成普通 `fix`。

# 默认工作流

## Step 1：先判断当前是什么任务

- 判断当前请求属于哪条路径：
  - 新建 skill
  - 修改现有 skill
  - 评估输出质量
  - 优化触发行为
  - 打包或交付 skill
- 进入这一步时，先设置：
  - `current_path` = 上面五种路径之一
  - `current_step` = `Step 1`
  - `next_action` = 用一句话说明接下来要做什么
- 如果用户还在探索或讨论阶段，就停留在结构判断/评审模式，不要强行进入实现或重型评测。
- 如果路径不清楚，先做最轻的结构判断，再决定是否继续下钻。

## Step 2：先定结构，再动笔

- 先确认最小必要信息：
  1. 这个 skill 要让 Agent 做什么？
  2. 它应该在什么情况下触发？
  3. 它应该产出什么结果或文件？
  4. 哪些内容必须留在主 body，哪些应该进 `references/`、`assets/`、`scripts/`、`config.yaml`？
  5. 这个 skill 是否需要额外的 `# 索引` 来帮助恢复上下文？
- 进入这一步时，更新：
  - `current_step` = `Step 2`
  - `next_action` = 补齐最小必要信息，先定结构再写正文
- 主 body 只保留耐久规则和默认工作流。
- 如果需要展开版写法指南，读 `<skill-base>/references/skill-architecture.md`。
- 如果只是想评审一个现有 skill 是否太胖、太散、太难执行，也先停在这一步，不要过早改写实现细节。
- 如果预计最终 skill 只是单文件、单产物，就先把“不创建额外目录/元数据/评测资产”视为默认方案，除非后面出现明确需求再加。
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
- 新 skill 如果适合先搭脚手架，就执行：`cd "<skill-base>" && python3 scripts/init_skill.py ...`
- 改已有 skill 时，优先保留真正承重的结构；把低频细节移到 bundled resources，而不是继续塞胖主 body。
- 长示例、长输出规格、长解释默认不要放在主 body，除非它们又短又关键。
- 如果任务属于“输入很脏、输出很稳”的结构化整理（例如访谈纪要、brief、研究总结），优先考虑补一份短而专的 `references/` 指南，而不是把抽取 heuristics 全塞进主 body。
- 如果这类结构化任务的最终输出本来就有固定章节或固定标题层级，把准确结构下沉到 `<skill-base>/assets/` 模板里，例如直接写死 `## Summary` 这类 heading level；不要只在正文里提章节名，让模型自己猜最终排版。
- 只有当目标交付环境真的需要 OpenAI 界面元数据时，才执行 `cd "<skill-base>" && python3 scripts/generate_openai_yaml.py ...`；不要把它当默认产物。
- 改写时优先让每个 Step 都只回答一件事：现在在哪条路径、下一步做什么、需要读哪个精确文件。
- 如果目标 skill 需要 `# 索引`，就让它只承担“恢复方向”这一件事：
  - 先复述 `current_path`、`current_step`、`next_action`
  - 再按当前路径直达精确文件
  - 明确写出“索引不替代 workflow”
- 如果目标 skill 很短、单路径、资源很少，就不要为了形式统一硬加 `# 索引`。
- 如果目标 skill 的默认交付物应该非常短，就把“什么时候允许扩写”写窄、写死；宁可偏保守，也不要让模型每次都顺手补一段解释或 body。优先写成明确条件列表，不要写成“有帮助时”“必要时补充更多背景”这种开放描述。
- 如果目标 skill 负责输出 Conventional Commit 这类高压缩结果，不要把高代价边界只留在脑补里；至少把反复出错的接口变更判型写死。旧 flag 被拒绝且新 flag 替代旧 flag，属于 breaking interface change，不是普通 `fix`。

## Step 4：选择最轻但有效的验证路径

- 进入这一步时，更新：
  - `current_step` = `Step 4`
  - `next_action` = 选一条最轻但仍可信的验证路径
- 只是讨论结构或架构：直接读文件并做判断。
- 快速体检：执行 `cd "<skill-base>" && python3 scripts/quick_validate.py <skill-dir>`，再配少量真实 prompt 做 sanity check。
- 标准输出质量迭代：读 `<skill-base>/references/eval-loop.md`；如果需要机器写入格式，再读 `<skill-base>/references/schemas.md`。
- 触发优化：读 `<skill-base>/references/description-optimization.md`。
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
