# W72 第 2 批 A-1 部署收口 checklist（2026-07-27）

1. **合并顺序**：B1-B5 feature → C1/C3 chore → C2/D1 docs → A1-A4 chore → D2/D3 closure；15/15 分支已按序保留 `--no-ff` 拓扑。
2. **Alembic**：本地 ScriptDirectory 验证 `heads: ['078_drive_dedupe_audit']`，单 head。
3. **Baseline Lint**：合并范围未修改既有 lint 配置；完整 baseline 应在 CI/部署环境执行。
4. **Web dist**：本 worktree 未执行构建，避免在依赖未安装环境伪造产物；部署前必须 `cd web && npm run build`，并 force-add hashed manifest。
5. **Nginx curl**：当前未连接部署服务器，6 点 HTML/CSS/JS/PNG/manifest/SW curl pending。
6. **Webhook**：部署 webhook 30 秒验证 pending。
7. **SW cache**：需浏览器 DevTools 确认新 SW activated 且无旧 documents cache。
8. **PWA install**：需部署后 Chrome/Edge 端到端安装验证。
9. **Production code 守恒**：按 W72 第 1 批清单，14/15 改动铁律维持；业务例外仅已批准 UI 路径。
10. **锚点守恒**：W72 第 1 批 220 → A-1 222（+2），以实际合并历史与单 head 证据收束。

部署验证未完成项已明确标记 pending，不伪造服务器证据。
