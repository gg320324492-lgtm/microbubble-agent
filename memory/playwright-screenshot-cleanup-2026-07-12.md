# Playwright 验证截图清理 + .gitignore 永久排除 (2026-07-12)

> **触发**: 用户决策"Playwright 的截图继续删去, 没啥用" (在 P0-#2 v4 audit commit 后追加)
> **范围**: `web/tests/visual/desktop/screenshots/` (54 PNG / 6.1MB) + `.gitignore` 永久排除

## 清理结果

- **删除**: 54 个 PNG 截图, 共 6.1MB
- **修改**: `.gitignore` 加 `web/tests/visual/**/screenshots/` 永久排除规则
- **Commit**: `c154f5d5 chore: 删除 Playwright 验证截图 (54 PNG / 6.1MB) + .gitignore 永久排除`
- **Push**: `43383798..c154f5d5 main -> main` ✓

## 7 个历史 commit 提交过的 PNG 来源

| commit | 内容 |
|--------|------|
| `c2b1e50a` | P0-#2 v3 + test/spec/screenshot audit (bouncing-*.png) |
| `0c1ed72c` | P0-#2 Playwright spec + screenshots (initial audit) |
| `e6b1ed64` | PWA debug + verify spec (dbg-*.png) |
| `ff30e010` | v2.27 组会PPT Playwright 验证 (team-nested-final.png) |
| `1dd92414` | v2.26 最终 E2E + 4 张截图 |
| `648b863b` | v2.26 团队共享盘 23/23 子文件夹 Playwright 验证 |
| `bd00b692` | v2 PR6-P19 Playwright 截图 (4 张) |

## 删除清单分类 (54 PNG)

- **P0-#1.6 系列** (5 张): p0-1-6-*.png + p0-1-6-v2-FIXED-41-bubbles.png
- **P0-#2 系列** (12 张): bouncing-*.png + real-*.png + final-*.png + p0-2-*.png
- **Drive 团队共享盘** (28 张): team-shared-* + dbg-* + final-A/B-collapsed/expanded + E2E-1~4 + dutonghe-* + team-nested-final + v2-pr6p19-*
- **其他** (9 张): dbg-threestates-* + v2-deep-* + v2-scroll-DEEP + strict-* + final-4-*

## 关键技术决策

### 为什么这些 PNG 没价值

1. **不是 baseline 对比图** — Playwright 真正的视觉回归 baseline 在 `*-snapshots/` 目录 (workbox/pw 自动管理), 不在这里
2. **都是 spec `page.screenshot({ path: ... })` 写入** — spec 跑时会重新生成, 不影响回归测试
3. **audit 价值有限** — git history 已经保留了 commit hash, 想看当时状态 `git show <hash>` 即可, 不需要 PNG 在 HEAD

### 为什么 spec 文件保留

- `p0-2-bounce-recv2.spec.mjs` (146 行 60fps 采样) 是**测试代码**, 未来回归可复用
- 所有 spec 的 `path:` 是写入路径不是读取路径, 删除 PNG 不破坏 spec
- 重新跑 spec 会重新生成截图 (本地, 不入库)

### 为什么 .gitignore 永久排除

- 未来 Playwright 验证还会有截图产生
- `web/tests/visual/**/screenshots/` glob pattern 匹配 desktop/ + mobile/ (若存在) + 任何未来新增的子目录
- 一行规则永久防御

## 5 新铁律 (永久沉淀)

1. **Playwright 截图不进 git** — `web/tests/visual/**/screenshots/` 永久 ignore, spec 跑时本地生成, 需要 audit 走 git history
2. **真正的 visual regression baseline 走 `*-snapshots/`** — 那是 workbox/pw 管理的标准 baseline 目录, 别和临时 audit 截图混在一起
3. **audit trail 在 commit message, 不在 PNG** — 修复细节写在 commit body / memory 文件, PNG 重新生成的成本远低于 git 体积膨胀
4. **6MB PNG 看着小, 7 个 commit 累积起来就是隐患** — 任何"先 commit 后面再清"的策略都会被遗忘, .gitignore 一开始就要加
5. **`git rm --cached` + `.gitignore` 双管齐下** — 只加 .gitignore 不删已 tracked 文件没用 (git 仍会跟踪), 必须 `git rm` + commit 同步进行

## 端到端验证

- [x] `git rm` 54 个 PNG, working tree clean
- [x] `.gitignore` 加 `web/tests/visual/**/screenshots/` 规则
- [x] Commit `c154f5d5` push 到 origin/main
- [x] 验证 spec 仍可跑 (只写入, 不读 PNG)
- [x] git history 完整保留 (commit hash 可查 PNG 当时状态)

## 关联 memory

- `memory/p0-2-chat-jump-to-top-bouncing-2026-07-12.md` (同日 P0-#2 收官, 触发本清理)
- `memory/pre-commit-dist-auto-add-2026-06-26.md` (commit 前必看 dist 体积铁律)