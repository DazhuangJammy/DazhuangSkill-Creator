# 触发描述优化

当用户关心的是“这个 skill 会不会在对的请求上触发”，而不是普通输出质量时，读这份文档。

默认把 `<skill-base>` 理解为当前 skill 的 `SKILL.md` 所在目录。

- 一旦进入这份文档，先固定：`current_path` = `优化`。
- 执行过程中始终显式维护：`current_step` 和 `next_action`。
- 每次进入新步骤，或准备进入批量 eval、优化循环、report 分析这类重型操作前，先复述：
  - 当前路径：`优化`
  - 当前步骤：`Step N`
  - 下一动作：一句话
- 如果任务已经从“优化触发描述”漂移成“重写 skill 结构”或“评估输出质量”，不要继续沿用这份文档；先回主 `SKILL.md` 的 Step 1 重新判路。

## 什么时候该走这条路径

满足下面任一条时使用：
- skill 明显漏触发或误触发
- 用户想验证 frontmatter description 是否真的在发挥作用
- 触发行为的重要性足够高，值得反复跑 eval

不要对每个 skill 都自动做这一步。先确认 skill 本体结构已经站得住。

如果你怀疑问题不只是 description，而是 skill 本体太散、太长、太难恢复方向，也先回主 `SKILL.md` 重新判断要不要先修结构。

## Step 1：构造真实的 trigger eval set

- 进入这一步时，更新：
  - `current_step` = `Step 1`
  - `next_action` = 先构造足够真实、能测路由边界的 trigger eval set
准备大约 20 条 eval，分成两类：
- should-trigger
- should-not-trigger

写法规则：
- 要真实，不要写成抽象练习题
- 保留自然语言里的噪音：模糊表达、背景信息、错别字、口语化、真实任务细节
- 负例要选“近似场景”，不要选那种一看就毫不相关的垃圾负例
- 正例要覆盖多种说法，而不是只换几个同义词

你的目标是测试“用户意图路由”，不是关键词匹配。

## Step 2：先和用户一起看 eval set

- 进入这一步时，更新：
  - `current_step` = `Step 2`
  - `next_action` = 和用户一起把 eval set 调整到足够真实、足够刁钻
用内置 HTML 模板：

1. 读取 `<skill-base>/assets/eval_review.html`
2. 注入 skill 名、当前 description、eval JSON
3. 让用户在浏览器里调整后导出 eval set

这一步很关键。eval set 一旦质量差，后面的触发优化就会越调越偏。

## Step 3：运行优化循环

- 进入这一步时，更新：
  - `current_step` = `Step 3`
  - `next_action` = 跑优化循环，用 train / held-out 表现筛 description
- 进入循环前，先再做一次状态播报，确认你是在优化触发，而不是拿 description 去替代结构问题。
在 `<skill-base>` 下执行：

```bash
cd "<skill-base>" && python3 -m scripts.run_loop --eval-set <path-to-trigger-evals> --skill-path <path-to-skill> --model <current-session-model> --max-iterations 5 --verbose
```

这条循环会做这些事：
- 评估当前 description
- 做 train / held-out test 切分，尽量减少过拟合
- 对每条 query 跑多次，估计 trigger rate
- 根据失败样本提出新 description
- 反复重测候选 description
- 在有 held-out test 的情况下，按 held-out 表现选最佳结果

## Step 4：看 report，不只看分数

- 进入这一步时，更新：
  - `current_step` = `Step 4`
  - `next_action` = 看 pattern、看 train/test 差异，不只盯最高分
优化循环会生成 HTML report，里面通常会展示：
- 每次迭代
- 哪些 query 过了，哪些没过
- train/test 的表现差异
- 当前找到的最佳 description

看 pattern，不要只看最高分。

## Step 5：谨慎应用结果

- 进入这一步时，更新：
  - `current_step` = `Step 5`
  - `next_action` = 判断最佳 description 是否真的符合 skill 边界，再决定写回
把最佳 description 写回目标 skill 前，先确认：
- 它真的符合 skill 的真实边界
- 它没有退化成又臭又长的关键词表
- 它仍然清晰、紧凑、可读

最后给用户展示 before/after，以及分数变化。

## 什么时候要同时考虑 `# 索引`

description 优化解决的是“会不会触发”，不是“触发后会不会沿着正确主线执行”。

如果你看到下面这些信号，不要只改 description；要回主 `SKILL.md` 的 Step 1/Step 2，重新判断目标 skill 是否也需要一个紧凑 `# 索引`：

- 目标 skill 有多条路径分流，但正文里缺少恢复方向的入口
- 目标 skill 有很多 `references/`、`agents/`、`scripts/` 指针，长对话里容易忘
- 目标 skill 经常在大段工具输出、viewer、benchmark、批量运行后丢主线
- 问题看起来像“触发后会用，但老跑偏”，而不是“根本不触发”

## 触发机制的现实限制

description 再好，也只有在请求足够“值得用 skill”时才会显出效果。

这意味着：
- 极简单、一步就能做完的请求，可能即使 description 完美，也不会触发 skill
- 真正适合做 trigger test 的，是多步、复杂、专业化的请求

所以如果 eval set 太简单，优化出来的结果大概率是假的。

## 相关脚本

- 单次评估：`cd "<skill-base>" && python3 scripts/run_eval.py ...`
- 优化循环：`cd "<skill-base>" && python3 scripts/run_loop.py ...`
- description 改写器：`cd "<skill-base>" && python3 scripts/improve_description.py ...`

## 索引

- 如果上下文变长、刚看完一大段优化日志、或需要重新找回方向，先复述：
  - `current_path`
  - `current_step`
  - `next_action`
- 然后按当前路径直达对应材料：
  - 触发优化主线：留在这份文档，继续当前 Step
  - 如果怀疑是结构问题：回主 `SKILL.md` 的 Step 1，再看 `<skill-base>/references/skill-architecture.md`
  - 如果要跑普通输出评测：回主 `SKILL.md` 的 Step 1，再看 `<skill-base>/references/eval-loop.md`
  - 如果要看机器写入 schema：`<skill-base>/references/schemas.md`
  - 如果要直接跑脚本：`cd "<skill-base>" && python3 scripts/run_eval.py ...`、`cd "<skill-base>" && python3 scripts/run_loop.py ...`
- 这个索引只用来快速恢复上下文，不替代上面的 Step 1 到 Step 5。
