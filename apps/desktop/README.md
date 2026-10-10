# `apps/desktop/` — Electron 桌面客户端

> **目录边界（结构重构批次 6，2026-10-10 补）**：本目录是**桌面端的实际代码**
> （pnpm workspace 成员之一）。`desktop-conversion/` 是**改造历史的文档工作区**，
> 两者不是同一个东西 —— 见下方对照表。

## 是什么

- 包名 `@mb/desktop`，产品名 **MicroBubbleWorkbench**（"小气 · 科研工作台"）
- 技术栈：Electron + electron-vite + Vue 3 + Element Plus + Pinia
- 当前版本 `1.3.2`
- 源码分三层：`src/main`（主进程）/ `src/preload`（预加载桥）/ `src/renderer`（渲染进程）+ `src/shared`

### 为什么它在 `apps/` 下

`pnpm-workspace.yaml` 只声明了两个顶层 glob：

```yaml
packages:
  - 'apps/*'
  - 'packages/*'
```

所以 `apps/desktop` 是 **pnpm workspace 的正式成员**，位置由 workspace 约定决定，
不是随手放的。仓库顶层还有 `packages/`（当前只有 `design-tokens`）——
`@mb/design-tokens` 通过 `workspace:*` 被本目录消费。

**不要**为了"目录名对称"把 `apps/desktop` 搬到别处：搬走会脱离
`pnpm-workspace.yaml` 的 `apps/*` glob，`pnpm install` 的 workspace 链接就断了。

---

## 与 `desktop-conversion/` 的关系（两回事，务必分清）

| | `apps/desktop/`（本目录） | `desktop-conversion/` |
|---|---|---|
| 性质 | **实际代码**（Electron 客户端） | **改造历史的文档工作区**（工单 / 验收 / 决策 / 计划） |
| 跟踪状态 | 本仓库 tracked（213 个 git 文件） | 曾是**独立 git 仓库**（自带 `.git`），父仓库 `.gitignore` 整体忽略（`git ls-files` 返回 0） |
| 内容 | `src/` / `package.json` / `electron-builder.yml` / `out/` / `release/` | `docs/plans` / `workorders` / `acceptance` / `decisions` / `session-log` + `AGENT.md` |
| 归属 | 主仓 monorepo | 原独立仓库（后于 **2026-10-10 裁定按方案 C 合并入主仓**，见下） |

**一句话**：`desktop-conversion/` 记录"桌面端是怎么一步步造出来的"，
`apps/desktop/` 是造出来的东西本身。查历史决策看前者，改代码看后者。

### 合并计划（D2 裁定，2026-10-10）

`desktop-conversion/` 是独立 git 仓（193 commits + 私有远端），而主仓已公开 ——
历史若带凭据泄露则不可直接并入。已完成可行性审计并**裁定走方案 C（只搬文件、不带历史）**，
审计报告：[`docs/audit/2026-10-10-desktop-conversion-merge-feasibility.md`](../../docs/audit/2026-10-10-desktop-conversion-merge-feasibility.md)。
**截至本 README 写入时合并尚未执行**（见结构重构计划批次 7），本目录因此仍是
唯一存放实际代码的地方。合并落地后请回来更新本表。

---

## ⚠️ 已知跨顶层耦合（移动前必看）

**1. `web/package.json` 有 3 条 `../scripts/k6/*.js` 引用**：

```json
"load:chat":  "k6 run --vus 10 --duration 30s ../scripts/k6/chat_stream.js",
"load:ws":    "k6 run --vus 10 --duration 30s ../scripts/k6/ws_notifications.js",
"load:drive": "k6 run --vus 5  --duration 30s ../scripts/k6/drive_collab.js"
```

`web/` 不在 pnpm workspace 里，它**越过 workspace 边界**直接引用顶层 `scripts/k6/`。
这是现状，评估任何"顶层目录归位"方案时必须把这 3 条算进去 ——
移动 `scripts/k6/` 时需同步改这 3 个 script，否则 load test 直接断。

**2. 本目录自己也跨顶层引用**：`predev` / `prebuild` 都调
`bash ../../scripts/sync-design-tokens.sh`（相对 cwd，非绝对路径）。
`electron-builder.yml` 里的 icon / resources / `out/**` 同理。
**移动 `apps/desktop` 会同时打断这几处** —— 这是本目录不宜随意移动的直接原因。

**3. `git ls-files` 驱动的脚本会静默跳过独立子仓**：
`desktop-conversion/` 归主仓之前，父仓库的 `.gitignore` 把它整体排除，
任何用 `git ls-files` 枚举"仓库里有哪些文件"的检查脚本都会**静默地看不到它**，
不报错、不告警。合并后这个陷阱消失 —— 但在那之前，审计/统计类脚本的
"零结果"要当回事。

---

## 常用命令

```bash
pnpm dev        # predev 先同步 design-tokens，再起 electron-vite dev
pnpm test       # vitest run
pnpm typecheck  # tsc --noEmit + vue-tsc --noEmit
pnpm build      # clean-out + electron-vite build
pnpm gate       # test + typecheck + build（提交前跑这个）
pnpm dist       # electron-builder 出 Windows NSIS 安装包
```

`node_modules/`、`out/`、`release/` 均为 gitignore 的构建产物。
