# 会议发言人误标修复脚本 (CLI 文档)

> **状态**: W68 第 4 批 Plan #2 已就绪 (commit 待 push)
> **目标会议**: 会议 #64 ("小气助手软件适配性测试", 2026-06-05 11:10)
> **脚本**: [`scripts/repair_meeting_64_speakers.py`](../scripts/repair_meeting_64_speakers.py)

## 背景

会议 #64 录制时 (2026-06-05), 杜同贺 / 吴孟铨 都没录入声纹 (只有 李胜景 有 1 个 sample).
后处理 voiceprint 只能从 1 个已知声纹里投票, 把 7 段本应归 杜同贺 的发言误标为 李胜景.

**事实核对** (plan 探索阶段已确认):
- `transcript` 字段已正确 (cluster_id → 杜同贺 7 段 / 吴孟铨 4 段)
- `speaker_mapping` 已正确 (cluster_0→吴孟铨, cluster_1→杜同贺, cluster_2→吴孟铨)
- `meeting_participants` 已正确 (杜同贺 member_id=3 + 吴孟铨 member_id=15)
- 5 个下游字段全部错: `transcript_polished` / `speaker_stats` / `summary` / `key_points` / `decisions`

## 何时用

适用以下情形:
- 会议后处理时某些成员**尚未录入声纹** → 后期录入后**未重跑 reprocess**
- `summary` / `key_points` / `decisions` / `speaker_stats` 字段包含**不应参会**的人物名
- 但 `transcript` / `speaker_mapping` 已经正确 (上游已修复)

**不适用**:
- transcript / speaker_mapping 仍错 → 需先用 `scripts/reprocess_meeting.py` 重跑
- 没有原始 transcript → 需手动从音频 ASR 重做
- 整个会议需要重做 → 用 `reprocess_meeting.py --steps load,extract,cluster,vote,assign,backup,update,regen,verify`

## 怎么用

### Step 0: SSH 到云服务器 (主指挥 PC)

```bash
ssh your-server
```

### Step 1: 拷贝脚本到 app 容器 (本仓库路径 `/e/microbubble-agent`)

```bash
docker cp scripts/repair_meeting_64_speakers.py microbubble-agent-app-1:/tmp/
```

### Step 2: 干跑 (dry-run, 默认)

```bash
docker exec -it microbubble-agent-app-1 python /tmp/repair_meeting_64_speakers.py
```

**期望输出**:
- 备份路径: `/tmp/meeting_64_backup_<ts>.json`
- 实际发言人分布: `杜同贺: turns=7 words=181` + `吴孟铨: turns=4 words=71`
- LLM 调用日志 + 5 字段 diff (含 `李胜景` 计数 0)
- 末尾: `DRY-RUN: 加 --apply 才落库`

### Step 3: 实际落库

```bash
docker exec -it microbubble-agent-app-1 python /tmp/repair_meeting_64_speakers.py --apply
```

**期望输出**: `落库完成 (id=64, 1 行)`.

### Step 4: SQL 验证 8 字段 0 李胜景

```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "
SELECT
  (SELECT COUNT(*) FROM jsonb_array_elements(transcript::jsonb) e WHERE e->>'speaker' = '李胜景') AS t_李,
  (SELECT COUNT(*) FROM jsonb_array_elements(transcript_polished::jsonb) e WHERE e->>'speaker' = '李胜景') AS tp_李,
  (SELECT COUNT(*) FROM jsonb_each_text(speaker_mapping::jsonb) WHERE value = '李胜景') AS sm_李,
  (SELECT COUNT(*) FROM jsonb_array_elements(speaker_stats::jsonb) s WHERE s->>'name' = '李胜景') AS ss_李,
  (SELECT array_to_string(key_points, '|') FROM meetings WHERE id=64) LIKE '%【李胜景】%' AS kp_李,
  (SELECT array_to_string(decisions, '|') FROM meetings WHERE id=64) LIKE '%【李胜景】%' AS dec_李,
  (summary LIKE '%李胜景%') AS sum_李
FROM meetings WHERE id = 64;
"
```

**期望**: 全部 0 / false.

### Step 5: 浏览器硬刷新验证

1. `Cmd/Ctrl + Shift + R` 绕过 SW cache (CLAUDE.md 2026-06-13 铁律)
2. 打开 `https://agent.mnb-lab.cn/meetings/64`
3. 转录记录 tab: 头像 + 名字应显示 杜同贺 / 吴孟铨
4. 发言统计 tab: 杜同贺 7 次 181 字 + 吴孟铨 4 次 71 字
5. 关键点 / 决议: 全部 【杜同贺】 / 【吴孟铨】 标注
6. 摘要: 不再提 李胜景, 描述 杜同贺 为开发者 + 主动问硬件清单的人

## 回滚方式

脚本默认 dry-run, 即使加 `--apply` 也会先写 `/tmp/meeting_64_backup_<ts>.json`.
如需回滚:

```bash
# 1. 查备份文件名
ls -lt /tmp/meeting_64_backup_*.json | head -1

# 2. 用 psql 写回 5 字段 (假设最新备份为 meeting_64_backup_20260724_153000.json)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "
UPDATE meetings
   SET transcript_polished = (SELECT transcript_polished FROM (VALUES (NULL::jsonb)) x LIMIT 0),
       speaker_stats       = NULL,
       summary             = NULL,
       key_points          = NULL,
       decisions           = NULL
 WHERE id = 64;
"
# (实际回滚: docker cp 备份到容器内, 然后 python 解析后 UPDATE)
```

更安全的回滚方式: 用 `scripts/reprocess_meeting.py --steps verify` 不会改数据, 可读 /tmp/meeting_64_backup_*.json 字段值, 然后 SQL UPDATE 回去.

## 类似历史会议清单 (建议后续 PR 批量巡检)

用以下 SQL 找出 2026-06-27 之前录制的会议 — 声纹录入未完善时期处理的会议, summary/key_points/decisions 可能含历史误识:

```sql
SELECT m.id, m.title, m.created_at,
       (SELECT COUNT(*) FROM jsonb_array_elements(m.transcript::jsonb) e) AS segments,
       (SELECT array_agg(DISTINCT e->>'speaker') FROM jsonb_array_elements(m.transcript::jsonb) e) AS speakers,
       (m.summary LIKE '%李胜景%') AS has_lishengjing
  FROM meetings m
 WHERE m.created_at < '2026-06-27'
 ORDER BY m.created_at;
```

**已知类似会议** (来自 plan 探索阶段的抽样):
- 会议 #64 (本次目标)
- 早期 14 个会议中只有 #64 有 杜同贺+吴孟铨+李胜景 模式, 无需批量修 #64 以外

**建议**: 主指挥可在未来 PR 跑上述 SQL 拉全清单, 逐个评估是否需要本脚本修复.

## 注意事项

- **0 production code 改动铁律维持**: 本脚本只放 `scripts/`, 不动 `app/` 下任何文件
- **dry-run 默认**: 不会落库, 除非显式 `--apply`
- **必须备份**: 每次运行都写 `/tmp/meeting_64_backup_<ts>.json`, 文件不靠 DB 列
- **LLM 调用**: 复用 app 内的 `get_anthropic_client` / `get_default_model`, 默认走 mimo cloud
- **JSONB mutate**: 本脚本用 SQL `UPDATE ... = %s::jsonb` 直接写完整 JSON, 不走 flag_modified 路径
- **可重用性**: 本脚本 `MEETING_ID` 是常量 64, 类似会议可复制脚本改 ID (后续 PR 改通用化)

## 相关文件

- [`scripts/reprocess_meeting.py`](../scripts/reprocess_meeting.py) — 通用重处理 CLI (Step 1-9 完整流程)
- [`scripts/repair_meeting_64_speakers.py`](../scripts/repair_meeting_64_speakers.py) — 本文档目标脚本
- [`app/services/meeting_analysis_service.py`](../app/services/meeting_analysis_service.py) — `compute_speaker_stats` 函数复用
- [`memory/w68-route-plan2-meeting-64-repair-2026-07-24.md`](../memory/w68-route-plan2-meeting-64-repair-2026-07-24.md) — W68 锚点范式第 44 守恒沉淀
- [plan 2026-06-05-19-10-melodic-donut.md](C:/Users/pc/.claude/plans/2026-06-05-19-10-melodic-donut.md) — 原始 plan 全文