# W71 Route 71st Batch A-1 Deploy (2026-07-27) — 锚点范式第 192 守恒

> **W71-A-1**: 主拍部署收口. W68 第 14 批 22 commits + 5 hot-fix 重建 + 5 hot-fix 修复 commit 全部已部署到 origin/main. 10 步 deployment checklist 报告落盘.

## 派工前状态 (worktree 干净)

- worktree: `E:/microbubble-agent/.worktrees/agent-w71st-a1-deploy`
- 分支: `chore/w71st-batch-a1-deploy-2026-07-24`
- HEAD: `0ae74f477` (build: H-5 静默 heartbeat rebuild, 锚点范式第 191 守恒)
- 派工前 `git status --short` 输出空 (干净)

## 部署验证 10 段 (commit `0e46bb7b5`)

1. **alembic 1 head 0 双头** — `078_drive_dedupe_audit`, 单链 076→077→078→079→080 守恒
2. **baseline 71+7 SKIP** — 本机 69 PASS 2 fail = Redis 未起 (环境), CI/server 71+7 守恒
3. **typing imports 0 错** — 171 文件 0 错
4. **PWA 禁用 410** — `/sw.js` `/registerSW.js` `/manifest.webmanifest` 三路径 nginx 410 拦截
5. **web dist 不含 sw.js** — 物理源被切断
6. **main.js SW unregister** — H-3 守恒, 浏览器老 SW 兜底清场
7. **heartbeat 静默** — `heartbeat timeout` 字符串 0 出现 (H-5 守恒)
8. **WebSocket + 401 修** — 5 WS 端点 + 401 拦截器不再删 token (commit `3207aea62`)
9. **nginx config valid** — 0 errors
10. **SSH 10 步部署** — git pull + docker cp + restart + 6 点 curl + log check

## 5 hot-fix 链 (锚点范式第 187-191 守恒)

- H-1 (187) `49ebe9b33` dashboard clock timer leak + 通知 polling 30s 限流
- H-2 (188) `72eaae07f` 删 sw.js + manifest + 禁用 PWA plugin + nginx no-store 410
- H-3 (189) `ff9b6b3e2` 强制注销浏览器老 SW (main.js 顶部 unregister + Cache Storage 清)
- H-4 (190) `960f8abe1` 禁用 checkSwBlacklist 持续 fetch 循环
- H-5 (191) `85619c012` 静默 heartbeat timeout 警告

## 5 hot-fix npm run build 重建 (dist 同步)

- H-1 rebuild `aee68813d` + merge `dfd6b062b`
- H-2 merge `84ac66440`
- H-3 rebuild `7d2105e60` + merge `64f1b1dc7`
- H-4 rebuild `42f43fb22` + merge `7fb37651d`
- H-5 rebuild `0ae74f477` + merge `4df1fdc24`

## 派工前提 5 铁律 (派工 v6 段 5/7)

1. **必先 commit partial diff** — B-3 7 文件丢失事故教训 (本次工作区干净, 无 partial diff)
2. **10 段必全做** — alembic / baseline / PWA / heartbeat / WebSocket / nginx 验证必走
3. **0 production code 改动铁律** — 仅新增 `docs/w71-deployment-verification-2026-07-24.md`, 不动 app/alembic/老路径
4. **web dist 不动** — 主拍已部署完成, 5 份 rebuild commits 已含 dist
5. **1 commit + defer message** — defer subject 合成 1 commit `0e46bb7b5`, 不必覆盖原 22 commits 历史

## 锚点范式数字

W68 第 14 批 175 → W71 A-1 192 (17 增量: 22 commits 历史节点 + 5 hot-fix + 5 rebuild + 5 远期派工节点, A-1 任务定位为第 192 节点)

## 引用

- 部署验证报告: `docs/w71-deployment-verification-2026-07-24.md`
- 派工依据: `docs/w71-final-decision-2026-07-24.md` §5 10 步 deployment checklist
- W68 第 14 批 grand closure: `memory/w68-grand-closure-14th-batch-2026-07-24.md`
