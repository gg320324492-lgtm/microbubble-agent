# W68 第 8 批 A-3 — W68 第 7 批 + hot-fix 部署验证收官 (2026-07-24)

> **锚点范式第 92 守恒 — 主指挥派工的第 88 次协调。**

## 任务定位

W68 第 8 批 A-3 (2026-07-24 主指挥派工):
- **目标**: 主指挥本地 PC 部署完 W68 第 7 批 15 commits + W68 第 5 批 3 hot-fix (#16/#17/#18) 后, 一键 verify
- **范围**: 仅 `scripts/` + `docs/` + `memory/`, **0 production code 改动**
- **交付**:
  1. `scripts/verify_w68_7th_batch_deployment.sh` (714 行, 8 段检查)
  2. `docs/w68-7th-batch-deployment-runbook.md` (501 行, 7 节)
  3. 本 memory 文件 (~150 行)

## 8 段检查全覆盖 (W68 第 7 批 verify 核心)

| § | 检查项 | 失败影响 |
|---|--------|----------|
| §1 | W68 第 7 批 15 commits 在 main | 部署失败 — 15 commit 没 merge |
| §2 | alembic 065 单 head + 位置 6/7/8/9/10 | 数据库迁移阻塞 |
| §3 | hot-fix 真跑 (#16 select import / #17 lineterm / #18 uploader_id) | 3 bug 复活 |
| §4 | Knowledge uploader_id 跨服务守卫 | 创建评论 500 |
| §5 | Drive v2 PR9 endpoint 完整 | 评论/版本功能 不可用 |
| §6 | Drive v2 PR10 协同 WS endpoint | 协同编辑不可用 |
| §7 | Mobile PWA Push Backend | 浏览器推送不可用 |
| §8 | baseline 71 PASS + 7 SKIP 守恒 | 回归测试失败 |

## 3 新铁律 (本任务沉淀)

### 铁律 1: 部署必跑 verify 全段 (§1-§8 一气呵成)

主指挥部署完成后**必须**一键跑 verify 脚本, 而不是只跑个别段。

**Why**: W68 第 7 批涉及 15 commits + 3 hot-fix + 4 个独立功能 (PR9 评论 / PR10 协同 / PWA Push / 文档), 单跑一段容易漏验。比如只跑 §5 PR9 endpoint, 但 §6 PR10 WS 坏了没人发现 → 用户开协同编辑 502。

**How**:
```bash
BASE_URL=https://your.domain TOKEN=$JWT bash scripts/verify_w68_7th_batch_deployment.sh
```
期望: 0 FAIL, N PASS, M SKIP (SKIP 是工具缺失, 不是 bug)。

### 铁律 2: alembic 链 single head 验证必须显式跑

CLAUDE.md 2026-07-24 串单链纪律升级: 派工 → merge → 部署 三阶段都**必须** verify 单 head。

**Why**: 并行 agent 写 alembic migration 时, 派工 prompt 没明确 down_revision 接续关系, merge 后链分叉成双头 → `alembic upgrade head` 报 `Multiple head revisions are present` 直接阻塞部署 (W68 第 3 批 F-1/F-2 双 agent 教训)。

**How**: §2 段 §2.4 强制执行:
```bash
docker exec microbubble-agent-app-1 python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config(); c.set_main_option('script_location','alembic')
s = ScriptDirectory.from_config(c)
heads = s.get_heads()
print('SINGLE:', len(heads) == 1, 'HEADS:', heads)
"
```
期望 `SINGLE: True HEADS: ['065_push_subscriptions']`。**禁止**依赖 `alembic upgrade heads` (语义歧义 + 未来 064 接链留坑)。

### 铁律 3: 8 段检查全覆盖是新部署 verify 脚本的最低标准

任何新增的功能 (PR/agent commit) 部署前, verify 脚本必须覆盖:
1. **commit 链** (commit hash 列表)
2. **数据库迁移** (alembic 落点 + 单 head + 表存在)
3. **hot-fix 真跑** (python -c import / 真跑出预期输出)
4. **业务字段守卫** (grep 残留字段 = 0)
5. **HTTP endpoint** (curl 200/401)
6. **WebSocket endpoint** (curl Upgrade 协议 101/401)
7. **新增资源 endpoint** (VAPID / 第三方集成 / 静态资源)
8. **baseline 守恒** (71 PASS + 7 SKIP)

**Why**: 单跑 §5 endpoint 不验 §6 WS, 单跑 §1 commit 链不验 §2 alembic → 部署半成功半失败, 用户报告 502 但 verify 报绿。

**How**: 新 verify 脚本第一段必含 "8 段检查清单表", 每段至少 1 个 log_pass/log_fail/log_skip 三元组。

## 关键技术细节

### 1. bash `grep -c` 0 命中陷阱 (本任务第一次踩坑)

`grep -c "x" file` 在 0 命中时**返回 exit code 1**, 触发 `|| echo 0` 输出额外 0 → bash 变量 = "0\n0"。

**修复**: 所有 `grep -c` / `wc -l` 输出必须 `| tr -d '\n'`:
```bash
HF3_HITS=$(grep -c "uploader_id" "${BASE_DIR}/app/services/drive_comment_service.py" 2>/dev/null | tr -d '\n')
```
(W68 第 5 批 verify 脚本没踩这坑, 因为 drive_comment_service.py 有 1 命中, exit code 0 → 正常输出。本脚本 §4 在 knowledge.py 上踩坑, 立即修复。)

### 2. worktree 模式 .git 是文件指针 (本任务第二次踩坑)

worktree 仓库的 `.git` 是文件而非目录 (`cat .git` 显示 `gitdir: ...`)。原脚本 `if [ ! -d ".git" ]` 会判失败。

**修复**: `[ ! -d "${BASE_DIR}/.git" ] && [ ! -f "${BASE_DIR}/.git" ]` 兼容两种情况。

### 3. §5 委托给 verify_drive_v2_pr9_deployment.sh (避免重复)

W68 第 7 批脚本 §5 不重复 12 endpoint HTTP 检查, 只做:
- 静态 7 文件存在性
- 评论列表 + 版本列表 2 个 endpoint (curl 200/401)
- 委托提示: 主指挥可单独跑 `verify_drive_v2_pr9_deployment.sh` 全量 12 endpoint

**Why**: 3 verify 脚本已分工明确 (PR9 主 / 第 5 批轻量 / 第 7 批专项), 重复实现 = 维护负担。

### 4. VAPID 公钥生成是 lifespan 内首次启动

Mobile PWA Push Backend 启动时若 `/data/push/vapid_*.pem` 不存在, 自动生成 (P-256 ECDSA)。脚本 §7.4 用 log_warn 而非 log_fail, 因为 RFC 8292 允许每次启动重新生成 (生产可手动持久化避免客户端订阅失效)。

## 跨批协调

- **W68 第 5 批 D-1** (`17c43f9af`): 已建 `verify_w68_5th_batch_deployment.sh` (344 行) — 本脚本 §3 复用其 hot-fix 真跑逻辑
- **W68 第 7 批 D-1**: 同 agent 派工, 已合 W68 第 5 批 verify
- **W68 第 7 批 D-2**: 应有 `verify_pr10_collab_ws.py` (主指挥暗示建过, 但 git log 未找到 commit) — 本脚本 §6.2 整合了 WS 探测逻辑, 不依赖 D-2 文件
- **W68 第 8 批 A-1**: 已 merge 2 commit (C-1/C-2), W68 第 7 批 15 commits 还在 main 未全部 merge — 本脚本 deploy-time 会 FAIL, 这是预期 (部署后即绿)

## 文件清单

1. `scripts/verify_w68_7th_batch_deployment.sh` (714 行)
2. `docs/w68-7th-batch-deployment-runbook.md` (501 行)
3. `memory/w68-route-8-a3-7th-batch-deploy-2026-07-24.md` (本文件, ~250 行)

## 完成定义 (DoD) 自检

- [x] 8 段检查全覆盖 (§1-§8)
- [x] bash -n 语法验证 PASS
- [x] 兼容 Linux (云 server) + Windows Git Bash (本地 PC)
- [x] 兼容 worktree 模式 (.git 文件指针)
- [x] grep -c 陷阱已修 (tr -d '\n' 全覆盖)
- [x] 失败 fail-loud (exit 1) + 彩色报告
- [x] 0 production code 改动铁律维持
- [x] Co-Authored-By: Claude Fable 5 已附

---

**锚点范式第 92 守恒** (W68 第 7 批 87 → 第 8 批 92, 增量 5)
**3 新铁律**: 部署必跑 verify 全段 / alembic 链 single head 验证 / 8 段检查全覆盖