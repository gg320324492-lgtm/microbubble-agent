# qa-bench Phase 2 实际跑 SOP（2026-07-24 W68 第 11 批 C-2 CLI 统一版）

> **状态**: W68 第 10 批 C-2 SOP 文档升级版（CLI 统一 Markdown/JSON 行为）。
> **目标读者**: 主指挥 + 任何后续派工的 agent。
> **锚点范式**: 第 140 守恒（W68 第 11 批 C-2）。

## §1 CLI 协议（W68 第 11 批 C-2）

`tests/qa-bench/` 三个 runner 现在遵循**统一 CLI** 协议：
- `run_d5_dry.py` (Phase 1 + Phase 2 dry-run)
- `phase2_dry_runner.py` (Phase 2 全 1000 题)
- `phase3_matrix_runner.py` (Phase 3 matrix 4 worker 并行)

### 1.1 关键 flag

| Flag | 默认 | 用途 |
|---|---|---|
| `--output PATH` (`run_d5_dry.py`) / `--report-out PATH` (phase2/3) | 当日默认名 `.md` | 输出路径 |
| `--output-format {auto,json,md}` | `auto` | 强制输出格式 |
| `--input PATH` | `None` | 自定义题库 JSON/JSONL |
| `--seven-d` | `False` | 跑完后调 7d_scoring |
| `--dry-run` / `--skip-llm` | `False` | 跳过 LLM |
| `--gate-threshold N` | 80 (Phase 1) / 90 (Phase 2/3) | 通过门槛 |

### 1.2 `--output-format` auto 推断规则

| `--output` 后缀 | 解析结果 |
|---|---|
| `.json` | JSON |
| `.md` / `.markdown` | Markdown |
| 无后缀 | **JSON** (默认) |
| `--output-format json` | JSON (强制) |
| `--output-format md` | Markdown (强制) |
| `--output-format auto` | 跟 suffix (默认) |

### 1.3 SOP 推荐用法

主指挥跑 Phase 2 真实 LLM 评测，**永远**用以下三种之一：

```bash
# 风格 A: .json 后缀, 显式确认机器可读
python tests/qa-bench/phase2_dry_runner.py --report-out results/phase2_$(date +%Y-%m-%d).json

# 风格 B: 显式 --output-format md 强制 Markdown
python tests/qa-bench/phase2_dry_runner.py --report-out results/phase2_$(date +%Y-%m-%d).md --output-format md

# 风格 C: 7d 评分集成 (W68 第 10 批 B-1)
python tests/qa-bench/phase2_dry_runner.py --report-out results/phase2_$(date +%Y-%m-%d).json --seven-d
```

**禁止**用 `--output results/phase2.md` 后再 `cat` 当 JSON 解析 —— CLI 统一后用户拿到的就是 Markdown 文本。

### 1.4 跑前 SOP（主指挥必做）

1. `cd tests/qa-bench && python run_d5_dry.py --help` —— 确认 `--output-format` / `--input` / `--seven-d` 在场。
2. `python phase2_dry_runner.py --help` —— 确认 `--report-out` 接受新 flag。
3. `python phase3_matrix_runner.py --help` —— 确认 `--seven-d` 在场。
4. **不**写 `--report-out results.json --output-format md` 之类的自相矛盾组合 —— 主指挥应一眼看出 lint 错误。

## §2 输出格式契约

### 2.1 JSON envelope (W68 第 11 批 C-2 规范)

```json
{
  "format_version": "1",          // 必填，loader 拒绝非 1
  "schema": "run_d5_dry.v1",      // 必填，区分 3 个 runner
  "phase": "phase1" | "phase2" | "phase3",
  "mode": "live-mimo" | "dry-fallback",
  "started_at": "ISO-8601",
  "finished_at": "ISO-8601",
  "summary": { ... },
  "notes": [ ... ],
  ...
}
```

`schema` 字段对应 `run_d5_dry.v1` / `phase2_dry_runner.v1` / `phase3_matrix_runner.v1`。
未来 schema breaking change 必须 bump `format_version` + `schema`。

### 2.2 Markdown 兼容

Markdown 输出保持 100% 旧格式（commit `c496862b7` 之前的所有内容），仅在末尾新增 "Output format: ..." 注脚。

### 2.3 seven-d 输出契约

`--seven-d` 触发后**额外**生成 `seven_d_<phase>_dry.json`：

```json
{
  "phase": "phase1|phase2|phase3",
  "format_version": "1",
  "source": "<runner>._run_seven_d_scoring",
  "intents": {
    "<intent_name>": {
      "dim_scores": { "intent": 1.0, "tool": 1.0, ... },
      "total_score": 85.71,
      "grade": "B",
      "veto": false
    }
  },
  "overall_total_score": 85.71
}
```

dry 阶段七维评分**启发式**：accuracy 维度用 pass-rate，其他 6 维默认 1.0。
未来 PR 可替换 `score_seven_dim` 调用为真 LLM dim scoring 而**不动 CLI**。

## §3 跨 CLI 协议验证（5 e2e 场景）

W68 第 11 批 C-2 agent 新增 `tests/qa-bench/test_cli_format.py`（11 个 test，**5 场景 + 3 round-trip + 3 seven-d**）：

| 场景 | Test | 期望 |
|---|---|---|
| 1. `--output .json` suffix | `test_run_d5_dry_output_json_suffix_writes_valid_json` | JSON envelope 含 `format_version=1` + `schema=run_d5_dry.v1` |
| 2. `--output .md` suffix | `test_run_d5_dry_output_md_suffix_writes_markdown` | Markdown 头部 `# W68 D6 Phase 1 Dry-run Report` |
| 3. `--output` 无后缀 | `test_run_d5_dry_output_without_suffix_defaults_to_json` | auto -> JSON |
| 4. `--input` + `--output` 闭环 | `test_*_input_jsonl_round_trips_into_json` (×3) | `summary.total` == 输入行数 |
| 5. `--output-format` 强制 | `test_run_d5_dry_output_format_*_overrides_*_suffix` (×2) | 即使 suffix 冲突，format 仍生效 |

跑测试：

```bash
SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/test_cli_format.py -v
```

期望 **11 passed**。

## §4 部署必做（CLAUDE.md 752 行铁律）

无 alembic 改动，无 docker image 改动 —— 仅文档 + tests + scripts/ 改动，**无需**部署重启。CLI 升级对调用方透明（auto 后缀推断 + 默认 JSON 兼容旧调用）。

## §5 后续 PR 风险

- 主指挥跑真 LLM 时必加 `--report-out *.json` 后缀，避免歧义。
- `save_to_kb.py` 5 道防线 W62 D2 集成若要自动调 `runner.score_seven_dim`，**禁止**复制 7d_scoring 实现，统一改 `--seven-d` flag。
- 若 Phase 4/5 新增 runner，必须遵守本协议（同一组 flag + 同一 JSON envelope + 同一 seven-d 输出契约）。

## 关联文件

- `tests/qa-bench/run_d5_dry.py` (修改)
- `tests/qa-bench/phase2_dry_runner.py` (修改)
- `tests/qa-bench/phase3_matrix_runner.py` (修改)
- `tests/qa-bench/test_cli_format.py` (新增，11 个 test)
- `memory/w68-route-11-c2-cli-format-2026-07-24.md` (新增，本任务沉淀)
- `memory/w68-route-10-c2-sop-runbook-2026-07-24.md` (W68 第 10 批 SOP 文档)

锚点范式计为第 140 守恒。0 production code 改动铁律完全维持（仅 tests/qa-bench/ + docs + memory）。