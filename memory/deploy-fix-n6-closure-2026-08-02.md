# DEPLOY-FIX-N6 收口（2026-08-02）

## 1. 目标完成度

DEPLOY-FIX-N6 已完成构建阶段：在 `E:/agent-deploy-fix-n6` 的 `chore/deploy-fix-n6` 分支，严格执行 `cd web && npm run build`，产出新的 hashed `web/dist`，并通过 postbuild 脚本。下一步是把 dist 与本次构建记录提交为单一 commit 并推送 `origin/chore/deploy-fix-n6`，由远端 webhook 负责生产部署。

## 2. 起步与依赖

- `git fetch origin`：完成。
- 起步工作树：干净；基线 `266c4ad16`，包含 W99 +12..+18 与 FIX-N6 守卫源码。
- Node：`v24.16.0`；npm：`11.13.0`。
- `web/node_modules` 起步不存在；按已有 `web/package-lock.json` 执行 `npm ci`，成功安装 1109 packages / audit 1110 packages。
- npm 报告 74 个 moderate vulnerabilities；本次不运行 `npm audit fix`，避免越界修改依赖或 lockfile。

## 3. Build 实测

命令：

```bash
cd E:/agent-deploy-fix-n6/web
npm run build
```

结果：

- `vite v7.3.6`。
- `3551 modules transformed`。
- `built in 8.27s`。
- 产物含 `web/dist/assets/index-a1c8aa7c.js`。
- `node scripts/postbuild-fix-manifest.js` 返回成功。
- postbuild 实测输出：`PWA 已禁用 (vite-plugin-pwa disable: true), sw.js 不存在 — 跳过所有 PWA 后处理`，随后 `完成 ✓`。
- Vite 既存非阻断警告：ShareDialog / FormulaBlock 自动导入命名冲突、Dart Sass `@import` 弃用、`@vueuse` PURE 注释位置、element-plus 与 echarts chunk 超过 500 kB。

## 4. PWA 实际结果

`web/vite.config.js` 的 `VitePWA({ disable: true })` 生效。当前 `web/dist` 顶层没有 `sw.js`、`service-worker.js`、`manifest*.webmanifest` 或 `registerSW.js`；`index.html` 没有 manifest / registerSW 引用。此批据实上报为：PWA 生成路径未运行，因为 PWA 已禁用；没有 hashed manifest 可提交，postbuild 的禁用分支是预期成功路径。

## 5. 健全性与 FIX-N6 守卫

- `find web/dist/assets -name 'index-*.js'`：1 个，PASS。
- `web/src/api/analytics.js`：`Array.isArray(payload.top_ids)` 守卫存在，且限制 `top_ids` 最大 20。
- `web/src/stores/useSearchAnalytics.js`：`Array.isArray(topIds)` + 非空守卫存在，且限制最大 20。
- bundle：`web/dist/assets/analytics-baa1399f.js` 命中 `isArray/top_ids`。
- bundle：`web/dist/assets/useSearchAnalytics-5e6dc032.js` 命中 `isArray/top_ids`。
- targeted PWA output check：无 SW、manifest、registerSW 文件；HTML 无实际 PWA 引用，PASS。
- `scripts/check-dist-before-commit.sh`：`sh -n` PASS；直接执行退出码 0。因为本 worktree 未安装 `.git/hooks/pre-commit`，本次通过显式执行脚本验证，未声称存在自动 hook。
- `git add -f web/dist/` 已执行，staged dist 文件数 116；staged 非 dist 文件在 build 阶段为 0。

## 6. 守恒与边界

- `python -m alembic heads`：唯一 head `093_add_search_log_answer_rating (head)`；有既存 SyntaxWarning（`028_figure_structured_fields.py` 的 `\d` docstring），不影响 head 结果。
- pytest：按任务要求不跑，纯 build 范畴。
- `app/`、`web/src/`、`alembic/`、`tests/`：本批无改动。
- `CHANGELOG.md`：无改动。
- `CLAUDE.md`：无改动。
- Alembic：无改动。
- 本批生产变更只来自构建产物；源码守卫来自基线 `266c4ad16`，本批不改源码。

## 7. 提交与部署

目标 commit message：

```text
[DEPLOY-FIX-N6 W99 +19] chore(web): build dist for webhook auto-deploy (FIX-N6 守卫源码修复 + ThinkingCapsule 集成)
```

目标分支：`origin/chore/deploy-fix-n6`。推送后由 webhook 触发生产自动部署；本地无法把 webhook 的服务器执行结果冒报为已验证，需以远端 webhook / deploy log 和生产 6 点 curl 为准。

## 8. 回归风险

- 构建本身 PASS，但依赖安装 audit 的 74 个 moderate advisory 未在本批处理。
- 组件命名冲突、Sass 弃用和大 chunk 警告均为 build 既存警告，未阻断产物。
- PWA 目前明确禁用；因此本批不验证 manifest MIME、SW hash 或 PWA install。若后续重新启用 PWA，必须恢复 `npm run build` + hashed manifest + 6 点 curl 验证纪律。
- 生产 webhook 是否成功、服务器静态资源 MIME、应用 `/health` 与浏览器回归必须由部署侧实测，不以本地 build 结果替代。
