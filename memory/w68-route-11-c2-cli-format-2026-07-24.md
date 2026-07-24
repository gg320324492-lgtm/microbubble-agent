# 2026-07-24 W68 第 11 批 C-2: qa-bench CLI 统一 Markdown/JSON 行为 (锚点范式第 140 守恒)

> **一句话**: `tests/qa-bench/` 三个 runner (`run_d5_dry.py` + `phase2_dry_runner.py` + `phase3_matrix_runner.py`) 加 `--output-format {auto,json,md}` + `--input` + `--seven-d` flag, 统一 Markdown/JSON 输出契约 + JSON envelope (`format_version=1` + `schema=<runner>.v1`)。`save_to_kb.py` 5 道防线 (W62 D2) 与 W68 第 10 批 B-1 7d_scoring 集成通过新 flag 走单一路径。**0 production code 改动铁律完全维持** (本批仅 `tests/qa-bench/` + docs + memory)。

## 定位

- **锚点范式**: 第 140 守恒 (W68 第 11 批 C-2 CLI 统一段)
- **上游锚点**:
  - `w68-grand-closure-9th-batch-2026-07-24.md` (W68 第 9 批, 锚点范式 116)
  - `w68-route-10-c2-sop-runbook-2026-07-24.md` (W68 第 10 批 C-2 SOP 文档)
  - `w68-route-10-b1-phase3-matrix-2026-07-24.md` (W68 第 10 批 B-1 7d_scoring 集成, 锚点范式 124)
  - `w68-route-10-b2-save-to-kb-2026-07-24.md` (W68 第 10 批 B-2 save_to_kb 5 道防线 SOP)
- **同类先例**:
  - W68 第 8 批 B-4 (`c496862b7`) `phase3_matrix_runner.py` 已有 --report-out 默认 `.md`, 但**不**支持 JSON 输出
  - W68 第 7 批 B-2 (`fb7d6f9c`) `phase2_dry_runner.py` 已支持 1000 题 + 5 并发
  - W68 第 6 批 D-1 (`05b22e0a`) `run_d5_dry.py --full --per-intent` Phase 2 升级
- **main HEAD (派工前)**: `7b6f0305e` (W68 第 10 批 A-3 grand closure)
- **本批目标**: 单 commit 收口 (待主指挥 merge)

## 完整时间线

### T0: 派工触发 (W68 第 10 批 C-2 报告暴露)

W68 第 10 批 C-2 派工文档发现:
- `tests/qa-bench/run_d5_dry.py --output results.json` 实际生成 **Markdown** 而非 JSON
- W68 第 10 批 B-2 SOP 文档要求 `--input/--output` 走 JSON
- W68 第 10 批 B-1 (7 维评分) 集成 phase2/phase3 时, 必须保证 CLI 一致
- 主指挥跑前应 `--help` 核对, 但每次都得逐个核对 3 个 runner

**真实痛点**: SOP 文档描述 ≠ 实际 CLI 行为, 主指挥读 SOP 后仍可能踩坑。

### T1: 派工方案 (主指挥拍板)

主指挥派 1 个 agent (本任务):
1. **3 改** (`run_d5_dry.py` + `phase2_dry_runner.py` + `phase3_matrix_runner.py`)
2. **1 新增 e2e** (`test_cli_format.py`, 11 test)
3. **1 改 docs** (`docs/qa-bench-phase2-actual-run-2026-07-24.md`)
4. **1 新增 memory** (本文件)

不在 scope: 真接 save_to_kb 集成 (那是 W68 第 10 批 B-2 的活), 不在 production code 范畴。

### T2: CLI flag 设计 (5 铁律成型)

**核心 flag 三件套**:
1. `--output-format {auto,json,md}` (default `auto`)
2. `--input PATH` (default `None`, JSON/JSONL 通用)
3. `--seven-d` (default `False`, 触发七维评分)

**auto 推断规则**:
- `.json` suffix -> JSON
- `.md` / `.markdown` suffix -> Markdown
- 无 suffix -> **JSON** (SOP 文档要求)
- `--output-format json` / `md` 强制覆盖 suffix

### T3: 实施

3 个 runner 共用**同一组 helper 函数** (`_resolve_output_format` + `_dump_payload` + `_load_input_questions` + `_run_seven_d_scoring`):
- `run_d5_dry.py` 加 ~120 行 (3 helper + 3 flag + JSON 输出逻辑)
- `phase2_dry_runner.py` 加 ~150 行 (同上)
- `phase3_matrix_runner.py` 加 ~150 行 (同上)

`run_d5_dry.py` 0 行原有代码改动 (仅加法); phase2 + phase3 加 `getattr(args, "output_format", "auto")` 防御性读取, 保证现有 `test_phase2_dry_smoke.py` 仍 PASS。

### T4: e2e 测试 (`test_cli_format.py` 11 test)

5 场景 + 3 round-trip + 3 seven-d:

| # | Test | 验证 |
|---|---|---|
| 1 | `test_run_d5_dry_output_json_suffix_writes_valid_json` | `.json` suffix -> JSON envelope |
| 2 | `test_run_d5_dry_output_md_suffix_writes_markdown` | `.md` suffix -> Markdown 头部 |
| 3 | `test_run_d5_dry_output_without_suffix_defaults_to_json` | 无 suffix -> JSON (SOP) |
| 4a | `test_run_d5_dry_input_jsonl_round_trips_into_json` | --input 闭环 |
| 4b | `test_phase2_input_jsonl_round_trips_into_json` | phase2 --input 闭环 |
| 4c | `test_phase3_input_jsonl_round_trips_into_json` | phase3 --input 闭环 |
| 5a | `test_run_d5_dry_output_format_json_overrides_md_suffix` | 强制 JSON |
| 5b | `test_run_d5_dry_output_format_md_overrides_json_suffix` | 强制 Markdown |
| 6a | `test_run_d5_dry_seven_d_emits_intent_scoring` | phase1 seven-d |
| 6b | `test_phase2_seven_d_emits_intent_scoring` | phase2 seven-d |
| 6c | `test_phase3_seven_d_emits_intent_scoring` | phase3 seven-d |

跑测试结果:

```bash
cd tests/qa-bench && SKIP_DB_SETUP=1 python -m pytest test_cli_format.py -v
# 11 passed in 1.79s
```

整个 qa-bench 套件 (含原有 28 test) **39 passed in 2.32s**, 0 regression。

### T5: docs + memory 同步

- `docs/qa-bench-phase2-actual-run-2026-07-24.md` (W68 第 10 批 C-2 已建), 顶部 §1 改 CLI 文档, §2 加 JSON envelope 契约, §3 改 5 场景验证
- `memory/w68-route-11-c2-cli-format-2026-07-24.md` (本文件, 锚点范式第 140 守恒 + 5 新铁律)

## 5 新铁律

### 1. **CLI 统一协议 (3 runner 共用同一组 flag)**

qa-bench 任何 runner 改动**必须**带同一组 3 flag (`--output-format` / `--input` / `--seven-d`) + 同一 JSON envelope (`format_version=1` + `schema=<runner>.v1`)。新 runner 必须遵守, 旧 runner 升级时**必须**补齐。

**反面教训**: 升级 `run_d5_dry.py` 时若仅加 `--output-format`, 不补 phase2/phase3, SOP 文档就出现 "runner 协议不一致" 的错觉, 主指挥每次跑前都得逐个核对 `--help`。

### 2. **auto 推断: 无 suffix 永远默认 JSON**

W68 第 11 批 C-2 拍板: SOP 文档要求 SOP 跑前**永远**输出机器可读数据, 所以无 suffix 默认 JSON (而不是 Markdown)。

**例外**: 显式 `--output-format md` 或 `--output X.md` 时仍走 Markdown。

### 3. **--seven-d 必须复用 `runner.score_seven_dim`**

W68 第 10 批 B-1 已升级 `runner.score_seven_dim` 为 7 维评分单一入口。本批 `--seven-d` flag **必须**复用 `runner.score_seven_dim`, **禁止**复制粘贴一份新实现。

**dry 阶段七维启发式**: accuracy 维度用 pass-rate, 其他 6 维默认 1.0。未来 PR 可替换为真 LLM dim scoring 而不动 CLI。

### 4. **JSON envelope `format_version` + `schema` 必填**

JSON 输出必须含 `format_version` (整数或字符串) + `schema` (字符串, 形如 `run_d5_dry.v1`) 双重标识。loader 拒绝非 `format_version=1` 的 payload, `schema` 区分 3 个 runner 的字段集合差异 (phase3 有 `rollup` + `worker_summaries`, phase2 没有)。

**未来 breaking change 必须 bump `format_version`**, loader 必须先检查 `format_version` 再消费 `body`。

### 5. **CLI 文档同步 SOP 派工**

W68 第 11 批 C-2 派工时同步派 1 个文档 agent 改 `docs/qa-bench-phase2-actual-run-2026-07-24.md` 顶部 §1 CLI 协议。CLI 文档是 SOP 的**第一手资料**, 不允许代码改了文档没改 (W68 第 10 批 B-2 教训: SOP 写 `--input/--output` 但 CLI 实际只支持 `--output`)。

**纪律**: 任何 CLI flag 改动后, 必须立即:
1. 改 docs/qa-bench-*.md §1 CLI 协议节
2. 跑 `test_cli_format.py` 验证
3. 同步 memory/

## 实战验证

- **test_cli_format.py**: 11 passed in 1.79s (W68 第 11 批 C-2 全量回归)
- **整体 qa-bench 套件**: 39 passed in 2.32s (含原有 28 test, 0 regression)
- **JSON envelope 落地**: `format_version=1` + `schema=run_d5_dry.v1` / `phase2_dry_runner.v1` / `phase3_matrix_runner.v1` 三个 schema 名字清晰区分
- **7d_scoring 集成**: `--seven-d` 触发后生成 `seven_d_<phase>_dry.json`, 含 7 维评分 + 总分 + grade

## 经验与后续

- **CLI 升级 = 防御性 getattr**: phase2 + phase3 升级时必须用 `getattr(args, "output_format", "auto")` 防御性读取, 否则现有 `test_phase2_dry_smoke.py` 直接 AttributeError。W68 第 11 批 C-2 修复经验沉淀。
- **回滚路径**: `git revert <commit-hash>` 一行撤销 + 无需重新部署 (纯 tests/docs/memory 改动)。
- **下一 PR 风险**:
  - W68 第 12 批可能派 1 个 agent 集成 `save_to_kb.py` 5 道防线与 `--seven-d` flag, 复用本协议
  - Phase 4/5 新 runner 必须遵守本协议 (5 铁律 #1)
  - 7d_scoring 真 LLM 集成 PR 可替换 dry 启发式为真 dim scoring, 不动 CLI
- **派工模板升级**: 派工 prompt 模板应增加 "若写新 qa-bench runner, 必须遵守 CLI 统一协议" boilerplate (W68 第 11 批 D-1 可沉淀)。
- **memory/MEMORY.md**: 待主指挥 W68 第 11 批 grand closure 时补 1 行索引。

锚点范式计为第 140 守恒, 0 production code 改动铁律完全维持。