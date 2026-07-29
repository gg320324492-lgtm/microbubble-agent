# W68 第 7 批 A-2: cheerful-questing-kite 3 个新脚本 + 12 会议 anchor 自动化 — 锚点范式第 76 守恒

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 7 批 A-2"
> **分支**: `chore/w68-7th-batch-a2-cheerful-anchor-scripts-2026-07-24`
> **Plan**: `C:/Users/pc/.claude/plans/cheerful-questing-kite.md`
> **锚点范式**: W68 第 7 批 76 守恒 (W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → **W68 第 7 批 76**)
> **0 production code 改动铁律**: 维持 (本任务 6 文件全部在 scripts/ + tests/ + docs/ + memory/)

---

## TL;DR

🎯 **Plan cheerful-questing-kite 闭环 100%** — 3 个新脚本 `list_anchors.py` / `mark_voice_confirmed.py` / `incremental_anchor.py` 全部落地. 12 会议清单 (杜同贺 + 张宏魁 已 confirmed) + 月度巡检 SOP 全部行文. **0 production code 改动铁律 100% 维持** (6 文件全是 scripts/ + tests/ + docs/ + memory/, 不动 app/).

**Why**: plan 实施已达 95% (schema + 核心代码 + skip 守卫完成), 缺**主指挥可执行工具层**. 没有这 3 个脚本, 12 会议清单 2 anchor mark confirmed 是手工 SQL 操作, 不可审计 + 不可批量 + 不可定期巡检.

**How to apply**: 见下方 6 文件清单 + 3 新铁律 + 12 会议清单 + 月度 SOP.

---

## 一、plan 状态回溯

### 1.1 已完成 (95%)

- ✅ Schema (alembic 036) — `voice_confirmed_at` / `voice_confirmed_by` / `voice_confirmed_meeting_id` 3 列
- ✅ 核心代码 — `get_anchor_members` (line 374) + `identify_speaker_anchored` (line 392)
- ✅ skip-confirmed 守卫 — `purify_voiceprints_from_meeting.py:188` (累计时跳过已 anchor)
- ✅ 2 anchor mark confirmed — 杜同贺 (会议 153) + 张宏魁 (会议 151)

### 1.2 待补充 (本任务闭环)

- ✅ `scripts/list_anchors.py` (~210 行) — 列出 anchor 成员 (table + JSON)
- ✅ `scripts/mark_voice_confirmed.py` (~250 行) — 单次 mark anchor + audit
- ✅ `scripts/incremental_anchor.py` (~280 行) — 批量候选扫描 + apply
- ✅ `tests/e2e/test_anchor_scripts_smoke.py` (~430 行, 10 场景)
- ✅ `docs/voiceprint-anchor-scripts.md` (~280 行)
- ✅ `memory/w68-route-7-a2-cheerful-questing-anchor-2026-07-24.md` (本文件)

**核心纪律**: 0 production code 改动 = 复用 `app/services/voiceprint_service.py:get_anchor_members` + `Member` / `MemberVoiceHistory` ORM, 全部 reads/writes 走脚本 in-function 拉 engine.

---

## 二、6 文件清单

### 2.1 新增 (3 个 scripts)

| 文件 | 行数 | 用途 |
|---|---|---|
| `scripts/list_anchors.py` | ~210 | 列出 anchor + (可选) 已 enrolled 未 confirmed |
| `scripts/mark_voice_confirmed.py` | ~250 | 单次 mark anchor (dry-run 默认, --apply 才写) |
| `scripts/incremental_anchor.py` | ~280 | 批量候选扫描 (min_samples + days_lookback) |

### 2.2 新增 (1 个 e2e + 1 个 docs + 1 个 memory)

| 文件 | 行数 | 用途 |
|---|---|---|
| `tests/e2e/test_anchor_scripts_smoke.py` | ~430 | 10 场景 sqlite + fakeredis e2e |
| `docs/voiceprint-anchor-scripts.md` | ~280 | 月度 SOP + 12 会议清单 + 部署必做 |
| `memory/w68-route-7-a2-cheerful-questing-anchor-2026-07-24.md` | ~280 | 本文件 (沉淀 3 新铁律) |

**6 文件合计**: ~1730 行. 0 production code 改动 (脚本用 in-function 拉 engine, 不动 app/).

### 2.3 复用 (5 个已闭环文件)

| 文件 | 使用的元素 |
|---|---|
| `app/services/voiceprint_service.py:374` | `get_anchor_members` (脚本不直接调, 走自己的 query) |
| `app/models/member.py:55-57` | `voice_confirmed_at/by/meeting_id` 字段 |
| `app/models/member_voice_history.py` | 审计表 (`source="anchor_confirmed"`) |
| `scripts/purify_voiceprints_from_meeting.py:188` | skip-confirmed 守卫 (本任务**不动**) |
| `alembic/versions/036_add_voice_confirmed.py` | schema 增量 (本任务**不动**) |

---

## 三、3 新铁律 (本次任务沉淀)

### 铁律 1: incremental_anchor 阈值设置

**铁律内容**: `incremental_anchor.py --min-samples` 默认 5, `--days` 默认 30. **不要把 min_samples 调太低** (e.g. 3) — 否则会把"刚被识别 1-2 次的新成员"误标的判为 anchor 候选. **也不要调太高** (e.g. 30) — 否则永远没候选.

**实战证据 (W68 第 7 批)**:
- 杜同贺 (anchor #1): 4 samples → 当时是手工 mark, 不在本脚本触发
- 张宏魁 (anchor #2): 125 samples → 远超 min_samples=5 阈值 ✅
- 陈金薪 (强候选): 33 samples → 强建议 mark_confirmed (≥ 5*4=20)
- 周之超 (中等候选): 12 samples → 中等建议 review (≥ 5*2=10)
- 贾琦 (hold): 1 sample → 不达标 (< 5)

**纪律**:
1. `min_samples` 默认 5 — 配合 cross-anchor 策略"每个新成员用 1-2 场会议就能累积", 5 是最低样本数门禁
2. `suggestion` 字段分级 — `mark_confirmed` (≥ 4x) / `review_manually` (≥ 2x) / `hold_continue_learning` (< 1x)
3. 调阈值需主指挥拍板 — 任何调整必须写 memory 沉淀

### 铁律 2: mark_voice_confirmed 审计

**铁律内容**: `mark_voice_confirmed.py` **必须**写 `MemberVoiceHistory` audit (source= `"anchor_confirmed"`, notes 含 meeting_id + confirmed_by). **不要**省略 audit — anchor 是单向不可逆操作, 没有 audit 链无法追溯谁确认 / 何时确认 / 哪场会议触发.

**实战证据 (W68 第 7 批 e2e 验证)**:
```python
# mark_voice_confirmed.py:171-181
history = MemberVoiceHistory(
    member_id=m.id,
    source=AUDIT_SOURCE_ANCHOR_CONFIRMED,  # "anchor_confirmed"
    old_embedding=list(m.voice_embedding) if m.voice_embedding is not None else None,
    new_embedding=new_emb,
    sample_count_before=int(m.voice_sample_count or 0),
    sample_count_after=int(m.voice_sample_count or 0),
    weight=None,
    notes=(
        f"anchor_confirmed: meeting_id={meeting_id}, "
        f"confirmed_by={confirmed_by}"
    ),
)
```

**纪律**:
1. **每 1 次 mark_confirmed 必写 1 条 audit** — 写库失败也要 `try/except + logger.error(exc_info=True)` 至少记日志 (CLAUDE.md 5 条铁律: 持久化失败 must best-effort)
2. **force override 必加 FORCE OVERRIDE 标记** — 防止后续看不懂 audit 链
3. **audit notes 含 meeting_id + confirmed_by** — 后续 audit 链反查必备

### 铁律 3: list_anchors 定期巡检

**铁律内容**: `list_anchors.py` 应**每月由主指挥跑 1 次** (月度 SOP). **不要**只在 mark_confirmed 时跑 — 容易忘看 anchor 链增长趋势 + 候选成员清单.

**实战证据 (W68 第 7 批)**:
- 当前 2 anchor (杜同贺 + 张宏魁) — 显然不够, 12 会议清单 5+ 候选待 mark
- 候选成员 3 个 (陈金薪 33 / 周之超 12 / 贾琦 1) — 至少 1 个强候选应月度 mark
- 未 enabled 模式: `--include-unconfirmed` 可看完整候选链

**月度 SOP** (详见 docs/voiceprint-anchor-scripts.md §3.2):
```bash
# 1. 巡检
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/list_anchors.py --include-unconfirmed

# 2. 扫描候选
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/incremental_anchor.py --days 30 --min-samples 5

# 3. 逐个成员 mark_confirmed (按 suggestion 优先 mark_confirmed)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/mark_voice_confirmed.py \
  --member-name "陈金薪" --meeting-id 167 --confirmed-by "user" --apply

# 4. 验证
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/list_anchors.py
```

**纪律**:
1. **月度月初头 1 周执行** — 不抢时间, 主指挥工作流不阻塞
2. **优先 mark_confirmed 强证据** — 跳过 review_manually (那些累积样本还不够)
3. **不批量 mark** — 每个成员单独执行, 失败不影响后续
4. **mark 后必 list_anchors 验证** — 闭环确认 audit 链生效

---

## 四、12 会议清单 + anchor 状态

### 4.1 已知 anchor (2 个)

| # | 成员 | 会议 ID | mark 时间 | 备注 |
|---|---|---|---|---|
| 1 | 杜同贺 | 153 | 2026-06-28 12:37:04 | 手工 mark (干净录入 4 段) |
| 2 | 张宏魁 | 151 | 2026-07-02+ | 累积 125 samples |

### 4.2 候选 anchor (3 个, 本任务列出可立即 mark)

| # | 成员 | 累积 samples | suggestion | 建议 |
|---|---|---|---|---|
| 3 | 陈金薪 | 33 | mark_confirmed | **下一批 mark_confirmed** |
| 4 | 周之超 | 12 | review_manually | 主指挥 review |
| 5 | 贾琦 | 1 | hold_continue_learning | 累积不够, 不 mark |

### 4.3 12 会议清单 (plan 原表)

| 会议 ID | 标题 | 当前状态 | anchor 链期望路径 |
|---|---|---|---|
| 064 | 小气助手软件适配性测试 | ✅ 已 4 人 | 杜同贺 + 吴孟铨 → 候选 mark |
| 068 | 臭氧气泡实验变量分析 | ✅ re-purify | **陈金薪 → mark_confirmed 候选 #3** |
| 070 | 实验数据可靠性排查 | ✅ 已完成 | 贾琦 → 候选 |
| 071 | 臭氧微纳米气泡实验条件 | ✅ 已完成 | 周之超 → 候选 |
| 083 | 持续研究UV臭氧纳米气泡 | ⚠️ rollback | 待用户复核 |
| 095 | 水产养殖纳米气泡 | ⏳ 待处理 | 听音频后 anchor 链识别 |
| 120 | 实验相关工作安排 | ⏳ 待处理 | 同上 |
| 121 | 普通泡与纳米气泡技术对比 | ⏳ 待处理 | 同上 |
| 122 | 声纹识别与音频上传机制 | ⏳ 待处理 | 同上 |
| 135 | 研究方案讨论与实验指导 | ✅ override | 王天志 + 韩重阳 → 复核 |
| 151 | 同贺实验相关讨论 | ⚠️ partial | **张宏魁 → 已 confirmed #2** |
| 153 | (合并到 151) | (跳过) | (跳过) |

---

## 五、跨任务累计

### 5.1 锚点范式

- W68 第 7 批 76 守恒 (W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 7 批 **76**)
- 单调上升: **0 下降** (跨 67+ commit / 27+ worker / 6+ batch)

### 5.2 0 production code 改动铁律

- W68 第 7 批本任务 6/6 守恒 (3 脚本 + 1 e2e + 1 docs + 1 memory)
- 累计: 锚点范式 6/6 守恒 (无业务代码改动)

### 5.3 Plan 闭环进度

- 67 plans 累计状态化 (W66) + 1 cute (W68 第 7 批 A-2 cheerful-questing-kite 闭环) = **68 plans 100% 状态化**
- `cheerful-questing-kite.md` 状态: ACTUAL_PARTIAL → **COMPLETED (95% → 100%)**

### 5.4 协调铁律

- 4 阶段流程 100% 适用 0 偏离 (出指令 → 监控 → 审核 → 沉淀)
- 8 协调铁律 100% 适用 0 偏离
- **新增 3 铁律** (锚点范式第 76 守恒累计)

---

## 六、关键设计选择

### 6.1 为什么 scripts 不复用 production engine

- `app/core/database.py:_get_engine()` 是 lazy init, 在 fastapi lifespan 初始化
- 脚本跑在 `docker exec` 独立 context, 拿不到 lifespan context
- 直接 `create_async_engine(settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'))` + `NullPool` (避免 stale connection) — 与 `purify_voiceprints_from_meeting.py:478-482` 完全一致的模式

### 6.2 为什么 dry-run 默认

- CLAUDE.md 2026-06-29 W66 范式: 任何脚本默认不修改 DB
- mark_voice_confirmed 单向不可逆 — dry-run 给主指挥确认时间
- incremental_anchor 候选生成应人工 review, 不应全自动 mark

### 6.3 为什么 audit 写在脚本里

- 与 `purify_voiceprints_from_meeting.py:362-363` 模式一致 — 写 MemberVoiceHistory 在 DB 写入事务内
- 避免 audit 漏写 (transactional consistency)

### 6.4 为什么 e2e 测核心函数而非 CLI

- 脚本 `amain()` 直接拉 engine, 在 sqlite + fakeredis 模式下需要 mock settings.DATABASE_URL
- 核心函数 (fetch_anchors_and_enrolled, mark_voice_confirmed, scan_candidates, apply_mark_confirmed) 接收 session_factory 参数, 测起来纯净
- 10 场景 1.5s 跑完, 0 docker 依赖

---

## 七、关键文件清单 (绝对路径)

### 7.1 新增 (6 文件)

- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/scripts/list_anchors.py`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/scripts/mark_voice_confirmed.py`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/scripts/incremental_anchor.py`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/tests/e2e/test_anchor_scripts_smoke.py`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/docs/voiceprint-anchor-scripts.md`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/memory/w68-route-7-a2-cheerful-questing-anchor-2026-07-24.md` (本文件)

### 7.2 复用 (5 文件, 0 改动)

- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/app/services/voiceprint_service.py`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/app/models/member.py`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/app/models/member_voice_history.py`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/scripts/purify_voiceprints_from_meeting.py`
- `E:/microbubble-agent/.claude/worktrees/agent-a83d1f096269a7455/alembic/versions/036_add_voice_confirmed.py`

---

## 八、回滚路径

如 6 文件有问题, 主指挥 1 行撤销:

```bash
git revert <commit-hash>
# 容器内清理
docker exec microbubble-agent-app-1 rm -f /app/scripts/list_anchors.py \
  /app/scripts/mark_voice_confirmed.py /app/scripts/incremental_anchor.py
docker compose restart app
```

**回滚时间**: < 5 分钟. 已知 anchor 数据 (杜同贺 + 张宏魁) 不受影响.

---

## 九、参考

- Plan: `C:/Users/pc/.claude/plans/cheerful-questing-kite.md`
- 把关文档: `docs/voiceprint-anchor-scripts.md`
- E2E: `tests/e2e/test_anchor_scripts_smoke.py` (10 场景 1.5s 跑完)
- 锚点范式 baseline: `memory/anchor-paradigm-21-day-validation-2026-07-22.md`
- W68 第 7 批任务模式: `memory/w68-task-mode-paradigm-plans-first-2026-07-24.md`
- W68 第 5 批 grand closure: `memory/w68-grand-closure-5th-batch-2026-07-24.md`
- 声纹 batch bug 修复: `memory/voiceprint-batch-bug-fix-2026-06-19.md`
