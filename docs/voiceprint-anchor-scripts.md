# 声纹 Anchor 脚本使用文档 (W68 第 7 批 A-2 cheerful-questing-kite Plan 闭环)

> **作者**: Agent "W68 第 7 批 A-2"
> **日期**: 2026-07-24
> **锚点范式**: 第 76 守恒
> **0 production code 改动铁律**: 维持 — 仅 `scripts/` + `tests/` + `docs/` + `memory/`

---

## 一、为什么需要这些脚本

`plan cheerful-questing-kite.md` (增量 Cross-Anchor 策略) 实施卡在 **95%**:

- ✅ Schema (alembic 036) + 核心代码 (`get_anchor_members` + `identify_speaker_anchored`) + skip-confirmed 守卫
- ✅ 已有 2 个 anchor (杜同贺 + 张宏魁)
- ❌ **3 个新脚本未落地** — `incremental_anchor.py` / `mark_voice_confirmed.py` / `list_anchors.py`

这 3 个脚本是**主指挥 SSH 部署节奏**的核心工具:
- `list_anchors.py` — 巡检当前 anchor 链状态 (谁已 confirmed, 谁还待累积)
- `mark_voice_confirmed.py` — 单次确认 1 个新 anchor (单向不可逆操作)
- `incremental_anchor.py` — **批量候选生成** (月度巡检找出下一个待 confirm 的人)

---

## 二、3 个脚本用法

### 2.1 `scripts/list_anchors.py` (anchor 巡检)

**用途**: 列出当前所有 anchor 成员 + (可选) 未 confirmed 但已 enrolled 的成员.

```bash
# 默认 table 输出
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/list_anchors.py

# JSON 输出 (供 CI / 自动化消费)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/list_anchors.py --json

# 同时显示未 confirmed 但已 enrolled 成员 (候选 anchor)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/list_anchors.py --include-unconfirmed
```

**输出字段** (table):
```
=== 声纹 Anchor 列表 (Cross-Anchor 策略, 2 个) ===
  # |   id | name       | username     | confirmed_at        | by       |  meet | samples |   norm
  1 |    1 | 杜同贺     | du           | 2026-06-28T12:37:04 | user     |   153 |       4 | 1.000
  2 |    7 | 张宏魁     | zhang        | 2026-07-02T08:45:00 | user     |   151 |     125 | 0.974
```

**输出字段** (JSON):
```json
{
  "count": 2,
  "anchors": [
    {
      "member_id": 1,
      "name": "杜同贺",
      "username": "du",
      "voice_sample_count": 4,
      "voice_enrolled_at": "2026-06-28T12:37:04",
      "voice_embedding_norm": 1.0,
      "voice_confirmed_at": "2026-06-28T12:37:04",
      "voice_confirmed_by": "user",
      "voice_confirmed_meeting_id": 153
    }
  ],
  "unconfirmed_enrolled": [
    {
      "member_id": 28,
      "name": "陈金薪",
      "voice_sample_count": 33,
      "voice_confirmed_at": null
    }
  ]
}
```

### 2.2 `scripts/mark_voice_confirmed.py` (单次 mark anchor)

**用途**: 标记 1 个成员为 anchor (写入 3 字段 + audit). **单向不可逆** — 后续 strict pipeline 永远跳过此成员.

```bash
# 默认 dry-run (只显示将要写入什么, 不实际写库)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/mark_voice_confirmed.py \
  --member-id 28 --meeting-id 167 --confirmed-by "user"

# 真正写入
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/mark_voice_confirmed.py \
  --member-id 28 --meeting-id 167 --confirmed-by "user" --apply

# 用 name 而非 id
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/mark_voice_confirmed.py \
  --member-name "陈金薪" --meeting-id 167 --confirmed-by "user" --apply

# 强制覆盖已 confirmed 成员 (默认拒绝, 防误操作)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/mark_voice_confirmed.py \
  --member-name "陈金薪" --meeting-id 167 --confirmed-by "user" --apply --force

# JSON 输出 (供 CI / 自动化消费)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/mark_voice_confirmed.py \
  --member-name "陈金薪" --meeting-id 167 --confirmed-by "user" --apply --json
```

**输出** (dry-run):
```
=== mark_voice_confirmed ===
  member: 陈金薪 (id=28)
  username: chen
  meeting_id: 167
  confirmed_by: user
  status: dry_run
  [DRY-RUN] 未实际写库

  before:
    voice_confirmed_at: None
    voice_confirmed_by: None
    voice_confirmed_meeting_id: None
    voice_sample_count: 33
  after:
    voice_confirmed_at: 2026-07-24T23:00:00 (DRY-RUN)
    voice_confirmed_by: user
    voice_confirmed_meeting_id: 167
```

**输出** (apply):
```
=== mark_voice_confirmed ===
  ...
  status: applied
  ...
  after:
    voice_confirmed_at: 2026-07-24T23:00:00
    voice_confirmed_by: user
    voice_confirmed_meeting_id: 167
    voice_sample_count: 33
    audit_id: 42
```

**安全模式**:
- 已 confirmed 成员默认拒绝 (无 `--force`)
- `--force` 覆盖时会写 audit 标识 `FORCE OVERRIDE prev meeting_id=...`

### 2.3 `scripts/incremental_anchor.py` (批量候选生成)

**用途**: 扫描过去 N 天的成员, 找出累积样本数 ≥ 阈值的 anchor 候选. 强证据建议 `mark_confirmed`, 中等证据建议 `review_manually`.

```bash
# 默认 dry-run 扫描 (过去 30 天 ≥ 5 samples)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/incremental_anchor.py

# 自定义扫描窗口 + 阈值
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/incremental_anchor.py --days 60 --min-samples 10

# 指定单个成员 (只对该成员生成候选)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/incremental_anchor.py --member-name "陈金薪"

# 真 mark_confirmed (按成员执行, 必填 --meeting-id + --confirmed-by)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/incremental_anchor.py \
  --member-name "陈金薪" --meeting-id 167 --confirmed-by "user" --apply

# JSON 输出
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/incremental_anchor.py --json
```

**输出** (table):
```
=== Anchor 候选扫描 (lookback=30d, min_samples=5) ===
  total candidates: 5
  eligible:         3
  hold:             2

  id | name       | samples |   norm | eligible | suggestion         | enrolled_at        | reason
   2 | 陈金薪     |      33 | 0.974  |      YES | mark_confirmed     | 2026-06-30T10:00:00 | —
  7 | 张宏魁     |     125 | 0.987  |      YES | mark_confirmed     | 2026-07-02T08:45:00 | —
  8 | 周之超     |      12 | 0.945  |      YES | review_manually    | 2026-07-05T14:00:00 | —
  3 | 贾琦       |       1 | 0.812  |       no | hold_continue...   | 2026-07-01T09:00:00 | sample_count=1 < 5
  9 | 新人       |       2 | 0.701  |       no | hold_continue...   | 2026-07-04T10:00:00 | sample_count=2 < 5
```

**Suggestion 字段语义**:
- `mark_confirmed` — 强证据 (samples ≥ `min_samples * 4`)
- `review_manually` — 中等证据 (samples ≥ `min_samples * 2`)
- `hold_continue_learning` — 不达标 (samples < `min_samples`)

---

## 三、主指挥 SSH 部署必做

### 3.1 首次部署 (一次性)

CLAUDE.md 752 行铁律: **任何脚本部署必须先复制到容器, 再 `docker compose restart app`**.

```bash
# 1. cp 3 个脚本到容器
docker cp scripts/list_anchors.py          microbubble-agent-app-1:/app/scripts/
docker cp scripts/mark_voice_confirmed.py  microbubble-agent-app-1:/app/scripts/
docker cp scripts/incremental_anchor.py    microbubble-agent-app-1:/app/scripts/

# 2. 容器内 chmod (脚本有 shebang)
docker exec microbubble-agent-app-1 chmod +x /app/scripts/list_anchors.py \
  /app/scripts/mark_voice_confirmed.py /app/scripts/incremental_anchor.py

# 3. 重启 app (CLAUDE.md 752 行铁律)
docker compose restart app
```

**验证**:
```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/list_anchors.py
# 期望: 至少能看到 #1 杜同贺 (script 阶段已存在的 anchor)
```

### 3.2 月度巡检流程 (主指挥 SOP)

```bash
# 1. 巡检当前 anchor 状态
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/list_anchors.py --include-unconfirmed

# 2. 扫描候选 (标识 mark_confirmed 强证据)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/incremental_anchor.py --days 30 --min-samples 5

# 3. 人工 review 后, 对每个首选执行 mark_confirmed
# (按脚本建议顺序逐个成员执行, 不要批量)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/mark_voice_confirmed.py \
  --member-name "陈金薪" --meeting-id 167 --confirmed-by "user" --apply

# 4. 验证新 anchor 链
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python /app/scripts/list_anchors.py
```

**触发频率**: 月度 (1 次 / 30 天). 主指挥在月初头 1 周执行.

### 3.3 已知 12 会议清单

| # | 会议 ID | 标题 | 当前 anchor 状态 | 处理建议 |
|---|---|---|---|---|
| 1 | 064 | 小气助手软件适配性测试 | ✅ 已 4 人 100% | 杜同贺 + 吴孟铨 → 候选 mark_confirmed |
| 2 | 068 | 臭氧气泡实验变量分析 | ✅ 已 re-purify | **陈金薪 → mark_confirmed 候选** |
| 3 | 070 | 实验数据可靠性排查 | ✅ 已完成 | 贾琦 → mark_confirmed 候选 |
| 4 | 071 | 臭氧微纳米气泡实验条件 | ✅ 已完成 | 周之超 → mark_confirmed 候选 |
| 5 | 083 | 持续研究UV臭氧纳米气泡 | ⚠️ rollback | 待用户复核 cluster 归属 |
| 6 | 095 | 水产养殖纳米气泡 | ⏳ 待处理 | 听音频后用 anchor 链识别 |
| 7 | 120 | 实验相关工作安排 | ⏳ 待处理 | 听音频后用 anchor 链识别 |
| 8 | 121 | 普通泡与纳米气泡技术对比 | ⏳ 待处理 | 听音频后用 anchor 链识别 |
| 9 | 122 | 声纹识别与音频上传机制 | ⏳ 待处理 | 听音频后用 anchor 链识别 |
| 10 | 135 | 研究方案讨论与实验指导 | ✅ 已 override | 王天志 + 韩重阳 → 听音频复核 |
| 11 | 151 | 同贺实验相关讨论 | ⚠️ partial | **张宏魁 → 已 confirmed (#2)** |
| 12 | 153 | (合并到 151) | (跳过) | (跳过) |

**当前已知 anchor**: 2 个 (#1 杜同贺 + #2 张宏魁). 优先目标: #2-5 候选逐个 mark_confirmed.

---

## 四、关键纪律

### 4.1 0 production code 改动铁律

- ✅ 3 脚本全部在 `scripts/`, 不动 `app/` 任何代码
- ✅ 复用 `app/services/voiceprint_service.py:get_anchor_members` (已闭环)
- ✅ 复用 `Member` / `MemberVoiceHistory` ORM (已存在)
- ✅ 复用 alembic 036 schema (已存在)

### 4.2 脚本默认 dry-run

- `mark_voice_confirmed.py`: 默认 dry-run, 必须 `--apply` 才写库
- `incremental_anchor.py`: 默认 dry-run 扫描, 必须 `--apply` + `--member-name` + `--meeting-id` + `--confirmed-by` 才 mark
- `list_anchors.py`: 永远只读 (无需 `--apply`)

### 4.3 越权防护

- 脚本直接走 root DB (主指挥 SSH 跑), 不用 JWT
- 主指挥通过 SSH + docker exec 验证权限, 不需要 application-level 鉴权

### 4.4 测试覆盖

`tests/e2e/test_anchor_scripts_smoke.py` 10 个场景全过:
1. list_anchors 返空 (无 anchor)
2. list_anchors 返单 anchor (按时间升序)
3. list_anchors JSON 输出
4. mark_voice_confirmed dry-run 不写库
5. mark_voice_confirmed apply 写库 + audit
6. mark_voice_confirmed 拒绝覆盖已 confirmed (无 --force)
7. incremental_anchor 候选生成
8. incremental_anchor --member-name 单成员过滤
9. incremental_anchor apply mark_confirmed + audit
10. 跨脚本协作 (incremental_anchor → list_anchors)

---

## 五、关键文件清单

### 5.1 新增 (3 个脚本 + 1 个测试 + 1 个文档 + 1 个 memory)

- `scripts/list_anchors.py` (~210 行)
- `scripts/mark_voice_confirmed.py` (~250 行)
- `scripts/incremental_anchor.py` (~280 行)
- `tests/e2e/test_anchor_scripts_smoke.py` (~430 行, 10 场景)
- `docs/voiceprint-anchor-scripts.md` (本文件)
- `memory/w68-route-7-a2-cheerful-questing-anchor-2026-07-24.md`

### 5.2 复用 (5 个已闭环文件)

- `app/services/voiceprint_service.py:get_anchor_members` (line 374)
- `app/services/voiceprint_service.py:identify_speaker_anchored` (line 392)
- `app/models/member.py` (voice_confirmed_at/by/meeting_id 字段, line 55-57)
- `app/models/member_voice_history.py` (审计表, source="anchor_confirmed")
- `scripts/purify_voiceprints_from_meeting.py:apply_recovery` (line 188, skip-confirmed 守卫)

### 5.3 Plan 字段映射

| Plan 字段 | 脚本实现 |
|---|---|
| `voice_confirmed_at` | `mark_voice_confirmed.py` 写入 |
| `voice_confirmed_by` | 同上 |
| `voice_confirmed_meeting_id` | 同上 |
| MemberVoiceHistory audit | 同上 (source="anchor_confirmed") |
| Anchor 链顺序 | `list_anchors.py` 按 voice_confirmed_at 升序 |
| 候选扫描 | `incremental_anchor.py:scan_candidates` |
| 候选 mark_confirmed | `incremental_anchor.py:apply_mark_confirmed` |

---

## 六、回滚策略

如 3 个脚本有问题, 主指挥执行:

```bash
# 回滚 (删除 3 个脚本 + 1 个 test + 1 个 docs + 1 个 memory)
git revert <commit-hash>

# 容器内清理
docker exec microbubble-agent-app-1 rm /app/scripts/list_anchors.py \
  /app/scripts/mark_voice_confirmed.py /app/scripts/incremental_anchor.py

docker compose restart app
```

**回滚时间**: < 5 分钟. 已知 anchor 数据 (杜同贺 + 张宏魁) 不受影响 (只回滚脚本, 不改 DB).

---

## 七、未来 PR 排期

如有用户提出增量 Cross-Anchor 升级需求, 候选:

- **PR1**: 给 `incremental_anchor.py` 加 strict 90% 门禁 (跨会议识别率 ≥ 90% 才建议 mark_confirmed)
- **PR2**: 给 `mark_voice_confirmed.py` 加 audit WORM 模式 (anchor 写后禁止任何修改, 包括 force)
- **PR3**: 给 `list_anchors.py` 加 anchor 链健康度评估 (anchor 间 cos_dist 矩阵, 识别"误 anchor"风险)

---

## 八、参考

- Plan: `C:/Users/pc/.claude/plans/cheerful-questing-kite.md`
- Anchor skip 守卫: `scripts/purify_voiceprints_from_meeting.py:188`
- Voiceprint 服务: `app/services/voiceprint_service.py:374`
- Member 模型: `app/models/member.py:55-57`
- Alembic 036: `alembic/versions/036_add_voice_confirmed.py`
- 沉记忆: `memory/w68-route-7-a2-cheerful-questing-anchor-2026-07-24.md`
