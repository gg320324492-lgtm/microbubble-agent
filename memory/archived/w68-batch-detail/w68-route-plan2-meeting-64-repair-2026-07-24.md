# W68 第 4 批 Plan #2: 会议 64 杜/吴 误标修复 (锚点范式第 44 守恒)

> **日期**: 2026-07-24 (W68 第 4 批, Plan #2)
> **Agent**: W68 第 4 批 Plan #2 Agent
> **Plan**: [2026-06-05-19-10-melodic-donut.md](../../../../../Users/pc/.claude/plans/2026-06-05-19-10-melodic-donut.md) (NOT_STARTED plan-mode → COMPLETED)
> **类型**: data-only 修复脚本, 不动 `app/` 下任何生产代码
> **锚点范式**: 第 44 守恒 (W66 27 → W67 28 → **W68 30** 单调上升, 第 4 批延续)

## 任务概述

实施已有 plan `2026-06-05-19-10-melodic-donut.md` (NOT_STARTED 早期 plan-mode). 会议 64 ("小气助手软件适配性测试", 2026-06-05 11:10 录制, 1 分 2 秒) 的转录里所有 杜同贺 的发言被错误标注为 李胜景, 需写脚本修复.

## Plan 上下文

- 会议 2026-06-05 录制时, 杜同贺/吴孟铨 都没录入声纹 (只有 李胜景 有 1 个 sample)
- 后处理 voiceprint 只能从 1 个已知声纹里投票, 把 7 段本应归 杜同贺 的发言误标为 李胜景
- 2026-06-27 杜同贺/吴孟铨 才录入声纹 (7 sample / 4 sample), 此时会议已处理完毕, 没有重跑
- 后续 v76 声纹 sample_count 重置为 1 也没追溯历史会议

**事实已核对** (plan 探索阶段已完成):
- `transcript` 字段**已正确** (cluster_id → 杜同贺 7 段 / 吴孟铨 4 段)
- `speaker_mapping` 字段**已正确** (cluster_0→吴孟铨, cluster_1→杜同贺, cluster_2→吴孟铨)
- `meeting_participants` 字段**已正确** (杜同贺 member_id=3 + 吴孟铨 member_id=15)
- 5 个下游字段**全部错**: transcript_polished / speaker_stats / summary / key_points / decisions

## 交付 (4 文件)

| 文件 | 角色 | 行数 |
|------|------|------|
| [`scripts/repair_meeting_64_speakers.py`](../../scripts/repair_meeting_64_speakers.py) | 修复脚本 (dry-run + LLM regen + 镜像 + 重算 stats) | ~275 |
| [`docs/repair-meeting-speakers.md`](../../docs/repair-meeting-speakers.md) | CLI 使用文档 (何时用 / 怎么用 / 回滚 / 类似会议清单) | ~150 |
| `memory/w68-route-plan2-meeting-64-repair-2026-07-24.md` | 本文件 (锚点范式第 44 守恒 + 闭环沉淀) | ~120 |
| [plan 2026-06-05-19-10-melodic-donut.md](../../../../../Users/pc/.claude/plans/2026-06-05-19-10-melodic-donut.md) | 头部 `## Status` 段更新为 COMPLETED | +1 段 |

## 脚本设计要点

### 流程 (5 步)

1. **fetch_meeting**: psycopg 直连 PostgreSQL (`DATABASE_URL` env), 读 9 字段
2. **backup_to_file**: 写 `/tmp/meeting_64_backup_<ts>.json` (CLAUDE.md 铁律 2/3: 必须文件备份不靠 DB 列)
3. **fix_transcript_polished**: 镜像 `transcript[i].speaker` 到 `transcript_polished[i].speaker` (11 段平行数组)
4. **compute_speaker_stats_local**: 纯本地计算 (复用 `app/services/meeting_analysis_service.py:compute_speaker_stats` 逻辑)
5. **call_llm_regen**: 调 LLM 重新生成 summary / key_points / decisions, 显式约束"只输出 杜同贺 + 吴孟铨, 严禁出现 李胜景"

### dry-run 默认 + --apply 才落库

```bash
# dry-run (默认): 只 print diff, 不写 DB
DATABASE_URL=... python scripts/repair_meeting_64_speakers.py

# 实际落库
DATABASE_URL=... python scripts/repair_meeting_64_speakers.py --apply
```

### 不依赖 ORM

直接用 psycopg3 + dict_row, 避免 SQLAlchemy session 跨 event loop 复杂问题 (CLAUDE.md 752 行铁律升级). 5 字段用 SQL `UPDATE ... = %s::jsonb` 直接写完整 JSON, 不走 flag_modified.

### LLM 复用 app 客户端

```python
sys.path.insert(0, "/app")
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response
```

## 锚点范式第 44 守恒

- W7 12 → W66 27 → W67 28 → **W68 30 单调上升** (本次第 4 批延续)
- 0 production code 改动铁律维持 (本任务例外: 实施 plan 闭环, CLAUDE.md 已批准, 仅放 scripts/ + docs/ + memory/)
- 26+ baseline 守恒 (71 PASS + 7 SKIP, 跨 60+ commit 0 regression)
- W19 选项 A 维持 (plan 执行而非修代码)
- 第 4 批 Plan #2 闭环 plan `2026-06-05-19-10-melodic-donut.md` (从 NOT_STARTED → COMPLETED)

## 类似会议清单 (留给未来 PR)

写一段 SQL 找出 2026-06-27 之前录制的所有会议 — 声纹录入未完善时期处理的会议, summary/key_points/decisions 可能含历史误识:

```sql
SELECT m.id, m.title, m.created_at,
       (SELECT COUNT(*) FROM jsonb_array_elements(m.transcript::jsonb) e) AS segments,
       (SELECT array_agg(DISTINCT e->>'speaker') FROM jsonb_array_elements(m.transcript::jsonb) e) AS speakers,
       (m.summary LIKE '%李胜景%') AS has_lishengjing
  FROM meetings m
 WHERE m.created_at < '2026-06-27'
 ORDER BY m.created_at;
```

**已知类似会议** (plan 探索阶段抽样):
- 会议 #64 (本次目标)
- 早期 14 个会议中只有 #64 有 杜同贺+吴孟铨+李胜景 模式, 无需批量修 #64 以外

**未来 PR 建议**: 主指挥可跑上述 SQL 拉全清单, 评估是否需要 `repair_meeting_64_speakers.py` 通用化版本 (`--meeting-id N` + `--forbidden-speaker "X"`).

## 7 条新铁律沉淀 (本次 + 历史累加)

1. **会议后处理时未录入声纹的成员, 全部误标为唯一已知声纹** — 必须等所有声纹录入完毕才 reprocess, 不能匆匆处理 (plan 探索阶段确认)
2. **`transcript` 已正确但 `transcript_polished` 仍错** — 前端实际渲染字段是 polished 不是 transcript, 修声纹后必须同步 polished (CLAUDE.md 2026-06-15 教训)
3. **文件备份必须不靠 DB 列备份** — SQLAlchemy 静默忽略未映射属性, 必须 `json.dump` 写文件 (CLAUDE.md 铁律 2/3)
4. **LLM regen 必须显式约束允许的人物名单** — 否则 LLM 会"幻觉"出不存在的人, 复现历史误标 (本次 plan 探索)
5. **psycopg3 直连 DB 优于 ORM 用于数据修复脚本** — 避免 SQLAlchemy 跨 event loop + async session 复杂度, 5 字段 UPDATE 用 `= %s::jsonb` 直接写完整 JSON
6. **JSONB mutate 后必须 `flag_modified`** (CLAUDE.md 2026-06-28 教训) — 本脚本用 SQL `UPDATE ... = %s::jsonb` 绕开此陷阱, 但 ORM 场景仍适用
7. **dry-run 默认 + --apply 才落库是数据修复脚本的安全模式** — 主指挥可放心跑, 任何时候只看 diff 不写库

## 部署路径

主指挥在云服务器跑:
```bash
# 1. 拉新 commit (push 后 webhook 触发)
ssh your-server
cd /path/to/microbubble-agent
git pull origin feat/plan-meeting-64-repair-2026-07-24

# 2. dry-run 看 diff
docker cp scripts/repair_meeting_64_speakers.py microbubble-agent-app-1:/tmp/
docker exec -it microbubble-agent-app-1 python /tmp/repair_meeting_64_speakers.py

# 3. apply 落库
docker exec -it microbubble-agent-app-1 python /tmp/repair_meeting_64_speakers.py --apply

# 4. SQL 验证
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "<见 docs/repair-meeting-speakers.md Step 4>"

# 5. 浏览器硬刷验证
# 打开 https://agent.mnb-lab.cn/meetings/64
```

## 不在本次范围 (留给后续)

1. **通用化**: 写 `--meeting-id N --forbidden-speaker "X"` 参数化版本, 供未来 PR 批量修
2. **根因防护**: `post_meeting_tasks.py` 加守卫 — "如果 meeting_time 早于所有 voiceprint enrolled_at, 在 prompt 里提示 LLM '此会议处理时这些声纹未录入, 你的 label 可能不准确'" (需用户决策)
3. **HARDCODED_ALIASES**: `speaker_assignment.py:PHONETIC_CORRECTIONS` 仍存在 `吴孟栓` (栓) 而 `name_aliases.py` 是 `吴孟拴` (拴) — 此 bug 跟当前任务无关, 是技术债
4. **数据库审计**: 类似会议清单 (上面 SQL) 主指挥可在未来 PR 跑

## 教训与反思

- plan 探索阶段发现 `transcript` 已正确但下游 5 字段仍错 — 这种"半修复"状态在前端实际渲染时仍暴露问题, 必须修到 polished 字段
- LLM 在 regen 时如不显式约束允许的人物, 会"幻觉"出历史误标 (本次 plan 探索已确认)
- 数据修复脚本适合放 `scripts/` 而非 `app/`, 主指挥可独立运行不需要改生产代码
- 锚点范式第 4 批延续: 0 production code 改动铁律维持, 但 plan 闭环是例外 (CLAUDE.md 已批准)

## Plan 闭环证据

- ✅ 修复脚本 `scripts/repair_meeting_64_speakers.py` (syntax OK, ~275 行)
- ✅ CLI 文档 `docs/repair-meeting-speakers.md` (~150 行, 5 步 + 回滚 + 类似会议清单)
- ✅ Memory 本文件 (锚点范式第 44 守恒 + 7 铁律沉淀)
- ✅ Plan 头部 `## Status` 段已更新为 COMPLETED
- ⏸ Plan 不 merge (主指挥来 merge)
- ⏸ Push 到 origin

## 相关引用

- [CLAUDE.md 锚点范式 21 天实战](../../memory/anchor-paradigm-21-day-validation-2026-07-22.md)
- [CLAUDE.md 2026-06-13 PWA 5 警告修复链](#) (硬刷验证铁律)
- [memory/w68-grand-closure-2026-07-24.md](./w68-grand-closure-2026-07-24.md) — W68 第 1 批 grand closure
- [memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md](./w67-grand-closure-qa-bench-ci-final-2026-07-23.md) — 上一批 grand closure
- [scripts/reprocess_meeting.py](../../scripts/reprocess_meeting.py) — 通用重处理 CLI (本脚本互补)