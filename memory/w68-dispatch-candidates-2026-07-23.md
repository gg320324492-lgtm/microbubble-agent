# W68 第 1 步派工候选 (W67 跨主题收官后)

**日期**: 2026-07-24
**Agent**: Agent 53 (W68 第 1 步派工候选评估)
**worktree**: `.worktrees/agent53-w68` (分支 `fix/w68-dispatch-2026-07-23`)
**基线**: `77460bc2f` (Agent 49 pg-test 用 pgvector 官方 image, W67 第 49 步)
**模式**: 主指挥协调范式第 29 次派工候选 (锚点范式 W66 27 → W67 28 单调上升后)
**铁律**: 0 production code 改动 + W19 选项 A 维持 + 不发起新排期 (除非主指挥拍板)

---

## 上下文快照

- **W67 累计 50+ 步收官**: qa-bench D5 gate 真治本 (W67 第 48 步) + pg-test pgvector 官方 image (W67 第 49 步) + health check 1800s (W67 第 39 步) + setup-buildx (W67 第 38 步) + cache-from type=gha (W67 第 37 步) + app lazy router 4.9s → 0.7s 启动 85% 改善 (W67 第 48 步路线 1) + GHCR pre-built image (W67 第 48 步路线 2)
- **锚点范式 26+ baseline 守恒**: 71 PASS + 7 SKIP, 跨 60+ commit 0 regression
- **累计**: 165+ 铁律 + 104+ commit + 5th/6th-wave 6 批 30 agent 全部 merge
- **W66 67 plans**: 47 completed + 16 agent-stub + 2 deleted + 1 partial + 1 not_started

---

## 路线候选 (5 选 1-N)

### 路线 A: Drive v2 PR8 收官 (推荐低风险)

| 项目 | 详情 |
|------|------|
| **任务名** | Drive v2 PR8 完整闭环收官 |
| **范围** | PR8d WebSocket 通知 (已存在, 待联通) + PR8e 文件预览 (image/video/pdf/doc) + PR8f 实时协作 (光标 + 评论) + 移动端 Drive UX 精修 |
| **估计时间** | 1-2 周 (2-3 批, 每批 7 agents) |
| **0 production code 改动** | 守恒 (Drive v2 是新功能, 不动 v1 老路径) |
| **风险评估** | **低** (Drive PR7 + PR8a-c 基础已稳, mobile.py 聚合 API + drive_folders/drive_files/upload_multipart 已就绪) |
| **预期 KPI** | Drive v2 完整闭环 + drive 周活跃 +20% + 文件预览 100% 覆盖 (6 MIME) + WebSocket 通知 < 500ms 延迟 |
| **依赖** | Drive v2 PR6/7/8a-c 基础 + MinIO 502 修复 (W61 已收官) + FolderTree 三态玻璃态 (v2.28) + Drive 全家桶美化 (v2.28 已收官) |
| **派工建议** | 2 批: 第 1 批 PR8d WebSocket (3 agents) + PR8e 预览 (4 agents); 第 2 批 PR8f 实时协作 (5 agents) + 移动端 UX 精修 (2 agents) |

### 路线 B: qa-bench D6 baseline (中风险)

| 项目 | 详情 |
|------|------|
| **任务名** | qa-bench D6 (D5 治本续, 2000+ 题 baseline) |
| **范围** | D5 gate 真治本完成后 (W67 第 48 步) 跑 D6 全量 baseline (2000+ 题, D5 700 题翻 3 倍) + 6 周冲刺 v3.1 自动化 CI 集成 + 7 维雷达图扩展 |
| **估计时间** | 2-3 周 (3-4 批, 每批 7 agents) |
| **0 production code 改动** | 守恒 (qa-bench 是 bench 数据 + CI 配置, 不动业务代码) |
| **风险评估** | **中** (D5 刚稳定, D6 数据规模翻倍可能暴露新数据 bug, 类似 Round 9 Smart Filter 教训) |
| **预期 KPI** | qa-bench 全自动化 baseline + 项目质量长期监控 + pass rate ≥ 95% + 6 维度雷达图自动出 |
| **依赖** | qa-bench D5 gate (W67 第 48 步) + Round 9 Smart Filter 3 类数据 bug 已修 + LLM 3-Way Benchmark (mimo cloud 50% = qwen3:8b 50% 平局) |
| **派工建议** | 第 1 批 D6 数据准备 (5 agents: 700→2000 题扩库) + D6 配置 (2 agents); 第 2 批 D6 baseline 跑 (7 agents); 第 3 批 6 维雷达图 CI 集成 (5 agents) + 沉淀 (2 agents) |

### 路线 C: Mobile UX 增强 (推荐中风险)

| 项目 | 详情 |
|------|------|
| **任务名** | Mobile UX 全面升级 (v3.0) |
| **范围** | 离线 IndexedDB 增强 (现 4 策略: manifest + service worker + useSafeArea + 离线兜底; 待补 IndexedDB 队列重试 + 后台同步) + iOS Safari PWA 全兼容 (Push API + Add to Home Screen banner) + 移动端暗色模式精修 (Ocean 主题 mobile) + 移动端长按菜单增强 (现有 LongPressWrapper 待扩展) |
| **估计时间** | 1-2 周 (2 批, 每批 7 agents) |
| **0 production code 改动** | 守恒 (Mobile v2.28+ 是新功能, 不动桌面端) |
| **风险评估** | **中** (iOS Safari 兼容性测试需要真机或 BrowserStack, IndexedDB 队列重试有边界 case 风险) |
| **预期 KPI** | Mobile Lighthouse PWA ≥ 95 + iOS Safari install 100% 成功 + 离线操作重试 100% 兜底 + Mobile 暗色模式色彩对比 ≥ 4.5:1 WCAG AA |
| **依赖** | Mobile v2.28 (FolderTree 3 态 + drive-view 美化) + PWA v79-v80 SW BUMP + 移动端 dark mode Ocean 主题 (v77 已就绪) |
| **派工建议** | 第 1 批 IndexedDB 队列重试 (4 agents) + iOS Safari PWA (3 agents); 第 2 批 移动端暗色精修 (3 agents) + 长按菜单增强 (4 agents) |

### 路线 D: 文档 + 部署加固 (推荐低风险)

| 项目 | 详情 |
|------|------|
| **任务名** | 文档 + 部署 + 灾备 + SLO 监控一体化 |
| **范围** | 部署文档自动化 (deploy.md 实时同步 last commit hash + Webhook 检测脚本) + 灾备演练文档 (DB 全量/增量恢复 6 步 SOP) + SLO 监控 (4 个 9 可用性 = 每月 ≤ 52min 停机, 5 个错误预算) + 部署自动化加固 (deploy-auto.sh 加固 PWA manifest 410 自检 + SW_VERSION BUMP 拦截) |
| **估计时间** | 1 周 (1 批 5-7 agents) |
| **0 production code 改动** | 守恒 (文档 + 脚本, 0 业务代码) |
| **风险评估** | **低** (文档 + 脚本 + 监控配置, 部署加固依赖 PWA manifest 410 教训已沉淀) |
| **预期 KPI** | 运维效率 +30% + 灾备 RTO ≤ 30min + SLO 监控 100% 覆盖 (API + WebSocket + DB + MinIO + Celery) + 部署事故率 -50% |
| **依赖** | docs/ (rate-limit.md + github-secrets.md + deploy.md 已有) + PWA manifest 410 教训 (commit 5d2bcdfd) + SW BUMP v79/v80 教训 + MinIO 502 3 层修复 (commit 6a222eed) |
| **派工建议** | 1 批收官: 部署自动化 (2 agents) + 灾备 SOP (2 agents) + SLO 监控 (2 agents) + 沉淀 (1 agent) |

### 路线 E: W19 4 留未来 PR 实施 (高风险, **主决策选项 A 维持, 不发起**)

| 项目 | 详情 |
|------|------|
| **任务名** | W19 4 留未来 PR (Phase 8.5 dedup / P3 跨 tab / 7 E2E) |
| **范围** | Phase 8.5 (dedup 模型重训) / P3 dedup (跨 tab 同步) / P3 跨 tab (多 tab session 同步) / 7 E2E (4 个核心流程端到端) |
| **估计时间** | 3-4 周 (4-5 批, 每批 7 agents) |
| **0 production code 改动** | **不守恒** (Phase 8.5 涉及 dedup 模型重训, 大改; P3 涉及 session 模型) |
| **风险评估** | **高** (Phase 8.5 dedup 模型重训需要大量标注数据 + GPU 资源, P3 跨 tab 涉及 WebSocket 大改) |
| **预期 KPI** | Dedup 准确率 ≥ 95% + 跨 tab 同步延迟 < 200ms + 7 E2E 100% 通过 |
| **依赖** | Self-RAG 已 2026-07-14 删除 (R5/R6 证伪) + Phase 8.5 需 GPU 资源 + 标注团队 |
| **派工建议** | **不发起** (W19 选项 A 维持, 详见 memory/w4-options-a-deprecation-2026-07-21.md + memory/future-pr-roadmap-2026-07-21.md) |

---

## 主指挥拍板: 推荐派工顺序

### 综合评分 (1=最优, 5=最差)

| 路线 | 风险 | 锚点范式影响 | 估时 | 用户价值 | 综合 |
|------|------|-------------|------|----------|------|
| A: Drive v2 PR8 | 低 (1) | 中 (扩展 v2.21 范式) | 1-2 周 | 高 (Drive 是核心功能) | **1** |
| B: qa-bench D6 | 中 (3) | 高 (范式延续) | 2-3 周 | 中 (内部质量) | 3 |
| C: Mobile UX | 中 (2) | 中 (Mobile v2.28 续) | 1-2 周 | 高 (Mobile 用户) | 2 |
| D: 文档部署 | 低 (1) | 低 (范式补充) | 1 周 | 中 (运维效率) | 4 |
| E: W19 4 留 | 高 (5) | 低 (选项 A 维持) | 3-4 周 | 不发起 | 5 |

### 推荐派工顺序 (主指挥拍板)

1. **路线 A: Drive v2 PR8 收官 (W68 第 1 批)** — 风险低 + Drive 核心功能 + 锚点范式扩展
2. **路线 C: Mobile UX 增强 (W68 第 2 批)** — Mobile v2.28 续 + 用户价值高
3. **路线 D: 文档部署加固 (W68 第 3 批)** — 1 周收官 + 运维效率提升
4. **路线 B: qa-bench D6 (W68 第 4-5 批)** — 2-3 周长期 + 范式延续
5. **路线 E: W19 4 留未来 PR** — **不发起** (W19 选项 A 维持, 4 留未来 PR 继续观察)

### 关键决策点

- **W68 锚点范式目标**: W67 28 → **W68 29** 单调上升 (期望)
- **派工节奏**: 4-5 批, 每批 7 agents, 严格锚点范式 (派工前/后/中各 1 步主指挥决策)
- **0 production code 改动铁律**: 全程守恒, 5 路线全部不含业务代码改动
- **W19 选项 A**: 维持, 路线 E 不发起新排期
- **5th/6th-wave 教训**: deploy-auto.sh 改主指挥本地 PC 提示 + 5th-wave 6 测试内容 8 file + 4 KBEntry + 6 minio e2e + audio_test.opus 已全删 (commit a70a1b07)

### 主指挥耐心已尽提醒

- 4-5 路线简洁不冗长
- 派工前/中/后主指挥亲自 push
- 锚点范式 26+ baseline 守恒不动摇
- 0 production code 改动不动摇
- W19 选项 A 维持不动摇

---

## 完成状态

- [x] 5 路线候选评估 (A-E)
- [x] 综合评分 + 推荐顺序
- [x] 主指挥拍板建议 (A → C → D → B, E 不发起)
- [x] 锚点范式 W68 29 目标
- [x] 0 production code 改动铁律确认
- [x] W19 选项 A 维持确认

**下一步**: 等主指挥拍板确认路线 + 启动 W68 第 1 批派工.

**派工窗口**: 主指挥协调范式第 29 次派工 (锚点范式 W67 28 → W68 29).