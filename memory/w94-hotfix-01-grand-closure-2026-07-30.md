# HOTFIX-01 W94 P0 PWA 部署阻塞 hotfix 收口 (2026-07-30)

## 任务
PR5 `cb5c98498` 引入 `web/src/views/admin/RAGEvalPanel.vue:24` `import { Play } from '@element-plus/icons-vue'`,
Element Plus icons-vue **没 export `Play`** → `npm run build` FAIL → PWA 部署阻塞.

## 收口成果

- **commit hash**: `c8aa1112b`
- **branch**: `chore/w94-rag-pr5-play-hotfix-2026-07-30`
- **push origin**: 成功
- **锚点**: 477 → 478 (W94 +1 据实, 派工 v11 段 9 锚点前缀规则)
- **5 件套守恒实测**:
  1. alembic heads = `['091_add_kg_entity']` (1 head 守恒, W94 +0 不变)
  2. pytest 守恒 (本次未跑 — docs/ 范畴非后端代码, 件 2 不适用)
  3. PWA build PASS (据实): `vite build` + postbuild 完成, `dist/` 生成
  4. 件 4a: `git diff main..HEAD` 仅 +2/-2 行, 仅 RAGEvalPanel.vue 1 文件
  5. `git log --grep "hotfix-01\|HOTFIX-01" | wc -l` = 1

## 文件改动

仅 1 个文件, 2 行:
- `web/src/views/admin/RAGEvalPanel.vue:27` `import { Refresh, Play, DataAnalysis }` → `import { Refresh, VideoPlay, DataAnalysis }`
- `web/src/views/admin/RAGEvalPanel.vue:114` `<el-icon><Play /></el-icon>` → `<el-icon><VideoPlay /></el-icon>`

## 5 条派工前提铁律遵守 (E25/E27/E29/E41/E42)

- E25 alembic 1 head 守恒 ✓
- E27 push 失败 → 报成功, 无失败
- E29 件 4a 双门控 (Vue SFC) → grep `<Play|<VideoPlay` 实测 0 hit on `<Play `, 1 hit on `<VideoPlay `, 守恒
- E41 顺手修其他问题 → 禁止, 仅改 RAGEvalPanel.vue 1 文件
- E42 改 .tsx / .ts 路径错配 → 本任务仅碰 .vue (PR6 模式对齐) ✓

## 不擅自修其他问题实测证明

- 仅 commit 1 个文件 `web/src/views/admin/RAGEvalPanel.vue`
- 1 file changed, 2 insertions(+), 2 deletions(-)
- 无其他文件改动
- 无 alembic 改动
- 无后端 service/model 改动
- 无其他前端文件改动

## Build FAIL 复现 (派工 v6 §1.2 据实上报铁律)

原始错误:
```
src/views/admin/RAGEvalPanel.vue (24:18): "Play" is not exported by
"node_modules/@element-plus/icons-vue/dist/index.js", imported by
"src/views/admin/RAGEvalPanel.vue".
```

修后 build PASS:
```
✓ built in 11.12s
[postbuild] PWA 已禁用 (vite-plugin-pwa disable: true), sw.js 不存在 — 跳过所有 PWA 后处理
[postbuild] H-3 修复: 强制注销浏览器老 SW + 清空 Cache Storage 已在 main.js 顶部实现
[postbuild] 完成 ✓
```

## 起步 memory

`memory/w94-hotfix-01-start-2026-07-30.md` (起步事实 + 派工前提铁律)

## 派工 v11 段 7 错误 19 类 (HOTFIX-01 specific) 遵守

- 必读 + grep `<Play|<VideoPlay` 守恒 ✓
- 件 3 PWA build 真 PASS ✓
- 件 4a 双门控 ✓
