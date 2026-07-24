# 会议转录自动润色 (`autoPolishIfNeeded`) 决策记录

> **文档背景**: W68 第 7 批 A-1（2026-07-24）。Plan `cached-giggling-pebble.md` 深度审计 #1 发现
> Plan 核心建议 P0 改动 1「删除 `autoPolishIfNeeded`」被后续 commit 反向重写为强化限流版，
> 但 Plan Status 段仍标 COMPLETED 且挂错 commit hash。本文档记录完整决策链，
> 供未来维护者理解为什么 `MeetingDetailView.vue:564` 的 `autoPolishIfNeeded` 至今保留。

**涉及文件**: `web/src/views/MeetingDetailView.vue:564` `autoPolishIfNeeded()`（76 行强化限流版）

**状态**: PARTIAL_REGRESSION (USER_APPROVED) — 主指挥 W68 第 7 批拍板接受现状，不删除。

---

## 第 1 节：Plan 原始设计（删除 `autoPolishIfNeeded` 的 4 个理由）

Plan `cached-giggling-pebble.md`（"转录记录 Tab 加载慢优化"）P0 改动 1 建议**直接删除**
`autoPolishIfNeeded` 整个函数 + `polishedTexts` ref + `getPolishedText` 兜底，理由：

1. **数据库已有 `transcript_polished` 字段** — 后端 L3 全文精润色结果已存 `meeting.transcript_polished[]`，
   前端 polish 只是给"短段合并后无标点"再加逗号，属**多此一举**。
2. **串行 LLM 调用是 tab 卡顿罪魁祸首** — 原版 `for` 循环顺序 `await` 每个 `/polish-text` 调后端 Claude ≈ 1.5s，
   实测会议 #135（98 段待润色）总计 ≈ 147s 卡顿。
3. **触发时机过于宽松** — `setTimeout(() => autoPolishIfNeeded(), 500)` 在**每次** `fetchMeeting()`
   （首次加载 / `saveBasic` / `saveMinutes` / `onCallEnded`）都跑，即使用户没切到转录 tab。
4. **`transcriptEntries` computed 内部 mutate `_needsPolish`** — 触发不必要的响应式更新，
   删除 polish 逻辑后该字段一并失去意义。

**Plan 预期端到端效果**：tab 激活 0 个 LLM 调用，节省 ~147s，用户"瞬间进入"。

**原始实施**: commit `9986eb67d`（2026-06-26）确实按 Plan 删除了 `autoPolishIfNeeded`。

---

## 第 2 节：反向重写原因（DB `transcript_polished` 字段完整性检查）

Plan 的核心假设是 **"数据库已有 `transcript_polished` 字段存 L3 全文精润色结果"**。
删除后实际运行中发现：**该假设不成立** —— 大量历史会议的 `transcript_polished` 字段
为 `NULL` 或未完全回填（仅新会议 + 手动 reprocess 过的会议才有）。

字段完整性检查方式：

```sql
-- 统计 transcript_polished 为空的会议数
SELECT count(*) FILTER (WHERE transcript_polished IS NULL) AS null_count,
       count(*)                                            AS total
FROM meetings;
```

当 `transcript_polished IS NULL` 时，`transcriptEntries` computed 回退到原始 `transcript[]`
（无标点的短段合并文本），前端若无 polish 兜底则展示体验劣化（大段无标点连续文本）。

因此 commit `bb18c9708`（2026-07-08）**反向重写**，重新加入 `autoPolishIfNeeded`，
但改为强化限流版（见第 3 节），既保留前端 polish 兜底，又规避原版的性能与稳定性问题。

---

## 第 3 节：强化版设计（限流保护）

当前 `MeetingDetailView.vue:564` 的 76 行实现相比原版有 3 层限流保护
（commit `bb18c9708`，2026-07-08）：

1. **chunked batch 200** — 按 200 条分块调 `/polish-text-batch`（后端硬上限 200 条/批，
   防 LLM token 超限）。长会议 #120（3357 段）/ #95（333 段）/ #151（426 段）不分块会触发 400。
   ```js
   const BATCH_SIZE = 200
   ```

2. **concurrency 3（并发限流）** — `MAX_CONCURRENT_CHUNKS = 3`，最多 3 个 chunk 同时发。
   ```js
   const MAX_CONCURRENT_CHUNKS = 3
   ```
   根因：原版 `Promise.all` 会把所有 chunk 同时发（17 个 LLM 请求持 17 个 DB session）
   → 后端连接池 30 个全占满 → 所有 API 500/504。

3. **大会议 500+ 段跳过** — `pending.length >= 500` 时直接 `return`，不做前端 polish。
   ```js
   if (pending.length >= 500) {
     console.warn(`...${pending.length} 段待润色 > 500，跳过自动润色（防 DB 连接池耗尽）`)
     return
   }
   ```
   长会议用户已能接受原始 ASR 文本（会议纪要 + 关键要点已由 LLM 生成）。

此外强化版仍保留原版跳过逻辑：`transcript_polished[i].text !== transcript[i].text` 时
认定 DB 已润色，跳过该段（避免重复 polish 已回填的会议）。

**对比 Plan 原版（串行 `for` + 每段单独调 `/polish-text`）**：强化版
批量 + 并发限流后，即使触发也不再是 147s 串行卡顿或连接池耗尽事故。

---

## 第 4 节：决策日志

| 日期 | commit | 决策 |
|------|--------|------|
| 2026-06-26 | `9986eb67d` | 按 Plan `cached-giggling-pebble.md` P0 改动 1 **删除** `autoPolishIfNeeded` |
| 2026-07-08 | `bb18c9708` | **反向重写**：重新加入强化限流版（chunked 200 + concurrency 3 + 500+ 跳过），因 DB `transcript_polished` 未完全回填 |
| 2026-07-24 | (W68 第 7 批 A-1) | 主指挥拍板**接受强化版存在**，不删除；修正 Plan Status 段 + 写本决策文档 |

**主指挥拍板理由（2026-07-24）**：DB `transcript_polished` 字段实际未完全回填，
前端 polish 限流保护仍必要。强制删除会导致历史会议（`transcript_polished IS NULL`）
转录 tab 展示无标点连续文本，体验劣化。强化版已通过 3 层限流规避原版的性能与稳定性问题，
保留是当前最优解。

Plan Status 段从 `COMPLETED`（且挂错 commit hash — 原写"3rd-wave Agent 4: knowledge 提取"）
修正为 `PARTIAL_REGRESSION (USER_APPROVED)`，如实反映：P0 改动 1 被反向重写，
P0 改动 2-3 + P1 + P2（3/4）完成。

---

## 第 5 节：未来优化

**真正删除 `autoPolishIfNeeded` 的前置条件**：全量回填 `transcript_polished` 字段。

建议路线（未来 PR）：

1. **全量回填脚本** — 遍历所有 `transcript_polished IS NULL` 的会议，
   离线批量调后端 polish 写回 DB 字段（复用现有 `reprocess_meeting.py` 模式 + 批处理限流）。
2. **回填完整性验证** —
   ```sql
   SELECT count(*) FILTER (WHERE transcript_polished IS NULL) FROM meetings;  -- 期望 0
   ```
3. **确认 0 NULL 后** — 前端 `autoPolishIfNeeded` 可真正删除（回到 Plan 原始设计），
   `getPolishedText` 简化为 `return entry.text`，tab 激活 0 个 LLM 调用。
4. **新会议保证** — 后端会议后处理管线确保新入库会议 100% 写 `transcript_polished`，
   防止字段再次出现 NULL。

在上述回填 + 验证完成前，强化限流版 `autoPolishIfNeeded` 保留。
