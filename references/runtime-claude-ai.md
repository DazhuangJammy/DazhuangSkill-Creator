# 运行环境说明：Claude.ai

当这个 skill 运行在 Claude.ai，而不是本地 Codex 风格环境时，读这份文档。

默认把 `<skill-base>` 理解为当前 skill 的 `SKILL.md` 所在目录。

- 进入这份文档时，沿用主 `SKILL.md` 已经判定好的 `current_path`；这份文档只负责环境适配，不重写主路径。
- 执行过程中始终显式维护：`current_step` 和 `next_action`。
- 每次进入新步骤，或准备依赖浏览器、子代理、严格 benchmark 这类能力前，先复述：
  - 当前路径：沿用主流程
  - 当前步骤：`Step N`
  - 下一动作：一句话
- 如果任务已经不只是环境适配，而是回到了“评估 / 优化 / 打包”的主路径判断，回主 `SKILL.md` 的 Step 1 再决定走哪条 reference。

## Step 1：先确认 Claude.ai 里哪些能力还成立

- 进入这一步时，更新：
  - `current_step` = `Step 1`
  - `next_action` = 先确认 Claude.ai 里哪些能力可用，哪些要降级
- 高层流程仍然成立：起草 -> 测试 -> review -> 改进 -> 重复。
- 先假设本地工具、子代理、浏览器能力都可能比 Codex 弱，再按实际能力收缩方案。

## Step 2：把测试路径改成 Claude.ai 能稳定完成的版本

- 进入这一步时，更新：
  - `current_step` = `Step 2`
  - `next_action` = 用串行 sanity check 代替默认的并行子代理测试
- 测试用例优先串行执行，而不是并行子代理。
- 直接按照 skill 的说明完成任务。
- 把这一步视为 sanity check，而不是严格 benchmark。
- 如果环境不支持公平 baseline，对比就先跳过。

## Step 3：把 review 改成对话优先

- 进入这一步时，更新：
  - `current_step` = `Step 3`
  - `next_action` = 选择能在 Claude.ai 里稳定完成的 review 方式
- 如果打不开浏览器式 reviewer，就直接在对话里展示结果。
- 对于文件输出，把文件保存好并明确告诉用户路径。
- 反馈改成在聊天里直接收，而不是依赖完整 viewer 流程。

## Step 4：对 benchmark 和 trigger 优化保守降级

- 进入这一步时，更新：
  - `current_step` = `Step 4`
  - `next_action` = 判断哪些重路径要保留，哪些要跳过
- benchmark 更偏向定性 review，而不是重型定量 benchmark。
- 只有环境真的支持时，才上严格 benchmark 机制。
- 触发描述优化依赖 `claude` CLI 这套脚本链路。
- 如果环境不支持这些命令，就先跳过。
- 如果用户真正想做严格对比，回主 `SKILL.md` 的 Step 1，再判断是不是应该换到更适合的运行环境。

## Step 5：保留能用的打包交付能力

- 进入这一步时，更新：
  - `current_step` = `Step 5`
  - `next_action` = 在 Claude.ai 可行的前提下完成打包和交付
- 只要有 Python 和文件系统，打包仍然可用：

```bash
cd "<skill-base>" && python3 scripts/package_skill.py <path-to-skill-folder>
```

- 如果要进入完整交付路径，回 `<skill-base>/references/package-and-present.md`。

## Step 6：完成环境适配后，回主线继续

- 进入这一步时，更新：
  - `current_step` = `Step 6`
  - `next_action` = 把当前环境限制说明清楚，然后回主线继续执行
- 汇报时要说明：
  - 哪些流程照常可用
  - 哪些步骤被降级了
  - 哪些重路径被跳过了
  - 为什么这是 Claude.ai 下更稳的做法

## 索引

- 如果上下文变长、刚看完一大段环境限制说明、或需要重新找回方向，先复述：
  - `current_path`
  - `current_step`
  - `next_action`
- 然后按当前路径直达对应材料：
  - Claude.ai 适配主线：留在这份文档，继续当前 Step
  - 普通输出评测：回主 `SKILL.md` 的 Step 1，再看 `<skill-base>/references/eval-loop.md`
  - 触发描述优化：回主 `SKILL.md` 的 Step 1，再看 `<skill-base>/references/description-optimization.md`
  - 打包交付：回主 `SKILL.md` 的 Step 1，再看 `<skill-base>/references/package-and-present.md`
- 这个索引只用来快速恢复上下文，不替代上面的 Step 1 到 Step 6。
