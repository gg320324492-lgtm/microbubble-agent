# W71 B 路线 5 Agents SubAgent 编排契约 (2026-07-24)

> **W71-C-2 派生新任务**: 派工纪要 v6 段 6 实战, 防止 B 路线 5 agents 跨服务调用时类型不匹配 / 数据结构不一致。
> **任务依据**: W71 派工 v6 段 5 反馈 #4 (SubAgent 编排接口协调) + W70-W71 plans backlog survey v2 调研发现 (子 plan ② 缺口 + 验收路径)。
> **范围**: 仅 `docs/` + `tests/qa-bench/mocks/` 新增, 0 production code 改动。
> **基线**: W68 第 14 批 A-3 调研 `docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md`。
> **目标锚点**: 锚点范式第 202 守恒。

## 1. W71 B 路线 5 Agents 概览

W71 选项 A 派 5 agents 验收子 plan ② 缺口。每个 agent 输出必须能精确契约验证:

| Agent | 文件 | 任务 | 状态 |
|-------|------|------|------|
| **B-1** | `tests/qa-bench/runner.py:465 score_seven_dim` | 七维评分验收 | 实施存在 (`63cdac3bb`) |
| **B-2** | `tests/qa-bench/save_to_kb.py:122 collect_candidates` | 五道防线矩阵/负测 | 实施存在 (`b388cc72b`)，5 道防线未独立模块 |
| **B-3** | `scripts/auto_intake_rollback.py:35 find_rollback_candidates` | Celery rollback 契约 | 脚本形态 (Celery beat 缺失, `64660718c`) |
| **B-4** | (端到端串联 B-1+B-2+B-3) | KB 闭环 E2E | 实施存在 (`0066087c8`)，闭环证据需补 |
| **B-5** | `tests/qa-bench/dashboard/gen_data.py:16 main` | Dashboard 验收 + smoke | 实施存在 (`4c7816c1e`) |

## 2. W71 B 路线 5 Agents 接口契约表

| Agent | 输出类型 | 下游 Agent | 关键字段 | Mock 模板 |
|-------|---------|-----------|---------|----------|
| **B-1** `score_seven_dim` | `dict[str, Any]` | B-2 `collect_candidates` | `dim_scores: dict[str, float]`, `total_score: int`, `grade: str`, `veto: bool` | `tests/qa-bench/mocks/score_item.json` |
| **B-2** `collect_candidates` | `list[dict[str, Any]]` | B-3 `find_rollback_candidates` | `qa_id: str`, `question: str`, `content: str`, `score: int`, `intent: str` | `tests/qa-bench/mocks/defense.json` |
| **B-3** `find_rollback_candidates` | `list[dict[str, Any]]` | B-4 (端到端串联) | `id: int`, `title: str`, `source_type: str`, `created_at: datetime` | `tests/qa-bench/mocks/rollback.json` |
| **B-4** (E2E 串联) | `dict[str, Any]` | B-5 Dashboard fetch | `stage: int`, `score: dict`, `defense: dict`, `review: dict`, `rollback_eligible: bool` | `tests/qa-bench/mocks/kb_loop.json` |
| **B-5** Dashboard fetch | (前端 HTML) | (主指挥视觉验证) | N/A | N/A |

### 2.1 B-1 → B-2 接口详解

```python
# B-1 输出 (实际代码: tests/qa-bench/runner.py:478-484)
{
    "dim_scores": {"intent": 1.0, "tool": 0.5, ...},  # 0-1
    "total_score": 84,  # 0-100
    "grade": "B",
    "veto": False,  # True if content<0.5 or defense<0.7
}

# B-2 输入 (实际代码: tests/qa-bench/save_to_kb.py:148)
# collect_candidates 读 onebyone_log.jsonl, 取 d["quality"]["auto_score"]
# d["quality"]["auto_score"] 即 B-1 输出的 total_score
# veto=True 必须过滤 (Veto 拒绝入库)
```

**字段守恒**: `total_score` (B-1) = `d["quality"]["auto_score"]` (B-2 读取) = `score` (B-2 candidate dict)

### 2.2 B-2 → B-3 接口详解

```python
# B-2 输出 (实际代码: tests/qa-bench/save_to_kb.py:165-174)
{
    "qa_id": "S-001",
    "question": "...",
    "content": "...",
    "scope": "qa-bench",
    "score": 84,  # = B-1 total_score
    "intent": "query_task",
    "tool_calls": [...],
    "rich_blocks": [...],
}

# B-3 输入 (实际代码: scripts/auto_intake_rollback.py:35-44)
# find_rollback_candidates 查 knowledge 表
# SELECT id, title, source_type, created_at FROM knowledge
#   WHERE source_type = 'auto_expansion' AND created_at < NOW() - 7 days
# 注意: B-2 输出走的是 candidate/queue (qa-bench runner),
#       B-3 输入走的是 DB 已入库条目 (auto_expansion)
#       衔接点: B-2 入库成功后, KB 行 source_type='auto_expansion' 被 B-3 7 天后扫描
```

**字段守恒**: B-2 candidate dict 中 `qa_id` 是 qa-bench 题号, 落库后与 B-3 扫描的 `knowledge.id` 通过 backup 备份映射 (`auto_intake_rollback.py:55 match_backups` 用 `qa:{id}` 字符串匹配)。

### 2.3 B-3 → B-4 接口详解

```python
# B-3 输出 (实际代码: scripts/auto_intake_rollback.py:43-44)
[
    {"id": 42, "title": "...", "source_type": "auto_expansion", "created_at": "..."},
    ...
]

# B-4 端到端串联输入:
# - B-1 七维评分 (780 题抽样)
# - B-2 candidate dict list (灰度过滤后)
# - B-3 rollback candidates (7 天后扫描)
# 串联产出 KB 闭环五阶段状态机:
```

### 2.4 B-4 → B-5 接口详解

```python
# B-4 输出 (设计契约, 实际待 B-4 agent 实施时落地)
{
    "stage": 4,  # 当前闭环阶段 (1=候选 / 2=评分 / 3=防线 / 4=入库审计 / 5=review)
    "score": {...},  # B-1 输出快照
    "defense": {...},  # B-2 五道防线逐项状态
    "review": {...},  # 24h/7d review 结果
    "rollback_eligible": True,  # 是否触发 rollback
}

# B-5 输入 (tests/qa-bench/dashboard/gen_data.py 读取)
# Dashboard 四卡片: 入库数 / 通过率 / 抽检数 / 告警数
# Dashboard 数据源: B-4 输出 JSON + data/auto_intake_summary.json + data/auto_intake_rollback_*.json
```

## 3. W71 B 路线 5 Agents 串联图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    W71 B 路线 5 Agents 串联图                        │
└─────────────────────────────────────────────────────────────────────┘

[B-1 score_seven_dim]              tests/qa-bench/runner.py:465
        │
        │  dict{dim_scores, total_score, grade, veto}
        ▼
[B-2 collect_candidates]           tests/qa-bench/save_to_kb.py:122
        │
        │  list[dict{qa_id, question, content, score, intent}]
        ▼
[POST /api/v1/knowledge/from-auto-expansion]   FastAPI 路由
        │
        │  knowledge.id + source_type='auto_expansion'
        ▼
[Celery beat daily 3:30 触发]
        │
        ▼
[B-3 find_rollback_candidates]     scripts/auto_intake_rollback.py:35
        │
        │  list[dict{id, title, source_type, created_at}]
        ▼
[B-3 rollback_entries]             scripts/auto_intake_rollback.py:47
        │
        │  dict{rolled_back: list[int]}
        ▼
[B-4 KB 闭环 E2E 串联]              (B-4 agent 实施时落地)
        │
        │  dict{stage, score, defense, review, rollback_eligible}
        ▼
[B-5 Dashboard gen_data]           tests/qa-bench/dashboard/gen_data.py:16
        │
        ▼
[HTML Dashboard 四卡片]            tests/qa-bench/dashboard/index.html
        │
        ▼
[主指挥视觉验收 + CI smoke 200]
```

## 4. 接口守恒验证 (typing imports + mypy 兼容)

### 4.1 typing imports 自检

**派工前提错误复盘 (派工 v4 铁律 3 实战)**: 任何新文件必须 `from typing import ...` 完备, 否则模块加载失败 → 工具一调就报。

```bash
bash scripts/check_typing_imports.sh   # 期望 0 错误
```

### 4.2 接口类型契约

```python
# B-1 输出契约 (实际已存在)
def score_seven_dim(
    expect: Dict[str, Any],
    actual: Dict[str, Any],
    auto_issues: List[Dict[str, Any]],
    expect_issues: List[Dict[str, Any]],
    duration_ms: int,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """Returns: {dim_scores: Dict[str, float], total_score: int, grade: str, veto: bool}"""

# B-2 输入契约 (实际已存在)
def collect_candidates(log_path: Path) -> list[dict]:
    """Each candidate: {qa_id: str, question: str, content: str, score: int, intent: str, ...}"""

# B-3 输入契约 (实际已存在)
def find_rollback_candidates(cur) -> list[dict]:
    """Each candidate: {id: int, title: str, source_type: str, created_at: datetime}"""
```

### 4.3 mock 数据类型约束

- `score_item.json`: `total_score` 必为 0-100 int, `veto` 必为 bool
- `defense.json`: `score` 必为 int, `intent` 必为 str
- `rollback.json`: `id` 必为 int, `created_at` ISO 8601 str
- `kb_loop.json`: `stage` 必为 int (1-5), `rollback_eligible` 必为 bool

## 5. 5 Agents 派工顺序 + 合并顺序表 (派工 v6 段 6 实战)

| 顺序 | Agent | 派工依据 | 合并依据 |
|------|-------|---------|---------|
| 1 | **B-1** 七维评分 | 其他 4 agent 依赖 score_item 输出 | 最先合 (接口契约基础) |
| 2 | **B-2** 五道防线 | 依赖 B-1 score (total_score/veto) | B-1 后合 (接口独立, 可与 B-3 并行) |
| 3 | **B-3** Celery rollback | 依赖 B-2 入库后的 knowledge 表 | B-2 后合 (DB schema 衔接) |
| 4 | **B-4** KB 闭环 E2E | 依赖 B-1+B-2+B-3 全部 | B-1+B-2+B-3 后合 (端到端串联) |
| 5 | **B-5** Dashboard | 依赖 B-1+B-2+B-4 输出 | B-4 后合 (前端 fetch) |

**派工实战**: 必先派 B-1 (其他 4 依赖), 等 B-1 commit 后派 B-2 + B-3 (并行, 接口独立), 等 B-2+B-3 commit 后派 B-4, 等 B-4 commit 后派 B-5。每个 agent 完工后必跑 mock 验证 (用上游 agent 输出 mock 测本 agent), 不依赖真接口。

## 6. Mock 数据模板 (5 JSON + __init__.py)

### 6.1 文件清单

- `tests/qa-bench/mocks/__init__.py` — mock loader (统一入口)
- `tests/qa-bench/mocks/score_item.json` — B-1 输出 mock (七维评分)
- `tests/qa-bench/mocks/defense.json` — B-2 输出 mock (候选 list)
- `tests/qa-bench/mocks/rollback.json` — B-3 输出 mock (rollback candidates)
- `tests/qa-bench/mocks/kb_loop.json` — B-4 输出 mock (KB 闭环五阶段状态机)

### 6.2 mock loader 用法 (B-1 → B-4 验证示例)

```python
from tests.qa_bench.mocks import load_mock

# B-2 agent 验证: 用 B-1 mock score_item 喂入
b1_output = load_mock("score_item")
# 期望: dict{dim_scores: {intent: 1.0, ...}, total_score: 84, grade: "B", veto: False}

# B-3 agent 验证: 用 B-2 mock defense 喂入
b2_output = load_mock("defense")
# 期望: list[dict{qa_id: "S-001", score: 84, ...}]

# B-4 agent 验证: 用 B-3 mock rollback 喂入
b3_output = load_mock("rollback")
# 期望: list[dict{id: 42, source_type: "auto_expansion", ...}]
```

### 6.3 typing 自检 (派工前提错误复盘 #2)

mock loader 必须 `from __future__ import annotations` + `from typing import Any` 完备, 避免 106 文件 typing check 回归。

## 7. SubAgent 编排 5 Agents 实战 (派工 v6 段 5 实战)

### 7.1 派工前提

1. **必先 commit partial diff** (B-3 教训)
2. **不动 v1-v6 历史约束** (派工 v6 第 4 条铁律)
3. **0 production code 改动铁律** (本任务纯 docs + mocks)
4. **接口必含 type hint** (派工 v6 段 6 实战)
5. **1 commit + defer message**

### 7.2 派工顺序 (防止接口不匹配)

```
Day 1 (派工 B-1):
  - B-1 agent 读 docs/w71-batch-orchestration-2026-07-24.md §2.1
  - B-1 输出 score_seven_dim 返回 dict{dim_scores, total_score, grade, veto}
  - 主指挥 merge B-1 commit
  - B-1 跑 tests/qa-bench/mocks/score_item.json 自验 (与 mock 字段一致)

Day 2 (派工 B-2 + B-3 并行):
  - B-2 agent 读 §2.2 + load_mock("score_item") 验证输入
  - B-3 agent 读 §2.3 + load_mock("defense") 验证输入
  - 两者接口独立可并行
  - 主指挥 merge B-2 + B-3 (顺序按 alembic 链纪律)

Day 3 (派工 B-4):
  - B-4 agent 读 §2.4 + load_mock("rollback") 验证 B-3 输入
  - B-4 端到端串联 B-1+B-2+B-3 输出
  - 主指挥 merge B-4 commit
  - B-4 跑 tests/qa-bench/mocks/kb_loop.json 自验

Day 4 (派工 B-5):
  - B-5 agent 读 §2.4 + load_mock("kb_loop") 验证 B-4 输入
  - B-5 Dashboard 验收 (前端 fetch 不依赖后端字段类型)
  - 主指挥 merge B-5 commit + 视觉验证
```

### 7.3 防接口不匹配 4 道关

1. **派工 prompt 必含接口契约表** (本 docs §2)
2. **每个 agent 完工后跑 mock 自验** (本 docs §6.2)
3. **typing imports 必跑 check_typing_imports.sh** (本 docs §4.1)
4. **接口变更必更新本 docs** (本任务维护责任)

## 8. 证据索引

- `tests/qa-bench/runner.py:465 score_seven_dim` — B-1 实际实施
- `tests/qa-bench/save_to_kb.py:122 collect_candidates` — B-2 实际实施
- `scripts/auto_intake_rollback.py:35 find_rollback_candidates` — B-3 实际实施
- `tests/qa-bench/dashboard/gen_data.py:16 main` — B-5 实际实施
- `docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md` — W68 第 14 批 A-3 调研依据
- `memory/w68-route-14-d4-w71-decision-2026-07-24.md` — W71 决策记录

> W71-C-2 派生新任务: docs-only + mocks-only; 目标锚点范式第 202 守恒。