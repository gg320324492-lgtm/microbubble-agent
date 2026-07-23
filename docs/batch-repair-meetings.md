# 批量修复会议误识 (W68 第 5 批 #5)

> 生效日期：2026-07-24  
> 适用范围：2026-06-27 12:00 之前录制的会议 (声纹库扩展前), 含历史误识嫌疑  
> 关联脚本：`scripts/scan_meetings_with_historical_misid.py` + `scripts/batch_repair_meetings.py`  
> 关联 memory：[`memory/w68-route-5-batch-repair-meetings-2026-07-24.md`](../memory/w68-route-5-batch-repair-meetings-2026-07-24.md)

## 背景

课题组声纹库在 2026-06-27 上午扩到杜同贺 / 吴孟铨等成员. 之前录制的会议后处理时, 声纹匹配只能命中当时录入的少数成员 (如 李胜景), 导致:

- `transcript_polished[].speaker` 误标为已录入成员
- `summary` / `key_points` / `decisions` LLM 综合时基于错误 speaker 标签 → 误识其他成员姓名
- `meeting_participants` 真实参会成员表**通常正确** (用户手动填写)
- `transcript` 原始 VAD + ASR 输出**通常正确** (无 speaker 标签)

`meeting_id=64` 是典型案例 (W68 第 4 批 Plan #2 已修复). 类似问题可能还有若干.

## 用法

### 三步流程

```bash
# 1. 扫描候选误识会议 → 输出 JSON
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \
  python scripts/scan_meetings_with_historical_misid.py \
    --output /tmp/meetings_candidates.json

# 2. 检查候选清单, 人工 review (确认确实需要修复的, 剔除 low severity 误报)
cat /tmp/meetings_candidates.json | jq '.[].meeting_id'

# 3. 批量修复 - 干跑 (默认 dry-run, 不落库)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \
  python scripts/batch_repair_meetings.py \
    --input /tmp/meetings_candidates.json \
    --min-severity high

# 4. 实际落库
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \
  python scripts/batch_repair_meetings.py \
    --input /tmp/meetings_candidates.json \
    --min-severity high --apply
```

### scan 脚本参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--cutoff` | `2026-06-27T12:00:00` | created_at 上限 ISO 格式 |
| `--min-severity` | `low` | 最低严重等级 (low / medium / high) |
| `--output` | stdout | JSON 文件输出路径 |

### batch 脚本参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--input` | (必填) | scan 脚本输出的 JSON 路径 |
| `--apply` | False | 加则落库, 默认 dry-run |
| `--min-severity` | `low` | 过滤候选 (low / medium / high) |
| `--limit` | 0 (全部) | 最多处理前 N 个 (测试用) |
| `--max-retries` | 3 | LLM 失败 retry 次数 (指数退避 1s/2s/4s) |

## 安全检查

### 1. 自动备份 (单会议粒度)

`batch_repair_meetings.py` 处理每个会议时**自动**写入 `/tmp/meeting_{id}_backup_{ts}.json`:

```json
{
  "meeting_id": 64,
  "title": "...",
  "backup_at": "20260724_153022",
  "transcript": [...],
  "transcript_polished": [...],
  "speaker_mapping": {...},
  "speaker_stats": [...],
  "summary": "...",
  "key_points": [...],
  "decisions": [...]
}
```

> ⚠️ 备份文件**不会自动清理**, 修复完确认无误后手动 `rm /tmp/meeting_*_backup_*.json`.

### 2. dry-run 默认开启

`batch_repair_meetings.py` **默认** dry-run, 只输出 diff + 备份路径, 不修改数据库. 加 `--apply` 才落库, 启动前还会 `asyncio.sleep(3)` 给 3 秒反悔窗口 (Ctrl-C 中断).

### 3. LLM 失败 retry 3 次

LLM 调 mimo cloud 可能偶发超时/限流. 脚本默认 `--max-retries 3`, 失败时**指数退避** (1s → 2s → 4s). 3 次都失败则该会议标记 `failed`, 不影响其他会议处理.

### 4. 严重等级过滤

scan 脚本按 transcript 是否 0 段归属误识姓名分 high / medium / low 三档:

| 等级 | 判定 | 建议 |
|------|------|------|
| **high** | summary 含 ≥ 2 个未参会姓名 OR transcript 0 段归属 | 必修复 |
| **medium** | summary 含 1 个未参会姓名, transcript 0 段归属 | 强烈建议修复 |
| **low** | summary 含未参会姓名, 但 transcript 有该姓名段 | 需人工 review (可能真参会但未在 participants 表) |

推荐 `--min-severity high` 起步, 确认无误后再放宽.

### 5. 候选清单 100% 人工 review

`--input` JSON **不会自动**跳过任何会议. 强烈建议在第 2 步 `jq` 列出后:

- 核对 meeting_id 是否真要修
- 删除 low severity 误报 (可能 LLM 偶然引用了非参会成员)
- 确认 candidate 中 `real_participant_names` 准确 (基于 `meeting_participants` 表)

## 回滚方式

### 方式 A: SQL 单会议回滚

```sql
-- 1. 找到备份文件路径
SELECT '/tmp/meeting_64_backup_*.json';

-- 2. 从备份读 transcript_polished / speaker_stats / summary / key_points / decisions
-- 3. UPDATE 写回
UPDATE meetings
   SET transcript_polished = %s::jsonb,
       speaker_stats       = %s::jsonb,
       summary             = %s,
       key_points          = %s::jsonb,
       decisions           = %s::jsonb
 WHERE id = 64;
```

### 方式 B: 整批回滚 (git revert)

本批只动 `scripts/` + `docs/` + `memory/`, **不改生产代码**. 若仅数据库被改, 需要手写 SQL 反向. 建议:

- 修复前 `pg_dump -t meetings > /tmp/meetings_before_batch.sql`
- 修复失败时 `psql < /tmp/meetings_before_batch.sql` 恢复

> ⚠️ **`pg_dump` 只在低峰期跑**, meetings 表可能 GB 级.

## 主指挥 SSH 部署必做

```bash
# 云服务器上跑 (有 PostgreSQL docker container)
ssh root@<cloud-server>

cd /opt/microbubble-agent  # 实际项目路径

# 1. 拉新分支代码 (主指挥 merge 后)
git fetch origin
git checkout main
git pull --ff-only

# 2. 跑 scan (需要 DATABASE_URL - 从 docker-compose env 读)
cd /opt/microbubble-agent

# 取 DATABASE_URL
export DATABASE_URL=$(grep DATABASE_URL docker/.env | cut -d= -f2-)
# 或: docker exec microbubble-agent-app-1 env | grep DATABASE_URL

# 3. 扫描
python scripts/scan_meetings_with_historical_misid.py \
  --output /tmp/meetings_candidates.json \
  --min-severity low

# 4. 人工 review
cat /tmp/meetings_candidates.json | jq '.[] | {meeting_id, severity: .mismatch_severity, suspected: .summary_suspected_names}'

# 5. 干跑 (确认无副作用)
python scripts/batch_repair_meetings.py \
  --input /tmp/meetings_candidates.json \
  --min-severity high \
  --limit 3

# 6. 实际修复
python scripts/batch_repair_meetings.py \
  --input /tmp/meetings_candidates.json \
  --min-severity high \
  --apply

# 7. 验证 (抽查 1-2 个)
psql -U postgres -d microbubble \
  -c "SELECT id, title, summary FROM meetings WHERE id IN (64, ...) ORDER BY id;"
```

## 已知限制

1. **scan 脚本假定成员姓名唯一**. 若有重名 (如两个 "王磊") 会误报. 修复前人工 review candidate `real_participant_names` vs `summary_suspected_names`.
2. **LLM 综合 summary 仍可能偶发误识**. 修复后 review 时若发现仍含误识姓名, 需手动 SQL 改回 (或重新跑 batch).
3. **transcript 原始 ASR 错误无法修复**. 本脚本只修 summary/key_points/decisions + transcript_polished speaker 标签, **不改** transcript 原始文本.
4. **备份文件无过期清理**. 长期累积 `/tmp/meeting_*_backup_*.json` 会占空间. 修复完确认无误后建议手动清理.

## 调试技巧

- **LLM 输出非 JSON** → 备份文件中有 `summary` 等字段, 直接看原始输出, 不需重跑 scan.
- **修复后某些会议仍含误识** → 备份文件 + `transcript` 字段可手动 SQL 改回 (方式 A).
- **`--limit 1` 测一个看效果** → 不要一次性跑大批, 防止 LLM 偶发问题污染所有会议.
- **本地无 PostgreSQL** → scan 脚本会 fallback 输出空清单 + 提示, batch 脚本会 SystemExit 报错. 这两个脚本必须在云服务器跑.

## 关联文件

- [`scripts/scan_meetings_with_historical_misid.py`](../scripts/scan_meetings_with_historical_misid.py) (~230 行)
- [`scripts/batch_repair_meetings.py`](../scripts/batch_repair_meetings.py) (~330 行)
- [`scripts/repair_meeting_64_speakers.py`](../scripts/repair_meeting_64_speakers.py) (W68 第 4 批 Plan #2 已建, 275 行, 复用其核心函数)
- [`memory/w68-route-5-batch-repair-meetings-2026-07-24.md`](../memory/w68-route-5-batch-repair-meetings-2026-07-24.md) (锚点范式第 62 守恒)