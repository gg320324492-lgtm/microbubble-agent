# 更新日志

> 项目所有重要变更记录。详细修复细节见对应 commit 注释和 `memory/` 笔记。

## [2026-06-19] 声纹识别核心修复 + 会议发言人重处理流程标准化

### 🐛 P0 修复：声纹 batch bug 推到主路径（影响所有会议）

- **ERes2Net 不支持 batch** — `modelscope ERes2Net_aug.py:__extract_feature` 强制 `unsqueeze(0)` 折叠 batch。**所有会议**通过 `post_meeting_tasks.py` 的 `vp_service.batch_extract_embeddings()` 都只处理了 batch 第 1 段（89/2830 段有效，97% 沉默失败）
- **修复** — [`app/services/voiceprint_service.py:batch_extract_embeddings`](app/services/voiceprint_service.py) 改用 `ThreadPoolExecutor(8)` + `threading.Lock` 并行单条调用
- **效果** — 50/50 → 100/100 段有效（之前 3%），**所有未来会议自动获得正确识别效果，无需手动重跑**
- **影响范围** — `post_meeting_tasks.py`（录音 hangup 后自动跑的全流程）和 `scripts/reprocess_meeting.py` 都受益
- **铁律** — 上游库 `modelscope` 不会修这个 batch bug（2026-06-19 验证），必须 app 层绕开

### 🛠 会议发言人重处理流程标准化

- **场景** — 老会议用旧版 `batch_extract_embeddings` 处理时 97% 显示"发言人?"，新录入了声纹的成员重跑识别
- **沉淀 9 步 CLI** — [`scripts/reprocess_meeting.py`](scripts/reprocess_meeting.py) (load → extract → cluster → vote → assign → backup → apply → regen → verify)
- **主机端 wrapper** — [`scripts/run-reprocess.ps1`](scripts/run-reprocess.ps1) (PowerShell) + [`scripts/run-reprocess.bat`](scripts/run-reprocess.bat) (cmd.exe) 自动 docker cp + exec
- **关键 bug 修复 3** —
  1. **ERes2Net 不支持 batch** — ThreadPoolExecutor + Lock 修复（已推到主路径）
  2. **SQLAlchemy 静默忽略未映射属性** — 备份改用**文件** `/tmp/meeting_<id>_backup_*.json`，避免"已备份"谎言
  3. **verify 误报人名提及** — 只检查 `【错标名】` 前缀，不检正文
- **会议 #120 实测** — 3252 段"发言人?" → 4 个真实发言人（王天志 1845 / 杜同贺 358 / 宋洋 335 / 贾琦 292）+ 8 字段全 0 旧错标人
- **文档** — [docs/reprocess-meeting.md](docs/reprocess-meeting.md) + [memory/reprocess-meeting-pattern.md](memory/reprocess-meeting-pattern.md) + CLAUDE.md 新增 11 条铁律

### 一键使用

```powershell
# 完整流程（声纹 + DB + 纪要 + verify）
powershell scripts/run-reprocess.ps1 -Meeting 120 -AudioPath "C:\Users\pc\Desktop\实验相关工作安排.m4a"

# 单独 verify
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps verify
```

---

## [2026-06-19] 全量审计 + CardList slot 修复 + 开始听会不再建任务

- **🛠 全量审计 + 修复 + 测试**（commits `b843ad86`/`9218ac44`/`433997de`/`4f4f4ce7`）— 4 个 commit 修复 5 处 P0 必修 + 9 处 P1 死代码 + 13 个孤儿文件 + 新增 3 个移动端 view + 17 个单元测试
- **🐛 CardList #item-actions slot 静默丢失**（commit `b843ad86`）— 5 个移动端 view 依赖 `#item-actions` slot 但 CardList 只支持 `item-{id}` 动态 slot，Vue 静默丢弃。修复：[CardList.vue](web/src/components/mobile/CardList.vue) 加 `<slot name="item-actions" :item :idx />`。**用户原报"找不到声纹录入入口"根因**
- **🔧 修开始听会不再自动建任务**（commit `ca3047b7`）— 加 `ENABLE_AUTO_TASK_FROM_MEETING=False` settings 开关，3 处 `_auto_create_task_from_meeting` 调用点全部加守卫。决策/行动项仍记录到 `meeting.decisions` / `meeting.key_points`，user 手动决定是否建任务

---

## [Unreleased] - 2026-06-17 部署与基础设施重建

### 修复

- **🐳 Docker Desktop 引擎崩溃循环** — 根因：WSL2 `docker-desktop-data` 发行版丢失，导致 `com.docker.service` 每 7-9 分钟反复启停。修复：删除 C 盘 24GB Docker 缓存（已备份），让 Docker Desktop 自动重建发行版。详见 [`memory/docker-desktop-fix-2026-06-17.md`](memory/docker-desktop-fix-2026-06-17.md)
- **📦 Docker 镜像源 404** — 多个 Dockerfile 使用 `mirrors.huaweicloud.com/debian bookworm-security`（Debian 已迁出该路径），改用 `mirrors.aliyun.com/debian-security bookworm-security`（路径正确支持）
- **🐢 PyPI 镜像限速** — aliyun PyPI 限速 ~600KB/s，下 torch 532MB 装 13 分钟；改用清华源（10-14 MB/s 稳定）
- **🔌 frp 客户端未自动启动** — 用 `Register-ScheduledTask` 注册 Windows 计划任务 `FRPClient`（用户级登录触发），调用 `start-frpc.ps1` wrapper 启动 `frpc.exe`

### 优化

- **💾 Docker 数据全量迁移 E 盘** — `C:\Users\pc\AppData\Local\Docker` 24GB → `E:\DockerData\appdata`（junction 透明重定向，C 盘 0 字节占用）
- **⚡ Dockerfile 构建优化** — 新建 `.dockerignore` 排除 `models/` `data/` `logs/` `.git/` `.agents/` `docs/`，build context 从 12GB 降到 700MB（17 倍提速）
- **🐳 Whisper Dockerfile 加 fallback** — apt-get install 第一个包失败时自动重试（解决 aliyun `libcaca0` 502 Bad Gateway 瞬时错误）
- **🔐 Git 身份 + SSH 准备** — 配置 `user.name=gg320324492-lgtm`、`user.email=gg320324492@users.noreply.github.com`，准备 push 到 `git@github.com:gg320324492-lgtm/microbubble-agent.git`

### 部署状态

- ✅ 9 个 Docker 服务运行中：app、db、redis、minio、neo4j、whisper、vision-mcp、celery-worker、celery-beat
- ✅ `https://agent.mnb-lab.cn` 端到端连通（之前 502 Bad Gateway，现在 401 = 端点通了，密码错）
- ✅ whisper `faster-whisper==1.2.1` large-v3 模型加载完成，CUDA 库就绪（RTX 5090 32GB）

### 清理

- 删除 24GB C 盘 Docker 缓存副本 `E:\DockerData\appdata-cache-c\`
- 删除 168GB 孤儿 `docker_data.vhdx`（旧 docker-desktop-data 发行版数据，已无引用）
- 删除 frp 冗余文件：`frps.toml`（服务端配置，本地用不到）、`run-frpc.bat`（旧 wrapper）、`frpc-stderr.log`
- 删除 Docker 镜像 `ubuntu:latest`（160MB，未使用）
- **共释放 ~192 GB**

### 铁律沉淀（[memory/docker-desktop-fix-2026-06-17.md](memory/docker-desktop-fix-2026-06-17.md)）

1. **junction 透明重定向** — C 盘软件硬编码路径，删原目录 + `mklink /J` 创建 junction 是 Windows 上让应用"运行在 E 盘"的标准做法
2. **WSL 发行版丢失检测** — `wsl -l -v` 看发行版列表，缺 `docker-desktop-data` 就需要清缓存重建
3. **Dockerfile 镜像源选择** — Debian bookworm-security 走 `debian-security/` 独立路径，不在 `debian/` 下
4. **pip 限速真相** — 国内镜像对单连接限速 600KB/s，下大文件必断。清华 TUNA 前 12 秒 14MB/s 后会降到 320KB/s。**最佳方案是装 PyTorch 官方 wheel 源 + pip 重试**（本项目最后回到清华源 + `--retries 10` 也成功）
5. **build context 必加 .dockerignore** — 任何含大目录（models/data/logs）的项目必须先写 .dockerignore，否则 build context 几十 GB

---

## [2026-06-18] 三连环修复 + 限流误伤复盘（7 commits）

### 修复

- **🐛 EP `useOrderedChildren.removeChild` null 崩溃**（commit `f8d27015`）— Element Plus tab/table pane 卸载时 `nodesMap.get(parentNode)` 返 undefined → `childNodes.indexOf(childNode)` 报 `Cannot read properties of undefined (reading 'indexOf')`。修复：`web/vite.config.js` 新增 `epUnregisterPaneNullPatchPlugin`，transform 阶段 patch EP 源码，与现有 `vueBumNullPatchPlugin` 同模式。触发页：AgentTracesView（19 el-table）/ TaskTrash（18）/ MeetingDetailView（el-tabs lazy）/ KnowledgeView（4 tab lazy）/ SpeakerMappingPanel（8）/ VoiceprintEnrollDialog
- **🎤 桌面"正在听会"指示器不接进度**（commit `f099e7e5`）— 桌面端 MeetingView 用 el-dialog 嵌套 MeetingRoom，与移动端 MobileMeetingRoom 全屏页 UX 不一致。修复：新建 `web/src/views/MeetingRoomView.vue`（218 行），桌面化镜像 MobileMeetingRoom（el-page-header 顶栏 + el-dialog 帮助），router `meetings/room` fallback 改用 MeetingRoomView，MeetingView.resumeRecording 改 navigate
- **🔌 `/auth/me` 限流 20/min → 200/min**（commit `a1fd8280`）— `app/core/rate_limit.py` 把 /auth/me 从 auth tier 移到 read tier。`/auth/` 下细分：白名单敏感路径（login/refresh/change-password 等）保留 20/min，写操作走 write 30/min，其他只读走 read 200/min
- **🔄 MeetingView.onMounted 重复 router.replace 覆盖**（commit `defb08e1`）— `resumeRecording()` 跳 `/meetings/room` 后，紧接着的 `router.replace({ path: '/meetings' })` 立即覆盖，导致 URL 永远停在 /meetings + 不断重渲。修复：删第二行
- **🐛 MeetingRoomView 模板 `.value` 反模式**（commit `9f11d97a`）— Vue 3 `<script setup>` 里 `.value`，但 template 里 Vue 自动 unwrap ref，写 `.value` 等于 `null.value` TypeError。修复：模板去掉 `.value`
- **🔓 `/auth/me` 完全豁免限流**（commit `22f5a7d7`）— 即便 200/min 也被 useUserStore 高频 polling 触发 429。修复：`_AUTH_UNLIMITED_PATHS = {"/api/v1/auth/me"}`，middleware 看到 "unlimited" tier 直接跳过

### 部署链路事故（详见 [memory/incident-2026-06-18-deploy-chain.md](memory/incident-2026-06-18-deploy-chain.md)）

- **本地 commit 后忘 push，误判 webhook 链断** — 服务器 git log 停在 `c1b969dd`、dist 无 MeetingRoomView chunk，初看像 webhook 断（CLAUDE.md 2026-06-17 教训复发）。**真根因**：本地 `git commit` 后没 `git push`，GitHub 端一直停在 `c1b969dd`。修复：补 push 后 webhook 5 秒内触发，服务器 HEAD 变 `f099e7e5` + `f8d27015`

### 铁律沉淀（详见 CLAUDE.md "2026-06-18 三连环修复"）

1. **`commit + push` 后必 `git log origin/main -3` 验证** — 缺这一步 = 服务器 deploy 永远拿不到新代码，症状与 webhook 断 100% 一样，浪费排查时间
2. **怀疑 webhook 断时第一步看 origin/main** — 服务器 `sudo git fetch origin main && git log origin/main -5`，区分"本地没 push"vs"webhook 链断"
3. **`/auth/` 路径按 path+method 细分限流** — 不能 `/auth/` 前缀一刀切，按"是否会被高频轮询"分类而非"是否敏感"
4. **高频只读端点完全豁免** — Vue reactive + WS 心跳 + 路由 prefetch 频次远超产品逻辑假设
5. **template 里 ref 永远不写 `.value`** — Vue 自动 unwrap，script 用 ref.value，template 用 ref
6. **router 操作一次只一个** — `router.replace/push` 后不要再紧接第二个，会被覆盖
7. **docker compose v1/v2 服务器不互通** — 服务器装的是 docker-compose 独立二进制（v1），必须 `sudo docker-compose`，不是 `docker compose`

### 文件变更

- 新增 `web/src/views/MeetingRoomView.vue`（桌面听会房间全屏页，218 行）
- 修改 `web/vite.config.js`（+epUnregisterPaneNullPatchPlugin）
- 修改 `web/src/router/index.js`（meetings/room fallback 改 MeetingRoomView）
- 修改 `web/src/views/MeetingView.vue`（resumeRecording 改 navigate + 删重复 router.replace）
- 修改 `app/core/rate_limit.py`（/auth/me 细分 + 完全豁免）
- 新增 `memory/incident-2026-06-18-deploy-chain.md`（部署链路事故笔记）

---

## [2026-06-15] 任务提醒 v2 + 会议 #95 声纹重置

- **🔔 主动提醒调度器补 11AM 窗口守卫 + highlight.js plaintext fallback**（3 commits `c18b01e8` + `d0ddf49e` + `09e4548d`）— 修复凌晨 2:48 仍收"分配已超过24小时"提醒根因
- **🎤 会议 #95 声纹重置 + 重识别全链路**（2 commits `af044bfc` + `3bcc8c20`）— speaker_mapping 严重错标 80 段，完整清理 8 个 JSON 字段
- **🎤 移动端声纹识别测试真全链路改造**（5 commits）— 解决"声纹测试显示开发中"+"点击没反应"

详见 ROADMAP.md 同日条目 + CLAUDE.md 第 11-15 行块。

---

## [2026-06-14] Agent 单阶段流式架构 + 质量优化

- **🚀 方案 C：Agent 单阶段流式渐进综合架构**（12 commits 完整链路 `5ce1203`→`48ac8dc`）— 取消 brief/detail 双层，用户问"请教谁"类问题直接推荐 3 人 + 理由
- **🤖 Agent 回答质量 5 大修复**（14 commits）— TOOL_REGISTRY 未注册 / LLM 代理不转发 tools / 长期记忆干扰 / synthesis 阶段 fake XML 泄露
- **🧪 qa-bench 360 题闭环** — 知识库 64→247 条（+183 条 / +286%）

---

## [2026-06-13] 移动端 PWA 收官

- **📱 移动端 PWA 收官**（10 个 PR）— NutUI 4 + Element Plus 路由级双栈架构，18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略
- **🛡️ Service Worker 升级机制** — `SW_VERSION v4→v5` 强制升级路径
- **🎨 webhint a11y img alt 警告**（5 处修复）— theme-color Firefox 不支持是浏览器限制
- **🐛 端到端实测修复 5 bug**（commit `5f01cac`）— agentic_loop await/async for / mimo-v2.5 thinking / TraceCollector None / CancelledError / Celery 守卫

---

## [2026-06-12] 会议录音全栈防御

- **🎙️ 会议录音全栈防御机制 5 阶段** — 解决 #84 案例"58 分钟录音断网丢失"
- **🌐 webhint paint keyframes 治理**（49+ 报告清零）
- **🐛 会议详情页 transcriptEntries / polish-text 400 双 bug 修复**
- **🔧 Vite hash 改 hex 真正消除 cache-busting 误报**
- **🐛 会议查询 bug 双层根因修复**（`app/agent/core.py:911` UnboundLocalError + LLM 撒谎模式）

---

## [2026-06-03] 垃圾桶系统 + 性能优化

- **🗑️ 垃圾桶系统 4 bug 全修**（commit `dc93bff`）— 精准倒计时双行显示
- **⏰ beat 调度 1h**（commit `47fb2c9`）
- **⚡ Webhook 性能 0.001s 响应**（commit `7ec6ce0`）
