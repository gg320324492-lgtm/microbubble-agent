# MicroBubble Agent - 路线图

> **本文件是项目未来规划 + 近期完成的高层摘要。**
> 详细 commit 流水账在 [HISTORY.md](HISTORY.md)（已存档 5730 行），权威变更日志在 [CHANGELOG.md](CHANGELOG.md)。

## 当前状态（2026-06-27）

**已交付**：
- 🆕 **会议 153 ASR 谐音/错识全链路清洗 hook** — `name_aliases` 扩容 7 条会议 153 真实误识 + `post_meeting_tasks` hook 推到主路径，所有未来会议自动清洗（[memory/name-aliases-phonetic-correction-2026-06-27.md](memory/name-aliases-phonetic-correction-2026-06-27.md)）
- ✅ v1-v6 完整后端架构（Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery + MinIO）
- ✅ v2/v3/v4 Agent 架构（34 个 `@tool` 装饰器工具 + 12 类 Rich Block + 多会话并行 + agent_traces 可观测性）
- ✅ 知识库 V1 + V2（动态 LLM 分析 + 知识图谱 + RAG 问答 + 自主研究引擎 + 公式分类 + 假设生成）
- ✅ 知识库 V3（多模态 OCR：图片 + 公式 + 表格 + 图表识别入库，10/10 PDF 端到端通过）
- ✅ 会议系统 v1-v4（录音机 + 离线后处理 + ASR + 声纹 + AI 摘要 + 三级润色 + **v70~v73 视觉迭代**）
- ✅ 声纹识别 v2（3D-Speaker + pgvector + HNSW 索引 + **修复 ERes2Net batch bug** 100% 段有效）
- ✅ 会议发言人重处理流程（[reprocess_meeting.py](scripts/reprocess_meeting.py) 9 步 CLI + 主机端 wrapper）
- ✅ 移动端 PWA 收官（18 个移动端页面 + 12 个移动端组件 + 路由级双栈 + 4 个 PWA 离线策略）
- ✅ v2 任务提醒体系（11AM 窗口 + acknowledged 状态 + Redis 24h 去重）
- ✅ **v28 智能论文阅读器**（8 phases + step 109.x 打磨：4 篇 PDF 37 张图 100% 核心不变量 + 12 列结构化字段 + 内嵌图 confidence 阈值 + IO Hysteresis 防跳变）
- ✅ **v29 Qwen3 全量迁移**（GPU 启用 + Qwen3 wrapper + 双模型 dispatch + alembic 030 + 知识库 350/351 条重算 + 列原子切换）
- ✅ **sentence-transformers 5.6.0 升级**（跨 3 大版本，0 breaking，删 170 行 wrapper，Qwen3 max_seq_length 4x → 32K，qa-bench 38%→42%）
- ✅ **v31 检索质量监控埋点**（3 endpoint + 5 指标 dashboard + per-user 维度 + qa-bench 360 题）
- ✅ **v31.2.x rate-limit 基建收尾**（XFF 空 IP 兜底 + analytics regex + user_id 维度 + X-RateLimit-Policy 头 + SSE tier + Redis ZSET 持久化）
- ✅ **v31.3 Whisper 常驻 GPU 8GB + bind mount**（聊天 ASR 时效性优先，源码 bind mount 免 `docker cp`）
- ✅ **v68 桌面主题切换 + SettingsView 玻璃态**
- ✅ **v69 P0+P1 dark mode 全面重构**（3 阶段：基础 5 token + 14 EP 覆盖；6 套主题切换；10 桌面视图 dark 适配）
- ✅ **v70 P0~P3 字面色 token 化 + 会议纪要 TL;DR + Stylelint 字面色禁用**
- ✅ **v71 P1 议程 timeline + 每 speaker 8 条常驻**
- ✅ **v72 P1 摘要+重点摘要合并主题色卡**
- ✅ **v74/v75/v76 测试基建**（CSS variable 6 主题组合自动化 + 9 个旧 fail 修复 + 视觉回归 5 件套）
- ✅ **pre-commit hook auto-add web/dist/**（CLAUDE.md 教训第 4 次沉淀后兜底）

**统计**（[app/stats.json](app/stats.json), 2026-06-27 自动重算）：
- **1434 commits / 286K 行代码 / 804 文件 / 43 开发天数**
- 9 个 Docker 服务运行中
- 87 后端 + 73 前端 + 17 移动端 + 8 ST 集成 + 11 visual-regression = 196+ 测试
- 知识库 64→247+ 条（+183，Phase 7 后再扩展多模态抽取）
- **2026-06-24~27 起 12+ 铁律沉淀**（清华源/ONNX 反优化/docker build 污染/pre-commit hook/dist 漏 commit/Stylelint 等，详见 [CLAUDE.md](CLAUDE.md) 末尾）

**最新里程碑**：
- 🆕 [会议 153 ASR 谐音/错识全链路清洗 hook](CHANGELOG.md#2026-06-27-会议-153-asr-谐音错识全链路清洗-hookname_aliases-推到主路径) - name_aliases 推到主路径 + 7 条防御性映射
- 🆕 [v76.2 视觉回归测试 5 件套收官](CHANGELOG.md#2026-06-27-v762-视觉回归测试-5-件套收官) - Playwright baseline + CI hard fail
- 🆕 [v72 P1 摘要+重点摘要合并主题色卡](CHANGELOG.md#2026-06-27-v72-p1-会议纪要-摘要-重点摘要-合并) - color-mix + var(--color-primary)
- 🆕 [v71 P1 议程 timeline + 每 speaker 8 条常驻](CHANGELOG.md#2026-06-27-v71-p1-议程-timeline--每-speaker-8-条常驻)
- 🆕 [v70 P0~P3 字面色 → token + TL;DR 卡](CHANGELOG.md#2026-06-27-v70-p0~p3-字面色-token-化--会议纪要-tldr) - 4 个 phase
- 🆕 [v69 P0+P1 dark mode 全面重构](CHANGELOG.md#2026-06-27-v69-桌面端-dark-mode-全面重构3-阶段) - 3 阶段收官
- 🆕 [v68 桌面主题切换按钮 + SettingsView 玻璃态](CHANGELOG.md#2026-06-27-v68-桌面主题切换按钮--settingsview-玻璃态)
- 🆕 [v31.3 Whisper 常驻 + 推理加速](CHANGELOG.md#2026-06-26-v31-3-whisper-常驻--推理加速用户决策chat-asr-时效性优先) - 模型常驻 GPU 8GB
- 🆕 [v31.2.5 rate-limit Redis ZSET 持久化](CHANGELOG.md#2026-06-26-v31-2-5-rate-limit-收官启用-redis-zset-持久化) - 抗 docker restart

## 🆕 待做：产品扩展（商业化 + 多组织 + 桌面 + APP）

> **2026-06-28 决策沉淀**：在 Phase 7~20 现有高优/中优/低优路线图基础上，新增产品级扩展方向。完整规划见 [docs/product-expansion-plan.md](docs/product-expansion-plan.md)（待补充）+ plan 文件 [C:\Users\pc\.claude\plans\exe-logical-pie.md](C:/Users/pc/.claude/plans/exe-logical-pie.md)。
>
> **核心战略**：1 个前置 P0（40 人天，单租户内打地基）+ 6 个 Phase（24 人月 / 18 月工期）。从"内部 Web 工具"→"多组织 SaaS + 桌面 + 三端 APP"。

### 前置 P0（必须先完成，否则后期改造 10 倍成本）[40 人天]

- [ ] **#PRE-001** [5d][infra][P0] 24 张表加 `organization_id` 占位列（NULL 允许）+ GIN 索引 — **多租户改造前置占位**
- [ ] **#PRE-002** [8d][auth][P0] OAuth provider 抽象层 + JWT refresh rotation 框架
- [ ] **#PRE-003** [5d][infra][P0] PG 备份 + 监控 + 慢查询日志（pg_stat_statements + P95 < 200ms 告警）
- [ ] **#PRE-004** [4d][frontend][P0] 前端 API 层加 `X-Organization-ID` header 透传 + Pinia store 改造
- [ ] **#PRE-005** [6d][infra][P0] 审计日志中间件（写操作 + 登录 + 切换组织 + 异步队列 + 归档）
- [ ] **#PRE-006** [4d][infra][P0] 限流扩展到组织维度（5 tier → 组织 × 用户双维度）
- [ ] **#PRE-007** [5d][backend][P0] Celery 任务加 `organization_id` 上下文传递（`task_context` 装饰器）
- [ ] **#PRE-008** [3d][infra][P0] 部署架构文档化（Docker Compose 9 服务拆分到 K8s / 阿里云 ACK）
- [ ] **#PRE-009** [30-60d][legal][P0] **软著申请（中国版权中心，不可压缩 30-60 天，今天就启动）**
- [ ] **#PRE-010** [5d][legal][P0] 法务合规检查（个保法 + 数据安全法 + 用户协议 + 隐私协议 + 科研数据出境评估）

### Phase 0：正式数据库 [3 人月]

- [ ] **#P0-001** RDS PostgreSQL 16 HA 主从迁移（阿里云，自动备份 7 天 + PITR）
- [ ] **#P0-002** pgvector HNSW 索引重建（数据量 > 1000 万时 HNSW 优势明显）
- [ ] **#P0-003** Prometheus + Grafana + AlertManager（CPU / 内存 / 连接数 / 副本延迟）
- [ ] **#P0-004** Loki + Promtail 日志聚合（替代 SSH 看日志）
- [ ] **#P0-005** Sentry 前后端错误聚合
- [ ] **#P0-006** 9 个 Docker 服务拆分到 K8s namespace
- [ ] **#P0-007** 阿里云 OSS 冷数据归档（90 天后转归档存储）
- [ ] **#P0-008** 灾备演练：RPO < 5 分钟，RTO < 30 分钟

### Phase 1：认证扩展 [3 人月]

- [ ] **#P1-001** OAuth provider 抽象层（`app/services/auth/providers/base.py`）
- [ ] **#P1-002** 阿里云短信 SDK（手机号验证码，5 分钟 TTL，防刷 1 分钟 1 次）
- [ ] **#P1-003** 微信开放平台网站应用（PC 扫码登录，14 步标准流程）
- [ ] **#P1-004** 微信开放平台移动应用（独立 appid，资质认证 600 元/年）
- [ ] **#P1-005** JWT refresh token rotation（24h access + 30d refresh，单次使用）
- [ ] **#P1-006** 双因子认证（组织维度配置，可开关）
- [ ] **#P1-007** 设备指纹 + 异地登录告警
- [ ] **#P1-008** 密码强度策略升级（zxcvbn 评分）
- [ ] **#P1-009** 第三方登录首次绑定手机号流程

### Phase 2：多组织 SaaS [6 人月] ⚠️ **最高优先级**

- [ ] **#P2-001** `organizations` + `org_members` + `org_invitations` 表
- [ ] **#P2-002** PostgreSQL Row Level Security（RLS）策略，24 张表全加
- [ ] **#P2-003** `OrganizationMixin` + SQLAlchemy event listener（自动注入 WHERE）
- [ ] **#P2-004** API 层 `Depends(get_current_org)` 强制校验
- [ ] **#P2-005** 子域名路由（`{org_slug}.agent.example.com` + Let's Encrypt 通配 HTTPS 证书）
- [ ] **#P2-006** 组织切换器（Web 顶栏 + 移动端 + 桌面托盘菜单）
- [ ] **#P2-007** 创建 / 加入 / 邀请组织流程（链接 / 二维码 / 邮件，72 小时过期）
- [ ] **#P2-008** 三级 RBAC（组织管理员 / 普通成员 / 访客）
- [ ] **#P2-009** 组织级配额（成员数 / 存储 / API 调用 / GPU 分钟数）
- [ ] **#P2-010** 数据迁移脚本（现有 20 人数据合并到默认"原始课题组"组织）
- [ ] **#P2-011** 灰度方案（先 1 个外部组织白名单，全量后 30 天清理）

**3 层数据隔离防御**：API 层（`Depends(get_current_org)`）+ ORM 层（`OrganizationMixin`）+ DB 层（PG RLS 兜底）

### Phase 3：桌面 EXE [4 人月]

- [ ] **#P3-001** Electron MVP（Windows + macOS + Linux）
- [ ] **#P3-002** Tauri 并行试点（验证可行性，3 月后决策）
- [ ] **#P3-003** 自动更新（Electron Updater / Tauri updater）
- [ ] **#P3-004** 系统托盘 + 全局快捷键（Ctrl+Shift+A 唤起搜索）
- [ ] **#P3-005** 离线缓存（IndexedDB + Service Worker）+ 增量同步
- [ ] **#P3-006** Windows EV 代码签名（DigiCert ¥4000/年）
- [ ] **#P3-007** macOS Developer ID 签名 + Notarization 公证
- [ ] **#P3-008** Linux AppImage / deb / rpm 三格式打包
- [ ] **#P3-009** 协议注册（agent:// scheme）+ 文件关联（.pdf / .docx 拖入）

### Phase 4：移动 APP [6 人月] ⚠️ **最大工程量**

- [ ] **#P4-001** Flutter 3.24+ 框架定型（Dart 3.5）
- [ ] **#P4-002** 业务逻辑 TypeScript → Dart 移植（或 WebView 容器嵌入 H5 保守方案）
- [ ] **#P4-003** 微信开放平台移动应用 appid（独立申请）
- [ ] **#P4-004** 极光推送 JPush（多厂商通道：华为 / 小米 / OPPO / vivo / 魅族 / iOS APNs）
- [ ] **#P4-005** iOS TestFlight 内测（90 天有效期）
- [ ] **#P4-006** App Store 上架（首次 2-4 周审核，避免 4.7/4.2 拒绝）
- [ ] **#P4-007** Android 华为应用市场上架（最严，软著必填）
- [ ] **#P4-008** Android 小米 / OPPO / vivo / 应用宝多商店上架
- [ ] **#P4-009** 鸿蒙 NEXT 适配（Flutter 鸿蒙版 alpha 或原生 ArkTS 重写，预留 ¥30-50 万）
- [ ] **#P4-010** ICP 备案 + 公安备案（7-15 工作日）
- [ ] **#P4-011** 移动端专属（摄像头扫码 / 生物识别 / 后台保活）
- [ ] **#P4-012** 离线缓存（SQLite / Hive）+ 增量同步

### Phase 5：商业化 [2 人月]

- [ ] **#P5-001** 订阅模型 3 档（基础版 ¥299/月/20人 / 专业版 ¥999/月/50人 / 企业版 ¥9999/月/200人，学校 8 折）
- [ ] **#P5-002** 微信支付 V3 集成
- [ ] **#P5-003** 支付宝 APP 支付集成
- [ ] **#P5-004** 14 天免费试用流程
- [ ] **#P5-005** 续费 / 降级 / 退款流程
- [ ] **#P5-006** 发票系统（电子发票 + 增值税专票申请）
- [ ] **#P5-007** 学校 / 院系返点接口（10-20%）
- [ ] **#P5-008** 价格表页 + 商务对接入口
- [ ] **#P5-009** 销售漏斗 UTM 追踪 + 转化看板

### 关键决策（2026-06-28 拍板）

| # | 决策 | 拍板方案 |
|---|------|----------|
| 1 | 多租户数据库 | ✅ 阿里云 RDS PostgreSQL HA（省心优先） |
| 2 | 桌面框架 | ✅ Electron MVP + Tauri 并行试点（3 月后决策） |
| 3 | 移动框架 | ✅ Flutter 3.24+（性能 + 跨端） |
| 4 | 鸿蒙策略 | ✅ 预留 ¥30-50 万原生重写预算 |
| 5 | 商业化时间窗 | ✅ 边做边邀请（6 月起白名单） |
| 6 | 数据合规 | ✅ 承诺"数据不出境"，用户协议明示 |
| 7 | 付费模型 | ✅ 混合模式（基础版按组织，专业版按成员数），学校 8 折 |
| 8 | 招人 vs 外包 | ✅ 1 名 Flutter 全职 + 鸿蒙必要时外包 |

### 关键风险

| ID | 风险 | 等级 | 缓解 |
|----|------|------|------|
| RISK-01 | 鸿蒙 NEXT 2026-10 强制下架 Android APK，三方适配成本不可预估 | 高 | ¥30-50 万原生预算 + 1-2 人常驻 |
| RISK-02 | PG RLS 性能损耗 5-15% | 中 | 预读 + Redis 缓存 + 慢查询监控 |
| RISK-03 | 多租户改造后期成本是前期 10 倍 | 高 | **强制 PRE-001 占位列** |
| RISK-04 | 软著申请 30-60 天 | 高 | **今天就启动**（PRE-009） |
| RISK-05 | 微信网站应用与移动应用 appid 不互通 | 中 | 同时申请两个 appid |
| RISK-06 | macOS Notarization 公证被拒 | 中 | electron-builder 默认配置 + 测试机预审 |
| RISK-07 | 科研数据涉及人类遗传资源 / 数据出境 | 高 | 限定境内服务器 + 法务预审 |
| RISK-08 | App Store 4.7 / 4.2 拒绝，延期 2-4 周 | 中 | 提前对照审核指南 + 多次 TestFlight |
| RISK-09 | Electron 内存占用 200-400MB | 中 | Tauri 试点（5-10MB） |
| RISK-10 | 微信支付 V3 + 商户号审核 7-15 工作日 | 中 | 提前 30 天准备 |
| RISK-11 | 20 人历史数据迁移跨用户引用断裂 | 中 | 引用图分析 + 2 周 buffer |
| RISK-12 | Celery ORM 与 RLS 兼容 | 中 | `task_context` 装饰器统一 |

### 里程碑 KPI

- **6 月**：1-2 个外部课题组试用 + 软著到手 + 多组织 MVP
- **12 月**：5-10 个课题组付费 + 月活 100-300 + 桌面三平台 + iOS/Android 上线
- **18 月**：20+ 课题组 + 月活 500-1000 + 鸿蒙 + 微信小程序 + 盈亏平衡倒计时
- **24 月**：50+ 课题组 + 月活 2000+ + 双端占比 > 60% + ARR > ¥200 万

### 团队配置

- **短期 6 月**：前端 2 + 后端 2 + 移动 1 + 运维 0.5 + PM 0.5 = **6 人**
- **长期 12 月**：前端 3 + 后端 3 + 移动 2 + 运维 1 + 测试 1 + PM 1 + 运营 0.5 = **11.5 人**
- **招人顺序**：移动 Flutter（最稀缺 40-60K/月）→ 后端 RLS 专家 → 鸿蒙原生 → K8s 运维 → 科研背景 PM

### 立即启动项（本周内）

- ✅ **今天启动软著申请**（PRE-009，30-60 天不可压缩）
- ✅ **本周启动 PRE-001**（24 张表加 `organization_id` 占位列 + alembic 035 migration）
- ✅ **本月完成 PRE-002**（OAuth provider 抽象层）
- ✅ **本月启动 Phase 0**（RDS PostgreSQL HA 迁移）

---

## 未来规划（从浅入深路线图）

### 🔴 高优先级（核心能力扩展）

| Phase | 目标 | 周期 | 状态 |
|-------|------|------|------|
| **Phase 7** | 多模态知识库（图片/公式/表格识别入库） | 4-6 周 | 待启动 |
| **Phase 8** | 科研数据自动备份（DB + 文件定时备份 + 异地容灾） | 2-3 周 | 待启动 |
| **Phase 11** | 智能实验记录本（结构化记录 + 模板 + 搜索 + 版本控制） | 4-6 周 | 待启动 |
| **Phase 12** | 科研协作工作流（任务分配 + 进度追踪 + 评审流程 + 通知提醒） | 4-6 周 | 待启动 |
| **Phase 16** | 深度论文理解（解析 + 关键信息提取 + 对比分析 + 趋势发现） | 4-6 周 | 待启动 |

### 🟡 中优先级（AI 能力深化）

| Phase | 目标 | 周期 |
|-------|------|------|
| **Phase 9** | 课题组知识图谱可视化（实体关系网络 + 交互式探索 + 路径发现） | 3-4 周 |
| **Phase 10** | 实时语音科研助手（语音对话 + 实时转录 + AI 问答 + 多语言） | 6-8 周 |
| **Phase 13** | 自动化文献综述（文献检索 + 摘要 + 引用管理 + 综述草稿） | 6-8 周 |
| **Phase 14** | 智能实验方案生成（基于知识库 + 参数推荐 + 风险评估） | 6-8 周 |
| **Phase 15** | 实验数据分析平台（数据导入 + 统计分析 + 可视化 + 报告） | 6-8 周 |
| **Phase 17** | AI 辅助论文写作（大纲 + 内容建议 + 格式检查 + 查重） | 6-8 周 |
| **Phase 20** | AI 科研助手移动端（移动 App + 语音交互 + 离线 + 推送） | 6-8 周 |

### 🟢 低优先级（远期愿景）

| Phase | 目标 | 周期 |
|-------|------|------|
| **Phase 18** | 智能实验设备管理（设备预约 + 使用记录 + 维护提醒） | 4-6 周 |
| **Phase 19** | 课题组专属 AI 研究员（自主研究 + 假设验证 + 论文草稿 + 实验设计） | 8-12 周 |

## 近期完成（按主题）

### 🛠 2026-06-19 全量审计 + CardList 修复 + 开始听会配置

- 5 处 P0 必修（ChatViewSSE `window.open` 运行时错误 / KnowledgeHealth 整页 / ProjectView 编辑 TODO / 移动端 3 处"开发中" / 移动端 2 处误导注释）
- 9 处 P1 死代码清理（4 处死 ref 复活 / ChatView 整文件删 / 6 个孤儿 view 删 / 4 个孤儿 composable 删 / 5 个死 helper 删 / 9 个 dashboard 死 computed 删）
- 13 个孤儿文件清空（knowledge/{Dashboard,Hypotheses,Formulas,Entities,Search}.vue + meeting/{List,Stats}.vue + 3 个 composable + 1 个 component）
- **CardList #item-actions slot 静默丢失根因修复**（用户原报"找不到声纹录入入口"）
- 3 个新移动端 view（MobileMemberDetailView / MobileProjectDetailView / MobileTaskTrash 自给自足）
- 4 个新移动端路由（projects/:id / members/:id / tasks/trash / mobile 移动）
- 17 个新单元测试（SpeakerSearchSheet 8 + MobileMemberDetailView 5）
- **开始听会不再自动建任务**（加 `ENABLE_AUTO_TASK_FROM_MEETING=False` settings 开关，3 处守卫）

### 📱 2026-06-18 移动端 26 commits 全面修复 + 三连环修复

- **移动端 13 个隐藏 bug**（图标 / 路由 / 端点 / 布局 / 指示器 / v-model / ASR / 被动事件 / 知识 / 头像）一次性修复
- **EP useOrderedChildren.removeChild null 崩溃**（Vite plugin patch EP 源码）
- **桌面"正在听会"指示器不接进度**（新建 MeetingRoomView 镜像 MobileMeetingRoom）
- **/auth/me 完全豁免限流**（高频 polling 429 根因）

### 🐳 2026-06-17 Docker Desktop 引擎崩溃 + 镜像源治理

- WSL2 `docker-desktop-data` 发行版丢失 + C 盘 24GB 缓存 → E 盘 junction 透明重定向
- huaweicloud 镜像源 404 → aliyun 正确路径
- aliyun PyPI 限速 → 清华源 + pip `--retries 10`
- `.dockerignore` 17 倍提速 build context（12GB → 700MB）
- 共释放 ~192 GB

### 🔔 2026-06-15 任务提醒 v2 + 会议 #95 声纹重置

- **主动提醒调度器补 11AM 窗口守卫**（修复凌晨 2:48 仍收提醒）
- **会议 #95 声纹重置 + KMeans 重识别**（80 段错标，清理 8 个 JSON 字段）
- **移动端声纹测试真全链路改造**（5 状态机 + 调真 /api/v1/voiceprint/test）

### 🧪 2026-06-27 测试基建收官（v74~v76.2）

- **v74 CSS variable 6 主题组合自动化测试** — 拦截字面色回归 + CI hard fail + token 白名单
- **v75 测试稳定性** — 9 个旧 fail 修复 + PR annotation + token orphan pre-commit 拦截
- **v76.2 视觉回归 5 件套** — Playwright baseline + ci-mode + max-increase + 组件级 CSS 测试

### 🎨 2026-06-26 会议纪要视觉迭代 4 阶段（v70~v72）

- **v70 P0~P2 字面色 → token** — ~340 处 hex 替换 CSS 变量 + dark mode 全面修复（`5ea74dd5` + `f6a2bc3d` + `e4b2eec3`）
- **v70 P3 会议纪要视觉精简** — 顶部 TL;DR 卡 + 默认折叠发言人卡片（`bd41497e`）
- **v70 P3 预防机制** — Stylelint 字面色禁用 + `docs/color-tokens.md` 规范
- **v71 P1 议程 timeline + 每 speaker 8 条常驻** — `el-timeline` 金橙圆 dot + per-card "展开全部" 按钮（`46c85892`）
- **v72 P1 摘要+重点摘要合并** — 主题色 TL;DR 卡显示 `meeting.summary` 完整段落（`eed0c409`）
- **v73 fallback 政策章节补全** — fallback orphan 修复 + CI 集成 + font-mono token（`1707c660` + `d8ae2a2f`）
- **pre-commit hook auto-add web/dist/** — `scripts/check-dist-before-commit.sh` 自动检测 `web/src/` 改动 + 未 tracked dist 文件，避免 dist 漏 commit 导致服务器 404（commit `6565415a`，CLAUDE.md 教训第 4 次沉淀）

### 🚀 2026-06-25~26 限流 / Whisper / 视觉 收官（v31 + v68 + v69）

- **v31.2.x rate-limit 基建收官** — XFF 空 IP 兜底 + analytics regex 永久化 + `request.state.user_id` 维度 + `X-RateLimit-Policy` 头 + SSE tier 10/min + auth prefix match + Redis ZSET 持久化
- **v31.3 Whisper 常驻 GPU 8GB** — 端到端 ASR 1s + `flash_attention` 暂禁用（Blackwell sm_120 上游不支持）
- **v31.3.1 whisper 容器 bind mount** — Dockerfile 删 `COPY` + bind mount 源码，本地改 `whisper_server.py` → `docker compose restart` 即生效
- **v68 桌面主题切换按钮 + SettingsView 玻璃态** — `<html data-accent>` 实时切换
- **v69 P0+P1 dark mode 全面重构** — 3 阶段：P0 基础 5 token + 14 EP 覆盖；P1a 6 套主题切换；P1b 10 桌面视图 dark 适配

### 🚀 2026-06-14 Agent 单阶段流式架构

- **方案 C 收官**（12 commits，取消 brief/detail 双层，用户问"请教谁"直接推荐 3 人 + 理由）
- **Agent 回答质量 5 大根因修复**（14 commits + qa-bench 360 题 84% 高分）
- **知识库 64→247 条**（+183 条 / +286%）

### 📱 2026-06-13 移动端 PWA 收官

- **10 PR × 18 commits**：从基建 → NutUI 4 → 18 个移动端页面 → PWA 离线策略 → Playwright 视觉回归
- 桌面端完全零影响（v-if="!isMobile" 隔离）
- 端到端实测修 5 bug（agentic_loop await / mimo-v2.5 thinking / TraceCollector None / CancelledError / Celery 守卫）

### 🛡️ 2026-06-12 会议录音全栈防御

- **5 阶段全栈防御**（IndexedDB 兜底 + 边录边传 + chunked 端点 + 硬校验 + Celery retry）
- webhint paint keyframes 治理（49+ 报告清零）
- 会议查询 bug 双层根因修复（UnboundLocalError + LLM 撒谎模式）
- Vite hash 改 hex 消除 cache-busting 误报

### 🗑️ 2026-06-03 垃圾桶系统 + 性能优化

- **垃圾桶 4 bug 全修**（精准倒计时双行显示）
- beat 调度 4h → 1h
- Webhook ThreadingHTTPServer（0.001s 响应）

## 详细文档

- 📜 [**HISTORY.md**](HISTORY.md) — 完整开发历史（按时间倒序 commit 流水账，已存档 5730 行）
- 📝 [**CHANGELOG.md**](CHANGELOG.md) — 权威更新日志（按日期组织，简洁）
- 🛡️ [**CLAUDE.md**](CLAUDE.md) — 项目开发铁律沉淀
- 🐛 [**memory/**](memory/) — 事件复盘 + 教训笔记
