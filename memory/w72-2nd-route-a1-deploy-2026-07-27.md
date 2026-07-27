# W72 第 2 批 A-1 部署沉淀

- 15 分支必须严格按 feature → chore → docs → grand closure 合并，全部使用 `git merge --no-ff`。
- 每个涉及迁移的合并阶段都要验证 Alembic 仅一个 head；本次最终为 `078_drive_dedupe_audit`。
- Web 构建只能使用 `npm run build`，hashed manifest 必须 force-add，不能用裸 `vite build`。
- 部署后执行 6 点 MIME/curl 检查，并完成 webhook、SW cache、PWA install 验证；无法访问服务器时必须显式标记 pending。
- 锚点数字以实际 git history 收束：W72 第 1 批 220 → A-1 222，禁止沿用预期数字。
