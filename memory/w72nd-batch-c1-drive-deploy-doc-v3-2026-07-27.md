# W72 第 2 批 C-1 — Drive v2 部署文档 v3 (2026-07-27)

> **commit**: (pending C-1 commit)
> **锚点范式**: W72 第 1 批 220 → W72 第 2 批 C-1 230 (+10 守恒)
> **批次**: W72 第 2 批 (主拍板: 派工纪要 v8 + 派工前提 6 项实战)
> **依据**: W72 第 1 批 A-2 (`e51699d48` PR9-11 master runbook) + W72 第 1 批 C-3 (`f1947d3c7` ppt-word 5 缺口) + W72 第 1 批 C-2 (`a78967661` 24 人月季度排期)

## 交付物

**主文档**: `docs/drive-v2-deployment-v3-2026-07-27.md` (~480 行, 9 段覆盖)

### 7 段覆盖 (按派工 prompt 段 1-7)

1. **段 0: alembic 链风险** — 实际链顺序 076 → 079 → 078 (B-1 接 079 而非 076) + 7 张新迁移串单链表 + 5 步 verify 流程
2. **段 1: PR17/18/5 部署** — 6 步部署 + 验证脚本 `verify_drive_pr17_dedupe.sh`
3. **段 2: 5 缺口收口** — PR2 sharing 081 + PR3/5/7 无迁移 + 缺口 5 gap recovery
4. **段 3: 商业化 Phase 8** — 082 alembic + Dockerfile.commercial + SaaS 多租户 + License + 9 项隔离
5. **段 4: 6 主题 dark mode** — v70-v74 token + v77 P2.6 移动端 dark + 18 视觉快照 CI
6. **段 5: 部署必做 10 步** — pull/alembic/cp/clear/upgrade/rebuild/restart/6点curl/SW-BUMP/PWA-install
7. **段 6: hot-fix 链预案** — 4 类 (alembic 双头 / PWA 410 / octet-stream / SW 污染)
8. **段 7: 锚点范式守恒** — 12 守恒表 + 0 production code 14/15 守恒 + W73 起步纪律 6 项
9. **段 8: 主指挥协调备忘** + **段 9: 文档历史**

### 4 新铁律沉淀

1. **alembic 链顺序必须以实际命名为准** — 派工 prompt 可能写 077/078 顺序, 但实际 PR17 078 接 079 (PR18)。**派工前提** 第 1.5 条: 主拍必须核对每个 migration 的 down_revision 行 (例 `alembic/versions/078_drive_dedupe_audit.py:35 down_revision: Union[str, None] = "079_team_folders"`), 不是凭记忆 / 计划文档。
2. **docker cp 多个新迁移必须 verify 1 head** — `python -c "ScriptDirectory.from_config...get_heads()"` 期望 list 长度 = 1。期望失败主拍 abort + 紧急 hot-fix (CLAUDE.md 永久锚点)。
3. **6 点 curl 验证是 nginx octet-stream 白屏的唯一防御** — HTML / CSS / JS / PNG / manifest / sw.js 6 个 Content-Type 全部不能是 octet-stream (CLAUDE.md 永久锚点 + commit `f148d96` 教训)。
4. **`npm run build` 唯一合法** — `vite build` 直跑必坏 PWA (manifest.webmanifest 没 hash → 服务器 410 → PWA install 失败)。派工 v4 铁律, 任何 agent commit 前 grep 自检 `git diff --cached -- web/dist/` 期望空输出。

### 0 production code 改动铁律维持

- C-1 = 文档任务, 不算 production
- 例外清单 (5 已批): B-1/B-2/B-3 alembic 078/079/080 (W68 第 14 批已批) + C-2/C-3 web alembic 081/082 + Dockerfile.commercial (W72 第 2 批新批)

## 派工前提 6 项实战 (派工 v6 段 6)

| # | 派工前提 | 实战 |
|---|---------|------|
| 1 | alembic 链风险段必含 | ✅ 段 0 实战, 链顺序以 migration 源码为准 |
| 2 | 6 点 curl 验证必含 | ✅ 段 5 步骤 8 实战 |
| 3 | SW BUMP + PWA install 必含 | ✅ 段 5 步骤 9-10 + 段 6 hot-fix 链预案 |
| 4 | 0 production code 守恒 | ✅ 文档任务不算, 主拍例外清单 5 已批 |
| 5 | 段 5 反馈循环实战 | ✅ 派工 v8 反馈 #3 实战, 主拍核对 migration 源码 down_revision 而非凭计划 |
| 6 | 文档历史可追溯 | ✅ 段 9 实战 v1 → v3 时间线 |

## 锚点范式数字正确性

- W72 第 1 批 220 (B-5 commit `b7ad730a6` 实测)
- W72 第 2 批 C-1 230 (+10 守恒预期)
- 锚点范式守恒 (W7 12 → ... → W72 第 1 批 220 → W72 第 2 批 230)

## 下一步 (W73 起步纪律)

- B-1 实施 PR17 验证脚本 (W72 第 3 批预计)
- W73 第 1 批 C-1..C-3 + D-1 = ppt-word 5 缺口收口 (PR2 sharing + PR3 comment v2 + PR5 trash + PR7 file_request + 缺口 5 gap recovery)
- 商业化 W74 第 2 批 B-1..B-3 + E-1 多租户验证

## 反思

C-1 是 docs-only agent, 最容易踩的坑:
1. **抄计划文档的链顺序而不是查 migration 源码** — 派工 prompt 写了 "078 接 079", 实际是 "079 接 076, 078 接 079"。文档必须以源码为最终准绳。
2. **漏段 0 alembic 链风险** — 派工 v6 段 6 已要求必含, 漏则主拍 abort
3. **漏 4 类 hot-fix 链预案** — 0 实战 hotfix 没沉淀等于下次踩同一坑
4. **漏 npm run build 唯一合法铁律** — 派工 v4 沉淀, 漏则回归 commit `59187ce8` 教训

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
