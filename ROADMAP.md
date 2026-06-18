# MicroBubble Agent - 路线图

> **本文件是项目未来规划 + 近期完成的高层摘要。**
> 详细 commit 流水账在 [HISTORY.md](HISTORY.md)（已存档 5730 行），权威变更日志在 [CHANGELOG.md](CHANGELOG.md)。

## 当前状态（2026-06-19）

**已交付**：
- ✅ v1-v6 完整后端架构（Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery + MinIO）
- ✅ v2/v3/v4 Agent 架构（34 个 `@tool` 装饰器工具 + 12 类 Rich Block + 多会话并行 + agent_traces 可观测性）
- ✅ 知识库 V1 + V2（动态 LLM 分析 + 知识图谱 + RAG 问答 + 自主研究引擎 + 公式分类 + 假设生成）
- ✅ 会议系统 v1-v3（录音机 + 离线后处理 + ASR + 声纹 + AI 摘要 + 三级润色）
- ✅ 声纹识别（3D-Speaker + pgvector + HNSW 索引 + 持续学习）
- ✅ 移动端 PWA 收官（18 个移动端页面 + 12 个移动端组件 + 路由级双栈 + 4 个 PWA 离线策略）
- ✅ v2 任务提醒体系（11AM 窗口 + acknowledged 状态 + Redis 24h 去重）
- ✅ 全量审计 5 commits（5 处 P0 + 9 处 P1 死代码清理 + 13 个孤儿文件删除）

**统计**：
- ~1100+ commits / 157K+ 行代码 / 630+ 文件 / 33 开发天数
- 9 个 Docker 服务运行中
- 87 后端 + 73 前端 + 17 移动端 = 177 测试全过
- 知识库 64→247 条（+183）

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
