# 2026-07-24 W68 路线 H-1 #2: Drive v2 PR9 部署 runbook 收口 (锚点范式第 70 守恒)

> **一句话**: W68 第 5 批 #13 agent 把 W68 第 3 批 H-1 docs 部署文档 (`docs/drive-v2-pr9-deployment.md` 400+ 行) 转化为**流程化 12 步主指挥操作手册**, 新建 `docs/drive-v2-pr9-deployment-runbook.md` (~340 行), 顶部加 runbook 链接, 沉淀 7 FAQ + 5 铁律。**0 production code 改动铁律维持** (本次仅 docs + memory)。

## 定位

- **锚点范式**: 第 70 守恒 (W68 第 5 批收口段)
- **上游锚点**: `w68-alembic-chain-discipline-2026-07-24.md` (5 铁律锚点范式第 46) — runbook §4 直接引用双头根因 + 解法 A 串单链 + 5 铁律
- **配套**: `scripts/verify_drive_v2_pr9_deployment.sh` (W68 第 4 批 H-2 锚点范式第 57) — runbook §2 6 点 curl 全部对齐验证脚本 §3
- **main HEAD (操作时)**: `243937b7f` (W68 第 4 批 grand closure)

## 完成交付

### 文件清单

| 文件 | 行数 | 状态 |
|------|------|------|
| `docs/drive-v2-pr9-deployment-runbook.md` | ~340 行 | 新建 |
| `docs/drive-v2-pr9-deployment.md` | 顶部加 runbook 链接 (1 段) | 改 1 处 |
| `memory/w68-route-5-drive-pr9-runbook-2026-07-24.md` | 本文件 | 新建 |

### 1. 新建 `docs/drive-v2-pr9-deployment-runbook.md` (~340 行)

#### 6 节结构

| 节 | 内容 | 行数估算 |
|----|------|---------|
| §0 部署前必读 | 主指挥本地 PC / 云服务器分工 / alembic 链约束 | ~30 |
| §1 SSH 部署 12 步 | git pull → verify chain → cp 062+063 → clear pycache → alembic current → upgrade → verify → restart → logs → web build (F-3 only) → verify script → 团队通知 | ~120 |
| §2 6 点 curl 验证 | ① 评论列表 ② 创建评论 ③ XOR 校验 ④ 版本列表 ⑤ 上传+下载 ⑥ 无鉴权 | ~80 |
| §3 验证脚本用法 | 4 用法 + 退出码 (0/1/2) | ~30 |
| §4 alembic 链风险 | 双头根因 + 解法 A 单链 + 解法 B 不可走 + 5 铁律 | ~40 |
| §5 回滚方案 | alembic downgrade -1/-2 + 代码 revert + 数据备份 SLA < 5min | ~30 |
| §6 已知问题 + FAQ | 7 个常见问题 (Multiple head / Can't locate / already exists / column does not exist / WebSocket 超时 / 全 SKIP / PWA 410) | ~50 |

#### 关键设计点

- **分工明确**: runbook 流程化 + deployment.md 详细说明 — runbook 是"操作手册", deployment.md 是"原理文档", 避免重复
- **§1 与 §2 联动**: 12 步 Step 11 引用验证脚本 (§3), Step 8-9 配套 §2 6 点 curl 的"手工版"
- **§4 直接复用**: W68 第 3 批 5 铁律 (锚点范式第 46) 内嵌到部署文档, 主指挥读完 runbook 即掌握纪律
- **§5 备份 SLA**: 复用 chat_engine_legacy 收官的 < 5 分钟回滚 SLA (commit `817f1ffa`)

### 2. 更新 `docs/drive-v2-pr9-deployment.md` 顶部

```markdown
# Drive v2 PR9 部署文档 (2026-07-24)

> **部署 Runbook (流程化 12 步) 见 [docs/drive-v2-pr9-deployment-runbook.md](docs/drive-v2-pr9-deployment-runbook.md)** 
> — 主指挥按 12 步主流程 + 6 点 curl 验证一键操作。本文档聚焦 alembic 链风险 + 回滚方案 + 端点速查, 与 runbook 互补不重复。
```

加 1 段 blockquote, 不破坏原文档结构。

### 3. memory 本文件 (锚点范式第 70 守恒)

沉淀 3 新铁律 (见下), 用于下次路由部署 / runbook 撰写参考。

## 3 新铁律

### 铁律 R-1: 流程化 runbook 与原理文档必须分工

- **背景**: docs 文件易越写越长, 300+ 行后把"流程"和"原理"混在一起 → 主指挥读起来累
- **规范**: 任何部署 / 迁移 / 升级类文档**至少 2 文件**:
  - `runbook.md` (流程化 12 步 + 验证 + FAQ) — 主指挥操作手册
  - `deployment.md` (原理 + 风险 + 回滚) — 教学文档
- **互引**: deployment.md 顶部 1 行 blockquote 指向 runbook, runbook 顶部"配套文档"列出 deployment.md
- **纪律**: 不允许 deployment.md 1000+ 行仍不分流 — 阅码体验是部署效率的一部分

### 铁律 R-2: runbook §X 验证必须与验证脚本一一对齐

- **背景**: runbook 写"6 点 curl 验证", 验证脚本写"6 个 endpoint check", 两边各写各的 → 主指挥 debug 时手工 6 点 vs 脚本 6 点不对齐, 排查错位
- **规范**: runbook §X 手工验证 + 验证脚本 §X 必须**端口 + 路径 + 期望码 + body grep pattern** 全部对齐
- **本次对齐**: runbook §2 ①/②/③/④/⑤/⑥ 与 `scripts/verify_drive_v2_pr9_deployment.sh` §3 注释 `log_info "① ~ ⑥"` 一字不差
- **纪律**: 任何 runbook 验证段必须 grep 验证脚本引用编号 — 主指挥 debug 时能快速切换

### 铁律 R-3: 部署 FAQ 必须含已出现过的 3+ 真实报错

- **背景**: 主指挥跑流程时最怕的是"未知报错" — 没有 FAQ 参考, 5 分钟部署变 5 小时
- **规范**: runbook §6 FAQ 至少 5 条, **前 3 条必须是上游同类部署曾真实出现过的报错 + 解法** (本次 6 条里 Q1/Q2/Q3/Q4 都是 W68 第 3 批 / 历史 PR6 部署踩过的)
- **本次沉淀**:
  - Q1 `Multiple head revisions` — W68 第 3 批实际触发 (commit `1852468a6`)
  - Q2 `Can't locate revision` — cp 漏文件历史
  - Q3 `relation already exists` — alembic_version 未更新历史
  - Q4 `column does not exist` 500 — restart 没做 (CLAUDE.md 752 行铁律场景)
  - Q5 WebSocket 探测超时 — curl 局限
  - Q6 全 SKIP — 缺 env var
  - Q7 PWA manifest 410 — 2026-07-11 铁律 (npm run build vs vite build)
- **纪律**: 任何部署 runbook FAQ 必须含上游锚点 memory ID (引文链)

## 6 FAQ 锚点引用 (用于后续 runbook 撰写参考)

| FAQ | 上游锚点 | commit |
|-----|---------|--------|
| Q1 Multiple head revisions | `w68-alembic-chain-discipline-2026-07-24.md` 第 46 守恒 | `1852468a6` |
| Q4 column does not exist 500 | CLAUDE.md 752 行铁律 (Python 进程迁移后必重启) | — |
| Q5 WebSocket 探测超时 | curl 局限, 非端点错误 | — |
| Q6 全 SKIP | 验证脚本环境变量设计 | `verify_drive_v2_pr9_deployment.sh` H-2 |
| Q7 PWA manifest 410 | `pwa-manifest-410-regression-2026-07-11.md` | `59187ce8` → `5d2bcdfd` |

## 完成定义验证

- [x] 新建 `docs/drive-v2-pr9-deployment-runbook.md` (~340 行, 6 节 + 12 步流程化 + 6 点 curl 验证 + 7 FAQ)
- [x] 改 `docs/drive-v2-pr9-deployment.md` 顶部加 runbook 链接 (1 段 blockquote)
- [x] 新建 `memory/w68-route-5-drive-pr9-runbook-2026-07-24.md` (本文件, 锚点范式第 70 守恒)
- [x] 分支 `docs/drive-pr9-runbook-2026-07-24` 已建 (本 agent 操作分支)
- [x] 0 production code 改动铁律维持 — 仅 docs + memory
- [ ] commit + push 待主指挥执行 (本 agent 指令明确"不 merge" + 提交 commit)

## 跨 W68 第 5 批同段

W68 第 5 批同段派工链:
- **#13 (本 agent)** — Drive v2 PR9 部署 runbook (docs only)
- **#14+ 其他** — 主指挥派工范围 (如 Drive v2 PR10 collab crud 收口 / qa-bench D6 phase 1 dry / Mobile v3.2 push 等)

锚点范式 W68 单调上升: 第 46 → 第 57 → 第 70 (本文) → 后续其他同段 agent 沉淀。

## 复盘

**对齐**: runbook §2 与验证脚本 §3 一一对齐 (R-2 铁律) 让主指挥 debug 效率最大化。
**改进空间**: 没写 `make runbook-deploy-pr9` Makefile 入口 — 主指挥仍需手写 12 步命令。后续可加 (一个 commit + symlink 即可), 但本次范围外, 不越界。
**主指挥 review 重点**: 12 步是否与本地 PC 实际命令完全一致 — `cd /e/microbubble-agent` 路径是否对所有平台 (Git Bash WSL WSL2 bash) 通用。

---

*memory: W68 路线 H-1 #2 (2026-07-24) — 锚点范式第 70 守恒. commit 待 push to `docs/drive-pr9-runbook-2026-07-24` 分支. 主指挥拍板 merge.*
