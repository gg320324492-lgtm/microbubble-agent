# W-N-GLITCH glitchtip-dev-1 restart loop 排查起步 (W-N-GLITCH +0, 2026-08-05)

**任务**: W-N-GLITCH glitchtip-dev-1 重启循环修复
**派工锚点**: W-N-GLITCH +0 起步 / +1 修复尝试 / +2 收口
**派工 brief base**: `74d1a965e` (W-N-DEPLOY 收口, 主仓库当前 HEAD)
**Worktree**: 主仓库 (本任务仅 docs/memory 范畴, 未开 worktree)

---

## 1. 起步 6 项 (W73 铁律)

### 1.1 派工锚点核对

- ✅ 派工 brief: W-N-GLITCH +0..+2 (3 commits)
- ✅ base head: `74d1a965e docs(deploy-status): W-N-DEPLOY 部署状态验证报告 + 起步 + 收口 (W-N-DEPLOY +0/+1/+2)`
- ⚠️ 派工 brief 启动验证: `git log --oneline -3` 显示 base head = `74d1a965e` ✅
- ⚠️ 派工 brief 工作目录核对: 本任务在主仓库 `E:\microbubble-agent` ✅
- ✅ 0 改 production code 守恒 (本次仅 docs/memory)
- ✅ 0 改 docker-compose.yml (派工 brief 严禁)

### 1.2 派工 brief 严禁清单

- ❌ 改 docker-compose.yml / docker-compose.dev.yml / docker-compose.test.yml
- ❌ 改 alembic/versions/
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 改 plan 文件
- ❌ 重启 glitchtip 容器 (派工 brief 严禁, 主拍决策)

### 1.3 派工 brief 允许范围

- ✅ 写 `docs/w-n-glitchtip-fix-attempt-2026-08-05.md` 决策记录
- ✅ 写 `memory/w-n-glitchtip-fix-startup-2026-08-05.md` 起步沉淀
- ✅ 写 `memory/w-n-glitchtip-fix-closure-2026-08-05.md` 收口沉淀
- ✅ commit docs/memory 范畴

### 1.4 W-N-DEPLOY 报告透露信息

- W-N-DEPLOY 验证 10 healthy + 1 glitchtip-dev-1 Restarting (旁路)
- glitchtip 列为"旁路"不视为阻塞 → 主拍决策不在本任务修复
- 派工 brief W-N-GLITCH +1 步骤 4 明确允许: (a) 修复配置 OR (b) 仅写决策文档留 future PR
- 派工 brief 严禁改 docker-compose.yml → 即使 (a) 也只能写决策文档

### 1.5 派工 v6 §5 反馈类 20 实战相关

- 类 20.140 (W100 +N): `docker compose up -d` 起的容器**有时**漏 attach default network. 表现: `getent hosts <other>` 返回空, 触发 "Network is unreachable" / "Temporary failure in name resolution". 修复: `docker network connect --alias <name> <network> <container>`. 预防: up 后**必须**跑 `docker network inspect` 验证 app 在列表.
- 类 20.138 (W100 +N): Docker Desktop 端口转发 endpoint metadata 缓存只能 GUI Quit+Start 清掉. W91-X-20 实战曾用过此 trick.
- 类 20.101 (W91-X-20 沉淀): docker service crash 排查必 4 件: docker logs / docker inspect / env / db 状态

### 1.6 起步结论

按 W-N-DEPLOY 报告 + 派工 brief, 起步 OK. 现状 deadlock 不是 critical (W-N-DEPLOY 旁路), 派工 brief 严禁改 docker-compose, 走 (b) 仅写决策文档路径.
