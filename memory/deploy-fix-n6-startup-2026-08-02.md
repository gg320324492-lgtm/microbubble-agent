# DEPLOY-FIX-N6 起步确认（2026-08-02）

- 目标工作树：`E:/agent-deploy-fix-n6`
- 分支：`chore/deploy-fix-n6`
- 起步基线：`266c4ad16`（FIX-N6 analytics 守卫源码修复，已包含 W99 +12..+18 与上一轮 dist）
- `git fetch origin`：完成；起步 `git status --short`：干净
- 变更边界：只生成并提交 `web/dist/`；不改 `web/src/`、`app/`、测试或 alembic
- 构建命令：`web/package.json` 明确为 `npm run build`，会执行 `vite build && node scripts/postbuild-fix-manifest.js`；禁止直接运行 `vite build`
- 构建前实测：Node `v24.16.0`、npm `11.13.0`；`web/node_modules/` 与 Vite binary 尚未就绪；`web/package-lock.json` 存在，后续使用 `npm ci` 仅恢复依赖
- PWA 配置实测：`web/vite.config.js` 的 `VitePWA({ disable: true })`；据实预期无 `sw.js` / manifest，postbuild 应走 PWA-disabled 分支
- Alembic 实测：单 head `093_add_search_log_answer_rating`（仅检查，不改迁移）
- dist 守卫源码实测：`scripts/check-dist-before-commit.sh` shell syntax OK；本工作树未安装 `.git/hooks/pre-commit`，因此构建后手动执行守卫脚本并记录结果
- 下一步：恢复依赖，严格执行 `npm run build`，检查 FIX-N6 analytics 守卫进入 hashed bundle，再强制 stage `web/dist/`、提交单一 DEPLOY-FIX-N6 commit 并推送远端分支
