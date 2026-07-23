# Drive v2 PR9 上线检查表 (Rollout Checklist, 2026-07-24)

> 主指挥专用。逐项打勾, 全绿才发用户通知。配套详细命令见 `docs/drive-v2-pr9-deployment.md`。

---

## 1. 部署前检查 (Pre-flight)

### 1.1 代码与分支

- [ ] 三个 PR9 分支已 review 并 merge 进 main:
  - [ ] `feat/drive-v2-pr9-comments-2026-07-24` (F-1, commit `0bfe36751`)
  - [ ] `feat/drive-v2-pr9-versions-2026-07-24` (F-2, commit `04e06f6fd`)
  - [ ] `feat/mobile-drive-comments-ui-2026-07-24` (F-3, commit `a6f183511`)
- [ ] **alembic 双头已解决**: merge 后已把 `063_drive_file_versions.py` 的 `down_revision` 从 `061_drive_folder_share` 改为 `062_drive_comments` (单链 061→062→063), 或明确决定走 `upgrade heads` (见 deployment 文档第 0 节)
- [ ] `docker exec microbubble-agent-app-1 alembic heads` 本地演练输出**单个** head
- [ ] `bash scripts/check_typing_imports.sh` 0 错误 (方案 C 铁律 2, PR9 新增 6 个 `app/` py 文件)
- [ ] main.py 两个 router 注册 diff 无冲突 (`drive_comments.router` + `drive_versions.router`)

### 1.2 测试基线

- [ ] 后端 pytest 全量: 87+ 基线不回归; F-1 12 e2e + F-2 5 e2e (需 PG) PASS
- [ ] 前端 vitest: 492+ 不回归
- [ ] Playwright `web/tests/e2e/mobile_drive_comments.spec.js` PASS
- [ ] Lint CSS 基线守恒: 71 PASS + 7 SKIP (0 drift)

### 1.3 数据与环境

- [ ] 生产 `alembic current` = `061_drive_folder_share` (前置 PR7 迁移已跑)
- [ ] PG 备份: `pg_dump -U postgres -d microbubble > backup_pre_pr9_$(date +%Y%m%d).sql` (新表迁移风险低, 但铁律照做)
- [ ] MinIO 可用 (F-2 版本对象写 `uploads/drive/{owner_id}/v{n}_...`): `docker compose ps minio` healthy
- [ ] 磁盘余量检查 (版本历史 = 完整副本, 空间敏感): 宿主机 + MinIO volume ≥ 20% 空闲
- [ ] 选好部署窗口 (建议组会外的低峰时段; 迁移仅建 2 张新表, 预计停顿 < 1 分钟)

### 1.4 前端 build 纪律 (CLAUDE.md 2026-07-11 铁律)

- [ ] F-3 dist 用 `npm run build` 产出 (**严禁** `vite build` 直跑)
- [ ] `git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'` 空输出
- [ ] 新增 hashed manifest 已 `git add -f`
- [ ] dist force-add commit 与 source commit 紧邻 (2026-07-12 教训)

---

## 2. 部署执行 (Execute)

- [ ] `git pull` main 到本地 PC Docker 宿主机
- [ ] `docker cp` 062 + 063 进容器
- [ ] `rm -rf /app/alembic/versions/__pycache__` (SKIP_DB_SETUP=1)
- [ ] `alembic upgrade head` 输出两条 Running upgrade (061→062→063)
- [ ] `docker compose restart app celery-worker`
- [ ] `docker compose logs app --tail 50` 无 error/traceback
- [ ] 前端 dist push → 云端 webhook 30s 发布

## 3. 部署后验证 (Verify)

- [ ] psql `\dt drive_*` 见 4 张表 (folder_shares / folder_members / comments / file_versions)
- [ ] `alembic_version` = `063_drive_file_versions`
- [ ] 6 点 curl 全过 (deployment 文档 3.2 节): 列表 200 / 创建 201 / XOR 400 / 版本列表 200 / 上传新版本 201 / 无鉴权 401
- [ ] 手机实机: 评论页渲染 + 发评论 + 长按菜单 + dark mode (iOS Safari + Android Chrome 各 1 台)
- [ ] 桌面端网盘老功能抽查不回归: 上传 / 下载 / 文件夹树 / 分享 (0 production code 铁律的验证面)
- [ ] 观察 30 分钟 `docker compose logs -f app` 无新增 500

## 4. 回滚触发条件 (Abort criteria)

任一命中 → 按 deployment 文档第 4 节回滚 (< 5 分钟 SLA):

- [ ] alembic 迁移中途报错且无法 stamp 修复
- [ ] 部署后网盘**老功能** (上传/下载/列表) 出现 500
- [ ] 评论/版本端点报 `column does not exist` 且 restart 后不消失
- [ ] 移动端评论页白屏且影响网盘主路由

---

## 5. 部署后用户通知模板

> 发到课题组微信群 / 小气助手公告。部署验证全绿后再发。

```
📢 网盘更新: 文件评论 & 版本历史上线啦

各位老师同学, 课题组网盘新增两个功能:

💬 文件评论
- 任何文件/文件夹下都能发起讨论, 支持多层回复
- 输入 @ 可以提醒指定成员 (对方会收到铃铛通知)
- 讨论有结论后可标记「已解决」, 记录永久可追溯
- 📱 手机端: 打开文件 → 评论, 长按评论可回复/编辑/删除

🗂 文件版本历史
- 同一文件反复修改, 走「上传新版本」, 每一版自动留档
- 文件 ID / 分享链接 / 评论都不变, 只更新内容
- 随时下载旧版本, 或一键回滚 (中间版本不丢, 可再滚回来)
- 建议: 迭代中的论文/数据表都用版本历史, 别再传 "最终版v3(2)" 了 😄

📖 详细教程: 网盘帮助 → 《Drive v2 PR9 用户指南》
❓ 有问题群里说, 或直接问小气助手

注意: 大文件 (视频/大数据集) 每个版本都是完整副本, 请避免频繁传新版。
```

**通知发送检查**:

- [ ] 验证清单 (第 3 节) 全绿
- [ ] 用户指南 `docs/drive-v2-pr9-user-guide.md` 已可访问
- [ ] 通知已发课题组群
- [ ] 发布后 24h 内留意群反馈 + `docker compose logs` 错误率

## 6. 收尾

- [ ] 归档本 checklist 勾选结果 (截图或 commit 注记)
- [ ] memory 回填实际部署 commit hash + 遇到的问题
- [ ] ROADMAP.md / README.md 待做清单同步 PR9 完成状态
- [ ] PR10 遗留项登记: WebSocket 评论实时推送 / 版本内容 diff / 版本保留策略 / 共享盘 folder 维度版本

---

*文档: W68 路线 H-1 (2026-07-24)。配套: `docs/drive-v2-pr9-deployment.md` (命令级) + `docs/drive-v2-pr9-user-guide.md` (用户教程)。*
