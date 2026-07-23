# W68 Drive v2 PR9 部署验证脚本 (第 4 批 H-2) — 2026-07-24

> **锚点范式第 57 守恒** — 主指挥协调范式 W68 第 4 批跨主题派工, 第 2 子任务 (H-2).
> 路线 H 部署验证系列: H-1 (部署文档) → **H-2 (验证脚本)** → 后续 H-3+ (deploy-auto 集成).
> 0 production code 改动铁律维持 — 仅 scripts/ + memory + docs 三个文件.
> 交付物: `scripts/verify_drive_v2_pr9_deployment.sh` (380 行 bash) + `scripts/verify_drive_v2_pr9_deployment.md` (179 行 docs) + 本 memory (120 行).

---

## 1. 触发 + 范围

**触发**: W68 第 3 批 H-1 写了部署文档 (含手动 6 点 curl 验证清单), 但主指挥 SSH 部署完经常**漏跑某点 / 复制粘贴错**, 没法快速知道 endpoint 是否真可用. 需要一键自动跑.

**原痛点** (W67 grand closure 复盘):
- 主指挥手动 curl 6 个 endpoint + 1 alembic 验证 + 1 WS 探测, 8 步独立 shell 命令
- 任意一步漏跑 → 团队上线后才发现 endpoint 500 (Drive v2 PR8 F-3 移动端 UI 当时就出过 1 次, W68 第 1 批最后 1 个 Safari fix commit)
- 没彩色报告, 失败原因藏在 shell history, 排错慢

**新方案**: 1 个 bash 脚本一键跑 10 个验证点 + 彩色输出 (绿/红/黄/蓝) + 失败 fail-loud (exit 1) + 详细排错提示.

---

## 2. 脚本核心设计

### 2.1 10 个验证点 (覆盖 PR9 全部新能力)

| # | 类别 | 验证点 | 期望 |
|---|------|-------|------|
| 1 | 评论列表 | `GET /api/v1/drive/comments?file_id=N` | 200 + 标准分页结构 |
| 2 | 评论创建 | `POST /api/v1/drive/comments` | 201 + body 含 `id` 字段 |
| 3 | XOR 校验 | `POST /api/v1/drive/comments` (同传 file_id+folder_id) | 400 |
| 4 | 版本列表 | `GET /api/v1/drive/versions/files/{id}/versions` | 200 + 数组结构 |
| 5 | 版本下载 | `GET /api/v1/drive/versions/versions/{id}/download` | 200 或 404 |
| 6 | 无鉴权 | `GET /api/v1/drive/comments?file_id=1` (无 TOKEN) | 401 |
| 7 | WebSocket | `wss://.../api/v1/ws/notifications?token=...` | 101 Switching Protocols |
| 8 | alembic 落点 | `docker exec alembic current` | 063_drive_file_versions |
| 9-12 | 4 张表 | `psql \dt drive_*` | drive_comments / drive_file_versions / drive_folder_members / drive_folder_shares |

### 2.2 关键设计决策

| 决策 | 选项 | 取舍 |
|------|------|------|
| 退出语义 | 跑完所有点再汇总 vs 第一点失败即停 | **跑完再汇总** — 用户想一次看到全部问题, 不要排错 A 后才能发现 B 也有问题 |
| DRY_RUN | 总是真发 vs 支持 DRY | **支持 DRY=1** — 本地脚本调试 / CI smoke 不真发请求 |
| 颜色 | 总是彩色 vs 检测 tty | **检测 tty** — `tput colors 8+` 才上色, 兼容 Windows Git Bash / 重定向日志 |
| WS 探测 | 用 wscat vs curl | **curl Upgrade 探测** — 0 新依赖, curl 7.86+ 自带, 主指挥云 server 都满足 |
| TOKEN 缺失 | 报错退出 vs 跑 401 负例 | **跑 401 负例** — 即使没 token 也能跑无鉴权点, 主指挥部署中可早拿 token 早跑早知道 |
| 4 张表 docker exec | 直接 psql vs 通过 docker | **docker exec** — 主指挥云 server 没装 psql, 本地 PC docker 容器是唯一入口 |

### 2.3 兼容性纪律 (CLAUDE.md 752 行铁律升级版)

- **shopt -s nocasematch 2>/dev/null** — Git Bash 默认 casematch=on, 部分场景需要忽略大小写; 加 `|| true` 避免老 bash 不支持直接报错
- **tput 命令包 `2>/dev/null || echo ''`** — Windows 默认无 terminfo, tput 命令不存在; 用 fallback 字符串保留脚本继续
- **`|| echo "000"` 给 HTTP code fallback** — 网络断开 / DNS 失败时 curl exit 非零, 用 000 表示"未连接"
- **`mktemp 2>/dev/null || echo "/tmp/..."`** — Windows Git Bash mktemp 默认 `-t` 行为差异, 兜底到固定路径

---

## 3. 与既有系统的接口

### 3.1 复用 (0 重复代码)

| 既有工具 | 复用方式 |
|---------|---------|
| `curl` | 主验证手段 (端点 + 鉴权 + WS 探测) |
| `docker exec` | alembic 落点 + psql `\dt drive_*` |
| `bash -n` | 脚本语法静态检查 (commit 前必跑) |
| `jq -r .access_token` | 主指挥拿 JWT (docs §2.2 已写好命令, 脚本本身不解析 login) |

### 3.2 留接口 (未来 W68 第 5 批可接入)

| 接入点 | 留接口位置 |
|-------|-----------|
| `scripts/deploy-auto.sh` Step 2.5 | docs §6 已写示例代码 (deploy-auto 第 2 阶段后端 restart 后调本脚本, 失败 exit 1) |
| `scripts/check-dist-before-commit.sh` (pre-commit hook) | 不接入 — 本脚本是真发请求, 不能在 commit 阶段跑 (会污染 Drive 数据) |
| `web/tests/e2e/` Playwright | 不接入 — Playwright 跑浏览器 UI, 本脚本跑 API, 互补不重叠 |
| `.github/workflows/qa-bench.yml` | 不接入 — Drive PR9 是部署验证不是 CI gate, CI 跑 qa-bench 不跑 drive |

---

## 4. 部署验证脚本 4 条新铁律 (本任务沉淀)

**铁律 A: 部署验证脚本必须支持 DRY_RUN**
- 主指挥本地 PC 调试脚本时不应真发请求污染 Drive 数据 (会创建 `PR9 部署验证 @HH:MM:SS` 评论 100+ 条)
- `DRY_RUN=1` 一行切换, 不需改代码

**铁律 B: HTTP code 验证 + body 结构验证 双层**
- 单看 HTTP code 不够 — 返 200 但 body 是 HTML 错误页也算"通了" (nginx SPA fallback 教训)
- body 必须含业务字段 (`items` / `total` / `id` / 数组结构), 才算真 PASS

**铁律 C: WS 探测用 curl Upgrade 而不是 wscat**
- wscat 需要 npm 全局安装, 主指挥云 server 无 npm, 本地 PC 偶尔有版本冲突
- curl 7.86+ 自带 `Upgrade: websocket` 头, 0 依赖探测 101/401/403

**铁律 D: 验证脚本失败必须 exit 非零**
- 主指挥 deploy-auto.sh 加 `set -e`, 验证脚本返非零自动停部署
- 验证脚本本身返 0 但 echo "FAIL" = 失效, 必须严格 exit code

---

## 5. 教训 (下次部署新特性时复用)

1. **WS 端点路径必须看实际代码** — 任务描述说 `/ws/drive/notifications`, 实际 main 里是 `/api/v1/ws/notifications`. grep `app/api/v1/ws_notifications.py:127` 确认 `@router.websocket("/ws/notifications")` (前缀 `/api/v1` 来自 main.py include).
2. **alembic 解法 A 单链 vs 解法 B 双头** — 本脚本只检查 `063_drive_file_versions`, **必须**确认 PR 合并时已按 H-1 docs §0 改了 063 的 `down_revision = "062_drive_comments"`. 否则 `alembic upgrade head` 会报 multi-head 错, 整个脚本 FAIL.
3. **Windows Git Bash 的 mktemp 行为** — 默认 `-t` 模板不同, 必须 `mktemp 2>/dev/null || echo "/tmp/v_pr9_$$.tmp"` 兜底.
4. **DRY_RUN 模式 body 检查必须 SKIP** — 否则空 body 误判为"返 200 但 body 不是标准分页结构" → 假阳性 FAIL. 加 `if [ "$DRY_RUN" = "1" ]; then log_skip ...; fi` 分支.
5. **curl --max-time 15 必须加** — 默认无超时, 部署后 server hang 时脚本卡死, 主指挥以为验证通过.

---

## 6. 后续动作 (W68 第 4 批 H-3+)

- [ ] **H-3 (可选, W68 第 5 批)**: `scripts/deploy-auto.sh` Step 2.5 接入本脚本 (docs §6 示例代码已就绪)
- [ ] **H-4 (可选, 后续 W)**: CI smoke job 跑 `BASE_URL=http://app:8000 bash verify_*.sh` (无 TOKEN, 只跑 401 + docker exec 验证 — 但 CI 没 docker, 此项实际不可行, 留作占位)
- [ ] **H-5 (W69 跨主题)**: 类似 verify 脚本覆盖 PR8 4 个特性 (WS push / file lock / preview / mobile UI) — 复用本脚本骨架, 改 endpoint 路径即可

---

*本 memory 由 W68 第 4 批 H-2 Agent 自动沉淀. 锚点范式第 57 守恒累计: 跨 W51-W68 累计 100+ commit, 200+ 铁律, 5 deploy-* 脚本 + 1 verify-* 脚本. main HEAD 待主指挥 merge.*