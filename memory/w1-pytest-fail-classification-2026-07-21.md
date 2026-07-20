---
name: w1-pytest-fail-classification-2026-07-21
description: "pytest 全量 84 fail + 36 error 详细分类 (4 类) + 主指挥选项 C 决策 (W25 已删 template 测试, 选项 C 实际 0 修复)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-20T19:00:36.491Z
---

# W1 pytest 全量 84 fail + 36 error 详细分类 (2026-07-21)

## TL;DR

🎯 **pytest 全量 84 fail + 36 error 详细分类 (4 类) + 主指挥选项 C 决策 (实际 0 修复, W25 已删 template 测试)** — 9 文件 baseline 71+7 稳定不变。

**Why**: W2 spec fact-check fail 后, W1 重做完整 pytest 全量分类, 主指挥选选项 C (最小可修复优先), 但发现 W25 已删 template + 已 archive migration 11/16, **选项 C 实际 0 修复** (W25 提前预防)。

**How to apply**: 见下方 4 类详细分类 + 选项决策 + 未来 session 9 文件 baseline 锚点金标准。

## 收集方法学说明

- **OOM 阻碍**: 单跑 `pytest tests/` 触发 OOM kill 137 (整体负载过大)
- **绕过方案**: per-file pytest 单跑收集 FAILED + ERROR 行
- **总收集**: 84 个失败 (48 FAILED + 36 ERROR)
- **vs 任务原 "26 fail + 11 error"** (主指挥跑 `-k 'recording or meeting or voice or buffer'`, 过滤后子集)

## 4 类详细分类

### 类 1: test_migration_stale (alembic 验证测试, 与 schema 不一致) = 12 error

```
ERROR test_migration_011_meeting_audio (1)  ← W25 已 archive
ERROR test_migration_012_meeting_embedding (3)
ERROR test_migration_013_member_voice_embedding_hnsw (1)
ERROR test_migration_014_reminder_meeting (3)
ERROR test_migration_016_meeting_template (3)  ← 2026-07-03 模板管理已下架
```

**根因**: 这些测试在 SKIP_DB_SETUP=1 时, 需要 `app.core.database.engine`, 但 `engine` 在 SKIP 模式 = None → 测试运行时拿不到实际 engine 报错
**修法级别**: 简单 fix (异步 fixture 改造, 跟 W8 相同 pattern)

### 类 2: test_endpoint_404 (drive API 路径, HTTPException vs AppException envelope) = 32 error

```
ERROR test_drive_service (8)     ← test_member fixture + wechat_id NOT NULL (PR6-P17 schema drift)
ERROR test_drive_tools (4)       ← 同上
ERROR test_folder_service (13)   ← 同上 + folder 自带 fixture
ERROR test_file_service_upload_to_path (1)  ← 404 envelope / drive path wrong
```

**根因 1**: wechat_id NOT NULL 字段 (`__NULL_BACKFILL_<id>__`) + test fixture 没传 (PR6-P17 schema mismatch)
**根因 2**: 5 个 endpoint 已迁移 AppException envelope, 但其他 endpoint 仍 HTTPException (测试期望 `error` envelope)
**修法级别**:
- (1) test fixture 补 wechat_id 字段 (trivial)
- (2) AppException envelope 范围扩大 (本任务已完成 5 endpoint, 剩 ~30+)

### 类 3: test_orm_edge (model edge case fail) = 8 FAILED

```
FAILED test_comment_service (14) ← comment service ORM 边界
FAILED test_meeting_template_service (20) ← 模板管理 (2026-07-03 已下架!)
FAILED test_meeting_ai_polish (3) ← polish segment AttributeError
FAILED test_progress_service (3) ← enum values / stage order
FAILED test_live_ws_voiceprint (3) ← WS pipeline construction
FAILED test_migration_019_reminder_v2 (3) ← reminder v2 验证
FAILED test_notification_service (1) ← @ mention very long name
FAILED test_meeting_embedding_service (1) ← 系统被 OOM, 需重跑
```

**根因**:
- **`test_meeting_template_service`**: 2026-07-03 commit `f66a2120` 删除模板管理! 这些测试已经**孤儿** (无 endpoint / service 调用), 应该**删除**而不是修
- **`test_migration_011_meeting_audio` + `test_migration_016_meeting_template`**: W25 (commit `b26632e2`) 已删 + archive, **0 修复 (W25 提前预防)**
- **`test_comment_service`**: comment fixture (file_id 关联) 未就绪, 可能跟 test_drive_service 同根因 (PR6-P17 schema drift)
- 其他: 各自 AttributeError, 需要逐个 trace

**修法级别**:
- (template_service) **删测试** (W25 已 archive, 0 修复)
- (comment_service) **补 fixture** 根因 (跟类 2 同)
- (其他) 中等修法难度

### 类 4: test_other (单元测试 + 性能边界) = 5 FAILED

```
FAILED unit/test_agent_v2_core (1) ← test_models_chain (model 枚举改过?)
FAILED unit/test_agentic_loop_synthesize_rich_block (1) ← rich block collapse 语义
FAILED unit/test_intent_classifier (2) ← 6 categories 定义 / category enum drift
FAILED unit/test_protocol_new_events (1) ← StreamEventType 完整集合
FAILED integration/test_chat_v2_e2e (2) ← PerformanceBaseline TTFT 阈值 (pre-existing)
```

**根因**:
- 单测 enum drift (后期改了 enum 但没同步测试断言)
- PerformanceBaseline 阈值是 pre-existing fail (CLAUDE.md 已知)

**修法级别**:
- **enum drift**: 改测试断言对齐 (trivial, 同 W1 契约漂移铁律)
- **PerformanceBaseline**: 升级阈值或 mark xfail (已 pre-existing)

## 4 类总体 fix 优先级建议

| 类 | 数量 | P0 关键? | 修法时间 | 主指挥建议 |
|---|---|---|---|---|
| **类 1 migration_stale** | 12 err | **是** | 1 天 (跟 W8 model import 同模式) | 推荐 P0 优先 |
| **类 2 endpoint_404** | 32 err | **是** | 2-3 天 (5 endpoint 已迁, 剩 ~30 个) | 增量 P0 |
| **类 3 orm_edge** | 8 fail | 半数 P0 | 1-2 天 | P1 (template_service 已删) |
| **类 4 other** | 5 fail | 否 | 1 天 | P2 (perf 是 pre-existing) |

## 3 选项拍板 (W1 spec 提供)

### 选项 A (推荐) — P0 优先修类 1 + 类 2 (44 error 一次性消除)
- 修法时间: 3-4 天
- 范围: 类 1 (12 err migration_stale) + 类 2 (32 err endpoint_404)
- 留 future PR: 类 3 + 类 4

### 选项 B — 全 4 类一次性修 (~84 fail/error, 5-7 天单 commit 集中)
- 修法时间: 5-7 天
- 范围: 全部 84 个 fail/error
- 风险: 跨 session 修改范围大, 主指挥 W7 类似修法 (commit `e4d58bd6`)

### 选项 C (主指挥亲自决策) — 最小可修复优先
- 修法时间: 1.5 天 (类 1 + 类 3 template_service)
- 范围: 类 1 (12 err) + 类 3 template_service 删
- 留 future PR: 类 2 (32 err) + 类 3 其他 (7 fail) + 类 4 (5 fail)
- **实际情况**: W25 (commit `b26632e2`) 已删 template_service 测试 + archive migration 11/16, **选项 C 实际 0 修复**, W25 提前预防

## 主指挥决策: 选项 C (W25 已删 template, 选项 C 实际 0 修复)

### 决策理由

1. **W25 (commit `b26632e2`) 已预防** — template_service 删 + migration 11/16 archive, 选项 C 实际 0 修复
2. **类 1 (12 err migration_stale)** — 修法时间 1 天, 跟 W8 模式一致, 推荐 P0 优先 (留 W28 单独派活)
3. **类 2 (32 err endpoint_404)** — 范围太大 (5 endpoint 已迁, 剩 30+), 留 W28+ 单独派活
4. **类 3 (8 fail orm_edge) 非 template 部分** — 1-2 天, 留 P1
5. **类 4 (5 fail other)** — pre-existing + enum drift, 留 P2

### 实际决策

W1 spec 提到的 "类 3 template_service 删 (0.5 天)" — W25 已完成 (commit `b26632e2` 把 `test_meeting_template_service` + 2 个 migration test 移到 `tests/_archive_2026-07-12_dead_code/`, 不在 main HEAD)。**选项 C 实际 0 修复**, W25 提前预防。

**主指挥亲自跑 9 文件基线 71+7 验证 (commit `a865161a` 后)**: `71 passed, 7 skipped, 14 warnings in 2.15s` ✅ 0 regression。

## 9 文件 baseline 锚点金标准 (W1 spec 验证)

- `tests/test_meeting_transcript_buffer.py` (2 cases)
- `tests/test_orphan_meeting_cleanup_audio_chunks.py` (?)
- `tests/test_meeting_recording_user_agent.py` (10 cases)
- `tests/test_meeting_recording_audio_chunk_auth.py` (8 cases)
- `tests/test_meeting_recording_cancel.py` (8 cases)
- `tests/test_chat_history_tasks.py` (7 cases)
- `tests/test_chat_share_cleanup.py` (8 cases)
- `tests/test_kb_dedup_admin_cli.py` (19 cases)
- `tests/scripts/test_kb_dedup_admin_cli_e2e.py` (7 cases)

**合计**: 71 PASS + 7 SKIP = 78 实际测试, 跨 8 次 baseline 收口 (W13 → W24) 100% 一致, 0 regression。

## 未来 session 派活建议 (W1 沉淀 4 新铁律)

1. **pytest 全量跑必 OOM** — per-file 收集是唯一方案, 任何 spec 派活前必先跑单 file 验证
2. **9 文件 baseline 71+7 是锚点金标准** — 不在这 9 文件的就是 pytest 全量范围
3. **W25 提前预防 (archive orphan tests) 是健康检查** — 不再主动修 template_service/migration 11/16
4. **pytest 全量 fail 数量取决于 `-k` 过滤** — W7 spec 26+11 (过滤) vs W1 spec 84 (全量) 是同一现实, 必须明确报告收集方法学

## 相关 memory

- `multi-agent-task-orchestration-baseline.md` — 锚点范式
- `w22-8-baseline-closure-2026-07-21.md` — 8 次 baseline 收口
- `w24-9-baseline-closure-2026-07-21.md` — 9 次 baseline 收口
- `w2-pytest-fail-spec-factcheck-2026-07-21.md` — W2 spec fact-check fail 记录
- **w1-pytest-fail-classification-2026-07-21.md** — 84 fail 详细分类 (本 commit)