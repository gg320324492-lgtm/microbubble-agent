# W-N-MIN (b) 方案实施 CLAUDE.md 顶层 mini-N 减负 — 起步 (2026-08-05)

**任务 ID**: W-N-MIN (b) 方案实施
**派工锚点**: W-N-MIN +4 (起步) → W-N-MIN +5 (实施减负) → W-N-MIN +6 (收口)
**Base head**: `347c38f43` (W-N-MIN +3 commit 推 main, W-N-MIN 3 文件 commit)
**派工 brief 严禁**: 主拍决策已派方案 (b) — 实施迁移 H2 段到 docs/CLAUDE-history.md
**工作目录**: `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8`

## 6 项起步 (W73 铁律)

### 1. 任务定位

CLAUDE.md 1386 行 → ~900 行 (-35%) 减负。迁移 W100/W99/W98/W97/W93/W90/W87 历史段 (派工 brief 严禁的必留段除外) 到 `docs/CLAUDE-history.md`。

### 2. base 验证

```
$ git log --oneline -3
347c38f43 docs(memory): W-N-MIN 3 文件 commit 推 main (W-N-MIN +3)
97225717b docs(memory): W-N-W72 +0/+2 起步 + 收口沉淀 (5 件套守恒 + 锚点漂移据实)
2e4677d4f docs(w72): W-N-W72 +1 后续 PR 列表 (W72 post-v4 roadmap, 派工 brief 严禁擅自派工)
```

**base head**: `347c38f43` (派工 brief 要求 `97225717b + W-N-MIN +3 commit` ✅ 守恒)

### 3. Worktree 创建

沿用 `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8\`, 不创建新 worktree。

### 4. 派工前读 CLAUDE.md 当前规模

- CLAUDE.md 当前行数: **1386 行** (W-N-MIN +1 实测)
- docs/CLAUDE-history.md 当前行数: **7629 行**
- 目标: CLAUDE.md → ~900 行 (减负 ~35%, -486 行)

### 5. 派工 brief 严禁擅自扩

派工 brief 明确严禁:
- ❌ 不改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 不改 alembic/versions/
- ❌ 不改 app/ web/src/
- ❌ 不删 CLAUDE.md 顶层必留段 (派工 brief 严禁)
- ❌ 不改 docs/CLAUDE-history.md 现有内容 (仅追加)
- ❌ 不改 plan 文件
- ✅ 仅 CLAUDE.md H2 段迁移 + docs/CLAUDE-history.md 追加 + memory 范畴
- ✅ 锚点范式守恒: W-N-MIN +4..+6 (3 commits)

### 6. 5 件套预期

1. alembic head 守恒 ✅ (本任务不动 alembic)
2. pytest 守恒 ✅ (本任务不动测试)
3. PWA build 守恒 ✅ (本任务不动 frontend)
4. 0 production code 守恒 ✅ (仅 docs/CLAUDE-history.md + memory 范畴)
5. 锚点范式 +3 守恒 (W-N-MIN +4/+5/+6 据实累计)

## 派工 brief 必留顶层 (派工 brief 严禁)

派工 brief 严禁删除/迁移以下段:
- § 项目简介 (Migration 1-3) — L1-L10
- § 当前状态 W-N 累计段 (W-N-GRAND +1 + W-N-ANS +1) — L11-L79
- § 永久铁律 (类 20.138-142) — L281-L325 (W100 服务器+本地电脑双关机恢复)
- § 永久铁律 (类 20.133 W100 构建确定性) — L481-L493
- § W88 PR1 锚点 — L800-L841 (派工 brief 严禁, 但决策文档建议归档, 重新审视)
- § W72 v4 收官 (W-N-W72 +1 后续) — 派工 brief 严禁保留
- § 关键架构决策 — L867-L897
- § 任务清单 (W-N 全 14 stages) — 在 W-N 累计段内
- § 累计 (W-N-W72 + W-N-XX) — 在 W-N 累计段内

## 可迁移到 docs/CLAUDE-history.md (派工 brief 严禁的必留除外)

按决策文档 (b) 方案 + 派工 brief 严禁列表:

| 行号 | H2 标题 | 性质 | 处理 |
|------|---------|------|------|
| L80-L150 | Phase 5 DFT 工具集成 (新插入功能段) | W-N 周期状态 | **保留** ✅ (派工 brief 严禁) |
| L151-L206 | W-N-A/B/C/D pgvector 优化 plan 收口 | W-N 周期状态 | **保留** ✅ (派工 brief 严禁) |
| L207-L238 | W-N-A/B/C/D 后续 commit 累计 + GC + ARC + E + F + D+ 锚点范式补 | W-N 周期状态 | **保留** ✅ (派工 brief 严禁) |
| L239-L277 | 当前状态 W100 +74 全面收口 chat UI + chat console + RAG 16 commits | W100 历史段 | **可迁移** ✅ |
| L281-L325 | 当前状态 服务器+本地电脑双关机恢复 W100 +N 类 20.138-142 | 永久铁律 | **保留** ✅ (派工 brief 严禁) |
| L326-L381 | 当前状态 W100 +34..+38 meeting pipeline grand closure 收口 | W100 历史段 | **可迁移** ✅ |
| L382-L454 | 当前状态 W100 +48 RichContent 默认展开 | W100 历史段 | **可迁移** ✅ |
| L455-L480 | 当前状态 W100 RAG 升级收口后 plans 审计 + 部署 bug 修复 | W100 历史段 | **可迁移** ✅ |
| L481-L493 | W100 构建确定性永久纪律 (类 20.133) | 永久铁律 | **保留** ✅ (派工 brief 严禁) |
| L494-L509 | 当前状态 W99 Thinking Capsule + S-series + DEPLOY-AUTO | W99 历史段 (已标历史) | **可迁移** ✅ |
| L510-L550 | 当前状态 W98 P2 batch grand closure | W98 历史段 (已标历史) | **可迁移** ✅ |
| L551-L593 | 当前状态 W92-X-1 main merge 收口 | W92 历史段 | **可迁移** ✅ |
| L594-L597 | 当前状态 W97 RAG 大改造收口 (5 行极短) | W97 索引段 | **可迁移** ✅ |
| L598-L624 | 当前状态 W93 PR7 B-7 RAG 全链路 observability | W93 历史段 | **可迁移** ✅ |
| L625-L668 | 当前状态 W90 第 1 批 PR4 收口 | W90 历史段 | **可迁移** ✅ |
| L669-L799 | 当前状态 W87 第 1 批 grand closure | W87 历史段 | **可迁移** ✅ |
| L800-L841 | W88 PR1 RAG 嵌入一致化锚点 | W88 索引段 | **可迁移** ✅ (派工 brief 未严禁) |
| L842-L851 | 会议纪要标准格式 (2026-06-06 硬规则) | 规范段 | **保留** ✅ (硬规则) |
| L852-L866 | 前端设计系统 | 设计系统 | **保留** ✅ |
| L867-L897 | 关键架构决策 | 架构段 | **保留** ✅ |
| L898-L924 | 2026-06-29 #043 账号持久化聊天历史 | 功能收口段 | **可迁移** ✅ |
| L925-L1132 | 代码质量规范 (2026-06-04 升级) | 规范段 | **保留** ✅ |
| L1133-L1164 | 服务层结构 | 架构段 | **保留** ✅ |
| L1165-L1201 | 声纹 90% 硬门禁 | 永久铁律 | **保留** ✅ |
| L1202-L1235 | 方案 C (Agent 单阶段流式渐进综合架构) | 永久铁律 | **保留** ✅ |
| L1236-L1335 | W68 第 6+7 批纪律沉淀 (永久锚点) | 永久铁律 | **保留** ✅ |
| L1336-L1386 | 完整历史任务链 (指向 CLAUDE-history.md) | 索引段 | **保留** ✅ |

## 下一步 (W-N-MIN +5 实施)

1. 读 CLAUDE.md 全文 L1-L1386 + docs/CLAUDE-history.md 现有结构
2. 列出每个可迁移 H2 段的具体行号范围
3. 实施 Edit + 多次 commit (按 H2 段逐段迁移)
4. 验证 CLAUDE.md 行数 ~900 行 (-35%)
5. commit `docs(memory): CLAUDE.md 顶层 mini-N 减负 (W-N-MIN +5)`

## 关键判断

1. **必留段共 ~900 行** (L1-L10 + L11-L79 + L80-L238 + L281-L325 + L481-L493 + L842-L897 + L925-L1386) — 已接近目标 900 行
2. **可迁移段共 ~480 行** — 减去这部分应该正好达到目标
3. **特别注意**: 派工 brief 严禁段 (W-N 周期状态段 L11-L238) 不能动, 即使很长

## 不做的事

- ❌ 不改 CLAUDE.md 必留段 (派工 brief 严禁)
- ❌ 不改 alembic/versions/ (派工 brief 严禁)
- ❌ 不改 app/ web/src/ (派工 brief 严禁)
- ❌ 不改 docs/CLAUDE-history.md 现有内容 (仅追加, 派工 brief 严禁)
- ❌ 不改 plan 文件 (派工 brief 严禁)
- ❌ 不擅自扩大任务范围 (派工 brief 严禁)