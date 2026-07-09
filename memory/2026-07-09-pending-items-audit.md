---
name: 2026-07-09-pending-items-audit
description: 待做清单核对 — 5 项未完成 (PR6-P18 填值 / Self-RAG 收尾 / voiceprint_relaxed 追踪 / MemberCreate wechat_id required / Phase 8 异地容灾)
metadata:
  node_type: memory
  type: project
  originSessionId: 7d13269c-c619-42dc-a52f-055fd11b9576
---

# 待做清单核对 (2026-07-09)

## Context

用户决策"看一下上面这些待做哪些事已经完成的" → 我对前一会话 (Drive 美化收官) 列出的 5 项待做逐项核对实际状态. 结果: 5 项全部未完成, 但分布合理 + 1 项需要 admin 决策.

## 核对结果

### ❌ 未完成 (5 项)

| # | 项目 | 实际状态 | 证据 |
|---|------|---------|------|
| 1 | **PR6-P18 admin 填 14 行 placeholder** | **未做** | DB 验证: `SELECT COUNT(*) FILTER (WHERE wechat_id LIKE '__NULL_BACKFILL_%') → 14` (仍是 14 行, 全 35 行 members 中). 工具链就绪但 `--apply --confirm` 没人跑过. |
| 2 | **#009 Self-RAG 30 天承诺收尾** (2026-07-30 截止) | **未到时间** | `app/config.py:233` 仍有 `AGENT_SELF_RAG_ENABLED: bool = True` + `app/agent/agentic_loop.py:1019` 仍在用双层控制 (ctx.self_rag_enabled + settings). 还有 21 天才到. |
| 3 | **`git status` 显示的 2 个未追踪文件** | **未追踪, 仍存在** | `scripts/voiceprint_relaxed.py` + `scripts/voiceprint_relaxed_v2.py` (5812 + 5457 字节, 2026-07-08 20:23/20:32 创建). 内容是声纹识别临时脚本 (会议 #203), 没 commit 也没 .gitignore. |
| 4 | **PR6-P17 留尾 — MemberCreate.wechat_id Optional → required** | **未做** | `app/schemas/member.py:21` 仍写 `wechat_id: Optional[str] = None`. 这是 CLAUDE.md "应用层 MemberCreate schema wechat_id: Optional → required (本次范围外, 留给业务决定)" 的 follow-up. |
| 5 | **Phase 8 异地容灾** | **未做** | 本地备份已就绪 (Task Scheduler + `scripts/backup_scheduler.bat` 2026-07-08 P0-2), 但异地 (cloud S3/OSS 镜像) 没做. |

### ✅ 已闭环 / 部分完成

| 项目 | 状态 | 备注 |
|------|------|------|
| PR6-P17 wechat_id NOT NULL 防 NULL 渗透 | ✅ DB 层 + Member 模型 `nullable=False` 同步 | 仅 #4 schema 层留尾 |
| PR6-P13~P16 case-insensitive uniqueness 4 列 | ✅ 完整收官 | username/wechat_id/personal_wechat_id/external_userid 全保护 |
| CLAUDE.md 拆分 | ✅ commit `44569e17` | 新会话启动 -81% read 量 |
| 25+ bug 修复收官 | ✅ commit `686eb9d6` | 30 commit 全 push origin/main |
| Drive 全家桶美化 | ✅ 6 commit 链 | 295848df → 782c92b → 0788f8bd → 196cd9e → 7d5bfb0 + 04c7fd2 测试 |
| 声纹循环净化 #151 90% 门禁 | ✅ 已落地 | 长期 sub-project 不算 TODO |

## 验证命令

```bash
# 1. DB 14 行 placeholder 验证
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c \
  "SELECT COUNT(*) FILTER (WHERE wechat_id LIKE '__NULL_BACKFILL_%') AS placeholder_count,
          COUNT(*) FILTER (WHERE wechat_id IS NULL OR wechat_id = '') AS null_empty_count,
          COUNT(*) AS total FROM members;"
# 期望: placeholder_count=14, null_empty_count=0, total=35

# 2. Self-RAG flag 还在
grep -n "AGENT_SELF_RAG_ENABLED" app/config.py
# 期望: 233:    AGENT_SELF_RAG_ENABLED: bool = True

# 3. MemberCreate.wechat_id 仍 Optional
grep -n "wechat_id" app/schemas/member.py | head -3
# 期望: 21:    wechat_id: Optional[str] = None

# 4. voiceprint_relaxed 仍 untracked
git status --short | grep voiceprint_relaxed
# 期望: ?? scripts/voiceprint_relaxed.py / ?? scripts/voiceprint_relaxed_v2.py
```

## 决策建议

5 项未完成中:

- **#1 PR6-P18 填值** — admin 一次性手工操作 (企业微信后台查 8 个 userid → 写 CSV → 跑 CLI), 工具链已就绪, **等你抽空跑**, 不阻塞业务.
- **#2 Self-RAG** — 还有 21 天到期, 不急. smoke 已验证 100 题 OFF 100% vs ON 98% 反劣化.
- **#3 voiceprint_relaxed*.py** — **这是当前唯一需要立即决策的**: 是删 (临时实验脚本, 无价值) 还是 commit (有保留价值的实验)? 决策完即可关闭.
- **#4 MemberCreate schema** — 业务决定, 当前 21 行真实 wechat_id + 14 行 placeholder 已能跑全功能, 不阻塞.
- **#5 Phase 8 异地容灾** — 真正的工程化升级, 单独 phase 评估.

## 3 铁律

1. **待做清单必须定期核对** — 用户决策"看一下哪些已完成"是健康检查, 5 项里 1 项是 admin 决策 (voiceprint_relaxed), 1 项是定时到期 (Self-RAG), 3 项是真实工作. 不能让 TODO 列表无限累积.
2. **DB 验证 > 文档声明** — PR6-P18 工具链状态 "已就绪", 但实际 DB 仍是 14 行 placeholder. 工具就绪 ≠ 实际跑过. 必须用 `psql` 实测才能说"完成".
3. **临时实验脚本必须决策归宿** — `voiceprint_relaxed*.py` 这种带具体 MEETING_ID=203 的脚本, 留 7 天无 commit = 该删. 不留"待定"状态超过 1 周.