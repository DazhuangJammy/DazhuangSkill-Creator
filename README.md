# Dazhuang Skill Creator

[中文文档](README.zh-CN.md) | English | [Changelog](CHANGELOG.md)

![Dazhuang Skill Creator benchmark overview](assets/benchmark-overview.png)

> Official original = Claude Code's official `skill-creator`  
> `My Skill Creator Copy` = my second iteration  
> `Dazhuang Skill Creator` = the final version in this repo

Dazhuang Skill Creator starts from Claude Code's official `skill-creator`, then rebuilds it with a stronger view of prompt architecture, skill architecture, and how CLI tool execution actually behaves in real usage.

This is not just a wording tweak. I reworked the workflow, structure, bundled resources, and maintenance model so the generated skill is easier to evolve, easier to debug, and easier to collaborate on over time.

For evaluation, I used Codex in headless mode - no GUI, no need to open the CLI page, just terminal execution - and ran at least 3 independent conversation tests per benchmark item. The full benchmark standards and archived reports are included in `测评报告/`.

If this project is useful to you, please consider giving it a star. For contact or collaboration:

- WeChat: `yinyinGyL`
- Email: `372749817@qq.com`

## What Was Benchmarked

### 1. Five task-type capability comparisons

- A | Content creation - whether prompts, templates, and platform style can be organized into reusable skills
- B | Structured output - whether the skill can follow a strict JSON schema and keep the output stable
- C | Tool research - whether it reads source files, cites evidence, and avoids hand-wavy summaries
- D | Script execution - whether the generated scripts actually run and fail safely when needed
- E | Hybrid orchestration - whether prompt, reference, asset, and script layers work together coherently

### 2. Five capability archetype comparisons

- Minimal compressed output
- Strict structured output
- Safety judgment
- Template-based abstraction
- Dirty-input normalization

## Evaluation Method

- Benchmarks were run with Codex headless mode in the terminal
- Each case was tested with at least 3 independent conversations
- The 3-version capability-archetype benchmark compared:
  - Claude Code official `skill-creator`
  - `My Skill Creator Copy` as the second iteration
  - `Dazhuang Skill Creator` as the final version
- The archived reports include:
  - `45 creation runs + 15 baselines` for the 3-version benchmark
  - `30 creation runs + 15 baselines` for the head-to-head task-type benchmark
- Source directory integrity checks remained clean during benchmarking (`manifest diff = 0`)

## Evaluation Dimensions

The benchmark scoring rolls up into five top-level dimensions:

- Process efficiency
- Precision
- Product quality
- Actual-use effect
- Stability

## Results

### Overall conclusion

- `Dazhuang Skill Creator` ranks first in both benchmark sets archived in this repo
- In the 3-version capability-archetype benchmark, the final version wins with a total score of `99.43`
- In the head-to-head task-type benchmark, the final version beats the official original with a total score of `99.44` vs `96.20`
- The result is a clear overall win, but not a "crushing" win according to the benchmark's own verdict rule

### 3-version capability-archetype benchmark

| Version | Total | Actual Use | Process | Precision | Quality | Stability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dazhuang Skill Creator | 99.43 | 98.64 | 100.00 | 99.53 | 100.00 | 100.00 |
| My Skill Creator Copy | 87.84 | 94.60 | 84.25 | 97.55 | 94.39 | 0.00 |
| Claude Code official `skill-creator` | 87.22 | 98.06 | 77.18 | 100.00 | 90.72 | 0.00 |

Key takeaways:

- Final version leads the runner-up by `11.59` points
- Final version achieves `100.0` downstream semantic accuracy in this benchmark set
- Final version is also the smallest of the three by average skill size (`4,290` bytes vs `7,063` and `6,613`)

### 5 task-type benchmark: final version vs official original

| Task Type | Official | Dazhuang | Result |
| --- | ---: | ---: | --- |
| A - Content creation | 100.00 | 100.00 | Tie |
| B - Structured output | 100.00 | 100.00 | Tie |
| C - Tool research | 98.89 | 100.00 | Dazhuang leads |
| D - Script execution | 100.00 | 100.00 | Tie |
| E - Hybrid orchestration | 83.72 | 83.82 | Dazhuang leads slightly |

Additional head-to-head results:

- Total score: `99.44` vs `96.20`
- Actual-use effect: `100.00` vs `98.08`
- Process efficiency: `97.74` vs `89.37`
- Downstream semantic accuracy: `96.76` vs `96.52`
- Runtime validation: both versions scored `100.0`

## Why This Version Is Easier To Maintain

Compared with the original version, this repo puts more emphasis on maintainable structure:

- Keep durable rules in the main `SKILL.md`
- Push long explanations into `references/`
- Put reusable templates into `assets/`
- Put deterministic or repetitive work into `scripts/`
- Keep frequently adjusted defaults in `config.yaml`

That makes follow-up iteration much easier. The original version can become hard to modify once generated, while this version is designed to remain editable and team-friendly over time.

## Default Strategy For Existing Skills

This repo no longer treats "optimize an existing skill" as "just tweak the `description`", and it does not treat refactoring as a separate methodology either.

- Creation and refactoring follow the same blueprint; the difference is whether you start from scratch or reorganize material from an old skill
- First diagnose whether the real issue is triggering, structure, or both
- If the old skill is bloated, scattered, or easy to derail across long contexts, default to structural refactoring so it realigns with the Dazhuang architecture
- Only run trigger eval / description optimization after the skill body itself is structurally sound
- The goal is alignment with the same blueprint, not mechanically forcing every skill into the same template; simple skills can still stay single-file

## Project Structure

- `SKILL.md` - the final Dazhuang Skill Creator skill definition
- `agents/` - benchmark and comparison agent prompts
- `references/` - architecture notes, evaluation workflow, packaging guidance, and schemas
- `assets/` - reusable assets and report templates
- `scripts/` - initialization, validation, evaluation, optimization, reporting, and packaging tools
- `config.yaml` - editable defaults for init, evaluation, optimization, and packaging
- `测评报告/` - archived benchmark reports and screenshots

## Quick Start

### Create a new skill scaffold

```bash
python3 scripts/init_skill.py my-skill --path ./out
```

### Validate a skill

```bash
python3 scripts/quick_validate.py ./out/my-skill
```

### Refactor an existing skill

- The refactor still follows the same blueprint used for new skills; it just starts by extracting what is worth keeping from the old skill
- First classify the intervention level as `light optimization`, `structural refactor`, or `full overhaul`
- If the problem is structural bloat, path drift, or losing the main line in long contexts, refactor `SKILL.md` and rebalance `references/`, `assets/`, and `scripts/` first
- Only move on to the trigger workflow after the structure is stable

### Evaluate triggering behavior

```bash
python3 scripts/run_eval.py \
  --eval-set ./path/to/eval-set.json \
  --skill-path ./out/my-skill
```

### Run the optimization loop

Use this only after the skill body is already structurally sound:

```bash
python3 scripts/run_loop.py \
  --eval-set ./path/to/eval-set.json \
  --skill-path ./out/my-skill
```

### Package a skill

```bash
python3 scripts/package_skill.py ./out/my-skill ./dist
```

## Benchmark Reports

You can inspect the archived benchmark outputs here:

- `测评报告/5 个能力原型对比/`
- `测评报告/5 个类型性能对比/`
- `测评报告/iShot_2026-04-04_12.17.26.png`

## License

Apache 2.0. See `LICENSE` and `LICENSE.txt`.
