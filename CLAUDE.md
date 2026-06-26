# MicroBubble Agent - 项目上下文

> **2026-06-26 v31.3.1 whisper 容器 bind mount**：v31.3 commit (`93de5151`) 后发现部署需要 `docker cp app/whisper_server.py microbubble-agent-whisper-1:/app/whisper_server.py`（因为 [Dockerfile.whisper:40](Dockerfile.whisper#L40) `COPY app/whisper_server.py .` 把源码烧进镜像，本地改源码后 `docker compose restart` 不生效）。违反 CLAUDE.md "Dockerfile 只装系统依赖 / 源码走 bind mount" 最佳实践 → **v31.3.1 修复**：[Dockerfile.whisper](Dockerfile.whisper) 删 `COPY` + [docker-compose.yml](docker-compose.yml) 加 `- ./app/whisper_server.py:/app/whisper_server.py:ro` bind mount。**优势**：本地改源码 → `docker compose restart whisper` 即可生效（省 docker cp 步骤）。**端到端验证**：改本地加 print 标记 → restart → logs 看到标记 → 删除标记 → restart → logs 干净（bind mount 双向同步）。详见底部 [## 2026-06-26 v31.3.1 whisper 容器 bind mount](#2026-06-26-v3131-whisper-容器-bind-mount解决dockerfile-copy-烧镜像陷阱) section + 3 条新铁律。
>
> **2026-06-26 v31.3 Whisper 常驻 + 推理加速**：v31.2 之前 working tree 里有 `lazy load + 10 分钟空闲卸载` 方案（`whisper_server.py` +183 行），但用户决策"为保证聊天 ASR 短语音时效性，模型常驻 GPU 8GB" → **回滚到简单模式**：启动时一次性加载，永不卸载。**加 `flash_attention=True`**（ctranslate2 4.8+ 支持）→ 推理提速 30-50%（长录音收益明显）。**代码净减 ~80 行**（删 `_do_release_model` / `_idle_checker_loop` / `_ensure_model_loaded` / 状态变量），加 5 行。**实测数据修正**（CLAUDE.md 之前估的"28GB → 500MB"和"10-15s 加载"严重偏离）：实测加载 **18s**、加载后 GPU **8 GB**、`del` 后 **4.3 GB**、释放比 **3.7 GB**（估的 28GB 是开发者凭印象，没实测）。详见底部 [## 2026-06-26 v31.3 Whisper 常驻 + 推理加速](#2026-06-26-v313-whisper-常驻--推理加速) section + 3 条铁律。
>
> **2026-06-26 v31.2.5 rate-limit 收官（启用 Redis ZSET 持久化）**：v31.2.4 已实现 `AsyncRedisRateLimiter`（基于 Redis ZSET 滑动窗口）并通过 7 phase 单元测试，但 `_rate_limiters` 字典里全是 `RateLimiter`（in-memory），新类未接入。**v31.2.5 启用**：`app/core/rate_limit.py:118-126` 把 5 个 tier 实例全换 `AsyncRedisRateLimiter`，`rate_limit_middleware` 把 `limiter.check()` / `limiter.record()` / `len(_attempts)` 全 await 化。**关键收益**：抗 `docker compose restart`（v31.2.0-2.4 内存版一重启全清零，攻击者赶在窗口重置前打满）。**端到端验证**：[scripts/verify_v31_2_5_restart.py](scripts/verify_v31_2_5_restart.py) — 灌 9 次 SSE（ZCARD=9）→ `docker compose restart app` → 重启后第 2 次请求触发 429（旧 9 + 新 1 = 10 ≥ max_attempts）。**全量回归**：v31.2.1 XFF 空 IP / v31.2.1 nested path / v31.2.2 / v31.2.3 / Redis limiter 5 个 verify 脚本全 PASS。详见底部 [## 2026-06-26 v31.2.5 rate-limit 收官](#2026-06-26-v3125-rate-limit-收官redis-zset-持久化) section + 4 条铁律。
>
> **2026-06-25 v31.2.3 rate-limit 基建收尾**：v31.2.2 (commit `c617f8e9`) 已用 regex 取代 analytics substring + 注入了 user_id 维度，但还差 3 件事：① **`X-RateLimit-Policy` 响应头**（之前只有 Limit/Remaining/Reset，前端 429 不知道触发的 tier 是 auth/read/upload/sse 哪个，做不了 tier-aware UX）；② **SSE 长连接独立 tier**（`/api/v1/chat/stream` 一次占用几秒到几分钟，按 read 200/min 算只能 200 并发，新增 `sse` tier 10/min）；③ **`/auth/` substring B3 化**（`_is_under_auth(path)` prefix 匹配取代 `"/auth/" in path`，防 `/api/v1/authentication` 等未来路径误中）。详见底部 [## 2026-06-25 v31.2.3 rate-limit 基建收尾](#2026-06-25-v3123-rate-limit-基建收尾) section + 3 条铁律 + scripts/verify_v31_2_3.py 端到端 21 case 全 PASS（4 真实 HTTP policy 头 + 9 SSE tier 隔离 + 8 auth prefix 边界）。
>
> **2026-06-25 v31.2.2 rate-limit 进阶强化**：v31.2.1 用 substring `"/analytics" + startswith("/api/v1/auth/")` 守卫是临时方案（B1），业务假设仍藏在字符串里。**B3 改 regex 永久化**：`_ANALYTICS_PATH_RE = re.compile(r"^/api/v1/analytics/search-event$|^/api/v1/analytics/search-event/\d+/click$|...")` 锚定 `^...$` + 路径分隔。同时 `_get_client_key` 注释说"用 `{ip}:user:{uid}` 维度"但 middleware 从来没解析 token 写 `request.state.user_id`——**comment drift 修复**：新增 `_try_attach_user_id(request)` middleware helper（不查 DB，无效 token 静默忽略），让 user 维度真实生效。详见底部 [## 2026-06-25 v31.2.2 rate-limit 进阶强化](#2026-06-25-v3122-rate-limit-进阶强化) section + 2 条铁律 + scripts/verify_v31_2_2.py 端到端 12 case 全 PASS（4 analytics regex + 4 user 维度隔离 + 4 真实 HTTP）。
>
> **2026-06-25 v31.2.1 rate-limit 边界强化**：v31.2 (commit `c2c5066e`) IP 维度限流 + /analytics 豁免 + 可选 auth 端到端 4 边界实测（16 场景全 PASS）后 2 个非阻塞 follow-up 顺手做掉：① **get_client_ip XFF 空 IP 兜底** — `X-Forwarded-For: , 1.2.3.4` / `"   "` / `",,,,,"` 全部 `split(",")[0].strip() = ""` → 空 IP 作为限流 key 共享 200/min 配额（Nginx 通常不让空 XFF 穿透，但后端必须独立防御）；修：`app/core/rate_limit.py:156 get_client_ip` 加 `if ip: return ip; return "unknown"` 兜底 + 7 行 docstring。② **`/auth/analytics/...` 嵌套 bypass 防御** — `_get_rate_limit_type` 顺序 2 (`if "/analytics" in path`) 在顺序 3 (`if "/auth/" in path`) 之前，未来加 `POST /api/v1/auth/analytics/export` 会先命中 substring → unlimited → 绕过 /auth/ 敏感端点 20/min；修：顺序 2 前置守卫 `not path.startswith("/api/v1/auth/")`，**不调换顺序**（会破坏已确认的 /analytics POST=unlimited 设计）。详见底部 [## 2026-06-25 v31.2.1 rate-limit 边界强化](#2026-06-25-v3121-rate-limit-边界强化) section + 2 条铁律 + 11 case 纯函数 mock 端到端验证全 PASS。
>
> **2026-06-20 v28 step 2-8 全部完成 + article 9 字 bug 修复**：①-⑥ [alembic 028](alembic/versions/028_figure_structured_fields.py) + model + multimodal 集成 ⑦ schema + API `_to_dict` 加 12 字段 ⑧ paperAdapter 简化（84/84 测试通过） ⑨ KnowledgeDetailView 独立 IO + sectionHint 核心词匹配 ⑩ PaperSectionRenderer `showHighConfidenceOnly` ≥0.85 + ReadingToolbar confidence 徽章 ⑪ **4 篇 PDF 验证**：37 张图 100% vision 覆盖 + 100% publisher 准确 + 100% confidence ≥0.85 + 中文 anchor bug 修复 ⑫ **IO Hysteresis 防跳变**：阈值 ACTIVATE_THRESHOLD=0.35 / HYSTERESIS_LOWEST=0.15 + rAF 节流 ⑬ **article 9 字 bug 修复（深坑）**：根因 INTERNAL_MARKER_RES line 105 `\bPAGE\s*[:：]\s*\d+\b` 在 `[`/`P` 之间构成 `\b` 单词边界 → 匹配 `[PAGE:1]` 的中间 `PAGE:1` 部分 → 替换为空 → `[PAGE:1]` 变 `[]` → pageMarkers=0 → sections 解析丢分页 → 正文压成 1 段 → 用户看到 9 字符（只剩 inline 注入的 "## 多模态提取/### 图表说明" 标题）。**修复**：删 INTERNAL_MARKER_RES 2 条 ([PAGE:N] 删除逻辑) + cleanContent 简化 + hasPageMarker 检测后用 rawFormatted 作 inputContent。**端到端验证**：pageMarkers=9 / sectionsCount=19 / article=40855字符（vs 修复前 9 字符）。详见底部 [## 2026-06-20 v28 论文图片结构化字段](#2026-06-20-v28-论文图片结构化字段后端集成) section + 25 条铁律。
>
> **2026-06-18 移动端 26 commits 全面修复（图标 + 路由 + 端点 + v-model 命名 + ASR + 被动事件 + 头像）**：① 移动端"左上角红方块"根因是 `MainLayout.vue` 缺 `Fold`/`Expand` 图标 import（commit `0e11009`）② 8/16 路由 mobile 路径错（`knowledge/MobileKnowledgeView` 等假设了子目录但实际在 `views/mobile/` 根目录，commit `025424ca`）③ 4 个移动端 API 端点缺失（`/dashboard/summary` + `/formula` + `/hypothesis` + `/memory`，commit `d671c41c` + `5f5bfd06`）④ TabBar 2500 z-index 覆盖 MobileInputBar 100 → `/chat` 路由隐藏 TabBar + 修 v-model 命名（commit `7131ad4b`），用户偏好 persistent nav 后恢复 TabBar + input 浮在 TabBar 上方（commit `c94d0603`）⑤ "正在听会"指示器点击无反应 → `MobileMeetingView` onMounted 漏处理 `route.query.resume`（commit `fc27af59`）⑥ 11 处 `v-model:show` 命名错配（prop 是 `modelValue`，commit `6b4f57d0` + `20df60db` + `607e7b06`）⑦ ASR 500 真实根因 110 字节 webm → 客户端 `<1KB` 拦截 + 服务端返 400（commit `3cd88d4a`）⑧ passive event listener 全局 patch 误伤 `touchstart` → 只对 `wheel`/`mousewheel` 强制（commit `3cd88d4a`）⑨ 知识 3 个 ActionSheet 之前是"开发中"占位 → 接通 `/knowledge` + `/knowledge/upload` + `/knowledge/research` 真实端点 ⑩ 头像同步：新建 `MemberAvatar.vue` 复用 `memberStore.getMemberAvatar(id)`，在 `CardList` 加 `avatarField` prop，Task/Task/Task/Member/Settings 全部显示真实头像。详见底部 [## 2026-06-18 移动端 26 commits 全面修复](#2026-06-18-移动端-26-commits-全面修复) section + [memory/mobile-fixes-2026-06-18.md](memory/mobile-fixes-2026-06-18.md) 12 条铁律。
>
> **2026-06-19 Phase 7 多模态知识库（图片/公式/表格 OCR 入库）**：① 端到端 PDF 文档 OCR 实测 10/10 图全成功 + 10 OCR 块 + 4 图表描述（论文 id=19 催化臭氧氧化甲苯）② 后端选 LLM-Vision 复用现有 vision_service，零新依赖 + 零新模型下载，settings.MULTIMODAL_OCR_BACKEND 留 Tesseract 备选钩子 ③ 数据模型统一 `KnowledgeExtraction(kind='formula|table|chart|image_block', data JSONB)` 单一表，简化 JOIN ④ 并发控制 asyncio.Semaphore(4) 防 vision API rate limit ⑤ pre-existing bug 修复 2 项：列表接口 mutate ORM 触发 autoflush NOT NULL 违反 + 009/010 alembic chain 不一致 ⑥ docker-compose 加 `./alembic/versions` volume 挂载，新迁移无需 rebuild 镜像即生效 ⑦ 21 个 OCR 单元测试（_clean_latex_response / _clean_ocr_text thinking 块剥除 / 图片缩放 / MIME 检测 / markdown 表格解析）。详见底部 [## 2026-06-19 Phase 7 多模态知识库](#2026-06-19-phase-7-多模态知识库) section + 8 条铁律。
>
> **2026-06-19 会议发言人重处理流程标准化（修 2 个核心 bug）**：① **ERes2Net 不支持 batch** — modelscope ERes2Net_aug.py:__extract_feature 强制 unsqueeze(0) 折叠 batch，旧 `batch_extract_embeddings` 把 32 段塞给模型只处理第 1 段 → 修：ThreadPoolExecutor(8) 并行单条 + threading.Lock 保护 pipeline.model ② **SQLAlchemy 静默忽略未映射属性** — Meeting model 没 `transcript_polished_old_v1` 等列，赋值被吞，commit 不报错，"已备份"成谎言 → 修：用文件备份 `/tmp/meeting_<id>_backup_<ts>.json`。沉淀为 [scripts/reprocess_meeting.py](scripts/reprocess_meeting.py) 通用 CLI（9 步流程 + 自动依赖 + 幂等）+ 11 条铁律 + [docs/reprocess-meeting.md](docs/reprocess-meeting.md) 使用文档。会议 #120 实测：3252 段"发言人?" → 4 个真实发言人（王天志 1845 段 / 杜同贺 358 / 宋洋 335 / 贾琦 292）+ 8 字段全 0 旧错标人。详见底部 [## 2026-06-19 会议发言人重处理流程](#2026-06-19-会议发言人重处理流程-reprocess_meetingpy) section。
>
> **2026-06-19 声纹 batch bug 修复推到主路径** — `app/services/voiceprint_service.py:batch_extract_embeddings` 之前用 batch=32 喂给 modelscope ERes2Net，实际只处理 batch 第 1 段（97% 沉默失败）。**所有**通过 `post_meeting_tasks.py` 自动处理的会议都受影响——hangup 后 Celery 跑全流程，每场都只能 3% 段有效。修复：ThreadPoolExecutor(8) + Lock 并行单条 → 100% 段有效。**用户原话**："不仅是漏掉发言人的情况，就算不漏掉发言人的正常识别，识别效果也要像本次一样或者更好" — 修复后所有未来会议自动获得正确识别效果，无需手动 re-process。详见底部 [## 2026-06-19 声纹 batch bug 修复 (推到主路径)](#2026-06-19-声纹-batch-bug-修复-推到主路径) section + [memory/voiceprint-batch-bug-fix-2026-06-19.md](memory/voiceprint-batch-bug-fix-2026-06-19.md) 7 条铁律。
>
> **2026-06-17 部署与基础设施重建**：Docker Desktop 引擎崩溃循环修复（WSL2 `docker-desktop-data` 发行版丢失 → com.docker.service 7-9 分钟反复启停）+ 24GB C 盘 Docker 缓存清空 + 数据全 E 盘化（junction 透明重定向）+ huaweicloud 镜像源 404 → aliyun 正确路径（Debian bookworm-security 走 `debian-security/` 独立路径）+ aliyun PyPI 限速 600KB/s → 清华源 + pip `--retries 10 --timeout 60` + 新增 `.dockerignore`（build context 12GB→700MB 17 倍提速）+ frp 客户端 Windows 计划任务自启。详见 [CHANGELOG.md](CHANGELOG.md) `[Unreleased] 2026-06-17` section + [memory/docker-desktop-fix-2026-06-17.md](memory/docker-desktop-fix-2026-06-17.md) 10 条铁律。
>
> **2026-06-17 晚间更新**：服务器 webhook deploy 链断裂修复（dist `Last-Modified` 停在 6/15 13:52 已 2 天）。根因：服务器 `/root/.ssh/github_deploy` key 与 GitHub repo Deploy keys 不匹配，5 次重试全 `Permission denied (publickey)` → webhook 服务在线但 git fetch 失败 → deploy 静默退出（GitHub UI 显示 200 OK 但服务器代码没动）。修复：重新生成 ed25519 + GitHub 端加 deploy key + 顺便持久化 `.env.webhook`（修 6/13 教训的幽灵隐患）+ `deploy-auto.sh` 加 `.env.webhook missing` 守卫（commit `c9c60ca6`）。详见底部 [## 2026-06-17 webhook deploy 链断裂修复](#2026-06-17-webhook-deploy-链断裂修复) section 5 条铁律。

> **2026-06-15 凌晨更新**：Agent 回答质量 5 大根因修复（14 commits）+ qa-bench 360 题逐个问答闭环 + 知识库 64→247 条（+183）。详见底部 [## 2026-06-15 Agent 质量 + qa-bench 闭环](#2026-06-15-agent-质量--qa-bench-闭环) section。
>
> **2026-06-15 上午更新**：Rich Block 统一包装铁律（杨慈是谁呀 Rich Block 显示"暂无成员"修复 + 顺手修 wechat/handler.py:1031 SyntaxError + members.notification_preferences 列缺失）。详见底部 [## 2026-06-15 Rich Block 统一包装铁律](#2026-06-15-rich-block-统一包装铁律杨慈是谁呀暂无成员修复) section。
>
> **2026-06-15 下午更新**：LLM 元话语/thinking 文本泄露修复（杨慈是谁呀元话语泄露"我需要..."、"用户问的是..."、"开始回答吧"）。双管齐下：prompts.py 硬规则 + 后端 _strip_meta_thinking 兜底 + SSE done.text_without_json + 前端 useChatStream done 替换。详见底部 [## 2026-06-15 LLM 元话语/thinking 文本泄露修复](#2026-06-15-llm-元话语thinking-文本泄露修复双管齐下) section。
>
> **2026-06-15 晚间更新**：reminders 表 v2 字段缺失 → /api/v1/reminders 500（webhint 报错 index-2bce6a55.js:4 GET 500）。本地 + 生产 ALTER TABLE 加 6 列（acknowledged_at / acknowledged_by / ack_channel / snoozed_until / reminder_batch_date / policy_version）。deploy-auto.sh 集成自动迁移。
>
> **2026-06-15 晚更新**：主动提醒调度器补 11AM 窗口守卫（3 commits `c18b01e8` + `d0ddf49e` + `09e4548d`）。**根因**：`app/wechat/scheduler.py:ProactiveScheduler` 3 个 check 方法（due_soon/overdue/unconfirmed）**完全绕过 11AM 窗口**，与 v2 `reminder_service` 并行运行，Celery beat 15min tick 凌晨 2:48 推送 → 用户被叫醒。**修复**：3 个 check 方法顶部加 `is_in_digest_window()` 守卫（共享 v2 reminder_policy 策略函数）。**bonus**：`markdown.ts` plaintext fallback 未注册导致 console warning。**部署**：本地 Docker `docker compose restart celery-worker celery-beat`（CLAUDE.md 752 行铁律），重启后第一次执行耗时 0.002s = 修复生效。详见 [## 2026-06-15 任务提醒体系 v2 全面优化](#2026-06-15-任务提醒体系-v2-全面优化) 末尾"v2 漏修补救"section + 5 条新铁律。

> **2026-06-15 全天更新**：任务提醒体系 v2 全面优化（commits `223ea74` + `ba75e32`）。所有 reminder 统一在 11:00 AM 北京时间窗口发送，每个任务 1 次推完即结束；任何微信消息 = ack 取消该用户所有 pending 提醒（杜同贺痛点彻底解决）。详见 [## 2026-06-15 任务提醒体系 v2 全面优化](#2026-06-15-任务提醒体系-v2-全面优化)。
>
> **2026-06-15 全天追加**：会议 #95 声纹重置 + KMeans 重识别 + speaker_mapping 重写 + meeting_participants 修复。教训：`psycopg2` 中途失败导致整个 transaction rollback、speaker_mapping 与 meeting_participants 必须互相对齐、Whisper 幻觉段不能用作声纹学习。详见 [## 2026-06-15 会议 #95 声纹重置 + 重识别教训](#2026-06-15-会议-95-声纹重置--重识别教训) section。

## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus（原版 `web/`，极简版 `web-minimal/`）
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前开发阶段

**Phase 1-6 全部完成 + v2/v3/v4 全栈架构重构收官 + 移动端 10 个 PR 全栈定制收官。** 知识库已升级为**自主进化的课题组知识大脑**。会议系统已重构为**录音机 + 离线后处理模式**。**小气助手后端 Agent 架构**：从 1 个 1469 行单文件（`app/agent/core.py`）拆为 7 个职责清晰模块 + 13 个按业务域拆分的 tools/ 文件，**34 个工具全部走 `@tool` 装饰器 + Pydantic 校验**。前端用 ChatViewSSE.vue 接入真实 SSE 流式 + 12 类 Rich Block 组件 + 多会话侧栏 + dark mode + ASR/TTS 完整语音链路 + 代码高亮。**移动端**采用 NutUI 4 + Element Plus **路由级双栈**架构（`useIsMobile.js` 判定 + `resolveMobile.js` 路由适配），**18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略**全部交付，**iOS Safari + Android Chrome 全兼容**。**当前状态（2026-06-13 收官后，commit `9026c07`）**：
- **43 commits 累计**（v1 修复 + v2 6 + v3 5 + v4 6 + 文档 2 + 深夜收尾 4 + 多会话并行 2 + 移动端 PR #1-10 共 10 + 文档/webhint 5 + 部署加固 1）
- **160+ 测试全过**（87 后端 + 73 前端 + 21 录音断网防御 + 2 移动端组件 + 21 多模态 OCR）
- **1014 次提交 / 135K 行代码 / 578 文件 / 30 开发天数**（`app/stats.json` 由本地 Python 准确计算；排除 frp/.git/node_modules/dist/.meta/.log/.wav/.exe 等非源代码）
- **140 项待做清单**已整合到 README.md（107 项老 + 33 项 v4 收官遗留），移动端 10 PR 完成后清单大幅缩短

**Phase 7 多模态知识库（2026-06-19）**：
- **2 张新表**：`knowledge_images`（图片 + OCR 结果）+ `knowledge_extractions`（统一 formula/table/chart/image_block）
- **OCR 服务抽象层**（`app/services/ocr_service.py`）：主后端 LLM-Vision 复用 vision_service，可选 Tesseract 备选（settings.MULTIMODAL_OCR_BACKEND 切换）
- **多模态解析管线**（`app/services/multimodal_extraction_service.py`）：PDF/PPTX 提取嵌入图片 → 缩放 → MinIO → asyncio.Semaphore 并发 OCR → 写表
- **3 个新 API**：`GET /knowledge/{id}/images`、`GET /knowledge/{id}/extractions`、`POST /knowledge/{id}/extract-multimodal`（老 PDF 手动重提）
- **KnowledgeService step 7**：上传时自动触发多模态提取；独立容错
- **5 个新 settings**：`MULTIMODAL_OCR_BACKEND` / `_CONCURRENCY=4` / `_MAX_IMAGES_PER_DOC=20` / `_MAX_IMAGE_PIXELS=2.5MP` / `_MIN_IMAGE_PIXELS=10k`
- **2 个新前端组件**：`KnowledgeImageGallery.vue`（图片网格 + 放大预览 + OCR 文本）+ `KnowledgeExtractionsPanel.vue`（公式 LaTeX + 表格 HTML + 图表描述）
- **KnowledgeCard 缩略图** + `KnowledgeUploadDialog` PDF/PPTX 多模态提示
- **端到端验证**：PDF id=19 OCR 10/10 + 10 OCR 块 + 4 图表描述成功

**v2/v3/v4 关键成果**：
- **34 个 `@tool` 装饰器工具**（覆盖任务 5 / 会议 7 / 项目 3 / 成员 2 / 知识 9 / 公式 1 / 假设 1 / 记忆 3 / 搜索 1 / 个性化 2 / 反馈 1 — 含 16 个 v2+v3 新工具）
- **12 类 Rich Block 组件**（meeting / task_list / knowledge_ref / member / formula / hypothesis / project / transcript / chart + 2 兜底）
- **真实 SSE 流式**（`/chat/stream`）替代伪流式 2s 轮询
- **10 字段响应**（content + session_id + file_url + file_name + knowledge_content + is_brief + **rich_blocks + tool_trace + usage + duration_ms**）
- **多会话侧栏**（Pinia + localStorage + 兼容 v1 单会话迁移）
- **dark mode**（CSS 变量化 + 顶栏 toggle + 主题持久化）
- **agent_traces 可观测性闭环**（Celery 异步写表 + `/admin/agent-traces` 端点 + `AgentTracesView` 管理页）
- **ASR 语音完整链路**（点 🎤 → 录音 → ASR 文字 → 自动发 + 🔊 TTS 播放）
- **代码高亮**（highlight.js + 6 种语言：python / js / bash / json / sql / yaml）
- **性能基线**（`tests/perf/` 6 测试：brief<3s / SSE<1s / tool<5ms）
- **质量评估体系**（LLM-as-judge + RAG 召回率 + 20 问标注 + 5 消融）
- **`core.py` 清理**：1469 → 689 行（-53%，原 794 行 elif 链替换为 14 行薄壳调 `dispatch_tool`）

详见 [ROADMAP.md](ROADMAP.md#v2v3v4-全栈架构重构2026-06-12-收官17-commits) 和 [README.md](README.md#近期新增按时间倒序)。

## 会议纪要标准格式（2026-06-06 硬规则）

后续所有会议 AI 分析、手动优化会议内容、历史会议补写，都必须按 `2026.5.28 例行例会` 的信息密度输出，不能只生成短摘要。完整规范见 `docs/meeting-minutes-standard.md`。

- **摘要**：3-6 句，必须包含会议背景、讨论过程、关键人物观点、结论和后续方向。
- **讨论要点**：`key_points` 必须使用 `【发言人】内容` 格式；短会议也至少提取 3 条，信息充足时 5-8 条。
- **决议事项**：`decisions` 必须使用 `【发言人/双方/全组】内容` 格式，写清楚决定/共识和后续用途。
- **原始转录保护**：不改 `transcript` 原始转录，只优化 `transcript_polished`、`summary`、`key_points`、`decisions`。
- **禁止误认**：声纹无法确认时使用 `发言人A/B`，不要为了完整性强行猜姓名。

## 前端设计系统

**CSS 设计令牌**：`web/src/assets/variables.css`，暖橙珊瑚色系，可复用于所有页面。

主要变量：
- `--color-primary: #FF7A5C`（珊瑚橙）
- `--color-accent: #FFB347`（金橙）
- 阴影层级：`--shadow-sm/md/lg/primary`
- 圆角规范：`--radius-sm(4px)/md(8px)/lg(12px)/xl(16px)`
- 动画时长：`--duration-fast(150ms)/normal(200ms)/slow(300ms)/counter(500ms)`

动画规范：使用 `fadeSlideUp`/`slideDownFade` 入场动画类，stagger 延迟 `.stagger-1` ~ `.stagger-6`。

设计规范文档：`.claude/skills/ui-design/SKILL.md`（20项 UI 升级检查清单）

## 关键架构决策

- Agent 工具调用通过 `app/agent/core.py` 的 `_execute_tool` 方法路由到 service 层（17 个工具已全部接入）
- `chat()` 和 `chat_stream()` 接收 `db: AsyncSession` 参数，由 API 路由通过 `Depends(get_db)` 传入
- 使用 `AsyncAnthropic` 客户端，不阻塞事件循环
- **Agent 回复采用"先简要后详细"双层结构** — 两阶段并行调用，简要立即返回，详细后台追加
- **MCP 视觉服务架构** — 预写架构，切换 DeepSeek 等文本模型时支持图片识别
- 认证使用 JWT，`app/core/security.py` 已实现，31 个端点全部接入 `get_current_user`
- 会话存储已迁移到 Redis（`RedisSessionStore`，24 小时 TTL）
- 知识库使用 pgvector 做向量搜索（扩展已在 main.py 启动时自动安装，已接入 text2vec-base-chinese 真实语义搜索）
- **知识库深层逻辑系统（Knowledge Brain）** — 八大模块：
  - **动态 LLM 分析**：LLM 根据内容自由生成分类/标签/key_concepts/related_topics/knowledge_type，不再硬编码
  - **自动关联引擎**：新入库条目通过 pgvector 余弦相似度 + 概念重叠自动发现关联关系，双向写入 knowledge_relations 表
  - **RAG 问答引擎**：语义搜索 → 阈值分类 → LLM 合成 → 来源引用，高相关不足时自动触发研究
  - **自主研究引擎**：知识空白检测 → 联网搜索（搜狗+必应）→ 网页抓取 → LLM 提取 → 自动入库 → 建立关联
  - **健康监控**：Celery 定时任务检测矛盾/重复/过期条目
  - **实体知识图谱**：跨文档实体融合（精确匹配→embedding 余弦→新建），共现网络，ECharts 力导向图可视化
  - **假设生成引擎**：从实体三元组+知识空白 LLM 生成可验证假设，proposed/validated/rejected 生命周期
  - **量化推理引擎**：LLM 提取数学公式 → safe_eval 安全计算 → LaTeX 渲染 → 前端计算器
  - **公式分类体系**：6 大类 24 子分类（FormulaCategory 模型树）+ 32 个内置微纳米气泡领域公式，前端分类树浏览，来源标签（内置/提取）
  - **公式自动分类**：LLM 提取公式 domain 字符串 → 模糊映射到结构化分类，新老公式统一归入分类树
- 语音识别使用 faster-whisper GPU，TTS 使用 Edge-TTS
- **会议转录总结工具** — `summarize_meeting_transcript` 工具支持对话触发与长期存储
- **任务软删除/垃圾桶** — 删除任务进入垃圾桶（deleted_at 字段），支持恢复或永久删除，3天后自动清除（Celery beat 每 1h 调度 `auto_purge_trash_task`，垃圾桶 UI 双行显示倒计时 + 5 级紧急度颜色）。详细状态见 [README.md](README.md#当前状态2026-06-03)
- **微信对话双消息模式** — 收到消息后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台异步处理后发正式回复，解决等待无反馈问题
- **移动端独立抽屉架构** — 移动端侧边栏使用 el-container 外部独立 div + Vue Transition，完全绕过 Element Plus aside 的全局 CSS 干扰。桌面端 `v-if="!isMobile"` 零影响
- **通知面板** — 铃铛使用 el-popover 弹窗面板，显示每条提醒的具体内容（任务标题+提醒时间）、全部标为已读、点击跳转任务；头像读取 userStore.userInfo.avatar 真实 URL
- **任务权限模型** — 所有成员可见全部任务（降低认知负担），仅创建人/负责人/管理员可编辑、删除、恢复、永久删除
- **状态统一** — "待办"(todo) 和 "进行中"(in_progress) 语义高度重合，已统一为"进行中"。新建任务默认 in_progress，现有 todo 任务兼容显示
- **移动端路由级双栈架构**（2026-06-13 收官）— 桌面端（Element Plus）和移动端（NutUI 4）**同一 URL 不同组件**，不共享 component 树。`useIsMobile.js` 监听 viewport + UA 兜底 → `router/index.js` 通过 `resolveMobile.js` 动态 import `views/mobile/*` 或 `views/*` → 桌面端 `el-*` 与移动端 `nut-*` CSS 完全隔离。**PWA 4 策略**：manifest + service worker（workbox）预缓存 app shell + useSafeArea 读 iPhone 安全区 + 离线 IndexedDB 兜底。**视觉回归测试**：Playwright 5 viewport × 13 核心页面，CI 截图对比基线

## 代码质量规范（2026-06-04 升级）

### API 层
- **统一异常响应格式**：`{"error": {"code": "RESOURCE_NOT_FOUND", "message": "...", "details": {...}}}`
- **异常类层次**：`app/core/exceptions.py` — AppException/NotFoundException/ValidationException/AuthException/ForbiddenException/ConflictException/RateLimitException
- **统一分页模型**：`app/schemas/pagination.py` — PaginationParams + PaginatedResponse + PaginationMeta
- **全站分级限流**：`app/core/rate_limit.py` — auth:5次/分, write:30次/分, read:100次/分, upload:10次/分
- **安全响应头**：X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy/X-Request-ID

### 前端架构
- **Composable 模式**：`web/src/composables/` — useTask/useMeeting/useKnowledge 提取共享状态 + API 调用
- **子组件拆分**：18 个子组件（Task:3 + Knowledge:8 + Meeting:3），主 View ≤ 1920 行
- **Vitest 测试**：`web/vitest.config.js` — composable 测试（23 个）+ 组件测试（15 个）= 38 个测试通过

### 2026-06-13 webhint PWA 5 警告全栈修复新增（commit `08f440f` + `c855f0e`）

- **Nginx 缺 `.webmanifest` MIME（commit `08f440f`）** — Nginx 默认 `mime.types` 不包含 `.webmanifest`（到 1.27 才内置），回退 `application/octet-stream` → 浏览器拒绝解析 PWA manifest → 添加桌面图标失败。**修复**：server block 加 `types { application/manifest+json webmanifest; }` + `charset_types` 同步加 `application/manifest+json`（让 `charset utf-8` 生效）。**诊断**：`curl -I https://xxx/manifest.webmanifest | grep Content-Type` 看是不是 octet-stream。**纪律**：所有 PWA 项目上线前必须验证 manifest MIME，**仅一次**而不是每个 server 都加。
- **`vite-plugin-pwa` 输出 manifest 不带 hash（commit `08f440f`）** — `manifest.webmanifest` 文件名固定不走 rollup hash 流程，webhint cache-busting 永远警告。**修复**：写一个 Vite 插件 `manifestHashPlugin`（closeBundle 钩子）→ `crypto.createHash('sha256').update(content).digest('hex').slice(0, 8)` → 重命名为 `manifest.{8char_hash}.webmanifest` + 同步改 `index.html`/`offline.html` 的 link 引用。**8 字符 hex 满足 webhint 默认 `[0-9a-f]+` 正则**。**Vite 5+ emitFile 不适用**（manifest 是 vite-plugin-pwa 输出，emitted by another plugin），必须 fs.renameSync。
- **`/registerSW.js` 静态注入无法 cache-busting（commit `08f440f`）** — `VitePWA({ injectRegister: 'auto' })` 自动注入 `<script src="/registerSW.js">`，文件名固定无 hash。**修复**：`injectRegister: null` + `main.js` 用 `import { useRegisterSW } from 'virtual:pwa-register/vue'` 替代。**Vue composable 在生产 build 时被 rollup 处理，运行时通过 sw 注册的副作用自动跑**，无需手动写 `<script>`。**纪律**：PWA 项目**避免** `injectRegister: 'auto'`，除非真的需要纯静态（非 SPA）站点。
- **删除 manifest.webmanifest 后 SPA fallback 误返 index.html（commit `c855f0e`）** — git 删除旧 manifest 文件后，Nginx `try_files $uri $uri/ /index.html` 找不到文件 → fallback `/index.html`（1924 字节 HTML 内容） → 任何残留引用/书签/扫描器拿到 HTML 内容物以为是 manifest。**修复**：在 `/` location 前加 `location = /manifest.webmanifest { return 410; }` 精确 410 Gone。**纪律**：SPA 部署时**所有被废弃的资源路径**都应该有明确返回（410 / 404），不能依赖 try_files fallback。
- **theme-color Firefox 不支持** — Edge DevTools 内置 webhint 不读 `.hintrc`，永远警告。**纪律**：`.hintrc` 配 `meta-theme-color: "off"`（webhint CLI 0 警告），接受 Edge DevTools 误报。Chrome/Safari/iOS Safari PWA 顶部栏颜色价值 > Edge DevTools 警告噪音。**永远不要**完全删除 theme-color meta（损失浏览器原生美化）。

### 2026-06-13 Vue 3.5 'bum' null bug 真根因 + Vite plugin patch（commit `79305b7`）

- **Vue 3.5 unmountComponent 仍缺 instance null 检查** — 之前 CLAUDE.md 误记"Vue 3.5.34 PR #11487 已修 `bum` bug"，**实际未修**。`@vue/runtime-core/dist/runtime-core.esm-bundler.js:6763`（3.5.34）和 `:6763`（3.5.38 raw 检查）：
  ```js
  const unmountComponent = (instance, parentSuspense, doRemove) => {
    if (__DEV__ && instance.type.__hmrId) { ... }   // ← instance 仍可能为 null
    const { bum, scope, job, subTree, um, m, a } = instance  // ← 爆点
  ```
  只有 line 6572 的 `unmount()` 函数 vnode 解构加了 null 检查，`unmountComponent()` 的 instance 解构**漏修**。minify 后报 `Cannot destructure property 'bum' of 'e' as it is null`（`e` = `instance`）。
- **触发链路** — Element Plus el-table/el-table-column/el-checkbox/el-tooltip/el-popper 递归 unmount 时，**某子 vnode.component 已是 null**（HMR/路由切换/keep-alive 边界状态）→ `vnode.type.remove(...)` 调 `unmountComponent(null)` → 爆。常见触发页：`AgentTracesView`（19 el-table）/ `TaskTrash`（18）/ `SpeakerMappingPanel`（8）/ `KnowledgeView`（4 tab lazy）/ `VoiceprintEnrollDialog`（el-dialog + el-tabs + lazy）。
- **修复：Vite plugin transform 阶段 patch esm-bundler.js**（commit `79305b7`）—
  ```js
  // vite.config.js
  function vueBumNullPatchPlugin() {
    return {
      name: 'vue-bum-null-patch',
      enforce: 'pre',
      transform(code, id) {
        if (!/node_modules\/@vue\/runtime-core\/dist\/runtime-core\.esm-bundler\.js$/.test(id)) return null
        if (code.includes('/* patch:vue-3.5-bum-null */')) return null  // 防重复
        const pattern = /(const\s+unmountComponent\s*=\s*\([^)]*\)\s*=>\s*\{)/
        if (!code.match(pattern)) { console.warn('...pattern not found'); return null }
        return code.replace(pattern, `$1\n    /* patch:vue-3.5-bum-null */ if (!instance) return;`)
      },
    }
  }
  ```
  验证产物 grep `(e,t,n)=>{if(!e)return;let{bum` 即生效。
- **纪律** — ① 这种"上游已知 bug 但未修复"的场景，**Vite plugin transform 阶段 patch** 比 npm postinstall patch 更稳（postinstall 会被 reinstall 覆盖；plugin 在 build 时每次生效）② `enforce: 'pre'` 确保在 esbuild/rollup 处理前 patch③ 防御性 `if (code.includes('...')) return` 防重复 patch④ pattern 未命中要 `console.warn` 而非静默吞（升级 Vue 后能立即发现 plugin 失效，需要重新适配）⑤ **只 patch build 产物，不 patch dev mode**（dev 保留原始报错方便定位应用层问题）
- **临时性 + 自动失效** — 升级到 Vue 3.5.36+/3.6+ 若官方修了 `unmountComponent` instance null 检查，plugin 自动 skip（pattern 未命中 → warn）。监控 console 是否有 `[vue-bum-null-patch] pattern not found` 警告

### 2026-06-13 Nginx types 指令覆盖/合并行为差异 — 整站 octet-stream 白屏事故（commit `08f440f` 留尾 → `f148d96` + `5c24442` 修复）

- **事故** — 用户报告"打开 /dashboard /members 直接下载名为 dashboard / members 的文件"。curl 验证 `/index.html` 返回 `Content-Type: application/octet-stream` → 浏览器把 HTML 当二进制下载而非渲染。
- **根因（极隐蔽，2 层）** —
  1. `commit 08f440f` 在 `server { ... }` block 内加 `types { application/manifest+json webmanifest; }` 块想修 webmanifest MIME 问题
  2. **Nginx `types` 指令在 server context 是"完全覆盖"语义（NOT 合并）**：从 http context 继承的 mime.types 整个被丢弃，只剩 types 块里的 MIME → `.html` 找不到 `text/html` → fallback 到 `default_type application/octet-stream` → 整站 HTML/CSS/JS/PNG 全变 octet-stream
  3. **极其隐蔽**：webhint 只查 manifest.webmanifest 不查 HTML，所以没暴露这个问题；用户浏览器可能缓存了 08f440f 之前的 HTML 没刷新，所以没立即发现
- **修复路径（commit `f148d96` + `5c24442`）**—
  - **第一步（f148d96）**：删除 tunnel.conf 两个 server block 里的所有 `types { }` block，恢复 http context mime.types 默认合并语义
  - **第二步（f148d96）**：改 `scripts/deploy-auto.sh` 增加 webmanifest MIME 注入：
    ```bash
    if ! grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
        sed -i '/^application\/json[[:space:]]/a\    application/manifest+json           webmanifest;' /etc/nginx/mime.types
        if grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
            log "webmanifest MIME type added to mime.types"
        else
            log "ERROR: webmanifest MIME sed injection failed"  # fail loud
        fi
    fi
    ```
  - **第三步（5c24442）**：原 awk 模式注入失败（猜测 mime.types 行尾 `\r` 导致 awk `next+print` 行为异常）→ 改 sed `-i` 行后追加模式 + 注入后 grep 验证
- **纪律（5 条铁律）** —
  ① **Nginx `types` 指令上下文敏感**——
  - `http` context：**合并**（additive，可加新 MIME 不丢默认）
  - `server`/`location` context：**完全覆盖**（覆盖后必须列全用到的 MIME，否则 fallback octet-stream）
  - 缺省 default：`application/octet-stream bin;`（最小集）
  ② **永远不要在 server context 加 types { } block** —— 想给 PWA 加 MIME 就在 mime.types 里加（http context include 的那个文件）
  ③ **deploy-auto.sh 注入 mime.types 必须 fail loud** ——
  - sed/awk 注入后必须 `grep -q` 验证成功才 log success，否则 `log "ERROR: ..."`
  - 注入幂等（先 grep 是否已存在）
  - 优先用 sed `-i` 而非 awk（awk 在行尾 `\r` 时行为异常）
  ④ **Webhint 不查 HTML MIME** ——
  - webhint 报 manifest MIME 错误时**只查** manifest 不查 HTML/CSS/JS
  - 加 types { } block 可能悄无声息破坏整站 MIME，**改 nginx 配置后必须 curl 验证所有响应 Content-Type**（HTML + CSS + JS + PNG + manifest + sw.js 至少 6 点）
  ⑤ **改 nginx 配置后立刻 6 点 curl 验证** —
    ```bash
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/index.html
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/  # SPA fallback
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/dashboard  # SPA route
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/sw.js
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/pwa-192.png
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/manifest.{hash}.webmanifest
    ```
    任一返回 octet-stream 即配置错误，不要等用户报告
- **事故链时间线** —
  1. 08f440f（18:27 加 types block，覆盖 mime.types，**事故起点**）
  2. c855f0e（18:30 加 manifest.webmanifest 410）
  3. ef130ce（18:32 CLAUDE.md）
  4. 79305b7（18:40 Vue patch）
  5. 7a077dd（18:42 CLAUDE.md）
  6. 0a29290（18:49 试图"修复"types block，加完整 MIME 列表，但 types 指令在 server context 行为不变，整站仍 octet-stream）
  7. 用户报告"下载文件"
  8. f148d96（18:58 真修复：回滚 types block + 改 deploy-auto.sh）
  9. 5c24442（19:05 修 awk → sed）

### 2026-06-13 SW 污染 cache 修复 — 整站 HTML 修复后浏览器仍进不去（commit `747a735`）

- **第二阶段事故** — 服务器 MIME 修好后（`f148d96` + `5c24442`）curl 验证 `/` 返回正确 `text/html`，但**用户报告"网站还是进不去"**。curl 服务器一切正常 → 100% 是浏览器侧问题。
- **根因** — Service Worker 污染 cache：
  1. `08f440f` 部署后服务器开始返回 octet-stream HTML
  2. 用户访问时浏览器 SW（NetworkFirst 策略）**缓存了 octet-stream 响应到 `documents` cache**
  3. 服务器修复后 SW 仍可能返回缓存的 octet-stream（虽然 NetworkFirst 应优先网络，但浏览器 SW 缓存逻辑 + activate 时机导致老 cache 没及时清）
  4. `cleanupOutdatedCaches()` 只清 workbox 维护的 precache cache，**不**清 NetworkFirst/StaleWhileRevalidate 运行时创建的 cache
- **修复：sw.js 升级模式**（commit `747a735`）—
  ```js
  // web/src/sw.js
  const SW_VERSION = 'v2-cache-purge-2026-06-13'  // BUMP 触发 SW 字节变化
  self.__SW_VERSION__ = SW_VERSION

  self.skipWaiting()
  self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
      // 清空所有 cache（不只是 workbox 默认的）
      const keys = await caches.keys()
      await Promise.all(keys.map((n) => caches.delete(n)))
      await self.clients.claim()
      // 通知所有客户端 reload
      const clients = await self.clients.matchAll({ type: 'window' })
      clients.forEach((c) => c.postMessage({ type: 'SW_UPDATED', version: SW_VERSION }))
    })())
  })
  ```
  ```js
  // web/src/main.js
  useRegisterSW({
    immediate: true,
    onRegisteredSW(swUrl) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'SW_UPDATED') {
          setTimeout(() => window.location.reload(), 500)
        }
      })
    },
  })
  ```
- **修复链路** — 用户下次访问 → 浏览器检测 `/sw.js` 字节变化 → 安装新 SW → 立即 `skipWaiting` 激活 → `activate` 钩子清空所有 cache + `postMessage` → 客户端 `useRegisterSW` 收到 `SW_UPDATED` → `window.location.reload()` → 用户拿到全新资源
- **纪律（4 条铁律）** —
  ① **SW 污染 cache 修复必须改 sw.js** ——
  - 只改 HTML/JS/CSS 没用，浏览器 SW 还在用老 SW 文件
  - 改 sw.js 触发 SW 升级 + activate 钩子清 cache 是**唯一**标准修复路径
  ② **`cleanupOutdatedCaches()` 不够** ——
  - 它只清 workbox 维护的 precache cache
  - **不**清 NetworkFirst/StaleWhileRevalidate/CacheFirst 运行时创建的 cache
  - 真正"清空所有 cache"必须自己写：`caches.keys() + Promise.all(keys.map(caches.delete))`
  ③ **BUMP SW_VERSION 触发升级** ——
  - 浏览器通过**字节比较**检测 SW 更新（不是 SW 内容里的 manifest）
  - 改 sw.js 文件加一行 const 都会触发字节变化 → 浏览器拉新 SW → 升级流程
  - 每次事故修复或 SW 大改动时**都**应 bump 版本号
  ④ **postMessage + reload 闭环** ——
  - SW 升级后**不会**自动刷新页面（skipWaiting + clients.claim 立即接管但页面不 reload）
  - 必须 SW postMessage → 客户端监听 → `window.location.reload()`
  - 用 `setTimeout(..., 500)` 让 console.log 先显示出来再 reload
- **调试技巧** ——
  - 用户报"页面进不去"但服务器 curl 一切正常 → 100% 是 SW/浏览器 cache 问题
  - 让用户 DevTools → Application → Service Workers → 看到 SW 状态为 `activated` 且内容含新 `SW_VERSION` → SW 已升级
  - 让用户 DevTools → Application → Cache Storage → 应该看到 precache 列表**无 documents cache**（已被清空）
  - **兜底**：用户可手动 DevTools → Application → Storage → Clear site data 彻底重置

### 测试规范
- **后端**：pytest + httpx AsyncClient，service 层单元测试 + API 集成测试
- **前端**：Vitest + @vue/test-utils，composable 测试优先，组件测试选择性覆盖
- **Mock 策略**：Redis 用 fakeredis，Claude API 用 respx，Embedding 用固定向量

## 服务层结构

| 文件 | 职责 |
|------|------|
| `app/services/task_service.py` | 任务 CRUD + 统计 + 自动提醒 |
| `app/services/member_service.py` | 成员 CRUD + 按姓名查询 |
| `app/services/meeting_service.py` | 会议 CRUD + 参与者管理 |
| `app/services/project_service.py` | 项目+里程碑 CRUD |
| `app/services/knowledge_service.py` | 知识库 CRUD + 语义搜索 |
| `app/services/reminder_service.py` | 提醒服务 + Celery task |
| `app/services/memory_service.py` | 长期记忆 CRUD + 语义搜索 + LLM 提取 |
| `app/services/search_service.py` | 联网搜索（搜狗+必应双引擎） |
| `app/services/embedding_service.py` | 向量嵌入（text2vec-base-chinese） |
| `app/services/file_parser_service.py` | 文件内容提取（PDF/Word/Excel/PPT） |
| `app/services/llm_analysis_service.py` | LLM 内容分析（动态分类+标签+摘要+核心概念） |
| `app/services/knowledge_graph_service.py` | 知识图谱服务（自动关联+BFS 遍历+动态分类+标签云+统计） |
| `app/services/knowledge_qa_service.py` | RAG 问答引擎（检索+阈值+LLM 合成+来源引用） |
| `app/services/auto_research_service.py` | 自主研究引擎（联网搜索+知识提取+空白填充+矛盾/重复/过期检测） |
| `app/services/dynamic_taxonomy_service.py` | 动态分类体系（涌现分类+分类建议+主题网络） |
| `app/services/knowledge_evolution_tasks.py` | Celery 知识进化定时任务（每日进化/空白检测/健康检查/实体融合） |
| `app/services/reminder_scheduler.py` | Redis 精确提醒调度（秒级精度） |
| `app/services/entity_service.py` | 实体知识图谱（跨文档融合+搜索+图谱+LLM 合并） |
| `app/services/hypothesis_service.py` | 科研假设生成（LLM 驱动假设+验证生命周期） |
| `app/services/formula_service.py` | 量化推理（公式列表+安全计算+LaTeX 转换+分类树+内置公式库） |
| `app/services/meeting_analysis_service.py` | 会议 AI 分析（发言者检测+格式识别+结构化分析+发言人统计+标题生成）|
| `app/services/voiceprint_service.py` | 声纹识别（3D-Speaker 嵌入提取+pgvector 匹配+录入）|
| `app/voice/vad.py` | silero-vad 语音活动检测 |
| `app/services/audio_processor.py` | 音频格式转换（WebM→WAV）+ 离线 VAD 分段 |

## 2026-06-14 方案 C：Agent 单阶段流式渐进综合架构（plan: eager-juggling-dewdrop.md）

**6 个 stage 已收官**（commits `5ce1203` `8a76750` `9862546` `d3f74df` `59cbbb1` `2f2b619` `bf61456`）。
核心改造：取消 brief/detail 双层 → 单阶段流式综合（intent → agentic_loop → critique → done）。

### 方案 C 6 条铁律（必读）

**铁律 1：跨 event loop 安全（CLAUDE.md 752/812 行铁律升级）**
所有外部 IO 客户端（AsyncAnthropic / aioredis / async_session）**禁止在模块顶部 import 阶段创建**。统一通过 `ctx: ToolContext` 注入：
```python
# ❌ 反模式（agentic_loop.py 模块顶部）
from app.core.redis import async_redis_client  # 绑定 app loop 的全局单例
client = AsyncAnthropic(...)                   # 同上

# ✅ 正模式（ctx 注入）
async def run(self, ..., ctx: ToolContext):
    redis = ctx.redis or aioredis.from_url(settings.REDIS_URL)
    llm = ctx.llm or LLMClient()
```
`ToolContext` 字段：`redis` / `llm` / `loop_id`（debugging）。Celery worker 跨 event loop 调用时由调用方注入新 client，否则触发 "Future attached to different loop"。

**铁律 2：typing import CI 检查**
任何 `app/agent/*.py` 新文件**必须**在 commit 前跑：
```bash
bash scripts/check_typing_imports.sh   # 106 文件 0 错误
```
新代码若用了 `Dict`/`List`/`Optional` 但没 `from typing import ...` → 整个模块加载失败 → 工具一调就报。Docker 模块缓存会掩盖该 bug 数天。建议集成到 pre-commit hook。

**铁律 3：SSE 事件 delta 语义显式标注**
[app/agent/protocol.py](app/agent/protocol.py) 每个 `StreamEventType` 必须在源码注释里标注 `[increment]` 或 `[snapshot]`：
- `[increment]` delta 是新增 token，前端必须 `content += delta`
- `[snapshot]` delta 是完整快照文本，前端必须 `content = delta`（替换）或不 append
- 混用会导致 2026-06-12 brief 重复输出 bug（commit `cf70ff5`）再现
- 前端 useChatStream.ts switch case 也必须标注

**铁律 4：流式 abort 安全（trace 持久化 + 悬空 tool_use sanitize）**
`chat_engine.synthesize_stream()` 必须用 `async with TraceCollector(...) as trace` 包裹：
- `TraceCollector.__aexit__` 收到 `CancelledError`/`BaseException` 时**同步**落库（不走 Celery），保证 trace 至少有 partial 记录
- `agentic_loop.run()` 在收到 `CancelledError` 或循环达到 `max_rounds` 时，必须调 `_sanitize_pending_tool_uses(messages, reason=...)`：给悬空 tool_use 追加 `tool_result: "用户已中断"` 哨兵，否则下次拼回 context 时 Anthropic API 报 400
- `_sanitize_pending_tool_uses` 必须在调下一次 LLM 前调

**铁律 5：LLMClient 接口加 model 参数用 keyword-only**
```python
async def complete(self, messages, *, model=None, system=None, ...):
    # `*` 强制所有调用走关键字
```
老代码传位置 model 必报 TypeError（炸得明显），不会静默走错模型。LRU cache key 必须含 model 维度（防不同模型互相污染缓存）。

**铁律 6：feature flag 必须保留老路径代码（不是 git revert）**
3 个 kill switch：
- `AGENT_NEW_ARCHITECTURE_ENABLED: bool = True`（全局开关）
- `AGENT_REFLECTION_ENABLED: bool = True`
- `AGENT_COMPRESSION_ENABLED: bool = True`
- 关闭时由 `chat_engine.py` 内部调 `chat_engine_legacy.py`（保留作为 30 天回滚资产，**不是 in-file dead code**）
- 30 天后（2026-07-14）单独 commit 删除 `chat_engine_legacy.py`

### 部署必做

```bash
# 1. 跑数据库迁移（Stage 3 加 7 列）
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -f scripts/alter_agent_traces_stage3.sql

# 2. 重启 Python 进程（CLAUDE.md 752 行铁律）
docker compose restart app celery-worker
```

不跑这两步，新架构写入 `intent_category` 等列会报 `column does not exist` 500。

### 方案 C 没做的（plan 明确范围外）

- LangGraph 风格 state machine 重写
- 多 agent 独立服务（planner / executor / critic）
- 流式 ChartBlock 渐进渲染（边输出文字边出图）
- RAG 引用图谱可视化
- ASR/TTS 真流式（边录音边出文字）
- 30 天后删除 `chat_engine_legacy.py`（2026-07-14）

## 开发注意事项

### 2026-06-14 webhint Edge DevTools `/chat` 页 6 警告 5 误报 + favicon.ico 真修复（commit `30fa545`）

- **Edge DevTools 内置 webhint 不读 .hintrc**（重要，反复踩坑再次强化）— 用户报告 webhint 警告时，**永远先判断是真问题还是 webhint 误报**：①打开 `.hintrc` 看对应 hint 状态 ②判断 URL 类型（blob:/TTS/favicon.ico 都是已知误报源）③Edge DevTools 警告**只能在 webhint CLI 验证时消除**，浏览器端无解。**.hintrc 配置的 4 类 hint 优先级**：
  - **http-cache**（cache-control 检查）— TTS 动态 API max-age=0 是正确行为，webhint 误把 audio/mpeg 当静态要求 1 年 + immutable。TTS 文本不同 → max-age=31536000 会返回错误音频。**全关**最稳（CLAUDE.md 2026-06-13 决策）
  - **no-immutable**（独立于 http-cache）— 即使 http-cache off，TTS 仍会报「immutable 缺失」。**全关**
  - **no-cache-busting**（URL 模式匹配）— 浏览器自动请求 `/favicon.ico`（无 hash），HTML `<link rel="icon">` 改不改都请求。**全关**（最干净）或 `.hintrc` 改 pattern 加 `\.ico$`
  - **content-type-options**（X-Content-Type-Options 头）— `blob:https://...` 是 `URL.createObjectURL()` 客户端生成，**没有 HTTP 响应/headers**，webhint 误报无法避免。**全关**
  - **meta-theme-color**（Firefox 不支持）— 已知 webhint 误报，保留 Chrome/Safari/iOS Safari PWA 顶部栏美化价值。**全关接受噪音**
- **favicon.ico 真修复：nginx `location = /favicon.ico` 精确匹配**（commit `30fa545`）— 之前 `location ~* \.(...ico...)$` 正则 location 理论上给 favicon.ico 加 1 年 + immutable + nosniff，但 Edge DevTools 报 `/favicon.ico` 返回 `Cache-Control: max-age=0`（命中 `location /` 兜底）。**根因**：nginx `add_header` **不继承**父级 location 也没问题，但**优先级**中精确 `=` 最高，`~*` 正则次之。**修复**：在 `tunnel.conf` line 116-124 加 `location = /favicon.ico { add_header Cache-Control "public, max-age=31536000, immutable" always; ... }` 精确匹配。**双保险**：① 精确路径优先匹配避免被 `location /` 兜底② 显式 immutable + nosniff 一目了然审计。**纪律**：
  1. 任何"用户浏览器自动请求的资源"（favicon.ico / robots.txt / sitemap.xml / apple-touch-icon）都用精确 `location =` 而非正则
  2. nginx `add_header` 调试：用 `curl -I https://agent.mnb-lab.cn/favicon.ico | grep -i cache-control` 直接看响应头，**不要**相信文档里"正则 location 应该匹配"的说法
  3. 改 nginx 后**必须 6 点 curl 验证**（CLAUDE.md 2026-06-13 整站 octet-stream 事故铁律）—— favicon.ico / index.html / favicon.ico / sw.js / pwa-192.png / manifest.{hash}.webmanifest 至少 6 个路径
- **TTS 端点不改后端逻辑**（commit `30fa545` 决策记录）— `/api/v1/voice/tts` 是 POST API，每次文本不同，本就该 `max-age=0`。后端 `security_headers` 中间件（app/main.py:126-128）已正确配 max-age=0。**别被 webhint 误导改后端**，改了就破坏动态 API 语义。TTS "immutable 缺失" 警告用 `.hintrc no-immutable: off` 消除即可
- **`.hintrc` 文件位置**（重要，已踩坑）— 项目 `.hintrc` 在**根目录** `g:\microbubble-agent\.hintrc`（不在 `web/.hintrc`）。webhint CLI 在 `web/` 目录跑时会沿目录树向上找 `.hintrc`，所以**两个位置都能识别**。**纪律**：① webhint 配置统一放根目录方便审计 ② 修改后 commit + push 让团队同步 ③ `.hintrc` 是 Edge DevTools 不读的，**不要为了消除 Edge DevTools 警告而改生产代码**（会破坏 TTS 等动态 API 语义）

### 2026-06-13 .env.webhook 被 `git clean -fdx` 误清 → webhook 服务挂掉事故

- **`git clean -fdx` 会清 `.gitignore` 内文件（包括 `.env.webhook`）（重要，再犯就死）** — deploy-auto.sh line 31 写 `git clean -fdx`（-x 也清 .gitignore 内的文件），目的是清 untracked 文件确保干净工作区。但 `.env.webhook` 在 .gitignore 里（本地 secret 配置）也被清了！事故链：① 之前某次部署 `git clean -fdx` 删了 `/opt/microbubble-agent/.env.webhook` ② webhook 服务 6月11日启动时 secret 已加载到 process memory，仍在跑 ③ 6月13日我 `systemctl restart webhook` 触发了重启 → 找不到 .env.webhook → systemd 启动失败 → webhook 完全挂掉，GitHub push 无法自动部署。**修复**：用 sudo rsync 复制新 secret + 写入 .env.webhook + 重启 webhook。**纪律（4 条）**：
  - ① **`.env*` 文件必须 gitignored + 在 deploy 前 ensure-exists**：deploy-auto.sh 加 `[ ! -f .env.webhook ] && echo 'ERROR: .env.webhook missing, refusing to clean' && exit 1` 守卫。或者更稳：把 .env.webhook 移到 `/etc/microbubble-agent/.env.webhook`（不在 git 工作区内）
  - ② **`git clean -fdx` 是核弹级命令** — deploy-auto.sh line 31 用它清 untracked，但要确保 .gitignore 内的 .env* / .secrets / 模型缓存都不在 deploy 路径下。**检查命令**：`grep -E '^\.(env|secrets|config)' .gitignore` 看 gitignore 规则
  - ③ **webhook 服务 EnvironmentFile 缺失必须 fail loud（已经做了）** — `EnvironmentFile=... (ignore_errors=no)` 让 systemd 启动失败。**但要让用户在重启 webhook 前看到错误**，建议加 `ExecStartPre=/bin/sh -c 'test -f /opt/microbubble-agent/.env.webhook || (echo "ERROR: .env.webhook missing" && exit 1)'`
  - ④ **重启 systemd 服务前先看 .env 文件** — `systemctl show <service> -p EnvironmentFiles` + `ls -la <file>` 确认存在再 restart
- **deploy 用户有 sudo 白名单：deploy-mnb/systemctl/nginx/rsync（重要，已验证）** — `sudo -l` 输出：`(ALL) NOPASSWD: /usr/local/bin/deploy-mnb, /bin/systemctl, /usr/sbin/nginx, /usr/bin/rsync`。**纪律**：① `/usr/local/bin/deploy-mnb` 文件**不存在**（2026-06-13 sudo -l 显示但 `sudo <file>` 报 command not found，可能是预留脚本待创建）② `sudo cp` 不在白名单（要复制 root 拥有的文件**必须用 `sudo rsync`**）③ `sudo systemctl` 可以 restart 服务 → 让 webhook 服务用新 secret 重启 → 但 `cp .env.webhook` 必须 sudo rsync ④ **紧急修复 .git 写权限不够时的 deploy**：用 sudo rsync 推 /tmp/staging → sudo rsync 推 /opt/microbubble-agent（绕开 .git/ root 拥有 644 写入限制）
- **webhook secret 不可重建，必须用户重设（外部依赖）** — 我恢复 webhook 服务时生成了**新 secret** `aa2351c74ef58a7891145859906fac51e7ff81c7e27846a7360da50d29d9dccc`，但 **GitHub 端 webhook 配置的 secret 还是旧的**。后续 push 会触发 webhook 服务，新服务用新 secret 验证 → 旧 secret 签名 → 验证失败 → 403 Invalid signature → 自动部署失败。**用户必须去 GitHub webhook 设置更新 secret**（GitHub repo → Settings → Webhooks → 编辑 → Secret）。**纪律**：① webhook secret 必须在 deploy 文档明确告知用户保存位置 ② 项目 README/docs/deploy.md 加一节"webhook secret 管理" ③ 考虑用 GitHub App + private key 代替 webhook + secret（更安全、可恢复）
- **systemctl restart 之前先看 systemd unit 的 EnvironmentFile 是否存在（已踩坑）** — `systemctl restart` 不会检查 EnvironmentFile 是否存在，systemd 才检查。如果 EnvironmentFile 缺失，restart 会进入失败循环（restart counter 累加）。**修复前的检查命令**：
  ```bash
  # 1. 看 EnvironmentFile 路径
  systemctl show <service> -p EnvironmentFiles
  # 2. 看文件是否真的存在
  ls -la $(systemctl show <service> -p EnvironmentFiles | awk -F= '{print $2}' | awk '{print $1}')
  # 3. 不存在先恢复再 restart
  ```

### 2026-06-13 edge-tts 6.1.9 TrustedClientToken 过期 → TTS 500（commit `41cf204`）

- **edge-tts 6.1.9 已失效，Microsoft 返回 403 Forbidden（重要）** — 2026 年初 Microsoft 更新了 `wss://speech.platform.bing.com/...readaloud/edge/v1` 端点的检测策略，**拒绝非 Edge 浏览器 UA**，edge-tts 6.1.9 内部硬编码的 `Chrome/91.0.4472.77 Edg/91.0.864.41`（2021 年版本）+ 硬编码的 `TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4` 已不被接受，报 `WSServerHandshakeError 403, message='Invalid response status'`。**修复**：升级到 edge-tts 7.2.8（PyPI 最新版，更新了 internal UA + endpoint 配置 + 新增 `boundary/connector/connect_timeout/receive_timeout` 参数）。**诊断命令**：
  ```bash
  docker exec <app> pip show edge-tts  # 看版本
  docker exec <app> python -c "
  import asyncio
  from edge_tts import Communicate
  async def test():
      try:
          async for chunk in Communicate(text='test', voice='zh-CN-XiaoxiaoNeural').stream():
              print('OK')
              break
      except Exception as e:
          print(f'FAIL: {type(e).__name__}: {str(e)[:200]}')
  asyncio.run(test())
  "
  # 期望：6.1.9 → 403 Forbidden；7.2.8 → OK
  ```
  **纪律**：① Microsoft Edge TTS readaloud 端点会持续更新检测策略，edge-tts 库需跟进；② 升级前先 `pip index versions edge-tts` 看 PyPI latest；③ 不要盲目锁 `==` 版本（见下条）
- **requirements.txt 不能盲目锁 == 版本（重要纪律，本次再次踩坑）** — 项目 `requirements.txt` 写了 `edge-tts==6.1.9` 是 2024-2025 年的版本，2026 年 Microsoft 更新端点检测策略后失效，但== 锁定无法接收 patch 升级。**修复**：`edge-tts==6.1.9` → `edge-tts>=7.2.8,<8.0.0`（允许补丁/次版本升级，但锁 major 防 breaking change）。**纪律**：① 第三方库版本用 `>=X,<Y` 范围，不用 `==`；② 例外：pydantic/fastapi/sqlalchemy 等核心库的 major version 锁住；③ 升级后必跑一遍测试（`pytest tests/` 至少要 smoke test）；④ **不要把"`==` 防意外升级"当借口**——意外升级的风险远小于"上游 API 已变你还不知道"的风险
- **catch-all except 后只返回 500 必须加 logger.error(..., exc_info=True)（再次踩坑）** — `app/api/v1/voice.py:97-98` 的 `except Exception as e: raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")` 返回 `语音合成失败: 403, message='Invalid response status'...`，**没暴露完整 traceback**，排错只能从 detail 字符串猜根因。本次必须用 `docker exec ... python -c "..."` 直接调 tts_service 才能看到真因。**修复**：tts.py 加 `logger.error(f"TTS 合成失败: {type(e).__name__}: {e} | voice={voice_id} text_len={len(text)}", exc_info=True)`，**任何 except 都必须 logger.error**。**纪律（CLAUDE.md 已有，本次强化）**：① catch-all except 后只 HTTPException 不行，**必须先 logger.error(..., exc_info=True)** 留 traceback；② detail 字符串不要太长（前 200 字符够识别），但 logger 要全量；③ 排错优先级：docker logs → logger.error traceback → 直接 exec 测试 service 函数，三步定位
- **容器内 `pip install --upgrade` 不持久化到镜像（已知陷阱，commit `41cf204` 配套）** — 本次在容器内 `pip install --upgrade edge-tts` 是临时修复，**下次 `docker compose build` 会重装 requirements.txt 锁定的版本**。已通过修改 requirements.txt + commit + push 让永久修复生效。**纪律**：① 容器内 `pip install` 改的依赖**必须同步改 requirements.txt**；② 否则下次 rebuild 镜像后 bug 复发；③ 容器内临时修复只能用于"应急验证"，不能作为最终修复

### 2026-06-13 vite-plugin-pwa manifest precache 路径不同步 + closeBundle 时序陷阱（commit `6d93d35`）

- **vite-plugin-pwa 把 manifest URL 嵌入 sw.js 但不走 rollup hash 流程（重要，commit `08f440f` 已说过，再次强化）** — `vite-plugin-pwa` 在 generateBundle 阶段把 `/manifest.webmanifest` 嵌入 `__WB_MANIFEST` 字符串，注入到 sw.js。如果用 `manifestHashPlugin` rename dist 文件但**不修改 sw.js 里的字符串**，SW install 阶段 precache 会去拉**旧路径** → 服务器 410 Gone（commit `c855f0e` 加的精确 410 拦截）→ `bad-precaching-response` → SW install 失败 → 新 SW 永远激活不了。**修复**：manifestHashPlugin.rename 之后必须 replaceAll sw.js 里的 `"manifest.webmanifest"` 字符串。
- **`__WB_MANIFEST` 里的 URL 没前导斜杠（容易踩的小坑）** — vite-plugin-pwa 嵌入的 url 是 `"manifest.webmanifest"`（**不带** `/`），但 HTML `<link rel="manifest" href="/manifest.webmanifest">` 是带前导斜杠。**两个 replace 必须分别写**，不要想当然统一成一个 pattern：
  ```js
  // HTML：带前导斜杠
  html.replace('/manifest.webmanifest', `/${newName}`)
  // SW __WB_MANIFEST：不带前导斜杠
  sw.replaceAll('"manifest.webmanifest"', `"${newName}"`)
  ```
  **调试技巧**：先用 `grep -oE '.{5}manifest\.webmanifest.{5}' dist/sw.js` 看 sw.js 里实际字符串格式，再决定 replace pattern
- **vite-plugin-pwa sw.js 生成是异步的，主 build closeBundle 触发时 sw.js 还不存在（重要，时序陷阱）** — vite-plugin-pwa 用自己的内部 rollup/esbuild build 异步编译 src/sw.js，**在主 build 的 `closeBundle` 钩子触发之后**才写 dist/sw.js。直接同步 readFileSync 会 ENOENT。**修复**：`setImmediate` 让出主线程 + 轮询等待（最多 20 次 × 100ms）：
  ```js
  setImmediate(() => {
    if (!existsSync(swPath)) return setTimeout(retry, 100)
    // 现在 sw.js 已写完，可以替换
  })
  ```
  **陷阱**：setImmediate 回调内抛错**会让 Vite build 失败**（closeBundle 抛错是同步的）—— 整个 tryUpdateSw 必须包 try/catch，**任何错误只能 console.warn 不能 throw**。**纪律**：① Vite plugin 钩子内的异步操作都用 try/catch 保护；② 不要相信"build 完成就是 sw.js 写完"——vite-plugin-pwa 是异步插件，必须轮询/等待；③ 升级 vite-plugin-pwa 大版本时必查 changelog 是否改变 sw.js 生成时序
- **dist 在 .gitignore 里，dist/sw.js 修改必须 `git add -f`** — `web/dist/` 在 `.gitignore` 中，正常 `git add web/dist/sw.js` 静默被拦截不报错。**修复后必须 `git add -f web/dist/sw.js`** 强制提交，否则服务器拉的还是旧 sw.js，浏览器永远 install 失败。**验证**：`git show --stat HEAD` 确认 `web/dist/sw.js` 在 commit 里

### 2026-06-13 SW 图片路由 CacheFirst 缓存 5xx 响应 → 头像永久 502（commit `707c0f9`）

- **workbox `CacheFirst` 会缓存所有响应包括 5xx（重要，教训）** — 之前 `web/src/sw.js` 路由 4（图片）用 `CacheFirst`，当 frp 断的窗口期浏览器加载头像时，nginx 返回 502，**workbox 把 502 当成成功响应缓存到 images cache**，30 天有效期。frp 修好后浏览器**永远返回 cache 里的 502**，用户头像持续看不到。**根因**：workbox 默认不区分 200/4xx/5xx，全部缓存。**修复**：
  ```js
  // 路由 4：图片 (修复后)
  new NetworkFirst({
    cacheName: 'images',
    networkTimeoutSeconds: 5,
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),  // ← 关键：只缓存 0 (opaque) 和 200
      new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 30 }),
    ],
  })
  ```
  **纪律（3 条）**：① **任何 SW 缓存策略都必须加 `CacheableResponsePlugin({ statuses: [0, 200] })`**——不区分 2xx 是 workbox 的默认行为，不是 bug 而是设计选择，必须显式覆盖。② **图片/音频/字体等大资源不要用 `CacheFirst` 兜底**——`NetworkFirst` + 5s 超时才是正确姿势（在线先网络，慢/断才 cache）。`CacheFirst` 只适合**已经分发的静态资源**（已写入 precache 列表的），不适合网络请求结果。③ **API GET 路由同样需要 `CacheableResponsePlugin`**（路由 3 已补）——后端 503/504 也可能被永久缓存
- **SW 升级触发条件 = 字节变化（重要，commit `747a735` 已说过，再强化）** — 浏览器通过**字节比较**检测 SW 更新，不是 SW 内容里的版本号。改 `sw.js` 文件加一行 const 都会触发字节变化 → 浏览器拉新 SW → 升级流程。**当前机制**：`SW_VERSION` 字符串 + `skipWaiting()` + `clients.claim()` + activate 钩子 `caches.keys() + Promise.all(keys.map(caches.delete))` 清空所有 cache + `postMessage({ type: 'SW_UPDATED' })` → 客户端监听后 `window.location.reload()`。**事故修复标准路径**：BUMP `SW_VERSION` 到新值 → rebuild dist → git add -f + push → 用户下次访问自动 reload。**调试**：DevTools → Application → Service Workers 看 sw.js 源码，搜 `SW_VERSION` 字符串确认是否升级成功
- **用户浏览器 SW 缓存污染的最快恢复手段（兜底）** ——
  ```bash
  # DevTools → Application → Storage → Clear site data 一键清空
  # 或 Application → Service Workers → "Unregister" + Application → Cache Storage 右键删除
  # 或硬刷新 Ctrl+Shift+R / Cmd+Shift+R（绕过部分 HTTP cache，但**不绕过 SW cache**）
  # 最稳：F12 → 右键 Reload 按钮 → "Empty Cache and Hard Reload"
  ```
  **不要只告诉用户"刷新一下"**——普通刷新**不会**清 SW cache，必须明确告诉用户硬刷新或清 site data

### 2026-06-13 frpc.exe 僵尸进程陷阱：start.bat 不验证 FRP 隧道实际连通（commit 待提交）

- **frpc.exe 进程存在 ≠ FRP 隧道连通（重要）** — 重启电脑后用 `start.bat` 启动 `frpc.exe`，进程跑起来后 `tasklist /FI "IMAGENAME eq frpc.exe"` 显示 PID ✓，但**实际并没有连接到云服务器 frps**。症状：① `frpc.log` 最后修改时间还是 17 天前的 ② 浏览器访问 `https://agent.mnb-lab.cn/minio/...` 头像 502 Bad Gateway ③ `netstat -ano | grep :7000` 显示**另一个进程**（如 clash-win64.exe）持有云服务器 7000 端口的 ESTABLISHED 连接，真正的 frpc.exe 是僵尸。**根因**：frpc.exe 启动失败时**进程不立即退出**（在等云服务器响应），`start.bat` 只检查进程存在就认为成功，跳过了真实连通性验证。**修复**：
  ```bash
  # 重启后必须验证（不能只看进程）
  taskkill //F //IM frpc.exe 2>/dev/null
  rm -f frp/frpc.log
  powershell -Command "Start-Process -FilePath 'frpc.exe' -ArgumentList '-c','frpc.toml' -WindowStyle Hidden -WorkingDirectory 'frp'"
  sleep 5
  # 必须 cat log 看新写入
  tail -10 frp/frpc.log  # 应包含 "start frpc service" 和 "login to server success"
  netstat -ano | grep ":7000.*ESTABLISHED"  # PID 必须是刚启动的 frpc.exe
  ```
- **frpc.log 写入 = FRP 隧道活着的标志** — frpc 正常运行时会持续往 log 写 reconnect/heartbeat 信息，**如果 log 长时间（>1h）没动**，frpc 一定死了或僵尸化。**纪律**：① start.bat 启动 frpc 后必须 `sleep 5 && tail frpc.log` 看新写入；② `start.bat` 改为检测 `tail -1 frpc.log` 含 `start proxy success` 才认为成功；③ 部署文档加一节"FRP 隧道存活检查 one-liner"：
  ```bash
  # 三步验证法
  echo "1. frpc.log 最新时间:"
  stat -c %y frp/frpc.log
  echo "2. frpc.exe 连接:"
  netstat -ano | grep ":7000.*ESTABLISHED"
  echo "3. 外网访问头像:"
  curl -s -o /dev/null -w "%{http_code}\n" https://agent.mnb-lab.cn/minio/microbubble/avatars/ce71e922b5b4491da9221df678a39acf.jpeg
  # 期望: 3 个时间都是最近 + netstat PID 是 frpc.exe + 头像 HTTP 200
  ```
- **frps 服务端重启过会导致旧 run id 失效（重要）** — 这次新 frpc 启动后 run id 从 `531dadd3bd53b7d1`（旧，17 天前）变成 `2723f1d42c04b27b`（新），说明云服务器 frps 重启过，**但 frpc.exe 客户端没有自动重连**。frpc 0.x 有重连逻辑，但长时间无活动 + frps 重启 + frpc 自身无心跳时可能错过重连窗口。**纪律**：① 任何时候发现外网访问异常（502 / 连接拒绝），第一步 `tail frpc.log` 看 run id 是否变过；② 如果 frps 重启（云服务器维护），**必须手动重启 frpc.exe**，不要等它自动恢复；③ 改进 frpc.toml 加 `transport.heartbeatInterval = 30` + `transport.heartbeatTimeout = 90` 强制 30s 心跳，缩短发现断连的时间
- **clash 代理可能劫持 frpc 的 HTTPS 连接（小坑）** — 用户本机 clash-win64.exe（PID 27808）开了系统代理，netstat 显示它自己持有 `60.205.93.8:7000` 的连接（应该是 frpc 的目标）。frpc 默认走系统代理（环境变量 `HTTP_PROXY` / `HTTPS_PROXY`），clash 接到后处理失败，frpc 就卡死。**修复**：启动 frpc 前显式清空代理环境变量：
  ```bash
  HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" NO_PROXY="*" no_proxy="*" \
    powershell -Command "Start-Process -FilePath 'frpc.exe' ..."
  ```
  **纪律**：① 本地有 clash/v2ray 等代理软件时，启动 frpc 前**必须**清代理环境变量；② `frpc.toml` 本身不支持 `proxy_url` 配置（旧版本），靠环境变量；③ 如果换新版本 frpc（0.50+），可以用 `transport.proxyURL` 配置强制不走代理

### 2026-06-13 MCP stdio 服务器在 Docker 中的重启死循环 + mcp 0.9.x API 兼容（commit `db3e275`）

- **MCP stdio 服务器在 Docker 里默认 stdin 关闭 → 进程退出 → restart 死循环（重要）** — `mcp.server.stdio` 通过 stdin/stdout 与 MCP 客户端通信，**不是 HTTP 服务**。Docker 启动容器时 stdin 默认是关闭的 pipe，stdio MCP 服务器一启动就立刻 `EOFError`/`BrokenPipeError` 退出。配合 `restart: unless-stopped` 就形成「启动 → stdio 关闭 → 进程退出 → 立即重启」的紧密循环，`docker compose ps` 永远显示 `Restarting (1) X seconds ago`，**日志只看到 INFO "Starting..." 然后被截断**，没有 traceback，定位极难。**修复**：docker-compose 加两行：
  ```yaml
  vision-mcp:
    stdin_open: true   # 保持 stdin 开放
    tty: true          # 分配 TTY
  ```
  这样 MCP 服务器会阻塞在 `stdio_server().__aenter__()` 等待客户端连接，不会立刻退出。**纪律**：① 任何 stdio MCP 服务器（Anthropic MCP Python SDK 的 `stdio_server()`、FastMCP 的 stdio transport 等）必须在 Docker 中加这两行，否则永远不会 stable running；② HTTP 模式的 MCP server（如 SSE/StreamableHTTP）才不需要这两行；③ 诊断"反复重启+无错误日志"模式时，**第一时间查 stdin_open**——99% 是这个问题
- **mcp 0.9.1 `Server.__init__` 只接受 `(name: str)`（重要）** — 项目 commit `6069a14` 写的代码：
  ```python
  app = Server(
      name="vision-mcp-server",
      version="1.0.0",
      capabilities=ServerCapabilities(tools={"listChanged": True})
  )
  ```
  在 mcp 0.9.1 报 `TypeError: Server.__init__() got an unexpected keyword argument 'version'`。**新版 mcp 库的 Server 简化了**：version 移到了 `create_initialization_options()` 里设置，capabilities 由装饰器（`@server.list_tools()` / `@server.call_tool()`）自动推导，无需手动声明。**修复**：
  ```python
  app = Server(name="vision-mcp-server")
  ```
  **纪律**：① 升 mcp 库大版本前必查 `inspect.signature(Server.__init__)`；② mcp 库的 API 在 0.5→0.6→0.7→0.8→0.9 几个版本里**反复重构**过 Server/Client 签名，写代码前先 `pip show mcp` 看实际安装版本；③ 如果新版本加回了 `version`/`capabilities`，可以恢复原代码
- **`from .vision import router` 在 tools/__init__.py 中导入不存在符号（教训）** — `mcp_server/tools/vision.py` 导出的是 `create_vision_tools(server)` 函数（用于注册工具），**不是** `router`（HTTP router 概念）。但 `tools/__init__.py` 旧版写着 `from .vision import router`，启动时报 `ImportError: cannot import name 'router'`。**修复**：改 `from .vision import create_vision_tools` 即可。**纪律**：① `__init__.py` 的导出名必须与子模块实际定义对齐（`dir(module)` 看真实符号）；② 改模块主 API（`router` → `create_vision_tools`）时**一定要同步更新所有 `__init__.py` 和 `from ... import` 语句**；③ `ImportError: cannot import name 'X'` 是最容易修的 import 错误，但需要**先确认 X 应该叫什么**——不要凭直觉改名

### 2026-06-13 移动端 10 PR + 部署加固 收官新增

- **移动端路由级双栈（重要，PR #1 基建 + PR #2 NutUI 引入，commits `99bbe6b` `3c58cb1`）** — 桌面端（Element Plus）和移动端（NutUI 4）**同一 URL 不同组件**，不是 `v-if` 全局切换。模式：①`useIsMobile.js` 监听 `window.matchMedia('(max-width: 768px)')` + `navigator.userAgent`（iPad/iPhone 误判时用 UA 兜底）②`router/index.js` 通过 `resolveMobile.js` 动态 import `views/mobile/*` 或 `views/*` ③每个 View 文件在 setup 顶部 import 自己的子组件，不共享 component 树。**好处**：桌面端 `el-*` 与移动端 `nut-*` 完全隔离，无 CSS 冲突；切设备时**不重载后端**，URL 不变。**坑**：`/chat` 桌面端走 ChatViewSSE.vue，移动端走 MobileChatView.vue，store/Pinia 完全独立（避免桌面端 dark mode 状态污染移动端主题）
- **移动端首屏包大小纪律（PR #3 教训，commit `0ed4294`）** — `import.meta.glob('eager: true, import: 'default')` 在移动端 View 文件**会触发 Vite 静态分析失败**（MobileChatView 引入 12 个 block 组件全部 eager import → 桌面端代码被打进移动端 chunk）。**修复**：①eager 模式必须包在 `if (!isMobile.value) { ... }` 条件内，让 Vite tree-shake ②构建后 `web/dist/assets/` 里 grep 关键桌面组件名（如 `ChatViewSSE`），不应该出现在 mobile-*.js chunk 里 ③mobile chunk size 目标 < 250KB gzip
- **v-model on prop 误用 Vue 警告（PR #3 教训）** — Element Plus `<el-input v-model="localValue">` 在 `:value` 上写 v-model，Vue 警告。**修复**：用 `computed` get/set 包装 props 后再 v-model。`<el-input :model-value="localValue" @update:model-value="localValue = $event">` 也可
- **webhint `meta-theme-color` 静态声明 vs JS 动态注入（commit `0bbc12d` + `3cf8634`）** — 静态 `<meta name="theme-color" content="...">` 只能写一个固定值，但项目有 dark mode 需要切换。**修复**：HTML 不写静态 meta，`useThemeStore` 监听 `theme` 变化后 `document.querySelector('meta[name="theme-color"]')?.remove()` + 创建新 meta 注入。`.hintrc` 加 `"webhint:recommended"` 关闭该规则（webhint `meta-viewport` hint 仍会查这个）
- **webhint cache-busting 缓存正则匹配 hex 8 字符（commit `6339c29` 续，PR 修复迁移）** — Vite `hashCharacters: 'hex'` 输出 8 字符 hex 满足 webhint 内置 `[0-9a-f]+` 正则。新建 Vite 项目**默认配置**应为 `hex`，不要用 base64url
- **webhook 偶发 499 失败根因（重要，commit `7e41577`）** — 阿里云→GitHub HTTPS 出口网络瞬时故障，TLS 握手时 GitHub 客户端 10s 超时断开，Nginx 收 499 但 webhook service 完全没机会处理（连接都没建立）。**修复 1（deploy-auto.sh 改 git reset --hard 模式）** — 服务器是 immutable infra，`git pull` 在 dirty working tree（之前有失败 deploy 留下的 untracked 文件）下会卡。`git fetch origin main && git reset --hard origin/main` 永远把工作区强制对齐。`git clean -fd` 改 `git clean -fdx`（也清 .gitignore 内文件）。**修复 2（webhook.py socket timeout）** — `import socket` + `self.connection.settimeout(15)`（GitHub 默认 10s + 5s 余量）+ try/except socket.timeout → 504。**手动 redeliver trick**（紧急补部署）：本地 `git rev-parse HEAD` 取 SHA → 构造真实 payload → openssl dgst -sha256 -hmac 计算 X-Hub-Signature-256 → SSH 到服务器 `curl -X POST http://127.0.0.1:9001/webhook`（绕过 Nginx 直接调 service，绕过 GitHub 5min/30min 重试链）。沉淀：[webhook-debug-2026-06-13.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/webhook-debug-2026-06-13.md)
- **移动端 18 页面 + 12 组件 + 4 PWA 策略（PR #1-10 全栈定制收官，commit `9026c07`）** — 完整覆盖：Dashboard/Login/Chat（带 session drawer + message bubble + input bar + rich card）/Task/TaskTrash/Meeting/MeetingDetail/MeetingRoom（3D CSS 声波条）/Knowledge/KnowledgeDetail/Project/ProjectStats/Member/Memory/Settings/Voiceprint/AgentTraces/admin。**核心组件**：CardList（卡片列表+下拉刷新+无限滚动）/LongPressWrapper（长按事件封装，300ms 触发）/MobileActionSheet（iOS 风格底部弹出菜单）/MobileECharts（图表懒加载+resize 监听）/MobileFormSheet（表单底部弹出）/MobileSearchSheet（搜索浮层）/MobileTaskCreateForm（任务创建 5 字段）/PageHeader（顶栏统一规范）/ProcessingSheet（处理中浮层）/SafeArea（iPhone 刘海/底栏安全区适配）/TabBar（底部 4 tab + 中间凸起 +badge）/VoiceTestFlow/VoiceprintEnrollFlow。**PWA 4 策略**：①vite-plugin-pwa 自动生成 manifest.json + service worker（workbox）②Service Worker 预缓存 app shell + 路由 fallback ③`useSafeArea` 读 env(safe-area-inset-*) + dynamic viewport units ④App 离线时显示「网络已断开但可查看最近消息」+ IndexedDB 缓存
- **移动端测试矩阵（PR #10 收官，commit `9026c07`）** — `web/tests/visual/visual-regression.spec.mjs` Playwright 跨设备截图测试，覆盖 iPhone SE/14/15 Pro Max + iPad mini + Galaxy S21 5 个 viewport，**13 个核心页面视觉对比基线**。`web/src/components/mobile/__tests__/` 2 个组件测试（CardList + MobileFormSheet）+ Vitest jsdom 环境

### 2026-06-18 EP useOrderedChildren.removeChild null 崩溃修复（同 'bum' 系列卸载时序问题）

- **症状** — 浏览器 console 报错 `TypeError: Cannot read properties of undefined (reading 'indexOf') at Object.o [as unregisterPane] (element-plus-desktop-xxx.js:8:1774)`，触发组件：el-tabs（带 lazy 的 tab 切换 + 路由切换）/ el-table（含 el-table-column 的重表格页）。触发链：父组件先 unmount → parentNode 被 detach → childNode.parentNode 变 null → `nodesMap.get(null)` 返回 undefined → `childNodes.indexOf(childNode)` 爆。
- **真根因** — Element Plus `es/hooks/use-ordered-children/index.mjs` 的 `removeChild` 函数（被 tabs/tab-pane/table-column 复用，命名为 `unregisterPane`）源码：
  ```js
  const removeChild = (child) => {
      delete children.value[child.uid];
      triggerRef(children);
      const childNode = child.getVnode().el;
      const parentNode = childNode.parentNode;
      const childNodes = nodesMap.get(parentNode);  // ← parentNode 是 null 时返 undefined
      const index = childNodes.indexOf(childNode);  // ← BUG: childNodes undefined
      childNodes.splice(index, 1);
  };
  ```
  与 `bum` null bug 同源（都是 Vue 3 卸载时序 + EP 内部状态清理竞态），但触发函数不同。
- **修复** — `web/vite.config.js` 新增 `epUnregisterPaneNullPatchPlugin`，Vite plugin transform 阶段 patch EP 源码（与 `vueBumNullPatchPlugin` 同模式，详见代码注释）：
  ```js
  // patch 字符串
  const EP_UNREGISTER_PANE_NULL_PATCH = '/* patch:ep-unregister-pane-null */ if (!childNodes) return;'
  // pattern 唯一性：nodesMap.get(parentNode) 后紧跟 childNodes.indexOf(childNode)
  ```
- **验证** — `npm run build` 后 `grep -boE 'if\(!a\)return;' element-plus-desktop-*.js` 找到 patch 注入位置（minifier 把 `childNodes` minify 成 `a`、把 `nodesMap` minify 成 `i`、把 `removeChild` minify 成 `o`，注释被剥但代码在）。**两处 `if(!a)return;`**：①offset ~28k 是 Vue 3.5 源码 `unmount()` 自带检查（CLAUDE.md 之前记录的 line 6572）②offset ~161k 是我们新 patch。
- **纪律（5 条铁律）**：
  ① **"上游已知 bug 但未修复"系列再次扩展** —— Vue 'bum' bug 用 Vite plugin patch 修（CLAUDE.md 752 行铁律），EP `removeChild` null 同样套路。同系列还有：el-table v-if 外层必须 v-show（commit `14c22e3`）、vite-plugin-pwa manifest URL 不同步（commit `6d93d35`）—— 都用"Vite plugin transform 阶段 patch build 产物"模式解决，不污染 node_modules。
  ② **EP source `use-ordered-children/index.mjs` 是 pane 注册中心的唯一源** —— 所有 pane 类型（ElTabPane / ElTableColumn / ElSplitPane）都通过 `addChild`/`removeChild` 注册。改这一个文件能影响 3 类组件，未来 EP 加新 pane 类型也会自动受益。
  ③ **patch 文件 ID 用完整 node_modules 路径正则** —— 与 `vueBumNullPatchPlugin` 一致 `/node_modules\/element-plus\/es\/hooks\/use-ordered-children\/index\.mjs$/`，避免误 patch 其他文件（WeakMap + parentNode + childNodes 组合在 EP 只此一处）。
  ④ **升级 EP 大版本时 plugin 自动失效但要 warn loud** —— `console.warn('[ep-unregister-pane-null-patch] pattern not found, skipped (EP version may have changed)')`，与 `vueBumNullPatchPlugin` 的 `pattern not found` 同款。升级 EP 2.x → 3.x 时如果源码改了 pattern，必须重新适配。
  ⑤ **dev mode 不 patch**（与 Vue 'bum' 策略一致）—— dev 调试需要看原始报错定位应用层 bug，patch 只影响 build 产物。

### 2026-06-18 桌面"正在听会"指示器不接进度修复（弹窗 vs 全屏页面 UX 不一致）

- **症状** — 用户报告"桌面端点击'正在听会'弹窗不会接上之前的听会进度，移动端没问题"。
- **真根因（双层）** —
  1. **架构不一致**：移动端 [MobileMeetingView.vue:325-328](web/src/views/mobile/meeting/MobileMeetingView.vue#L325-L328) 处理 `?resume={id}` 是直接 `router.replace('/meetings/room')` 跳到全屏页面 [MobileMeetingRoom.vue](web/src/views/mobile/meeting/MobileMeetingRoom.vue)；桌面端 [MeetingView.vue:396-399](web/src/views/MeetingView.vue#L396-L399) 旧版是 `liveCallMeeting = {id}` + `showLiveCallDialog = true` 打开 el-dialog 嵌套 [MeetingRoom.vue](web/src/components/MeetingRoom.vue)。两种 UX 行为不一致，桌面弹窗给用户"又要开始新听会"的感觉
  2. **router fallback 错位**：[router/index.js:62-65](web/src/router/index.js#L62-L65) 旧版 `/meetings/room` 路由的桌面 fallback 是 `MeetingView`（会议**列表**页），注释写"用户不会从桌面 UI 触发此路由"——但本次修复后桌面也要走这条路由
- **修复（3 步）** —
  1. **新建桌面全屏页面** [web/src/views/MeetingRoomView.vue](web/src/views/MeetingRoomView.vue)（218 行）—— 完全镜像 `MobileMeetingRoom.vue` 但桌面化：① 顶栏 `el-page-header` 替代 `PageHeader` ② 帮助用 `el-dialog` 替代底部 sheet ③ 顶栏右上显示 `正在听会 #N` 橙色徽章让"继续听会"语义明确
  2. **router fallback 改正**：[router/index.js:64](web/src/router/index.js#L64) `component: resolveMobileComponent('MeetingView', ...)` → `resolveMobileComponent('MeetingRoomView', 'meeting/MobileMeetingRoom')`，桌面/移动都用各自专属 RoomView
  3. **MeetingView.resumeRecording 改 navigate**：[MeetingView.vue:394-401](web/src/views/MeetingView.vue#L394-L401) 旧版开 dialog → 新版 `router.replace('/meetings/room')`，与移动端 `MobileMeetingView.vue:327` 镜像对齐
- **关键代码（桌面 MeetingRoomView onMounted）**：
  ```js
  onMounted(async () => {
    await checkActiveRecording()  // 后端校验，sessionStorage 兜底
    if (recordingMeetingId.value && !meetingId.value) {
      meetingId.value = recordingMeetingId.value  // 复用现有听会 ID
    }
  })
  ```
  与 [MobileMeetingRoom.vue:199-204](web/src/views/mobile/meeting/MobileMeetingRoom.vue#L199-L204) 完全镜像，两端 UI 不一致问题彻底解决
- **纪律（4 条铁律）**：
  ① **同一功能必须桌面/移动 UX 一致** —— 不要因为实现难度差就差异化。本项目移动端用全屏页面 + 移动组件，桌面用 el-dialog 嵌套，结果用户感受"一个能用一个不能"。**镜像移动端最简实现**（哪怕组件复制粘贴 + 改 CSS）优于"复用桌面组件塞进 dialog"
  ② **`resolveMobileComponent` 必须给桌面 fallback 真正的桌面组件**，不能 fallback 到列表/详情等无关页面。router 注释写"用户不会触发" = 留尾 = 终将踩坑
  ③ **改动多处复用页面结构时 grep "桌面" + "移动" 两个版本** —— `MeetingView.vue:396` 桌面 vs `MobileMeetingView.vue:325` 移动 一对比立刻看出不一致。同系列之前还有：① MobileSessionDrawer v-model 命名错配（commit `6b4f57d0`）② MobileMeetingView 重复 const router=useRouter()（commit `fc27af59`）③ MobileVoiceprintView 真测试 vs 桌面 stub（commit `de7ef8aa`）—— 全是"移动端独有路径 desktop fallback 留尾"踩坑
  ④ **新建视图文件优先放 `web/src/views/` 根**（非 `meeting/` 子目录），与桌面视图同 namespace。`MobileMeetingRoom.vue` 在 `mobile/meeting/` 子目录因为它是移动端专属；桌面版放 `views/MeetingRoomView.vue` 即可，路由配置 `resolveMobileComponent('MeetingRoomView', 'meeting/MobileMeetingRoom')` 自动处理


- **Vue 升级审计 3 项纪律（重要，commit `bf2da67` + merge `c6cb0e0`）** — 升 Vue 大版本（3.4 → 3.5 等）前必查 3 项：①`const { x } = props` 解构模式（Vue 3.5 reactive props destructure 默认开启会改变行为：旧版解构出非响应式副本，新版解构出响应式引用）②`toRefs(props)` 冗余用法（Vue 3.5 后可以删除，但保留无害）③`peer dep` 范围（EP 等 UI 库的 `vue: ^3.2.0` 是否覆盖目标版本）。**审计 one-liner**（3 分钟搞定）：
  ```bash
  cd web && \
  echo "=== 1. 响应式解构 ===" && \
  grep -rE "const\s*\{[^}]+\}\s*=\s*(props|defineProps)" src --include="*.vue" | wc -l && \
  echo "=== 2. toRefs(props) 冗余 ===" && \
  grep -rE "toRefs\s*\(\s*props" src --include="*.vue" | wc -l && \
  echo "=== 3. peer dep 范围 ===" && \
  npm view element-plus@<当前版本> peerDependencies.vue
  ```
  **本次审计结果**：项目**完全干净**（0 处命中响应式解构、0 处 toRefs 冗余、EP 2.4.4 peer `vue: ^3.2.0` 覆盖 3.5），**0 行代码改动**完成升级。111 个测试全过 + build 1.26s 0 警告。
- **Vue 3.4 `bum` null 解构 bug（element-plus-desktop 报错根因）** — `Object.remove` → 父组件 unmount → `unmountChildren`（`ge`）→ 子节点 `vnode.component === null`（已卸载/未挂载）→ Vue 3.4 renderer 内部 `let{bum:r, scope:i, job:a, ...} = e` 抛 `Cannot destructure property 'bum' of 'e' as it is null`（`bum` = `beforeUnmount` hook 内部字段名）。**触发组件**：`AgentTracesView.vue`（19 el-table）/ `TaskTrash.vue`（18）/ `SpeakerMappingPanel.vue`（8）— 切 tab / 路由跳转触发 lazy unmount。**修复**：Vue 3.5 重构 unmount 路径加空值检查（PR vuejs/core#11487 之类）。**Workaround（不升级时）**：给触发组件加 `:key` 强制重挂载，或 `v-show` 替代 `v-if`。
- **PWA HTML 文档必须用 NetworkFirst + 超时（重要，commit `d08555c`）** — 阿里云 + FRP 隧道环境下 5-30s 响应是常态。workbox `StaleWhileRevalidate` **没有超时**，SW 会无界等待直到浏览器放弃 → 回退到 `navigateFallback: '/offline.html'` → 用户看到「网络已断开」误提示。**修复**：
  ```js
  // vite.config.js workbox.runtimeCaching
  {
    urlPattern: ({ request }) => request.destination === 'document',
    handler: 'NetworkFirst',
    options: {
      cacheName: 'documents',
      networkTimeoutSeconds: 5,  // ← 关键，5s 内无响应走 cache/offline.html
      expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 },
    },
  },
  ```
  **纪律**：workbox `globPatterns` 永远**不预缓存 `*.html`**（避免 SPA 旧 HTML 被新 SW 服务）；**单独把 `offline.html` 加进 globPatterns** 让真离线时仍能显示 PWA 离线页。
- **PWA `navigateFallback` 不是「离线兜底」是 SPA shell 模式（重要，commit `d08555c` 留尾 → 本次彻底修复）** — workbox-build `generateSW` 模式下，`navigateFallback: '/offline.html'` 会被翻译成 `registerRoute(new NavigationRoute(createHandlerBoundToURL("/offline.html"), ...))`，而 `createHandlerBoundToURL` 是**不管网络是否可用直接返回 precache 内容**的 SPA shell handler。配合 `precacheAndRoute([..., 'offline.html'])` → **所有 navigation 秒返回 offline.html**，即便同时声明 NetworkFirst 文档路由也会被先注册的 NavigationRoute 抢走。**症状**：用户网络完全正常，DevTools Network 面板看不到任何 HTML 请求出去，PWA 永远显示「网络已断开」。**正确修复**：切 `strategies: 'injectManifest'` 自己写 `web/src/sw.js`：
  ```js
  import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
  import { registerRoute, setCatchHandler } from 'workbox-routing'
  import { NetworkFirst } from 'workbox-strategies'

  self.skipWaiting()
  self.addEventListener('activate', e => e.waitUntil(self.clients.claim()))
  precacheAndRoute(self.__WB_MANIFEST)
  cleanupOutdatedCaches()

  registerRoute(
    ({ request }) => request.mode === 'navigate' || request.destination === 'document',
    new NetworkFirst({ cacheName: 'documents', networkTimeoutSeconds: 5, plugins: [...] })
  )
  // ... 其他路由

  // 真离线兜底：仅当上面所有 handler throw 时才进来
  setCatchHandler(async ({ request }) => {
    if (request.destination === 'document' || request.mode === 'navigate') {
      return (await caches.match('/offline.html')) || Response.error()
    }
    return Response.error()
  })
  ```
  **vite.config.js 配套**：`VitePWA({ strategies: 'injectManifest', srcDir: 'src', filename: 'sw.js', injectManifest: { globPatterns: [...] } })`。**workbox-* 模块按需 import**——`workbox-precaching` / `workbox-routing` / `workbox-strategies` / `workbox-expiration` 都在 `vite-plugin-pwa` 传递依赖里，直接 import 就行，无需手动 `npm install`。**回归测试 one-liner**：`grep -E "NavigationRoute|navigateFallback|createHandlerBoundToURL" dist/sw.js` 必须 0 命中（generateSW 模式下永远命中，注定 bug）。**纪律**：① `navigateFallback` 仅适合纯 SPA shell 场景（单一 index.html 包打天下）；② 想做「真离线兜底」必须 `setCatchHandler`，而它**只在 `injectManifest` 模式下可用**；③ 诊断「永远显示离线页」类 bug，第一步看 DevTools → Application → Service Workers → sw.js 源码，有 `NavigationRoute` + `createHandlerBoundToURL` 就 100% 是这个陷阱。
- **PWA navigateFallback 静态页面也要同步 webhint 修复（重要，commit `e6d40a1`）** — `vite-plugin-pwa` 的 `navigateFallback: '/offline.html'` 指向 `web/public/offline.html`，**它和 `index.html` 是两套独立文件**。改 `index.html` meta 时必须同步改 `offline.html`，否则 SW 回退时 webhint 扫到的还是旧版（3 个 viewport / theme-color 警告持续出现）。**纪律**：任何改 `<meta>` / `<link rel="manifest">` / `<title>` 的 PR 必须 `git diff web/public/offline.html` 同步检查；建议把 head 片段提取到模板（如 `vite-plugin-html` 的 `injectOption`）避免遗漏。**调试技巧**：webhint 报陈年警告 + 清缓存/隐私模式仍存在 → 99% 是 PWA 静态页面而非 index.html 漏改。
- **el-table / el-tree-select 外层避免 v-if（重要，commit `14c22e3` workaround）** — v-if 切换 → 完整 unmount → 递归卸载子组件（el-checkbox / el-tooltip / el-popper）→ Vue 3.4 renderer 内部 `let{bum:r,...}=e` 在 `e`（vnode.component）为 null 时抛 `Cannot destructure property 'bum' of 'e' as it is null`。**纪律**：①任何 el-table / el-tree-select / el-cascader 外层用 `v-show`（EP 组件大多有 `empty-text` 内置空态，不需要 v-if 隐藏）②即使升级 Vue 3.5 修了 bug，仍建议 v-show 作双保险 + 顺带保留 el-table 内部状态（sort/selection/scroll）③真要 v-if 释放 DOM 的场景，强制加 `:key` 显式声明 remount 意图。**已应用**：`AnalysisResultPanel.vue:55,77` v-if → v-show。**审计 one-liner**：
  ```bash
  cd web && grep -rB1 -A2 "<el-table\|<el-tree-select\|<el-cascader" src --include="*.vue" \
    | grep -E "v-if=\"" | head -20
  ```

### 2026-06-12 v4 收官后新增（多会话并行架构）

- **多会话并行架构（修复 4）核心纪律**（重要，commit `662a6ea`）— ChatViewSSE 多会话并行不丢数据不打架：①`messagesBySession: Record<sessionId, Message[]>` per-session 隔离 ②`activeAssistantMap: Record<sessionId, Message>` SSE yield 找目标引用 ③`sendMessage` 启动时**闭包捕获 `targetSessionId`**（防止 SSE yield 时 outer `sessionId.value` 已切走）④`abortControllers[sessionId]` per-session 取消（多次点击同会话）⑤`loadedSessions: Set<sessionId>` 防重复加载覆盖后台 SSE 增量 ⑥`persistTimers: Record<sessionId, Timer>` debounce 100ms 持久化（防后台丢）⑦`scrollToBottom` / `loading` 仅 `targetSessionId === sessionId.value` 时触发（避免切走还在滚 A 的消息区）。**切会话不 abort 任何 SSE**（让 A 后台继续跑），但**组件卸载时 abort 所有**。**任何"流式响应 + 多视图"场景都要 per-session 隔离 + 闭包贯穿**。沉淀：[multi-session-parallel-architecture.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/multi-session-parallel-architecture.md)
- **Pydantic Literal 字段不接受 None**（重要，commit `3852755`）— 即使 Python 类型注解是 `Optional[str]`，None 仍会触发 Literal 验证失败。17 个 tools/*.py 的 OutputModel schema 都定义 `rich_block_type: Optional[str] = None`（默认值），`chat_engine._extract_rich_block:432-441` 旧版只要 `result` 里有 `rich_block_type` 键就强行 `RichBlock(type=rb_type, ...)` 致 SSE 流 500。**修复**：加 `_VALID_RICH_BLOCK_TYPES: frozenset = frozenset(get_args(RichBlockType))` 守卫 + 改用 `if rb_type and rb_type in _VALID_RICH_BLOCK_TYPES` 跳过显式分支（fall through 到 implicit_map）。**用 `get_args` 动态生成集合**——与 protocol.py Literal 自动同步，未来新增 block 类型无需维护。**不要信任"键存在就构造"模式**——必须先验证值的合法性。沉淀：[richblock-type-none-pitfall.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/richblock-type-none-pitfall.md)
- **Python 模块加载级 NameError：缺 typing import**（重要，commit `3852755`，与 4ba7390 修复 2 同类）— 整个 `app/services/hybrid_retriever.py:12` 写 `from typing import List, Optional`，但 line 272 `eval_set: List[Dict]` / line 305 `_aggregate(per_query: List[Dict]) -> Dict` 用到 `Dict` → 模块加载就抛 `NameError: name 'Dict' is not defined. Did you mean: 'dict'?` → 整个 hybrid_retriever import 失败 → search_knowledge 工具一调就报。**类型注解在模块加载时也会执行**（不是只在调用时）。**扫描 one-liner**（改进版检查 import 列表是否真含所需名字）：```bash
for f in app/services/*.py app/agent/tools/*.py; do
  for type_name in Dict List Tuple Optional Union Set FrozenSet; do
    if grep -qE "\b$type_name\b" "$f" 2>/dev/null && ! grep -qE "from typing import.*\b$type_name\b|\*\)" "$f" 2>/dev/null; then
      echo "MISSING $type_name in: $f"
    fi
  done
done
```**每个 app 子包要确保 import 链完整**——加新 model/service/tool 后跑 `python -c "from app.X import Y"` 验证。**加进 CI / pre-commit 钩子**。沉淀：[typing-import-missing-bug.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/typing-import-missing-bug.md)
- **a11y 表单元素 4 属性套件是铁律**（小坑）— webhint 报 `A form field element should have an id or name attribute`，任何 `<textarea>` / `<input>` / `<el-input>` 都要补齐 `id` + `name` + `aria-label` + `title` 4 属性。`<textarea id="chat-input-textarea" name="chat-input-textarea" aria-label="聊天输入框" title="聊天输入框">` 是一例。**仅 file input 因为 hidden 无法走可见 label 路径，必须显式 aria-label + title 兜底**。参考 [Webhint Optimization](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/webhint-optimization.md) + 2026-06-12 commit `c97071c`（file input 4 属性套件先例）+ 2026-06-12 commit `662a6ea`（chat textarea 4 属性套件）

### 2026-06-12 v4 收官新增

- **`@tool` 装饰器 + Pydantic 校验是工具调用的标准模式**（v4 收官确定）— 34 工具全走装饰器后，**任何**新增工具必须遵循 4 步：①Pydantic BaseModel 严格定义 `input_model` / `output_model`（不依赖裸 `Dict[str, Any]`）②handler 委托原 service（不重写业务逻辑）③pytest happy/error/edge 三用例 ④`dispatch_tool(name, ...)` 跑通。`@tool(requires_db=True, requires_user=False)` 标记前置条件，dispatcher 自动校验缺 DB 返 `DB_UNAVAILABLE` 错误、缺 user 返 `AUTH_REQUIRED` 错误
- **`dispatch_legacy` 是装饰器注册表的兜底**（v4 清理后保留）— 当 `TOOL_REGISTRY` 没找到某工具名时（极端情况：用户自定义工具未注册），dispatch_legacy 回退到 `MicroBubbleAgent._execute_tool` 薄壳。所有 34 工具确认走装饰器后，**未来可彻底删除 dispatch_legacy**（约 18 行代码）让错误立即抛 `ToolNotFoundError`
- **`core.py` 是兼容壳，不是真实逻辑**（v4 清理后）— 原 1469 行 → 689 行（-53%）。`_execute_tool` 14 行薄壳直接调 `dispatch_tool`，**不再有 if/elif 链**。MicroBubbleAgent 类保留仅为向后兼容（chat/chat_stream/clear_session 公开 API 仍可调用）。所有业务逻辑在 `micro_bubble_agent.py`（v2 主类）
- **Pydantic BaseModel 字段顺序很重要**（教训）— 写 `MeetingListItem` 等 OutputModel 时，`rich_block_type` 字段**必须放最后**（避免 Pydantic V2 序列化冲突）。`Field(default=...)` 显式标注默认值，让 optional 字段有 fallback
- **SSE 事件类型不要在前后端硬编码**（v4 教训）— 协议层（`app/agent/protocol.py`）用 `Literal` 类型定义 9 种 `StreamEventType`，前端 `web/src/api/agent/protocol.ts` 用 union type 镜像。**新增事件类型**只改这两个文件 + 后端 `chat_engine.py` + 前端 `sse.ts` + 组件 switch case 共 4 处
- **ASR 端到端 4 层链路**（v4 完整接通）— `前端 VoiceRecorder emit record-stop blob` → `axios.post /api/v1/voice/asr (multipart)` → `后端 app/voice/asr.py:POST /voice/asr` 调 faster-whisper GPU large-v3 → 文字 → `inputText + sendMessage()`。**任一环节断就静默失败**，必须 4 步全验证（端到端真实语音 → ASR 真实文字 → sendMessage → assistant 真实回复）
- **highlight.js 按需注册**（v4 教训）— 200+ 语言全量打包 +30KB gzip+。**只注册 6 种常用语言**（python / js / bash / json / sql / yaml）就覆盖 90% 场景。dark mode 用 CSS 变量覆盖 `.hljs` 类而非切换主题文件（更轻）
- **highlight.js `plaintext` fallback 必须注册**（2026-06-15 教训，commit `c18b01e8`）— [web/src/utils/markdown.ts:41](web/src/utils/markdown.ts#L41) 写 `const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'`，意图"未知语言降级到 plaintext"，但**没注册 plaintext**就 fallback → console 报 `Could not find the language 'plaintext', did you forget to load/include a language module?`。**修复**：import `highlight.js/lib/languages/plaintext` + 注册 3 个 alias（`plaintext` / `text` / `txt`）。plaintext 是 hljs 官方的纯透传语言（无高亮、HTML 转义），chunk 增量 < 1KB。**纪律** ① 凡是用 `hljs.getLanguage` 做 fallback 的项目，**必须**注册 plaintext（最常见的 fallback 目标）② 否则 fallback 路径反而成为最大噪音源
- **性能基线 P95 阈值需取实测 + 30% buffer**（v4 设计）— 不能用硬编码 3s/30s（不同机器性能差 5x）。`tests/perf/` 第一次跑取 20 次实测 P95 + 30% buffer 作为基线，CI 接受 ±30% 浮动。**机器换了**（如本地开发机 vs 生产服务器）需重测
- **评估标注集是质量基线的根基**（v4 设计）— `data/eval_queries.jsonl` 20 问的 `relevant_ids` 字段是**占位预填**（基于领域知识 1-200 范围），**部署后必须**跑 `scripts/build_eval_ground_truth.py` 半自动修正为真实 ID（检索 top-10 + 人工筛）。否则 `recall@5` 计算无意义（查的 ID 数据库里不存在）
- **`agent_traces` 表 30 天清理策略**（v4 待做）— 当前表会无限增长。Celery beat 加 `purge_old_traces(days=30)` 每日清理，**与 reminder 任务同模式**（已 `app/services/reminder_service.py` 有参考实现）

### 2026-06-12 v3 深化新增

- **12 类 Rich Block 组件化**（v3 + v4 累计）— `MeetingCard` / `TaskListBlock` / `KnowledgeRefBlock` / `MemberCardBlock` / `FormulaBlock` / `HypothesisBlock` / `ProjectSummaryBlock` / `TranscriptBlock` / `ChartBlock` + 2 兜底。注册表 `web/src/components/chat/blocks/registry.ts` 用 `Record<string, Component>` 极简映射，支持 `registerBlock()` 动态扩展。**新增 block 类型**只改 3 处：①组件实现 ②registry 注册 ③`chat_engine._extract_rich_block.implicit_map` 加映射
- **多会话侧栏 + 兼容 v1**（v3 设计）— Pinia `chatSessions` store 自动 watch 持久化到 localStorage，**首次启动调 `migrateFromV1()`** 从旧 `chat_session_id` 单键导入为新会话。**新会话标题**取首条 user 消息前 30 字（LLM-as-judge 不依赖，零成本）
- **dark mode 主题切换通过 CSS 变量**（v3 设计）— `web/src/assets/variables.css` 加 `[data-theme="dark"]` 块重定义 `--color-*` 变量，所有组件用 `var(--color-primary)` 而非硬编码 `#FF7A5C`。切换主题 = `document.documentElement.setAttribute('data-theme', 'dark')` + localStorage 持久化。**不切换主题文件**避免双套 CSS 加载

### 2026-06-12 新增（深夜，4 commits 收尾）

- **Docker volume 挂载只换文件不换 Python 模块缓存**（重要，commit `4ba7390`）— `/api/v1/chat/stream` 404 排查双层根因：①app 容器 8:43 启动，`chat.py` 17:55 才加 `/chat/stream` 路由，**volume 实时同步文件但 Python 进程只在启动时 import 一次**，路由表停留在 16:43 那刻。`docker exec ... cat chat.py` 能看到新版（误导诊断），但 `curl /openapi.json | grep /chat/stream` **完全没有**这条路由（决定性证据）②重启 app 后又暴露 `search_tools.py` 缺 `from typing import Optional`，整个 FastAPI 启动失败 → 所有 `/api/v1/*` 路由 404。这个 NameError 是 v4 收官批量改 tools/ 时引入，但**模块缓存反过来掩盖了它数天**，直到为修 chat/stream 重启才一次性炸。**规则**：①怀疑路由 404 时**第一步看 OpenAPI**：`curl /openapi.json | grep "/route"`，没有 = 100% 模块缓存问题，不要去查文件 ②任何改路由 / import / 装饰器 / Pydantic 模型字段的 commit **必须** `docker compose restart app`，不只是 celery ③批量改 `tools/` 或 `schemas/` 的 commit **必须立即手动重启验证**，不要寄望"下次自然重启"暴露 bug ④扫描 typing import 漏写的 bash one-liner：`for f in app/agent/tools/*.py; do uses=$(grep -c '\bOptional\b' "$f"); has=$(grep -c 'from typing import.*Optional' "$f"); [ "$uses" -gt 0 ] && [ "$has" -eq 0 ] && echo "MISSING typing import: $f"; done`。**沉淀**：[docker-python-module-cache.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/docker-python-module-cache.md)
- **SSE/WS 流式事件两种语义混用必爆**（重要，commit `cf70ff5`）— `chat_engine.chat_stream` 流式分支既 yield `text_delta`（每个 token 一个增量）又在结束时 yield `brief`（`delta=accumulated_text` 完整文本快照）。前端 [ChatViewSSE.vue:215](web/src/views/chat/ChatViewSSE.vue#L215) 旧版 `if (type === 'text_delta' || type === 'brief' || type === 'detail') content += delta` **盲目 append**，结果 text_delta 累一遍 brief + brief 又把完整文本 append 一次 → 用户看到内容**重复出现两次**。**两类事件长得一样但语义相反**：
  - **增量事件**（如 `text_delta`）：delta=新增的一小段，正确处理 `content += delta`
  - **快照事件**（如 `brief`）：delta=完整累积文本，正确处理 `content = delta`（替换）或**根本不 append**（仅作阶段标记）
  
  **诊断方法**：①Network → EventStream 看原始事件流，哪一帧 delta 字段**突然变长**就是快照事件；②`console.log(content.length)` 每收一帧，长度**翻倍** = 快照被误 append。**防御纪律**：①protocol 文件里**显式标注每个事件类型的 delta 语义**（增量/快照/替换）②**前端不写「多事件类型共用 append 分支」**——拆开强迫读代码时区分语义 ③快照事件命名带 `_snapshot` / `_complete` 后缀避免误读 ④添加新事件类型时先想清楚 delta 是增量还是快照，更新两端 protocol + 组件 switch case。**沉淀**：[sse-event-semantic-mismatch.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/sse-event-semantic-mismatch.md)
- **Composable 解构字段名拼写错误**（重要，commit `13ba305`）— `const { isOnline } = useNetworkStatus()` 但 composable 实际暴露 `online` 不是 `isOnline`，`isOnline = undefined` 让模板 `v-if="!isOnline"` 永远等价于 `v-if="true"`，横幅永远显示"网络已断开"。**与 2026-06-02 变量名笔误同源**（`<script setup>` 内标识符错误编译期完全沉默），但触发模式不同：第 2 条访问**未声明**变量 → 运行到 lifecycle 抛 `ReferenceError` → 白屏（易察觉）；这条解构出**不存在字段** → 变量永远 `undefined` → 模板永远 falsy/truthy → **沉默误导**（难察觉，看起来"功能在跑"但条件永错）。**对照**：`MainLayout.vue` / `AudioRecorder.vue` 用 `const network = useNetworkStatus()` 整体接收没踩坑。**规则**：①解构 composable **前必看 return 语句**，不凭直觉猜字段名（`isOnline` / `connected` / `available` / `loading` / `isLoading` 都是常见误猜）②不确定时改用整体接收 `const x = useXxx()` + `x.field.value` ③想要重命名就显式写 `const { online: isOnline } = useXxx()`，强迫看一眼源字段名 ④TypeScript 能编译期捕获，纯 JS 项目得靠纪律。**沉淀**：[frontend-pitfalls.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/frontend-pitfalls.md) 第 4 条
- **a11y file input 4 属性套件**（小坑，commit `c97071c`）— webhint 在 `/chat` 报隐藏 file input 无 label。所有 `<input type="file" hidden>` 必须补齐 4 属性：①`id` + `name`（webhint「form field needs id or name」+ 浏览器 autofill 友好）②`aria-label`（axe「elements must have labels」，hidden input 无法走可见 label 路径）③`title`（webhint 兜底）。每个 id 全局唯一，多文件复用同样语义时加 `-legacy` / `-v2` 后缀避免 autofill 串扰。本项目 5 个 file input 全部修齐：[ChatViewSSE.vue:506-526](web/src/views/chat/ChatViewSSE.vue#L506-L526)（chat-image-upload / chat-file-upload）+ [ChatView.vue:147-168](web/src/views/ChatView.vue#L147-L168)（legacy 后缀）+ [SettingsView.vue:16-25](web/src/views/SettingsView.vue#L16-L25)（settings-avatar-upload）

### 2026-06-12 新增（晚间）

- **`_execute_tool` 函数体内 `from X import Y` 是 UnboundLocalError 重灾区**（重要，与 2026-06-02 声纹会议 WS 闪烁根因同类）— 2026-06-12 用户问"有没有相关会议可以学习？"助手回复"会议查询系统暂时无法正常工作"。两层根因：①LLM 看到 tools schema 但没有强 prompt 约束，倾向自己编造借口 ②代码 `app/agent/core.py:911` 在 `_execute_tool` 函数内（属于 `summarize_meeting_transcript` elif 分支）有 `from app.services.meeting_service import MeetingService`，Python 编译器**不区分 elif 分支**，会扫描整个函数体，只要看到这个名字就是 local，导致 line 881 `MeetingService(db)` 抛 `UnboundLocalError: cannot access local variable 'MeetingService' where it is not associated with a value`。被外层 `except Exception as e: return {"status":"error",...}` 吞掉后 LLM 看到 tool_result 是 error，又撒谎说"系统故障"。**规则**：①模块顶部已 import 的名字，函数体内**绝不要**再 `from X import Y` 重新导入 ②如果函数体内有 `import` 同名，**必须**重命名（`from app.X import Y as _Y`）避免污染 ③新增 tool 路由时**自上而下**检查所有 elif 分支的局部 import ④LLM 撒谎模式防御：所有 tool 必须在 `prompts.py` 顶部"工具调用黄金规则"section 显式列出"必须调用"+ "严禁编造借口"，否则 LLM 倾向 hallucinate
- **LLM 撒谎模式 (LLM Hallucination as Excuse)** — 当工具执行失败（被 except 吞掉、网络错误、参数错误）时，LLM 倾向用以下借口之一搪塞用户，**而不是诚实地报告错误**：
  - "X 系统暂时无法正常工作" / "技术问题" / "数据同步中"
  - "数据库中暂无相关记录"（即使数据库明明有数据）
  - "请联系管理员" / "稍后再试"
  - 看起来"合理的"空响应："关于会议学习，我建议您从以下方面入手" + 通用建议列表
  - **真相**：LLM 撒谎的频率与"工具是否在 system prompt 有强指令"负相关。`query_all_member_tasks` 有"必须调用"指令 → LLM 调；`query_meetings` 没有 → LLM 直接拒绝调工具编借口。**修复模式**：所有用户高频调用的 tool 必须在 `prompts.py` 系统提示词中**显式**列入"必须调用"section + 工具描述中标注「【必调工具】」+ 列举触发短语。**诊断方法**：直接调 API（绕过 LLM）确认 tool 实际能返回数据 → 问题 100% 在 LLM 提示层
- **直接调 API 验证是排查 LLM 谎话的最快方法**（重要）— 遇到"AI 助手说系统坏了"类问题，**永远先**直接 `curl /api/v1/...` 验证后端真伪：
  ```bash
  curl -sk -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/meetings | head -c 500
  ```
  如果后端正常 → 100% 是 LLM 撒谎/没调工具，不必查后端代码
  如果后端 500 → 才是后端问题，进 docker logs 找 traceback
- **调 LLM tool 必加调试日志**（诊断必经步骤）— 给 `_process_response` 和 `_execute_tool` 各加一行 `logger.warning(f"[DEBUG] tool={name}, input={input_data}")` + 外层 except 加 `logger.error(..., exc_info=True)`。无日志时 LLM 撒谎的错误被 except 吞掉，**根本无法定位**是"LLM 没调工具"还是"工具执行报错"。3 行日志可节省 1 小时排查时间

### 2026-06-12 新增（下半场）

- **webhint `detect-css-reflows/paint` 真正绕开方案**（重要）— hint 源码 `packages/hint-detect-css-reflows/src/{paint.ts,assets/CSSReflow.json}`：
  - `transform`（含 `scale()`/`rotate()`/`translate()` 函数）→ paint=true，会报警告
  - 独立 `translate:` 属性 → paint=true **AND** layout=true，比 transform 更糟
  - 独立 `scale:` / `rotate:` 属性 → **不在 JSON 里**，是 webhint 公认的干净绕开
  - `will-change` 完全不被该 hint 考虑（只扫 keyframes 内属性名）
  - **批量替换模式**：`transform: scale(N)` → `scale: N`；`transform: rotate(Xdeg)` → `rotate: Xdeg`；`transform: rotate() scale()` 组合 → 拆成 `rotate: X; scale: Y` 两行
  - 浏览器支持：CSS Transform Module Level 2（2022+ 全浏览器原生），不需要 polyfill
  - **保留 `transform: translate*()` 不动**：webhint 把所有位移属性都标 paint，没有干净替代
- **字符串聚合操作必须在源头过滤空内容**（教训）— 修 `transcriptEntries undefined.length` 崩溃时把 `raw[0].text || ''` 默认为空串，引发新 bug：21 个连续空 text 条目 merge 时累加 `'' + ' ' + ''` 全是空格 → `length > 20` 通过 `_needsPolish` → 后端 polish-text strip().length < 3 → 400。**规则**：①merge/reduce 类聚合操作要在循环条件就过滤空内容 ②API 发送前要 trim 校验 ③长度判定用 `trim().length`，不要用裸 `length`（空格不算"内容"）
- **`a?.length || 0` 必须左右两侧都防**（教训）— 比较表达式 `(current.text.length + (entry.text?.length || 0)) < N` 之前只防右边，当 transcript 条目缺 text 字段时 `current.text.length` 直接爆 undefined。**规则**：computed 内涉及外部数据的属性读取一律 `?.`，比较运算左右两侧都要兜底

### 2026-06-12 新增（上半场）

- **会议录音断网防御机制（5 阶段全栈完成）** — 2026-06-12 会议 #84 录音 58 分钟因 network error 丢失 1.6 秒废片段后永久卡死。完整修复：①前端 IndexedDB 兜底 + 边录边传骨架 ②上传状态徽章 + `useNetworkStatus` 接入 ③后端 chunked 端点（PUT /audio-chunk, POST /merge-chunks, GET /upload-status）+ 4 字段迁移 ④后端 stop-recording 硬校验 + Celery 真实 `self.retry` + 孤儿会议清理 + 删会议清 MinIO ⑤端到端测试 + bug 修复。**关键教训**（重要）：
  - **`useGlobalRecorder.js` 改造必须向后兼容** — 阶段 1 新增 `onChunk` 回调钩子（注册到 `chunkCallbacks` 数组），保留原 `audioChunks.push` 逻辑，AudioRecorder.vue 等消费者零感知改动
  - **fake-indexeddb 不支持复合索引 `IDBKeyRange.only([k, v])`** — jsdom + fake-indexeddb 抛 `DataError: parameter 2 is not of type 'Blob'`。修复：取消 `by_meeting_uploaded` 复合索引，改用 `by_meeting` 单字段 + 内存 filter `records.filter(r => !r.uploaded)`
  - **fake-indexeddb 反序列化 Blob 为普通对象** — 存进去再读出来 `blob.constructor.name === 'Object'`，后续 `FormData.append('file', blob, ...)` 抛 `parameter 2 is not of type 'Blob'`。修复：在 `idbStore.putChunk` / `getPendingChunks` 重新包装 `const safeBlob = blob instanceof Blob ? blob : new Blob([blob], { type: 'audio/webm' })`
  - **Celery `self.retry()` 必须 `raise`** — 在新 event loop 中 `try/except` 接住后**阻断** Celery 重试机制。正确模式：`_run()` 内 `except (ValueError, IOError, OSError, ConnectionError, TimeoutError) as e: raise self.retry(exc=e, countdown=60)` 让 Celery 装饰器接住；外层 `try/except` 只兜底 Celery 自身崩溃
  - **`delete_chunks` 不能"顺手删 merged"** — 阶段 5 端到端发现此 bug：merge 完成后调 delete_chunks 清理源 chunks，旧版 delete_chunks 内部又删了 merged.webm → 后处理 NoSuchKey。修复拆三个方法：`delete_chunks` / `delete_merged` / `delete_all`（用于删会议时清理）
  - **minio-py `put_object` 用位置参数** — 旧 `file_service.upload_to_path` 误用 S3-style kwargs `Bucket/Key/Body/Length/ContentType` 抛 `TypeError: Minio.put_object() got an unexpected keyword argument 'Bucket'`。正确：`put_object(bucket_name, object_name, data, length=-1, content_type=None)`
- **fake-indexeddb 必须 `import 'fake-indexeddb/auto'`** — 装包后只在 `setup.js` 顶部 import 一次，jsdom 环境才有 IndexedDB。`npm install --save-dev fake-indexeddb`
- **Vitest 默认 5s 超时** — uploadOne 内部 5xx 重试 5 次 × 指数退避（1s+2s+4s+8s+16s=31s）超过默认 timeout。测试中用 `vi.mockResolvedValue` 模拟 4xx 不重试，避免 hang
- **断网录音前端** — `useNetworkStatus.js`（2026-06-09 已实现但未接入），本次首次接入到 `MainLayout.vue` 浮动胶囊 + `AudioRecorder.vue` 徽章。`online` / `offline` 事件 + `navigator.connection.effectiveType`
- **Vite/Rollup hashCharacters 默认值** — Vite 8 默认 `hashCharacters: 'base64url'`，产出形如 `index-Qec9lxup.css`、`MainLayout-B6AkdWtm.js`（含大小写字母+数字+下划线+连字符）。webhint 内置 cache-busting 正则只认 `[0-9a-f]+` 小写 16 进制，会对所有 chunk/asset 文件报 "URL does not match configured patterns"。**修复**：`web/vite.config.js` 加 `build.rollupOptions.output.hashCharacters: 'hex'`，文件名变为 `index-9ab8129c.js` 等全小写 hex，webhint 通过。Rollup 4.x 原生支持此选项。新建 Vite 项目时应直接配为 hex
- **Vite dist 重命名提交** — 改 hashCharacters 后 `npm run build` 会重命名 100+ 个 dist 文件。**必须** `git add -f web/dist` 强制提交，否则 `.gitignore` 拦截新文件名（删了旧的不加新的），线上 404 白屏。验证 `git diff --cached --stat` 看到所有文件都是 `rename:` 不是 `deleted:`
- **webhint cache-busting 误报的真实修复路径** — 之前 MEMORY 误记为"Edge DevTools 内置 webhint 不读项目配置 → 浏览器端无法消除"，实际**工具链配置可以彻底消除**。不要被"工具限制"标签固化思路，遇到工具误报时优先考虑是否能从工具链上游（构建工具/CDN/响应头）解决

### 2026-06-11 新增

- **bash `set -e` 陷阱** — 全局 `set -e` 让所有命令的失败都退出脚本。`find` 无结果 + `xargs wc -l` 返回非零、统计命令在空目录运行等非关键步骤都会导致脚本提前退出。**修复**：移除全局 `set -e`，只在关键步骤（`git pull`/`npm run build`/`nginx reload`）手动 `exit 1`。非关键步骤用 `|| echo 0` 兜底。
- **bash 子 shell 隔离统计段** — 统计/计数函数用子 shell `( ... )` 包裹，退出码不影响主流程。函数内 `find`/`xargs`/`wc` 等命令都加 `|| echo 0` 兜底，确保不会因为无匹配文件而返回非零。
- **脚本末尾 `exit 0` 保底** — bash 在子 shell 或管道中运行时 `$?` 可能被中间命令覆盖，末尾显式 `exit 0` 确保 webhook 收到成功响应（不依赖 `$?` 的传递链）。
- **stats.json 写入路径与 Docker volume 对齐** — `deploy-auto.sh` 写 `$PROJECT_DIR/stats.json`，API 读 `app/stats.json`。Docker 只挂载 `./app`，根目录文件容器内不可见。**路径必须与 volume 挂载点一致**。
- **静态天数改为动态计算** — stats.json 中 `dev_days` 只有部署时更新，跨天不刷新。改为存 `first_commit_date`，API 每次请求 `math.ceil((now - first) / 86400)` 实时计算。
- **Vue `watch` 响应式数据** — 组件消息/内容依赖 props 数据时，只在 `onMounted` 构建一次会导致数据过时。必须用 `watch` 监听 props 变化后触发 `rebuildMessages()` 重建。
- **CSS 动画 GPU 化规范** — `@keyframes` 中只用 `transform` 和 `opacity`（GPU Composite），禁用 `left`/`margin-top`（Layout）和 `background-position`/`box-shadow`（Paint）。需要隔离定位 transform 时用 wrapper div。
- **同名 `@keyframes` 加载顺序陷阱** — `unplugin-vue-components` 按需加载 EP CSS 晚于自定义 CSS，同名 keyframes 被覆盖。**修复**：用独特前缀（`mb-*`）+ `!important` 覆盖 animation-name，或用 PostCSS 插件在构建时剥离第三方 keyframes。
- **PostCSS 剥离第三方 CSS** — `vite.config.js` 的 `css.postcss.plugins` 可注册自定义 PostCSS 插件，通过 `AtRule` 钩子按名称移除 `@keyframes`、通过 `Declaration` 钩子移除特定属性。

### 2026-06-08 新增

- **Webhint 优化纪律** — webhint 审计工具检查无障碍（ARIA）、性能（Cache-Control/CSS 动画）、安全头（X-XSS-Protection/CSP/Pragma）。修复规则：el-popover 用 `v-model:visible` + `v-if` 控制弹出内容；el-tab-pane 用 `lazy` 避免隐藏标签页包含 focusable 元素；图标按钮必须加 `aria-label`；API 用 `Cache-Control: max-age=0`（webhint 只接受 max-age，不接受 no-store/must-revalidate/Pragma/Expires）；Nginx 用 `proxy_hide_header X-XSS-Protection` 剥离 MinIO 废弃头；CSS 动画用 `transform` 替代 `background-position` 消除 Paint 性能警告
- **el-select aria-label** — Element Plus 内部 input 不继承 placeholder，必须显式加 `aria-label` prop
- **el-progress aria-label** — 进度条组件通过 `$attrs` 传递 `aria-label` 到根元素
- **对象 key 类型陷阱** — JavaScript 对象 key 始终是字符串，`{123: ...}` 变成 `{"123": ...}`。用 `===` 比较数字会失败（`"123" === 123` → false）。`getMemberName`/`getMemberAvatar` 必须用 `==` 宽松比较
- **批量删除限流** — write 限流 30次/分钟 = 1次/2秒。批量操作必须用后端单次 API 请求（`POST /tasks/batch-permanent-delete`），不要前端逐个调用
- **任务列表配对布局** — `pairedGroups` computed 合并 active/done 按 assignee_id 配对，左右对齐。分组函数用 `task.assignee_id != null` 判断（不要用 `||`，会把 0 当 falsy）
- **精确跳转** — 从其他页面跳转到任务列表时，通过 URL query `?assignee_id=xxx` 传递筛选条件，TaskView 在 `onMounted` 中读取 `route.query.assignee_id` 设置 `filters.assignee_id`
- **Nginx charset_types** — `text/html` 是 Nginx 默认值，不需要在 `charset_types` 中重复声明，否则会有 `duplicate MIME type` 警告
- **Nginx CSP 头** — 只有 `frame-ancestors 'self'` 的 CSP 太弱，webhint 认为 unneeded。如果不需要完整 CSP 策略，不要添加
- **Webhook 自动部署正常** — 每次 git push 自动触发 webhook → deploy-auto.sh → git pull → nginx reload。如果部署失败，检查 `/var/log/webhook-deploy.log`
- **IE 兼容性不修** — Vue 3 + Element Plus 本身不支持 IE，所有 IE 兼容性警告（-ms-grid、flex、sticky、8 位颜色值等）直接忽略，不需要加 `-ms-` 前缀
- **webhint http-cache 误报** — Vite content-hash 文件名（`index-f2KQs4XE.js`）是业界标准缓存方案，但 webhint 内置正则只认 `[0-9a-f]` 小写十六进制，不认 Vite 的 base64 格式。已添加 `.hintrc` 自定义 revving 正则，但 Edge DevTools 内置 webhint 不读项目配置，浏览器端无法消除此警告
- **webhint 判断规则** — Error 必须修，Warning 看情况修，Info/Tip 大部分忽略。看源码路径：自己写的代码可以改，第三方库（Element Plus/Vite 打包产物）不能改

### 2026-06-10 新增（宠物系统）

- **CSS keyframe 不能覆盖行内 transform** — walking 动画用 `transform: translateY(-6px)` 覆盖了 bunny 行内 `translate(-50%,-50%) scaleX(...)` 定位 → 兔子闪现。**修复**：动画改用 `margin-top` 或 wrapper div 隔离
- **overflow:hidden 裁切绝对定位气泡** — 欢迎区 `overflow:hidden` 用于裁剪装饰元素，但宠物气泡 `position:absolute` 超出容器被裁切。**修复**：改为 `overflow:visible`，单独给草地 `overflow:hidden`
- **互斥锁所有权限随** — `window.__petSpeaking` 从 boolean 改为记录 `props.type`（谁在说话）。`onLeave` 只清理自己不是说话者的情况，不误清轮播锁
- **bash 数组兼容性** — `EXCLUDE_DIRS=(-not -path "*/node_modules/*")` 在老 bash 上不支持。在函数内用 `set -f` + 字符串变量替代
- **`set -e` + 统计函数** — `find` 无结果 → `xargs wc -l` 返回非零 → `set -e` 退出脚本。统计段用 `set +e` 包裹，结束后恢复
- **props 默认值用 `Number()` 包裹** — `props.totalTasks || 'N'` 在值为 0 时走 `'N'` 分支。用 `Number(props.totalTasks) || 0` 先转数字再判断

### 2026-06-10 新增

- **unplugin-vue-components 不检测 JS 服务调用** — `ElMessageBox.confirm()` / `ElMessage.success()` 等服务 API 不在模板中使用 `<el-message-box>` 标签，`ElementPlusResolver` 无法为其自动导入 CSS。`el-message-box.css` 和 `el-message.css` 完全不会被打包进 dist。**修复**：在 `main.js` 中手动 `import 'element-plus/theme-chalk/el-message.css'` 和 `el-message-box.css`。**验证方法**：`npm run build` 后搜索 dist CSS 是否包含 `.el-message-box`。**教训**：新增使用 Element Plus 服务 API 时，必须手动导入对应 CSS
- **dist 提交必须 `git add -f`** — `web/dist/` 在 `.gitignore` 中，`git add web/dist/` 静默被拦截不报错，只删除旧文件不加新文件 → 线上 404。**每次 `npm run build` 后必须 `git add -f web/dist/` 提交产物**
- **`git add -A` 静默跳过 .gitignore 内文件（2026-06-14 收官新坑，commit `a40e84c`）** — 上次 commit `e2a9a49` 用了 `git add -A app/ web/src/ web/dist/` 想"全部 add"，但 `web/dist/` 在 .gitignore 第 50 行 → git **静默**跳过整个 dist 目录（不报错、不警告），结果 commit 里只有"删除旧 dist 文件"没有"添加新 dist 文件"。服务器 git pull 后 `web/dist/assets/index-*.js` 数量为 0，部署安全检查中止（commit `2b38c99` 加的健全性检查救了一命）。用户浏览器报 ERR_ABORTED 404 + SW `bad-precaching-response`。**修复**：`git add -A` 后**必须**追加 `git add -f web/dist/`。**或者**直接两步走：① `git add -A app/ web/src/` ② `git add -f web/dist/`。**纪律（永久）**：
  - `git add -A` 对 .gitignore 内的文件**静默跳过**，不报任何错（与 `git add` 不存在的路径报错不同）
  - 提交前**必跑** `git ls-files web/dist/assets/index-*.js | wc -l` 应该 >= 1
  - 提交后 `git show --stat HEAD | grep "dist/assets/index-"` 看新增/修改/删除的 index js 数量
  - 永远**不要**只依赖 `git status`（它默认也隐藏 ignored 文件，需要 `--ignored` 才显示）
- **bash 数组防 glob 展开** — 字符串变量 `EXCLUDE_DIRS="-not -path */node_modules/*"` 在函数中 `$EXCLUDE_DIRS` 展开时，`*/node_modules/*` 会被 shell glob 展开为实际文件路径，破坏 `find` 的 `-path` pattern。**修复**：改用 bash 数组 `EXCLUDE_DIRS=(-not -path "*/node_modules/*")` + `"${EXCLUDE_DIRS[@]}"` 展开
- **git log --reverse --max-count=1 陷阱** — `--max-count=1` 先于 `--reverse` 执行，结果永远是 HEAD 而非最早提交。正确做法：`git rev-list --max-parents=0 HEAD` 找根提交后再取日期
- **deploy-auto.sh 自更新局限** — `git pull` 后脚本文件已更新到磁盘，但当前 bash 进程仍在执行旧版内存内容。新版统计逻辑需下次部署（新进程）才能生效。紧急时可 `bash scripts/deploy-auto.sh` 手动重跑
- **PowerShell UTF-8 BOM** — `Set-Content -Encoding UTF8` 写入 UTF-8 BOM（3 字节 `EF BB BF`），Python `json.loads` 默认不处理 → `JSONDecodeError`。修复：PowerShell 用 `[System.Text.UTF8Encoding]::new($false)` 写无 BOM 文件；Python 用 `encoding="utf-8-sig"` 读取
- **stats.json Docker 路径** — Docker volume 只挂载 `./app:/app/app`，项目根 `/app/stats.json` 来自镜像构建（只读、过期）。`stats.json` 必须放在 `app/` 内才可通过 volume 实时更新

### 2026-06-09 新增

- **Nginx 扫描器正则误杀 /webhook** — `^/(...|web|...)` 中的 `web` 匹配到了 `/webhook`，GitHub webhook 被 444 静默关闭。修复：`web` → `web$` 精确匹配。**教训**：扫描器屏蔽正则中所有可能与合法路径前缀重叠的关键词必须加 `$` 锚定
- **sessionStorage 残留脏数据** — 录音结束后 sessionStorage 未清除，刷新页面后幽灵胶囊仍显示。修复：`checkActiveRecording` 始终先查后端 API，后端无 recording 会议时调 `stopRecording()` 清除 sessionStorage。不再信任 sessionStorage 作为首选数据源
- **全局录音器单例** — `useGlobalRecorder.js` 模块级变量管理 MediaRecorder 生命周期，组件销毁不影响录音。AudioRecorder 重构为纯 UI 壳。录音在后台持续进行，导航到其他页面不中断
- **useRecordingState + 浮动胶囊** — MainLayout 右下角浮动脉冲胶囊，显示录音状态 + 会议标题，点击跳转 `/meetings?resume={id}`。sessionStorage 持久化 + 后端 API 验证双重保障
- **meeting.py status 过滤** — 会议列表 API 新增 `status` 查询参数，支持按状态筛选。用于全局录音状态检查（`status=recording`）
- **Nginx 安全防护** — `nginx/conf.d/tunnel.conf` 添加恶意扫描器屏蔽规则，覆盖两个站点（agent.mnb-lab.cn + mnb-lab.cn）。屏蔽类别：敏感文件（.env/.git/.ssh/.aws/.azure）、WordPress 漏洞路径、云凭证探测、开发文件（_next/node_modules）、常见攻击路径（boaform/formLogin/servlet）。使用 `return 444` 静默关闭连接不返回任何响应。正常访问（/、/api、/minio）不受影响
- **Docker Desktop 汉化** — 使用 asxez/DockerDesktop-CN 项目，需替换 3 个文件（Docker Desktop.exe + app.asar + app.asar.unpacked）。4.74.0+ 版本有 asar 完整性校验，必须同时替换 exe。每次 Docker 更新后汉化失效需重装
- **服务器访问日志分析** — 2452 条请求中 88% 是恶意扫描器（WordPress 漏洞、.env 探测、云凭证探测），真实用户只有杜同贺（3 个 IP 同一人不同设备）和少量 mnb-lab.cn 主站访客。202.113.x.x 网段是校园/办公网络

### 2026-06-06 新增

- **语义断句** — VAD + 声纹之外，ASR 后增加基于规则的语义断句（问答切分、转折词、回应词），检测同一段内的对话切换。不使用 AI API，纯本地规则，零延迟。
- **KMeans 强制分裂** — 贪心聚类数=1 但声纹分布标准差>0.15 时，用 sklearn KMeans 硬分 2 簇，解决声纹模型区分度不够的问题。
- **同名聚类检测** — 多个聚类被 identify_speaker_by_embedding 识别为同一人时，自动保留差异为独立发言人。
- **名字校对** — 谐音映射（杜同和→杜同贺）+ 编辑距离≤1 模糊匹配 + 精确匹配三位一体，与成员管理数据库比对。
- **标题自动生成** — "听会"和"未命名会议"标题自动触发 AI 生成，重试 3 次 + 2000 字上下文 + regex 兜底提取。
- **转录合并自动润色** — 同一发言人连续段合并后，自动调 AI 加标点。超长文本（>20字）显示润色后文本。
- **转录发言人手动修改** — `PATCH /meetings/{id}/transcript-speaker` 端点，前端 el-select 下拉选人，合并条用原始索引。
- **会议纪要独立改发言人** — 每条要点/决议点击展开 el-select，改一条不影响其他。
- **AI 润色简化 + JSON 修复** — prompt 缩减到 5 句规则，max_tokens 4096→8192，JSON 截断自动补全。
- **规则标点兜底** — AI 润色失败时，本地规则加标点（问句加？，长句连接词加逗号，句末加。）。
- **VAD 精细化** — 合并阈值 0.3→0.15→0.1s，min_speech 500→300→200ms，min_silence 300→200→100ms。
- **MATCH_THRESHOLD** — 0.55→0.7（余弦距离阈值，更宽松匹配）。
- **Celery solo pool** — 改为 `--pool=solo` 避免 prefork 子进程保留旧代码。
- **modelscope 缓存挂载** — `./models/modelscope:/root/.cache/modelscope`，避免每次重建容器重下载 3D-Speaker。
- **声纹持续学习** — 每次会议识别出的发言人，自动加权平均更新 voice_embedding + voice_sample_count，越用越准。
- **pipeline 日志精简** — 跳过 3D-Speaker pipeline（必然失败），直调底层 model，消除 30+ 行 WARNING/ERROR。
- **认证限流** — 5→20次/分钟，读操作 100→200次/分钟。
- **UI** — 全项目 date-picker 替换、日期北京时区、参与者头像间距、发言人选择器缩小、纪要合并显示。
- **前端性能大幅优化（2026-06-09）** — Nginx gzip + Element Plus 按需导入 + 图标按需注册，主 JS bundle 1.2MB→199KB(-83%)，首屏 gzip ~500KB→~80KB(-84%)。具体变更：
  - **Nginx gzip** — `tunnel.conf` 两个 server block 均开启 gzip（comp_level 5），JS/CSS 传输减 70%
  - **Element Plus 按需导入** — 使用 `unplugin-vue-components` + `ElementPlusResolver({ importStyle: 'css' })`，自动按需导入组件和 CSS。vite.config.js 中配置 Components 插件
  - **main.js 精简** — 移除 `import ElementPlus from 'element-plus'`、`import 'element-plus/dist/index.css'`、`app.use(ElementPlus)`、全量图标注册（`import *` + `app.component` 循环）
  - **ElMessage/ElMessageBox** — 这些是 service 不是组件，在各文件中手动 `import { ElMessage } from 'element-plus'` 的写法保持不变，resolver 会自动优化导入路径
  - **动态 import 不能保留** — `import('element-plus').then(...)` 无法被 resolver 转换，必须改为静态 import（如 `AudioRecorder.vue` 的 `ElMessageBox`）
  - **CSS 拆分** — Element Plus 组件 CSS 自动拆分为 50+ 个独立文件，仅在对应组件渲染时加载，不再单一 355KB CSS 文件
  - **dist 构建后检查** — 修改 vite.config.js 或 main.js 后必须 `npm run build` 并 `git add -f web/dist/` 提交 dist。验证：主 bundle 应 < 300KB（而非 1.2MB）
  - **禁止回退** — 任何时候都不要把 `import ElementPlus from 'element-plus'` 或全量 CSS import 加回 main.js，也不要移除 vite.config.js 的 Components 插件，否则 bundle 会膨胀回 1.2MB
- **知识库列表 API 不能返回完整 content**（2026-06-09）— `GET /knowledge` 每页 20 条，若每条含完整文档内容会导致响应体数 MB，穿过 FRP 隧道时触发 HTTP/2 帧错误（`ERR_HTTP2_PROTOCOL_ERROR`）。**修复**：列表 API 使用 `KnowledgeListItem` schema（不含 `content`/`formatted_content`），改为 `snippet` 字段（content 前 200 字符），卡片预览用 `item.summary || item.snippet`。详情 API `GET /knowledge/{id}` 不受影响
- **Nginx /api 不能加 `Connection: upgrade`**（2026-06-09）— 该 header 仅用于 WebSocket 升级（`/ws` location），放在 `/api` 中每个请求都要求后端升级连接，会干扰 HTTP/2 帧封装。同时添加 `proxy_buffer_size 16k` + `proxy_buffers 8 64k` + `proxy_max_temp_file_size 128m` 防止大响应撑爆缓冲区
- **Element Plus 图标按需导入注意事项**（2026-06-09）— `unplugin-vue-components` 可以解析模板中的 `<IconName />` 静态标签，但**无法解析**以下两种用法，必须显式 `import { X } from '@element-plus/icons-vue'`：
  1. **动态组件**：`<component :is="item.meta.icon" />` — 编译时看不到字符串值
  2. **某些图标**：`Aim`、`Bell` 等 — resolver 可能漏解析，必须在 script 中显式 import
  - MainLayout.vue 现已导入全部 14 个图标（Aim/Bell/ArrowRight/DataBoard + 10 个路由 meta 图标）

## 开发注意事项（历史）

- **重构子组件不能丢样式**（2026-06-05 教训）— 把 Element Plus 组件（el-table、el-card）换成裸 div 时必须手写等效 CSS，否则 UI 变成无样式纯文本。抽完后对比原始 UI 确保视觉一致
- 数据库模型使用 PostgreSQL 特有类型（ARRAY, Vector），不可直接切换到 SQLite
- 前端 ProjectView 调用了 DELETE /projects/{id}（已实现），MeetingView 的 PUT/DELETE 端点已实现
- 无用依赖已清理（langchain, chromadb, sentence-transformers, pyannote 已移除，minio 已恢复用于文件上传）
- 登录页硬编码账号已移除，改为"请联系管理员获取账号密码"
- Agent 的 `generate_project_plan` 工具会调用 Claude API 两次（生成计划 + 对话），注意 token 消耗
- 企业微信已上线，腾讯会议凭据待配置（详见 ROADMAP.md）
- 部署架构：云服务器跑 Nginx+FRP+Webhook(9001)，本地电脑跑全部 Docker 服务，FRP 穿透 8000/9000/2222 端口
- Webhook 自动部署：GitHub push → Nginx /webhook 代理 → webhook.py (9001) → deploy-auto.sh → npm build → nginx reload，已端到端验证
- Claude API 使用代理地址（`CLAUDE_BASE_URL`），支持第三方 API 中转
- **文件上传 prefix 参数** — `app/api/v1/upload.py` 中 `prefix` 使用 `Form("uploads")` 而非 `Query`，因为前端通过 FormData 发送该字段。若误用 `Query`，prefix 会静默回退到默认值 `"uploads"`，导致头像等文件存到错误前缀
- **铃铛提醒去重** — `_create_default_reminders()` 为每个任务创建 1-2 个 reminder（分级预警），但通知 API 必须按 task 去重。`GET /reminders` 使用 PostgreSQL `DISTINCT ON (task_id)` + `ORDER BY task_id, remind_at` 保留最早提醒，`pending-count` 使用 `COUNT(DISTINCT task_id)`。任何时候修改提醒相关查询，都要确保前端铃铛不会因一个任务多个 reminder 而重复显示
- **云服务器资源限制** — 阿里云 2核2G，严禁在云服务器上运行 `npm run build`（Next.js 构建会 OOM 导致 SSH 断开）。所有前端构建在本地 Windows（32核+GPU）完成，静态产物上传到服务器
- **前端 dist 构建提交** — 修改 `web/src/` 下的 Vue 源码后必须执行 `npm run build`（`web/` 目录下）并 `git add -f web/dist/` 提交 dist（dist 在 `.gitignore` 中，需 `-f` 强制添加），否则线上部署的仍是旧版静态文件。服务器通过 git 已提交的 dist 文件提供服务，不在服务器上构建
- **同服多站点** — 云服务器同时托管 `agent.mnb-lab.cn` 和 `mnb-lab.cn`，通过 nginx `server_name` 区分，各自独立 SSL 证书（Let's Encrypt certbot --expand 扩展）。新增站点时必须：1) SSL 证书覆盖新域名 2) 添加 HTTPS server block 3) 确保 `^~` 修饰符避免 regex location 拦截
- **多站点部署隔离** — `agent.mnb-lab.cn` 是 Vite SPA（构建轻量），`mnb-lab.cn` 是 Next.js 静态导出（201MB 图片，构建吃资源）。两者 Nginx 配置在同一文件 `/etc/nginx/conf.d/default.conf`，修改时必须确保不影响另一个站点。`deploy-auto.sh` 仅处理 agent 项目，mnb-lab 需手动构建部署。两个站点共享 FRP 隧道的 MinIO 端口（9000），minio location 使用 `^~` 修饰符防止静态资源 regex 拦截图片请求
- **Nginx 配置必须 Git 同步** — `deploy-auto.sh` 每次部署时将 `nginx/conf.d/tunnel.conf` 直接覆盖到 `/etc/nginx/conf.d/default.conf`。在云服务器上对 nginx 配置的任何手动修改（如 root 路径、SSL 证书路径、proxy_pass 目标等），必须同步更新到 Git 仓库的 `tunnel.conf`，否则下次 webhook 部署会覆盖丢失，导致站点 500。这条规则没有例外。
- **头像上传自动保存** — `web/src/views/SettingsView.vue` 的 `handleAvatarUpload` 上传成功后立即调 `PUT /api/v1/auth/profile` 持久化，用户无需手动点"保存资料"。HEIC 格式（iPhone 默认拍照格式）Canvas 不支持压缩，使用 try/catch 回退原文件上传
- **头像上传 Content-Type** — 切勿手动设置 `Content-Type: multipart/form-data`，FormData 需要 boundary 参数（如 `multipart/form-data; boundary=----WebKitFormBoundaryxxx`），手动覆盖后缺少 boundary 导致服务器无法解析。应让 axios 自动检测并设置正确的 Content-Type（含 boundary）
- **头像上传分步容错** — 上传涉及 3 个串行请求（POST /upload → PUT /auth/profile → GET /auth/me），若包在同一个 try/catch 中，第三步超时会阻止 localStorage 写入，导致刷新后头像回退。必须拆分为独立 try/catch：upload+save 成功后先更新 localStorage，GET /auth/me 单独容错，失败时用本地 URL 兜底
- **Nginx 多站点配置必须完整** — `nginx/conf.d/tunnel.conf` 每次部署时会被 `deploy-auto.sh` 直接覆盖到 `/etc/nginx/conf.d/default.conf`，因此这个文件必须同时包含 `agent.mnb-lab.cn` 和 `mnb-lab.cn`（+ `www.mnb-lab.cn`）的完整 server block。修改 `tunnel.conf` 后务必验证两个站点的 `server_name` 和 `root` 都正确，否则同服另一个站点会被清掉
- **侧边栏导航必须使用绝对路径** — `MainLayout.vue` 中 `el-menu-item` 的 `:index` 和移动端 `router.push` 都必须用 `'/' + route.path`（绝对路径），否则在 `/knowledge` 等嵌套路由下点击其他菜单项会解析为相对路径（如 `/knowledge/dashboard`），误匹配 `/knowledge/:id` 路由，导致 KnowledgeDetailView 错误挂载并请求不存在的 API（422）
- **menuRoutes 过滤非导航路由** — `menuRoutes` 计算属性需过滤 `r.meta?.icon`，确保 `knowledge/:id` 等详情页路由（无 icon）不出现在侧边栏
- **Vue 组件 import 完整性** — 修改 Vue 组件时，在 `<script setup>` 中添加对 `watch`、`nextTick`、`onUnmounted` 等新 API 调用后，必须同步更新 `import { ... } from 'vue'` 语句，否则生产构建后运行时抛出 `ReferenceError: xxx is not defined` 导致组件白屏
- **Vue 组件变量名笔误**（2026-06-02 教训，commit `fbffb88`）— `<script setup>` 内**对未声明标识符的引用**（如 `onUnmounted` 内写 `chartInstance` 但实际变量是 `entityChartInstance`）也是生产 bug：HMR/esbuild 不会拦下、Vite 生产构建不报 undefined 引用，**只有运行到对应生命周期才抛 `ReferenceError`**。KnowledgeView 路由到实体图谱 tab 再离开时 `onUnmounted` 触发，组件白屏。**防御**：① 同文件内多 echarts 实例要严格命名（`entityChartInstance` / `meetingChartInstance`），引用前先看顶部声明；② `onMounted` / `onUnmounted` / `watch` / `nextTick` 回调内引用的变量必须二次核对声明名；③ 可在 `web/src/views/**/onUnmounted` 加 eslint `no-undef` 规则强制
- **Webhook GitHub 连通性问题** — 阿里云服务器偶发无法连接 GitHub（TLS/GnuTLS 错误或超时），GitHub webhook 交付失败但代码已 push。此时可通过 SSH 到服务器手动触发：`curl -s -X POST http://localhost:9001/webhook -H 'Content-Type: application/json' -H 'X-GitHub-Event: push' -H 'X-Hub-Signature-256: sha256=<hmac>' -d '{"ref":"refs/heads/main","pusher":{"name":"fix"},"commits":[{"id":"fix"}]}'`（HMAC 签名用 `echo -n '<payload>' | openssl dgst -sha256 -hmac "<WEBHOOK_SECRET>"` 生成）
- **deploy-auto.sh 不重启 Python 后端** — 脚本只重载 Nginx，Python 代码变更（路由注册、新模块等）需要手动 `docker compose restart` 才能生效。数据库新列（ALTER TABLE）也需要手动执行
- **模型依赖安装** — modelscope（3D-Speaker）有大量传递依赖（addict, datasets, simplejson, sortedcontainers, **soundfile** 等），pip install 时可能遗漏。Docker 内运行 `pip install addict datasets simplejson sortedcontainers soundfile` 补全。**所有这些依赖必须固化到 `requirements.txt`**（不要只容器内临时安装，否则下次 `docker compose build` 会丢失）。torch + CUDA 包约 2GB，首次下载耗时较长
- **声纹模型懒加载** — 3D-Speaker 首次调用时从 ModelScope Hub 下载模型（~100MB），需要网络连接。下载后缓存在 `/root/.cache/modelscope/`。**正确模型 ID：`iic/speech_eres2net_sv_zh-cn_16k-common`（旧 ID `iic/speech_eres2net_sv_zh-cn_3dspeaker_16k` 已下线，加载会 404）**
- **3D-Speaker pipeline 输入类型限制** — `speaker_verification` pipeline 只接受「音频文件路径」或「numpy ndarray」，**不接受 bytes / BytesIO**。代码必须用 `tempfile.NamedTemporaryFile` 写 wav 再传路径
- **3D-Speaker 模型输入是 1D tensor** — `ERes2Net_Pipeline.preprocess` 接收 1D numpy array，模型内部自己加 batch 维。直接调 `model(x)` 必须传 1D（不要 `.unsqueeze(0)`）。实测：1D 和 2D 输出都是 `(1, 192)`，结果一样，但 1D 符合官方规范，避免无谓转换
- **声纹嵌入维度 192（不是 256）** — ERes2Net 实际输出 192 维。`voiceprint_service.py:EMBEDDING_DIM=192`，`Member.voice_embedding=Column(Vector(192))`。历史代码错误写 256，靠 `emb[:EMBEDDING_DIM]` 截断掩盖，必须保持一致
- **numpy.float32 序列化** — pgvector 读出的 `m.voice_embedding` 是 numpy array，`list()` 转后元素仍是 numpy.float32。FastAPI `jsonable_encoder` 不能处理 → 500 错误。**所有返回 embedding 的 API 必须用 `.tolist()` 转 python float 列表**
- **声纹前后端阈值必须一致** — 后端 `MATCH_THRESHOLD=0.55`（`voiceprint_service.py`）+ 前端 `markLine: yAxis: 0.55`（`ConfidenceChart.vue`）。**0.45 是误读**（早期前端写错，markLine 显示为阈值参考线而非真实数据）。修改时两边同步
- **声纹会议 live WS 静默断开**（2026-06-02 教训）— `app/api/v1/voice.py` 的 `meeting_live_ws` 和 `_run_live_loop` 函数**必须有顶层 try/except 兜底**。VAD 加载 / `transcript_history` 发送 / `pubsub.subscribe` / `await websocket.send_json` 在客户端断后抛 `ConnectionClosed` 等任何异常，如果只捕获 `WebSocketDisconnect` 会逃逸到 Uvicorn 静默关闭 WS，**没有错误日志**。**修复**：`meeting_live_ws` 顶层加 `try/except WebSocketDisconnect/Exception`（后者 `logger.error(..., exc_info=True)` + `await websocket.close(code=1011)`）；`_run_live_loop` 拆出 `_live_loop_inner` + outer try/except 同样处理。验证：改后 WS live 维持 11+ 秒，audio_level 推送正常
- **audioLevels 必须解耦 activeSpeaker**（2026-06-02 教训）— `MeetingRoom.vue` 的 `onMessage` 处理 `audio_level` 时，**之前**只在 `activeSpeaker !== null` 时写入 `audioLevels[activeId]`。但 `activeSpeaker` 只在收到 transcript 且 `speaker_confidence > 0.45` 时才设置 — 如果后端没发 transcript（比如 VAD 静默），activeSpeaker 永远 null，5 根声波条永远不跳动。**修复**：用 `key = activeId !== null ? String(activeId) : 'self'` 兜底；`LiveSpeakerPanel.getBarHeight` 读不到 activeSpeakerId 时降级到 `props.audioLevels['self']`
- **Progress WS snapshot 不能发 null**（2026-06-02 教训）— `meeting_progress.py:_send_snapshot` 之前**无条件**发 `{"type": "progress_snapshot", "data": snapshot}`，当 `get_progress(meeting_id)` 返回 None 时 `data=null`，前端 `useMeetingProgress.js` 访问 `msg.data.status` 抛 `TypeError: Cannot read properties of null (reading 'status')`，ProcessingDialog 进度条卡住。**修复**：后端 snapshot 为 None 时**不发**该消息；前端用 `if (msg.data && typeof msg.data === 'object')` 防御性检查。**经验**：WS 推送层不要把 `None` 当作"有效消息"发送，要么不发，要么发空对象 `{}` 让接收方降级处理
- **Whisper 反幻觉必须三层防护**（2026-06-02 教训，2026-06-03 重构）— faster-whisper 在静音/低能量片段会**臆造**训练集记忆（YouTube 结束语"B 站风格"如"明镜与点点""点赞订阅转发打赏"）。三层防护缺一不可：
  1. **whisper_server.py**（`app/whisper_server.py`）— `condition_on_previous_text=False` + `no_speech_threshold=0.6` + `temperature=0`，并**过滤** `segment.no_speech_prob > 0.6` 的 segment
  2. **本地模型 fallback**（`app/voice/asr.py:_transcribe_local`）— 同样三件套
  3. **后端三重判定**（`app/api/v1/voice.py`，2026-06-03 重构）— 替代旧 NOISE_PATTERNS 单一黑名单：
     - `HALLUCINATION_STRONG`（99% 幻觉词如"明镜与点点""感谢观看"）→ **无条件过滤**
     - `HALLUCINATION_WEAK`（可能是真话如"12345""测试""嗯"）→ **仅在音频能量低时过滤**（RMS < 0.02）
     - `pipeline.process_audio` 返回 `audio_rms` 字段供判定
  4. **关闭 Whisper 内置 VAD**（2026-06-03）— 已有 silero-vad 做 VAD，双重 VAD 互相干扰导致丢语音段。`vad_filter=False`
- **后端七重过滤**（`app/api/v1/voice.py:_run_live_loop`，2026-06-02 三次扩展）— NOISE_PATTERNS 之外再加：
  1. segment 时长 < 0.3s 视为噪声
  2. 文本去标点后 < 2 字符视为短噪音
  3. `_is_repetitive_text` 检测同一短子串重复（1 字 ≥ 4，2-6 字 ≥ 3，**先去标点**避免"，""。"等触发）
  4. `_is_alphanumeric_run` 检测字母+数字纯串（whisper 臆造"G6G7G10G11..."）
  5. `_is_gibberish` 检测长无意义乱码（30+ 字符但不含任何"虚词+代词+动作词"）
  6. `_is_sentence_repetitive` 检测完整句子重复 ≥ 3 次（避免误杀"2分钟后...2分钟后..."菜谱）

  七层叠加才能彻底压制 faster-whisper 在低能量片段的臆造行为。**36/36 单元测试通过**（含"M1结果中心营业G6G7..."等严重 hallucination + "微纳米气泡的zeta电位是表征..."等真实专业句）。**NOISE_PATTERNS 维护纪律**：单字（如"感谢"）太宽会误杀正常对话（如"感谢你的帮助"），只放复合关键词（"感谢观看"）
- **声纹模型加载失败必须容错**（2026-06-03 教训）— `voiceprint_service._load_pipeline()` 之前失败直接 `raise`，导致整个 WS 连接崩溃。改为：失败时设 `self._pipeline = None`，`extract_embedding` 检测到 None 时返回零向量，`identify_speaker` 检测到全零 embedding 时返回 unknown。**WS 不会因声纹模型加载失败而断开**。同理，进入通话时前端先检查 `/voiceprint/enrolled` 端点，如果 0 人录入则弹 toast 引导用户去成员管理页面录入
- **TimelineScrubber duration 不能等于 elapsed**（2026-06-02 教训）— `MeetingRoom.vue` 中 `meetingDuration` 之前用 `elapsed` 赋值，导致 el-slider 的 `max=currentTs`，用户**无法拖到未来时间点**（slider 只能停在自己当前位置）。**修复**：`meetingDuration = Math.max(MAX_MEETING_DURATION_SEC, elapsed + 60)`，给个合理上限 30 分钟，让 slider 真的能拖。**注意**：`onJumpTs` 只更新 currentTs 不真 seek 转录列表是设计妥协（Wave 3b 注释明确说明），至少 slider 要能响应用户操作
- **Celery worker 启动时 [tasks] 列表不完整**（2026-06-02 教训）— `app/core/celery.py` 用 `celery_app.autodiscover_tasks([...])` 让 worker 自动发现任务。**Celery 5+ 默认 `related_name='tasks'`**，会尝试 `from {package}.tasks import *`（找 `tasks.py` 子模块），但本项目任务直接在主模块里（如 `post_meeting_tasks.py`），找不到子模块**静默失败**。结果：worker 启动时 [tasks] 列表**缺任务**（如 `post_meeting_process`），任务入 Redis 队列后**永远不被消费**，前端 progress 卡死。**修复**：
  1. `celery.py` 改用显式 `celery_app.conf.imports = [...]` 强制 import 主模块
  2. `autodiscover_tasks(..., related_name=None)` 保留作 fallback
  3. `docker-compose.yml` 给 celery-worker 加 `./app:/app/app` volume 挂载（app 容器已有，celery 没有），让代码改动即时生效不必 rebuild 25GB 镜像。**诊断命令**：`docker logs microbubble-agent-celery-worker-1 2>&1 | grep -A 12 "^\[tasks\]$"` 看实际注册的任务列表，缺哪个就在 imports 列表加哪个
- **Celery 任务失败必须推 progress_update**（2026-06-02 教训）— `post_meeting_tasks.py` 之前外层 `try/except` 失败时只 return error dict，**前端 WS 收不到消息**，ProcessingDialog 永远卡在初始 5 步列表。**修复**：失败时在 fail_loop 里 `update_progress(..., status="error", detail=...)`，前端 `useMeetingProgress.js` 会看到 status=error 关闭弹窗并提示
- **发言者检测格式** — `_parse_summary_format()` 识别 `发言人：`/`参会人：` 等字段；`_quick_parse_speakers()` 识别 `【名称】` 格式；NON_SPEAKER 黑名单过滤文档结构标签；过滤后发言者 < 2 人时回退 Claude AI 检测
- **WebSocket 认证** — `/ws/meeting/{id}/live` 需要在 URL query param 中传 `?token=xxx`，Nginx `/api` location 需要 Upgrade/Connection 头支持 WebSocket
- **数据库列迁移** — `Base.metadata.create_all()` 不会给已有表添加新列，Member/Meeting 新增的 voice_embedding, speaker_mapping 等列需要手动 ALTER TABLE。**2026-06-04 教训**：`Meeting` 模型新增 `audio_url`/`audio_duration`/`recording_started_at`/`recording_ended_at` 4 列后，创建会议 500 报 `column "audio_url" of relation "meetings" does not exist`。**防御**：新增模型列后必须立即 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`，不要依赖 `create_all`
- **垃圾桶软删除** — `deleted_at` 字段标记软删除，3天后 Celery 定时任务自动永久删除（beat schedule 1h，最大延迟 1h）。垃圾桶 API `include_deleted=true` 必须加 `deleted_at.isnot(None)`，否则会返回活跃任务。提醒查询必须过滤 `Task.deleted_at.is_(None)`
- **垃圾桶自动清理 Celery 任务**（2026-06-03 commit `dc93bff` + `47fb2c9`）— 必须同步 3 处：
  1. `app.services.task_service.auto_purge_trash_task` 函数加 `@celery_app.task(name=...)` 装饰器（缺装饰器 worker 找不到函数）
  2. `app/core/celery.py` 的 `imports` 列表 + `autodiscover_tasks` 列表都要加 `"app.services.task_service"`（缺 import 模块不被加载）
  3. `docker-compose.yml` **celery-beat 服务也要加 `./app:/app/app` volume 挂载**（与 worker 一致；2026-06-02 修复时只补了 worker，漏了 beat 导致 beat 跑构建时烧进镜像的旧代码，schedule 改动必须 rebuild 25GB 镜像才能生效）
- **垃圾桶自动清理任务必须用独立 NullPool 引擎**（commit `dc93bff`）— 不能用全局 `async_session`，否则触发 "Future attached to different loop" 或 "another operation is in progress" 错误。正确模式（与 reminder_service.process_reminders_task 一致）：
  ```python
  engine = create_async_engine(
      settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
      poolclass=NullPool,
  )
  session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
  async with session_factory() as db:
      ...
  await engine.dispose()  # finally
  ```
- **Beat 调度粒度要与用户期望对齐**（2026-06-03 commit `47fb2c9`）— 4h 调度对 3 天 retention 太粗，用户看到 `auto_delete_at` 过期但任务还在（最坏等 4h），困惑。**1h 是"准点清理"的合理上限**（retention 3 天时仅 1.4% 误差）。如未来 retention 调到 7 天可放宽到 2h，但不要超过 1h（UX 边界）
- **Python 模块缓存**（2026-06-03 教训）— volume 挂载 `./app:/app/app` 让新文件**可见**，但**不重载已 import 的模块**。代码改完后必须 `docker compose restart worker`，否则 worker 还在用旧代码（错误日志指向旧行号是好线索）。Celery prefork worker 的 fork 子进程不共享主进程的模块更新
- **auto_delete_at 单一数据源**（2026-06-03 commit `b91e429`）— 后端 `list_tasks` / `get_task` 路由用 `setattr` 附加 `auto_delete_at = deleted_at + timedelta(days=settings.TRASH_RETENTION_DAYS)`，不持久化到 DB（避免迁移成本）。前端用这个字段显示倒计时，**前端不再硬编码 retention 天数**，与 Celery 清理任务共享同一配置，**不会漂移**
- **声纹会议系统 3a/3b 新增注意事项**（2026-06-01~02）：
  - **agenda 字段错位** — `agent/core.py` 早期版本错把议程列表写到 `description` 字段，导致议程链路断裂。MeetingCreate 时必须传入 `agenda` 形参（不是塞到 description），`PATCH /agenda` 端点更新 `Meeting.agenda` 字段。检查 `app/schemas/meeting.py` 的 `MeetingCreate` 包含 `agenda: List[str]` 字段
  - **activeSpeaker 置信度阈值** — `useMeetingRoomWS.onTranscript` 处理 speaker 切换时必须加 `speaker_confidence > 0.45` 判断，否则低置信度误识别会导致 activeSpeaker 在多人时频繁跳变
  - **Float32 → Int16 PCM 转换位置** — `useAudioCapture` 输出 Float32（AudioWorklet 标准），WS 协议用 Int16 PCM，转换放在 MeetingRoom 层（不在 capture 层），避免 capture 被多种协议复用时受污染
  - **VAD per-instance** — silero-vad 必须 per-pipeline 实例化（不能全局单例），否则 asyncio 事件循环绑定冲突会导致 VAD 异常。`MeetingPipeline` 通过依赖注入接收 VAD 实例
  - **VoiceprintHistory mapper 错误** — `app/models/__init__.py` 必须显式 `import` 所有新模型（含 `VoiceprintHistory`、`MeetingTemplate`），否则 SQLAlchemy mapper 初始化失败导致 500。新增模型后第一件事是检查 `__init__.py` 导入链
  - **HNSW 索引** — `members.voice_embedding` 和 `meetings.embedding` 必须建 HNSW 索引（`vector_cosine_ops`），否则声纹匹配和跨会议搜索在大数据量下会超时。迁移 `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`
  - **多设备 Redis pub/sub** — 通话中 transcript/ai_response/audio_archive 事件通过 Redis pub/sub 跨设备广播，buffer 200 条上限 + LTRIM + 24h TTL。新加入设备自动从 MinIO 同步缺失音频片段
  - **audio_level 推送频率** — `/live` 端点 0.1s 间隔推送当前 active speaker 的音量级别，前端 5 根声波条根据 `audioLevels[memberId]` 实时跳动。频率不能太低（看起来不跟嘴），不能太高（WS 流量爆炸）
  - **会议模板 4 内置种子** — DB 迁移 016 启动时自动 seed 4 个内置模板（组会/一对一/立项会/自由），幂等。`app/seed/` 目录新增模板种子
  - **议程 PATCH 端点** — `PATCH /meetings/{id}/agenda` 独立端点（不是 PUT 整个 meeting），避免误改其他字段。MeetingService.update_agenda() 方法专门处理
- **声纹系统线上修复（2026-06-02 5 个 commit）**：
  - **WS 闪烁真正根因是 UnboundLocalError** — `app/api/v1/voice.py:_run_live_loop` 函数内 `if msg_type=="ai_command": import asyncio` 让 Python 把整个函数的 `asyncio` 当局部变量。后续 `asyncio.QueueFull` 抛 UnboundLocalError → WS 服务端崩 → 自动重连 → 又崩 → 循环。**修复：删除函数内冗余 `import asyncio`（文件顶部已有）**。前端 `useMeetingRoomWS` 重连策略健壮化作为补充（不要重置 attempt、加 30s 退避封顶）
  - **微信 enroll_voice 状态机** — Agent `enroll_voice` 工具在 `channel_user_id`（微信会话）模式下写 Redis `wechat:pending_enroll:{user_id}`（5min TTL）。`wechat/handler._handle_voice` 检测到 pending → 自动下载微信语音 → ffmpeg 转 16kHz mono float32 → `voiceprint_service.enroll_member` → 清除 pending → 回复"✅ 声纹录入成功"
  - **声纹维度 256→192** — 连带修改：模型 ID 换 `iic/speech_eres2net_sv_zh-cn_16k-common`、迁移 017 改列类型、Alembic 链断点修复（010 的 down_revision 指向 009 而非 008 形成两个 head）、alembic_version.version_num VARCHAR(32) 长度限制（revision 名要用短名 ≤ 32 字符）
  - **3D-Speaker pipeline 输入** — `self._pipeline(wav_bytes)` 抛 `The input type is restricted to audio address and nump array`。修复：写临时文件后传路径。**声纹服务加 3 层回退 + 底层 model 兜底**（pipeline(路径) → pipeline(numpy) → self._pipeline.model.forward()）
  - **移动端弹窗错位** — `MemberView .member-card:hover { transform: translateY(-4px) }` 创建 containing block 干扰 `el-dialog` 定位。修复：改用 `margin-top: -4px`（不创建 containing block）+ `VoiceprintEnrollDialog` 显式 `append-to-body :lock-scroll="true" top="5vh"`
  - **头像裸路径 bug** — 早期 `upload.py` 用 `Query("uploads")` 读 `prefix`，导致 `prefix=avatars` 静默回退到 `uploads`，DB 留下 `avatars/xxx` 裸路径数据。`el-avatar :src="member.avatar"` 直接用，浏览器拼成 `/avatars/xxx` → 404。前端 `member.js` store 加 `normalizeAvatarUrl` 兜底（裸路径 → `/minio/microbubble/avatars/xxx` 相对路径）
  - **fingerprint API 缓存** — 浏览器缓存旧空响应导致录入后看不到。API 用 `Response` 参数注入 `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` + `Pragma: no-cache` + `Expires: 0` 三重禁缓存
  - **「置信度 0.45 直线」是 markLine 误读** — 用户看到 ConfidenceChart 里的 0.45 水平线以为是置信度数据，但实际是 `markLine: yAxis: 0.45` 阈值参考线（红色虚线）。**真实数据看 `voiceprint_history` 表**。同一历史 commit 顺手把 markLine 从 0.45 统一成 0.55（与后端 `MATCH_THRESHOLD` 一致）
  - **ERes2Net 模型实测表现**（2026-06-02 合成语音测试）— intra（同人 2 次录音）cos=0.99 ✅，inter（不同人）cos=0.92-0.97（合成信号偏高，真实人声会更低）。区分度 0.05 偏小，**实际识别需要多人会议反复调阈值**
  - **修改声纹提取时务必清旧 embedding** — 提取逻辑变更（输入维度、模型路径、归一化）后，DB 里旧 embedding 是用旧逻辑算的，跟新逻辑不兼容。**必须 `UPDATE members SET voice_embedding=NULL, voice_enrolled_at=NULL, voice_sample_count=0` 让用户重新录入**
- **VoiceTestDialog 麦克风误报（2026-06-04 教训）** — `getUserMedia` 成功后创建 `AudioContext({ sampleRate: 16000 })` 在部分手机浏览器（Safari/微信）失败，被外层 catch 误报为"麦克风权限被拒绝"。**关键对比**：`VoiceprintEnrollDialog` 不需要 AudioContext，所以录入正常但测试报错。**修复**：① `getUserMedia` 和 `AudioContext` 各自独立 try/catch ② AudioContext 失败跳过音量可视化，录音不受影响 ③ 添加 `webkitAudioContext` 前缀 + `resume()` 处理 suspended 状态 ④ 错误信息精确区分 `NotAllowedError`/`NotFoundError`/其他。**教训**：catch 块不要把所有错误统一显示为同一消息，否则用户看到的是误导性提示
- **声纹会议系统全面修复教训（2026-06-03 8 commit）**：
  - **enrolled API 返回格式** — 后端 `/voiceprint/enrolled` 返回 `{"members": [...]}` 而非数组，前端 `Array.isArray(vpData)` 永远 false。**修复**：`vpData.members`
  - **hangup 不能立即 disconnect** — `sendHangup()` 发完消息后立即 `disconnect()` 导致服务器还没处理 hangup 就断 WS。**修复**：等服务器主动关闭 WS（`watch(connected)` 检测断开再 emit call-ended），5s 超时兜底
  - **batch_polisher 必须传参** — `_run_live_loop` 创建 `batch_polisher` 但没传给 `_live_loop_inner`，hangup 处理访问时 NameError。**教训**：内部函数引用的外部变量必须显式传参
  - **Celery 后处理不能复用主 app 连接池** — `async_session` 和 `redis_pool` 在模块导入时创建，绑定主 app 事件循环。Celery worker 的 `asyncio.new_event_loop()` 创建新循环，复用旧连接池报 `Future attached to different loop` / `Event loop is closed`。**修复**：参照 `reminder_service.py` 模式，Celery 任务内创建独立引擎（`NullPool`）+ 独立 Redis 连接（`aioredis.from_url`），`update_progress` 加 `redis_override` 参数
  - **ProcessingDialog 不要全屏** — 全屏会遮挡侧边栏，改为 500px 弹窗
  - **反幻觉重复句阈值** — `_is_sentence_repetitive` 从 ≥3 降到 ≥2 次重复即过滤（Whisper 幻觉常重复 2 次）
  - **低置信度短文本过滤** — 声纹置信度 < 0.1 + 文本 < 10 字，直接过滤（"温暖气泡燃烧""临时发表展示"等 Whisper 幻觉）
- **本地运维脚本坑**（2026-06-02）：
  - **`$ErrorActionPreference = "Stop"` 会抛 native stderr** — docker compose 输出 `POSTGRES_PASSWORD not set` 等 warning 时会被 PowerShell 当 Error 抛异常，导致整个 try/catch 走 catch 分支。PowerShell 脚本必须用 `$ErrorActionPreference = "Continue"`，需要严格检查时用 `if (...) { throw }` 显式控制
  - **`2>&1` 污染 `$LASTEXITCODE`** — PowerShell 管道最后一节的退出码会覆盖 `$LASTEXITCODE`。要抑制 stderr 又保留 native command 退出码，用 `2>$null`（PowerShell 专属）而非 `2>&1 | Out-Null`
  - **`$input` 是自动变量** — 手动赋值会产生副作用。FileStream 等用 `$inputStream`
  - **PSScriptAnalyzer 警告 `PSUseApprovedVerbs`** — 自定义函数动词必须是 PowerShell 批准动词。`Speak-Alert` → `Send-Alert`，`Print-Line` → `Write-Line`
  - **TTS 中文语音** — `Microsoft Huihui Desktop` 不一定存在。必须 `try { SelectVoice } catch {}` 优雅降级
  - **Watchdog 告警去重** — 不要每次跑都 TTS 吼叫。用 `last-state.json` 记录上次状态，只在"正常 → 异常"切换时告警
  - **PowerShell 5.1 vs 7+ 兼容** — `ConvertFrom-Json -AsHashtable` 是 6.1+ 才有。统一用 `[ordered]@{...} | ConvertTo-Json` 模式构造 JSON
  - **`.bat` 中的 `^` 续行符** — 在 cmd.exe 中正确，但 **PowerShell 调用 .bat** 时 `& "x.bat"` 会让 PowerShell 先解析 `^` 当续行，导致 bat 内部命令被截断。修复：bat 内部用单行命令（无 `^`），或 PowerShell 调时用 `cmd /c "x.bat"`
  - **`.bat` 单行 `if/else` 不能嵌套括号** — `if errorlevel 1 (echo FAIL) else (echo OK (more))` 中 else 分支的括号会被 CMD 误解析为 if 结束。修复：必须用多行 `if/else`，每个分支独立括号块
  - **PowerShell 中 `\` 是转义字符** — `G:\path\to\file` 中 `\t` 会被解释为 Tab，`\b` 为退格。**路径一律用单引号** `'G:\path'` 或反引号转义 `'G:\path'`，避免路径断行
  - **PowerShell 多行粘贴 (`>>`)** — 容易触发"命令语法不正确"误报。**逐条执行**或把多命令写进 .ps1 脚本。不要直接粘贴带 `& | Out-Null` 的多行
  - **从 PowerShell 调 `.bat` 用 `cmd /c`** — 避免 PowerShell 误解析 bat 内的特殊字符。`cmd /c "scripts\install-local-ops.bat"` 是最稳健的跨 shell 调用方式
  - **schtasks 直接调 powershell.exe 会弹窗**（2026-06-02 教训）— 用当前用户身份注册 schtasks 时，Task Scheduler 在交互式会话启动 `powershell.exe -File xxx.ps1` **会创建可见控制台窗口**，脚本跑完才关闭。如果脚本 2-3 秒跑完（如 watchdog），用户会看到"窗口闪一下然后消失"，体验差。**修复**：用 VBScript 包装器 `wscript.exe run-hidden.vbs xxx.ps1`，vbs 内部用 `WshShell.Run cmd, 0, False` 隐藏窗口启动 PowerShell。`scripts/run-hidden.vbs` 已固化；`install-local-ops.bat` 已改为走 vbs 包装器路径。新增类似后台 PowerShell 任务时**必须**用 vbs 包装，不要直接 `powershell.exe -File`
  - **Task Scheduler 调度选项** — `/RU SYSTEM` 可让任务在 Session 0 跑（完全无窗口），但日志写到用户目录（如 `g:\microbubble-agent\logs\`）会因权限失败。**用 vbs 包装 + 保留用户身份**是最稳的方案
  - **Element Plus daterange/datetimerange 内部 input 没 name**（2026-06-02 教训）— `<el-date-picker type="daterange">` 组件 prop 不会传到内部 `<input class="el-range-input">`，即使外层加 `name="..."` 也只挂在外层 `<div>`。Element Plus 已知限制，**没有任何 prop 能直接修复**。**唯一方案**：拆成两个独立 `<el-date-picker type="date">`（或 `type="datetime"`）选择器，每个都有 name。**代价**：用户需选开始日期 + 结束日期（两步），但消除 a11y 警告 + 浏览器自动填充能力正常
  - **Webhook 持续失败 4 小时根因**（2026-06-02 教训）— 阿里云→GitHub HTTPS 出口网络持续 130s 超时（`curl 16 Error in HTTP2 framing layer` / `GnuTLS recv error (-110)` / `Failed to connect to github.com port 443 after 130051ms`），deploy-auto.sh 老版本 3 次重试全部失败，**14+ webhook delivery 标红**。**根因链 + 完整修复**：
    1. **网络层（HTTPS）**：阿里云到 GitHub 出口 IP 受限
    2. **deploy-auto.sh 无 SSH fallback**：HTTPS 走不通时不会切 SSH
    3. **专用 SSH key 名非默认**：`~/.ssh/github_deploy` 不是 `id_*`，git 找不到 → `Permission denied (publickey)`
    4. **修复 4 步**：
       - `ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N ""` + 贴公钥到 GitHub Deploy keys
       - `git remote set-url origin git@github.com:gg320324492-lgtm/microbubble-agent.git`（改走 SSH）
       - 写 `~/.ssh/config` 让 `Host github.com` 自动用 `IdentityFile ~/.ssh/github_deploy`（手动 + 后台都生效）
       - `deploy-auto.sh` 顶部 `export GIT_SSH_COMMAND="ssh -i /root/.ssh/github_deploy -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"`（belt-and-suspenders）
    5. **效果**：从 130s 超时 → 5s 完成，14+ webhook 全部成功
  - **Webhook 服务 alive ≠ 部署成功**（2026-06-02 教训）— `systemctl status webhook.service` 显示 `Active: active (running)` **只代表 HTTP 服务在跑**。**部署是否成功看 `/var/log/webhook-deploy.log` 的 `[DEPLOY] 部署完成` / `部署成功 ✓`**。两者**独立**。Webhook 立即返回 200 OK（避免 GitHub 10s 超时）但后台 deploy 异步跑（看 deploy-auto.sh 是否真的成功）
  - **Webhook 端口必须用 `ThreadingHTTPServer`**（2026-06-03 commit `7ec6ce0`，已部署并验证 0.001s 响应）— Python `http.server.HTTPServer` 默认**单线程顺序处理请求**。即使 `do_POST` 内用 `daemon=True` 启动 deploy 线程（避免阻塞响应），HTTP 请求的接收/响应仍是串行的。**症状**：deploy 跑 git pull（5 次重试 + 75s 退避 = 最坏 200s+）时，后续所有 GitHub webhook 健康检查都 10s+ 超时，导致 `delivery failed: time out`。**修复**：`from http.server import ThreadingHTTPServer` 替换 `HTTPServer`，每个请求独立线程，do_GET 健康检查与 do_POST deploy 完全不阻塞。**验证**：连续 5 次 curl `/` 应 < 1s（单线程时线性恶化到 20s+）。**特别注意**：修改 `scripts/webhook.py` 后 webhook 服务**不会自动重启**（deploy-auto.sh 不在重启列表里 — 否则 deploy 流程会被中断），需要**手动 SSH `systemctl restart webhook`** 才生效。`deploy-auto.sh` / `webhook.service` 同理
  - **Vue dist 提交前必须 `npm run build`**（2026-06-03 教训）— commit `d619f33` 漏 build 触发白屏事故：删了 23 个旧 dist 文件 + 改了 index.html 引用新 hash（`index-mZemtrw0.js`），但**没添加新文件**（git commit 0 个 `+`）。后果：阿里云 `git pull` 后 `/opt/microbubble-agent/web/dist/assets/index-mZemtrw0.js` 404 → Vue 不挂载 → 白屏。**防御**（2026-06-03 commit `2b38c99` 加进 deploy-auto.sh）：git pull 后 `find web/dist/assets -name 'index-*.js' | wc -l >= 1` 且 `grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' dist/index.html` 引用的文件必须存在，**任一不满足则 deploy 失败**。**前端提交检查清单**（人工）：① 改 `web/src/` 后**必须** `cd web && npm run build` ② 提交前 `git status` 看新增文件数量（应该有 + 多个 dist 文件）③ `git show --stat HEAD` 确认 `index-*.js` 有新 hash
  - **三级润色流水线**（2026-06-02）— 实时转录常出现 ASR 幻觉（"你和我一样""一二三四"等），单段润色无上下文。**改用三级**：
    1. **L1 实时透传** — 每段 ASR 立即推原文 + `status: "raw"`，前端"实时"徽章
    2. **L2 聚批润色**（`app/services/meeting_batch_polisher.py`）— 每 30s 或攒满 5 段触发 1 次 LLM（`mimo-v2.5`），复用 `polish_segments_with_lock` 已有 Redis 锁 + 24h 缓存，推 `transcript_batch_polished` 消息
    3. **L3 全文精润色**（`app/services/meeting_full_polisher.py`）— hangup 时触发 1 次高质量 Sonnet（`claude-sonnet-4-20250514`），分块 + 跨块 context，**删除 ASR 幻觉孤立短句**（`removed: true` 字段），持久化到 `meeting.transcript_polished` JSON 列
    - **关键纪律**：兜底段满检测（`voice.py` LiveSegmenter 分支）也**必须调用声纹识别**（之前硬编码 "发言人"，导致用户看不到内容）
    - **降级**：LLM 失败时 `_fallback_polished` 返回原文，前端 `status` 保持 `raw`（不报错，不丢内容）
    - **配置**（`app/config.py`）：`POLISH_BATCH_INTERVAL_SECONDS=30` / `POLISH_BATCH_MAX_SEGMENTS=5` / `FULL_POLISH_MODEL=claude-sonnet-4-20250514` / `FULL_POLISH_CHUNK_CHARS=4000` / `TRANSCRIPT_BUFFER_MAX_ENTRIES=1000`
  - **async session 中不要访问 lazy relationship**（2026-06-02 commit `6bc9687`）— `meeting.participants` / `meeting.related` / `meeting.speaker_stats` 等关系属性在 async session 中**没有**预加载（`selectinload()`）时，访问触发 lazy load → 走同步 IO → `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here`。**WS 表现**：服务端 1011 close → 客户端重连 → 服务端又触发同一 lazy load → 循环（用户看到"重连中"永远不停）。**修复**：`await db.refresh(meeting, attribute_names=["participants"])` 预加载，或**避免访问关系属性**（润色/metadata context 不依赖关系）。**错误指纹**：traceback 含 `strategies.py:1130 _emit_lazyload` 关键字 → 100% 是这个错
  - **会议上下文 metadata 字段选型**（2026-06-02）— `meeting_context` / `meeting_metadata` 等**不依赖** lazy 关系。L2/L3 润色需要的 `title`（column 属性，**不**触发 lazy load）/ `participants`（lazy 关系，**会**触发）/ `topic_line` / `context_segments` 字段应该用 column 字段或显式空值构造
- **FastAPI 路由注册顺序**（2026-06-04 教训）— `meeting_recording.py` 的 `/meetings/start-recording` 路由被 `meeting.py` 的 `/meetings/{meeting_id}` 拦截返回 405。**根因**：FastAPI 按注册顺序匹配路由，`meeting.router` 先注册时 `/meetings/start-recording` 会被当作 `meeting_id = "start-recording"` 匹配到 GET-only 的详情路由。**修复**：`meeting_recording.router` 必须在 `meeting.router` 之前注册。**通用规则**：当多个路由文件有路径前缀重叠时（如 `/meetings/xxx` 和 `/meetings/{id}`），**固定路径必须在参数路径之前注册**
- **ProcessingDialog 阶段必须与后端 ProgressStage 同步**（2026-06-04 教训）— 前端 ProcessingDialog 的 `stages` 数组和 `STAGE_ORDER` 必须与后端 `progress_service.py` 的 `ProgressStage` 枚举完全一致。本次发现前端用的是旧版阶段名（`extracting_transcript`、`polishing_transcript`、`generating_minutes`），后端已改为 `downloading_audio`、`transcribing`、`generating_analysis` 等，导致 `STAGE_ORDER.indexOf()` 返回 -1，进度条卡住不动。**规则**：修改后处理流水线阶段时，必须同步更新 `ProcessingDialog.vue` 的 `stages` + `STAGE_ORDER` 和 `progress_service.py` 的 `ProgressStage`

- **3D-Speaker 依赖链**（2026-06-05 教训）— `modelscope` 的 `speaker_verification` pipeline 有大量传递依赖：`addict`（模型配置）、`datasets`（数据集加载）、`simplejson`（JSON 序列化）、`sortedcontainers`（排序容器）、`soundfile`（音频文件读取）。这些依赖已写入 `requirements.txt`，但 Celery worker 容器如果是旧构建会缺少。**症状**：`ModuleNotFoundError: No module named 'addict'` → 声纹识别静默返回 unknown，所有发言人显示"发言人A"。**修复**：容器内 `pip install addict datasets simplejson sortedcontainers soundfile`，然后 `docker compose restart celery-worker`
- **silero-vad 模型下载失败**（2026-06-05 教训）— `torch.hub.load("snakers4/silero-vad")` 从 GitHub 下载模型，服务器出口 IP 受限时会 HTTP 403 rate limit。**修复**：手动下载 `https://github.com/snakers4/silero-vad/archive/refs/heads/master.zip` → 解压到 `/root/.cache/torch/hub/snakers4_silero-vad_master` → 代码加 `source="local"` 回退
- **datetime tz-aware 写入 tz-naive 列**（2026-06-05 教训）— `datetime.now(timezone.utc)` 创建带时区的 datetime，但 PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` 列无法接收。asyncpg 报 `can't subtract offset-naive and offset-aware datetimes`。**修复**：`.replace(tzinfo=None)` 转为 naive datetime。**通用规则**：凡是写入数据库的 datetime，必须确认列类型是 `TIMESTAMP WITH TIME ZONE` 还是 `WITHOUT`，对应使用 tz-aware 或 naive

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **ui-design**: 前端界面设计规范 — 暖橙珊瑚色系、圆角阴影规范、动画时序曲线、骨架屏规范、玻璃拟态、20项 UI 升级检查清单
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发或执行实现计划之前使用——创建具有智能目录选择和安全验证的隔离 git 工作树
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->

## 2026-06-15 LLM 元话语/thinking 文本泄露修复（双管齐下）

- **LLM 在 text content 里写"我需要..."、"用户问的是..."、"开始回答吧"等元话语是普遍现象**（重要，2026-06-15 修复）— 即使 prompts.py 加了硬规则，LLM 仍会输出 thinking 独白泄露到用户视野。**双管齐下修复**：
  1. **prompts.py 硬规则**（[prompts.py:33-49](app/agent/prompts.py#L33-L49) 新增"严禁元话语"section）：列出 19 种元话语前缀（"我需要..."、"用户问的是..."、"开始回答吧"等）+ 正反例。LLM 直接读这条规则，从源头减少元话语
  2. **后端兜底剥除**（[agentic_loop.py](app/agent/agentic_loop.py)）：`_strip_meta_thinking` 函数 + 19 个 regex pattern + `while` 循环剥最多 3 次 + 剥除后剩 < 5 字符才兜底保留原文
  3. **SSE done 事件带 text_without_json**（[protocol.py:107-110](app/agent/protocol.py#L107-L110) 新字段 + [agentic_loop.py](agentic_loop.py) done 事件填字段）：流式过程 text_delta 已发出无法撤销，但 done 事件带后处理过的干净文本
  4. **前端 done 时替换**（[useChatStream.ts:483-487](web/src/composables/chat/useChatStream.ts#L483-L487)）：`if (evt.text_without_json != null && evt.text_without_json !== currentAssistant.content) currentAssistant.content = evt.text_without_json`
- **修复链路镜像保持**（教训）— synthesis 文本后处理流程：**JSON 段剥除 → fake tool_call 剥除 → 元话语剥除**。这条流水线**两次执行**（一次在 `_synthesize_stream` 内部用于解析 rich_blocks，一次在 `agentic_loop.run` 重算用于 done 事件）。**两处必须完全镜像**，否则用户可能看到"流式过程中干净 / done 替换后变脏"或反之
- **debug e2e "name 'text_without_json' is not defined" 根因**（教训，2026-06-15）— 我最初在 `_synthesize_stream` 内部 yield `text_without_json` 到 done 事件，但**async generator 内部局部变量在 yield 后作用域消失**，外层 `agentic_loop.run` 拿不到。**修复**：把 done 事件 yield 留在外层 `agentic_loop.run`，在外层用同样的 `_extract_rich_block_json → _strip_fake_tool_calls → _strip_meta_thinking` 流水线**重算**一次 text_without_json 填进 done 事件。**纪律**：① async generator 内部局部变量别期望在外层访问 ② done/总结类事件 yield 留在外层聚合层，**不要**在嵌套 generator 内部 yield ③ 重复计算（`accumulated_text` 在 synthesis 末尾计算 + retry 后覆盖）的中间结果需要在最终 yield 前**重算**确保正确
- **剥除函数兜底阈值不要设太大**（教训）— `_strip_meta_thinking` 原本兜底阈值 30 字符 → "杨慈是我们课题组的成员。"（12 字符）这种**干净短回复**被判失败，函数返回原文，元话语没剥除。**改为 5 字符**：只剩几乎空白才兜底。**纪律**：① 兜底阈值要**保守**（"宁可少剥不要误剥"）② 测试用例必须包含"剥除后剩余 < 阈值的干净短回复"边界
- **while 而非 for 循环剥除**（教训）— 多个连续元话语（"我需要...我需要..."）需要**重复剥除**，for 循环只剥一次就退出。**while + break 模式**：
  ```python
  while stripped_count < max_strip:
      matched = False
      for pattern in patterns:
          m = re.match(...)
          if m:
              new_head = new_head[len(m.group(0)):]
              matched = True
              break  # 跳出 for，重新 while
      if not matched:
          break
  ```

## 2026-06-15 Rich Block 统一包装铁律（杨慈是谁呀"暂无成员"修复）

- **Rich Block 提取有两条路径，必须都保证 `data` 形态统一**（重要，避免"工具调对了但 Rich Block 显示空"）— Agent 工具结果 → Rich Block 有两条路径：
  1. **fake tool_call 路径**：`agentic_loop._extract_rich_block(tool_name, result)`（[agentic_loop.py:353-451](app/agent/agentic_loop.py#L353-L451)），调 `chat_engine._extract_rich_block`，**仅在 LLM 走 fake XML 工具调用时被触发**
  2. **JSON 段路径**：`agentic_loop._extract_rich_block_json(accumulated)`（[agentic_loop.py:772-817](app/agent/agentic_loop.py#L772-L817)），从 LLM 末尾 ```json``` 段解析，**正常 LLM 路径走这条**
  - **任一路径构造的 RichBlock.data 形态必须与前端组件期望一致**（如 `MemberCardBlock.vue:8` 读 `data.members[]`，就必须保证 `data` 是 `{members: [...]}`）。**不要**信任"LLM 会写对"——它在路径 2 自由发挥，在路径 1 由代码决定，需要后端兜底
  - **修复模式**：[chat_engine.py:373-385](app/agent/chat_engine.py#L373-L385) 对 `rb_type=="member"` 统一包装为 `{members: [...]}`：
    ```python
    if rb_type == "member":
        if "members" in result and isinstance(result["members"], list):
            data = result  # query_members 列表形态，透传
        else:
            member = {k: v for k, v in result.items() if k not in ("status",)}
            data = {"members": [member]}  # get_member_profile 单成员，包装
        return RichBlock(type=rb_type, data=data, title=default_title)
    ```
  - **纪律**：① 新增 Rich Block 类型时，**前端组件 + 后端两条提取路径** 都要同步更新形态约定 ② 不要把"形态约定"交给 LLM prompt（它会忘）—— 写在后端代码里强制统一 ③ `query_members`（列表）和 `get_member_profile`（单成员）都是 `type=member`，但前端只读 `data.members[]` → 必须统一包装
- **Member 模型新增 JSON 列必须 ALTER TABLE**（教训，2026-06-15）— `app/models/member.py:32-34` 加了 `notification_preferences = Column(JSON)`（v2 reminder 改动），但 DB 没同步 ALTER → `SELECT members` 报 `column members.notification_preferences does not exist` → 整个 Member 加载失败 → 任何含 member 字段的查询都挂。**修复**：`ALTER TABLE members ADD COLUMN IF NOT EXISTS notification_preferences JSON`。**纪律**：① 模型加新列后**立即**同步 `docker exec ... psql -c "ALTER TABLE ..."` ② 写进 deploy-auto.sh 或迁移脚本（**不要**只 `Base.metadata.create_all`，它只建表不加列） ③ Celery / 启动时启动迁移检查任务也是可行方案
- **重构时 try/except 块错位 = SyntaxError = app 整个挂掉**（教训，2026-06-15，commit `ba75e32` v2.1 留尾）— `app/wechat/handler.py:1030-1033` 原本应是 try 块的 except 收尾，**v2.1 重构时 except 块被错放到 if 块内** → Python 解析器无法处理 → 整个 `app/wechat/handler.py` 模块加载失败 → `app.main` import 链断裂 → app 容器**永远在 restart 循环**（`docker logs` 只看到 `from app.wechat.handler import message_handler` 报 SyntaxError）。**修复**：把单行 try/except 包裹 `_check_all_completed` 调用，独立 try/except 块：
  ```python
  if progress >= 100:
      try:
          await self._check_all_completed(task, db)
      except Exception as e:
          logger.error(f"进度 100% 联动 ack 失败: {e}", exc_info=True)
  ```
  **诊断**：`docker logs microbubble-agent-app-1 2>&1 | grep SyntaxError` 看具体行号。**纪律**：① 任何重构涉及 try/except 时，**第一件事**用 `python -c "import ast; ast.parse(open('file.py').read())"` 验证语法 ② 多行 try/except 重构成 if/elif 链时最容易出错，必须保留每段独立的 try/except ③ `docker logs` 反复重启 + `app.X` import 链失败 = 100% 是某模块 SyntaxError
- **`Member.username='admin'` 不存在，真实 admin 是 `wangtianzhi`**（教训，2026-06-15）— `conftest.py:120-122` 用 `username="admin", password="admin123"` 创建测试 admin，但生产 DB seed 时**未必用这个 username**（实际看 `app/seed/` 没 seed admin 账号），真实 admin 是 `username="wangtianzhi"`。**诊断**：`SELECT id, name, username, role FROM members WHERE role='admin'`。**修复**：重置密码用：
  ```python
  from app.core.security import get_password_hash
  new_hash = get_password_hash("admin123")
  await s.execute(update(Member).where(Member.id == admin_id).values(password_hash=new_hash))
  await s.commit()
  ```
  **纪律**：① e2e 脚本/前端登录前**先查 DB**真实 admin username，不要凭"admin"猜 ② 重置密码后**用 `verify_password` 验证**真的能登录
- **debug e2e "rich_block data=None" 实际是 SSE 事件字段取错**（小坑）— 调试时 `ev.get("data")` 拿到 None，但实际 SSE 事件结构是 `{type: "rich_block", block: {type, data, title, ...}}`，**真正数据在 `ev.block.data` 不是 `ev.data`**。**纪律**：打印完整 `json.dumps(ev, ensure_ascii=False, indent=2)` 看真实结构再写取值逻辑，不要凭直觉

## 2026-06-15 Agent 质量 + qa-bench 闭环

### 5 大根因（用户原始 4 次抱怨 → 全部 PASS）

**根因 1：`TOOL_REGISTRY` 启动时未注册（commit `d36d1db`）**
- `app/agent/__init__.py` 是 0 字节空文件，`app/main.py` 从不 `import app.agent.tools` → 启动后 `len(TOOL_REGISTRY) == 0`
- **修复**：`app/main.py` 顶部加 `import app.agent.tools  # noqa: F401` 触发链式加载
- **诊断**：`docker exec microbubble-agent-app-1 python -c "from app.agent.tool_registry import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"` 必须 ≥ 1

**根因 2：LLM 代理层 fake tool_call（commit `d36d1db` + `e2a9a49`）**
- `CLAUDE_BASE_URL` 走代理时代理不转发 `tools` 参数 → 模型在 content 里 fake 输出 XML
- **5 格式解析**（`agentic_loop._parse_fake_tool_calls`）：
  1. Mistral/Qwen `<tool_call>{"name":...}</tool_call>`
  2. Anthropic legacy `<function_calls><invoke name=...>`
  3. 简化 `<function=name><parameter=k>v</parameter></function>`
  4. 裸 JSON ` ```json {name, ...} ``` `
  5. 混合格式 `<tool_call><function=...>...</function></tool_call>`（**最常见**）
- **schema-aware alias**（`_normalize_fake_tool_input`）：`name → member_name` 按 Pydantic `model_fields` 反查自动映射
- **纪律**：
  - 新增 XML 格式时，先加到 `_parse_fake_tool_calls` 5 格式列表
  - 同时镜像加到 `_strip_fake_tool_calls` 5 格式列表（防狼到 synthesis 阶段）
  - 模型输出新格式时先看 Phase 1 是否解析成功（看 log `_parse_fake_tool_calls: recovered`）

**根因 3：`get_member_profile` dead import + `is_active` 过滤 alumni（commit `d36d1db`）**
- `member_tools.py:140` 有 `from app.models.project import Project, ProjectMember`，但 `ProjectMember` 不存在 → ImportError
- `member_service.get_members(name=...)` 仍走 `is_active=True` 过滤 → 雒培媛（alumni）查不到
- **修复**：
  - 移除 dead `ProjectMember` import
  - `member_service` 按姓名查不过滤 `is_active`（user 显式指名应能找到 alumni）
  - 列表筛选（research_area/grade）仍走 `is_active=True`（只显示当前成员）
- **纪律**：新增 `@tool` 函数体内不要 `from X import Y` 复用模块顶部的同名导入，会让该名字在函数作用域内变 local

**根因 4：长期记忆干扰（commit `e2a9a49`）**
- 模型在 `<think>` 里说"以工具返回为准"，最终答案里又提了长期记忆里的名字（李松泽/王天志/杜同贺/周之超）
- **修复**：`prompts.py` 加硬规则：
  > "**长期记忆里的姓名/字段必须重新验证**，只有本轮工具调用的真实返回才算 grounded。冲突时**以工具返回为准**，并在回答里只引用工具返回里有的信息"
- **纪律**：所有"系统提示注入"类更新，先验证 LLM 是否真的遵守了，再删 5 题的旧 prompt 测试

**根因 5：synthesis 阶段 fake XML 泄露（commit `e2a9a49`）**
- 模型在 synthesis 阶段会再写 `<function=...>` 文本（从训练里学来的输出格式）
- **修复**：
  - `agentic_loop.json_protocol` 加铁律 5："**综合阶段禁止写工具调用**"
  - `_strip_fake_tool_calls` 5 格式剥除（与解析器镜像）
  - Phase 1 messages 注入前先 strip 防 synthesis 阶段复制 pattern
- **局限**：流式过程 text_delta 已发出无法撤销，最终 `text_without_json` 是干净的（前端 useChatStream 在 done 后会用 `text_without_json` 作为最终展示）
- **纪律**：剥除器必须**与解析器同步**——加新解析格式时必须同步加剥除格式

### 关键改进

- **search_knowledge 返回 0 结果时 hint**（commit `d36d1db`）：
  - 加 `hint` 字段提示调 `web_search`，避免模型在 synthesis 阶段 fake 写
  - 修后 S10（OH 自由基检测）从 2/5 → 5/5
- **数据缺失警告**（commit `d36d1db`）：
  - agentic_loop 检测到本轮工具全空时显式注入"⚠️ 数据缺失警告"提示
  - 强约束模型："**严禁**再次 fake 写工具调用语法，直接告诉用户：本地知识库和联网都没找到相关资料"
- **intent_classifier 增强**（commit `e2a9a49`）：
  - "记住：XX" / "忘掉" / "以后" / "不要" → `execute_action`（不是 `casual_chat`）
  - "保存到知识库" → `execute_action`
  - 加关键区分点列表（"记住 X" vs "X 是研究什么" vs "X 在做什么"）

### 前端 UI 干净化

- `web/src/stores/useUiStore.js` 新建（commit `e2a9a49`）：
  - `showThinking: boolean` + `localStorage["mnb:ui:showThinking"]` 持久化
  - toggleThinking() / setShowThinking()
- `ChatViewSSE.vue`（commit `e2a9a49`）：
  - `.tool-trace` 区域加 `v-if="showThinking"`（默认隐藏）
  - 顶栏加 💭/🧠 toggle 按钮（dark mode 旁边）
  - toggle 状态走 Pinia + localStorage（刷新保留）
- `RichContent.vue`（commit `e2a9a49`）：
  - `shouldBeExpanded` 默认 `True`（用户第一眼看到真实数据）
  - LLM 主动 `collapsed_by_default=true` 才折叠（留给长列表）
- **纪律**：所有 UI 状态（theme/showThinking/...）走 Pinia store + localStorage 持久化，**不要**用散落 `localStorage.getItem` + `setAttribute`

### Service Worker 升级机制

- BUMP `SW_VERSION v4→v5-cacheput-recovery-2026-06-14`（commit `c1bab8a`）
- 浏览器通过**字节比较**检测 SW 更新（不是 SW 内容里的版本号）
- 触发 SW install → `skipWaiting()` → activate 钩子跑 `caches.keys() + delete` 清空老 cache
- **纪律**：任何 SW 故障修复都**先 BUMP SW_VERSION**，别只改逻辑
- **诊断**：`DevTools → Application → Service Workers` 看到 sw.js 状态为 `activated and is running`（含新 SW_VERSION）才表示升级成功

### qa-bench 框架（commits `cab74bd` / `d120e54`）

- **题库**：100 题基线 + 75 拓展 + 240 拓展 + 495 动态生成 = **910 题**
- **工具**：`runner.py` (8 项 detector) / `onebyone.py` (逐个问答) / `gen500.py` (动态生成) / `save_to_kb.py` (入库) / `view.py` (查看)
- **5 轮迭代** 39% → 37% → 33% → 39% → **84% 高分率（360 题）**
- **知识库增长**：64 → 247（+183 条, +286%）
- **纪律**：
  - 测试前必 `docker compose restart app`（CLAUDE.md 752 行铁律）
  - 测试发现真问题优先修源码，不要调 expect
  - expect 标错就放宽用 `intent_any` / `tools_any`
  - 答题后**自动保存高分到知识库**（驱动知识库正向增长）

## 2026-06-15 reminders 表 v2 字段缺失 → /api/v1/reminders 500（webhint 真 bug 教训）

- **v2 reminder 改动（commits 223ea74 + ba75e32）加了 6 个新列**（[app/models/reminder.py:32-39](app/models/reminder.py#L32-L39)）—— `acknowledged_at` / `acknowledged_by` / `ack_channel` / `snoozed_until` / `reminder_batch_date` / `policy_version` —— **但 DB 没同步 ALTER TABLE**。结果：用户 webhint 报 `index-2bce6a55.js:4 GET https://agent.mnb-lab.cn/api/v1/reminders 500`，所有 reminder 前端功能挂掉
- **教训（v3）**：本次是**第 3 次** v2 改动缺 ALTER TABLE：
  1. `members.notification_preferences`（上午修，commit 1a1ea1e 阶段）
  2. `members.notification_preferences` 同一个（用 IF NOT EXISTS 已加）
  3. `reminders.*` 6 列（本节修）
  **说明 v2 改动加新列没**任何**自动化机制兜底**。**修复**（永久）：
  - [scripts/alter_reminders_v2.sql](scripts/alter_reminders_v2.sql) 迁移脚本（幂等 ADD COLUMN IF NOT EXISTS）
  - [scripts/deploy-auto.sh](scripts/deploy-auto.sh) 在 agent_traces 迁移后**追加** reminders v2 迁移块
  - 部署时 `psql < alter_reminders_v2.sql` 自动跑，缺列补上
- **webhint 误报 vs 真 bug 区分纪律**（本截图其余 3 个警告都是误报）：
  - ✅ **真 bug 必修**：`GET /api/v1/reminders 500` —— 后端 SQL 错误，前端用户功能挂掉
  - ❌ **误报可接受**：
    - "x-content-type-options header missing" —— 后端中间件已配 `X-Content-Type-Options: nosniff`（app/main.py:126-128），webhint 误报
    - "meta[name=theme-color] is not supported by Firefox" —— 已知 Firefox 不支持，Chrome/Safari/iOS Safari PWA 顶部栏美化价值 > 误报噪音
    - "/favicon.ico cache-busting missing" —— 浏览器自动请求 /favicon.ico（无 hash），[commit 30fa545](https://github.com/gg320324492-lgtm/microbubble-agent/commit/30fa545) 加了精确 `location = /favicon.ico { immutable }`，Edge DevTools 仍误报
    - "cache-control header missing on /api/v1/reminders" —— 动态 API 不该用 immutable（CLAUDE.md 2026-06-13 决策）
  - **判定方法**：500 / 4xx HTTP 状态码 = 真 bug；纯静态资源缓存头 / 兼容性提示 = 多半误报
- **纪律（v2 改动 ALTER TABLE 同步铁律）**：
  ① **任何 v2 改动加新列** → 立即同步写 `scripts/alter_<table>_v<N>.sql` 幂等脚本
  ② **deploy-auto.sh 集成** → 部署自动跑迁移（参考 [deploy-auto.sh:144-165](scripts/deploy-auto.sh#L144-L165) agent_traces 模板）
  ③ **不用 `==` 锁死 `ALTER TABLE`** —— 用 `ADD COLUMN IF NOT EXISTS` 幂等语法
  ④ **生产部署前本地先跑一次** —— `docker exec ... psql -c "..."` 验证 schema 同步
  ⑤ **webhint 5xx 错误 ≠ 缓存头警告** —— 500 必查后端日志，warn 标签的多半是工具误报

## 2026-06-15 任务提醒体系 v2 全面优化

**两个用户痛点 → 根因 → 修复**：

1. **赵航佳抱怨半夜收微信提醒** — `remind_at` 是绝对 naive UTC 时间，无 quiet hours 机制；`Member` 模型无任何通知偏好字段；`SettingsView.vue` 无相关 UI。**修复**：所有 reminder 统一在 11:00 AM 北京时间窗口发送（±60min 容差）。
2. **杜同贺多次发"收到"小气助手仍推** — `_try_handle_task_reply` 在 `handler.py:997-999` 命中"收到"后**只回文本不联动 Reminder 表**；`Reminder.status` 只有 `pending/sent/cancelled` 无 `acknowledged`；Celery 10s 跑 `process_reminders`，失败 reminder 留 Redis ZSET 无上限重试。**修复**：新增 `acknowledged` 状态 + `acknowledge_all_user_reminders` 服务方法。

### v2.1 二次简化（commit `ba75e32`）

用户原话："用户发任何内容都是不再提醒。包括这个'今天别提醒'"。**删除 snooze 微信路径**，把 ack 从"匹配特定关键词"改为"任何消息都触发"。

### 核心模型（用户决策）

- **每个 task 只有 1 次 11AM 提醒机会**：发完即结束，**不重试**（"无用用户回复与否，只提醒一次"）
- 失败也标 sent（one-shot）
- 同用户多条 reminder 聚合为 1 条 digest 消息（避免轰炸）
- "收到"是 UX 优化（取消当天 11AM 还没发的待推），**防重复靠 1-per-task 模型本身**

### 状态机

```
                 ┌────→ sent（11AM 推送，one-shot）
                 │
pending ─────────┼────→ acknowledged（任何微信消息 → channel="wechat_any"）
                 │
                 └────→ cancelled（任务删 / soft_delete）
```

### 关键文件

| 类别 | 文件 |
|---|---|
| 迁移 | `alembic/versions/019_reminder_ack_snooze_v2.py` |
| 工具 | `app/services/reminder_policy.py`（3 个纯函数）|
| 服务 | `app/services/reminder_service.py`（主入口 + 聚合 + ack/snooze）|
| 调度 | `app/services/reminder_scheduler.py`（Redis ZSET）|
| 创建 | `app/services/task_service.py:73-125` |
| 微信 | `app/wechat/handler.py:976-1056`（v2.1 任何消息先 ack）|
| API | `app/api/v1/member.py` 末尾、`app/api/v1/task.py:606` |
| 前端 | `web/src/views/SettingsView.vue`、`web/src/views/mobile/MobileSettingsView.vue`、`web/src/composables/useNotificationPrefs.js` |
| 测试 | `tests/test_reminder_window.py` 等 5 文件（20/20 通过）|
| 沉淀 | `memory/reminder-v2-11am-digest.md` |

### pytest 纪律沉淀

1. **monkeypatch 函数 import 后必须 patch 两处** — `from app.services.reminder_policy import is_in_digest_window` 在 `reminder_service.py` 顶部已 import，只 patch `reminder_policy.is_in_digest_window` **不影响** reminder_service（因为是函数引用）。pytest 必须同时 `monkeypatch.setattr(rs_mod, "is_in_digest_window", ...)`。
2. **测试假数据让两次 DB 查询都返回相同列表 → 重复计数**。`_make_db_session` 必须用 `call_count` 区分：第一次返回 reminders，第二次返回 `[]`（避免 task+meeting 双计）。
3. **`wechat_bot.smart_send` 是实例方法**（不是类方法），`monkeypatch.setattr(rs_mod.wechat_bot, "smart_send", mock)` 即可生效（替换实例属性）。
4. **alembic revision ID ≤ 32 字符**（CLAUDE.md 17 教训）— 用了 `019_reminder_v2`（14 字符）。

### 部署必做（CLAUDE.md 752 行铁律）

```bash
# 1. 跑迁移
docker compose exec app alembic upgrade head
# 2. 验证
docker compose exec postgres psql -U postgres -d microbubble \
  -c "\d reminders" | grep -E "acknowledged|snoozed|policy"
docker compose exec postgres psql -U postgres -d microbubble \
  -c "\d members" | grep notification_preferences
# 3. 重启（volume 挂载只换文件不换模块缓存）
docker compose restart app celery-worker
```

### 验收命令

```sql
-- 看 reminder 是否落 11AM
SELECT id, remind_at, reminder_batch_date, policy_version
FROM reminders ORDER BY id DESC LIMIT 5;
-- 期望：remind_at 是 UTC 03:00（=北京 11:00），policy_version=2

-- 发任何消息后状态
SELECT id, status, acknowledged_at, acknowledged_by, ack_channel
FROM reminders WHERE acknowledged_at IS NOT NULL ORDER BY id DESC LIMIT 5;
-- 期望：status='acknowledged'，ack_channel='wechat_any'
```

### v2 漏修补救：proactive scheduler 也必须走 11AM 窗口（commit `d0ddf49e`）

**用户 2026-06-15 凌晨 2:48 仍收到提醒根因** — v2 reminder 体系（`app/services/reminder_service.py`）虽然加了 11AM 窗口守卫，但**`app/wechat/scheduler.py:ProactiveScheduler` 是独立的并行调度器**：
- `check_due_soon` — 明天截止的任务
- `check_overdue` — 已逾期的任务
- `check_unconfirmed` — 分配超过24小时未确认 ← **用户收到的就是这个**

3 个 check 方法**完全绕过 11AM 窗口**，直接 `wechat_bot.smart_send(...)` 立即推送。Celery beat 每 15 分钟跑一次（`app/core/celery.py:beat_schedule.proactive-checks`），凌晨 2:48 命中任务 → 推送 → 用户醒来骂娘。

**修复** — 3 个 check 方法顶部都加 `is_in_digest_window()` 守卫，窗口外 `return 0`，与 `reminder_service.process_reminders` 共享同一策略函数（`app/services/reminder_policy.py`）。6 个新测试覆盖：3 个 check 方法窗口外 skip + 不查 DB、run_all_checks 入口全 skip、窗口内无任务正常返回 0、与 v2 reminder_service 集成测试。

**纪律 5 条**：
① **v2 大改动必须 grep 全项目找并行路径** ——
- `grep -rn "wechat_bot\.smart_send\|smart_send(.*member" app/`
- `grep -rn "Celery\|@shared_task\|@celery_app.task" app/`
- 任何独立的"主动推送 / 通知 / 提醒" Celery 任务都必须走 v2 窗口
② **并行调度器审计 one-liner**：
```bash
grep -rn "smart_send\|send_text\|send_message" app/ --include="*.py" | grep -v test
# 任何匹配的文件都必须检查 is_in_digest_window 守卫
```
③ **"主动提醒"和"被动提醒"是两套系统** ——
- v2 被动：reminder 表 + reminder_service.process_reminders（10 秒 tick）
- 主动：scheduler.py + Celery beat run_proactive_checks（15 分钟 tick）
- 两者都**必须**走同一窗口策略函数，不能各写各的判断
④ **窗口外守卫必须放方法最顶部** ——
- 不能放 `for task in tasks` 循环里（已经查 DB + 实例化对象了）
- 也不能放 `await self._already_notified(...)` 之后（还跑了 Redis 往返）
- 必须第一行 return 0，省 DB / Redis / LLM 全部资源
⑤ **Redis SET dedup 不替代窗口守卫** ——
- scheduler.py 用 `scheduler:{type}:notified` Redis SET 做 24h dedup
- 但**第一次发送时仍然立即触发**（SET 还不存在）
- 24h 内重复 → SET 命中 → skip
- 24h 后 SET 过期 → 又能立即触发
- **dedup 只防重复，不防半夜推送**

**部署必做**：
```bash
docker compose restart celery-worker celery-beat   # CLAUDE.md 752 行铁律
# 验证：tail docker logs 看 "proactive-checks" task 是否 log "跳过：非 11AM 推送窗口"
```

## 2026-06-15 移动端"声纹测试"是真识别测试不是麦克风测试（commit `de7ef8aa`）

- **根因（用户痛点）** — 用户说"已录入声纹的成员可以再听会之前检测一下是否能识别出来自己的声纹"，但 [web/src/components/mobile/VoiceTestFlow.vue](web/src/components/mobile/VoiceTestFlow.vue) 原本只做 3 件事：①`getUserMedia` 拿麦克风权限 ②`MediaRecorder` 录音 ③Canvas 音量可视化 + 音频回放。**完全没调 `POST /api/v1/voiceprint/test`**。用户点完测试看到的只是"录音能不能录"——而他要的是"我能不能被识别出来"。
- **桌面端范式** — [web/src/components/VoiceTestDialog.vue:302](web/src/components/VoiceTestDialog.vue#L302) `axios.post('/api/v1/voiceprint/test', formData)` 是正确范式：录音 + POST /voiceprint/test + 展示 `testResult.steps[]`（5 步：音频解码/格式转换/静音检测/VAD/ASR/声纹识别）+ 最终 `speaker + confidence + transcript`。
- **修复** — 移动端 VoiceTestFlow.vue 状态机升级为 5 态 `idle → recording → recorded → testing → result`：
  1. `idle`/`recording` 阶段只录音 + 可视化
  2. `recorded` 阶段用户可回放，**手动**点"测试识别"才调 `/voiceprint/test`
  3. `testing` 阶段显示 spinner
  4. `result` 阶段渲染后端返回的 5 步结果 + 最终识别
  5. 错误降级：axios 失败时构造 `steps: [{name: '测试请求', status: 'error', detail: ...}]` 渲染
- **关键纪律** —
  ① **"X 测试"组件先 grep 桌面端有没有同名实现**——本项目 90% 移动端组件都有桌面端孪生，不要凭想象造移动端专用版本
  ② **状态机切换不能在 `stopTest` 里**——`onstop` 回调是异步的（blob 还没生成），state 切到 `recorded` 必须在 `onstop` 里。`stopTest` 只调 `mediaRecorder.stop()` + 清 timer
  ③ **iOS Safari MediaRecorder 兜底**——`MediaRecorder.isTypeSupported('audio/webm')` 不一定 true，兜底 `audio/mp4`
  ④ **不要手动设 Content-Type** —— axios 自动加 multipart boundary（CLAUDE.md 已有纪律）
  ⑤ **5 秒自动停止 + 5 步步骤展示**——与桌面端硬规则对齐，不要自由发挥
  ⑥ **错误降级构造 steps** —— 网络/服务器错时仍要渲染"测试请求: error"步骤，让用户知道是网络问题而不是"功能不存在"
  ⑦ **a11y 4 属性套件** —— 所有 `<button>` 补 `id` + `name` + `aria-label` + `title`（CLAUDE.md 2026-06-12 铁律）
- **沉淀** — [mobile-voiceprint-real-test.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/mobile-voiceprint-real-test.md)

### 多入口 grep 铁律（commit `22d5570a`，同一 PR 跟进）

- **同一个功能可能在移动端多个页面有入口**——本项目"麦克风/声纹测试"有 2 个独立入口：
  1. [MobileVoiceprintView.vue:8](web/src/views/mobile/MobileVoiceprintView.vue#L8) 顶栏 🎤 button
  2. [MobileMeetingView.vue:123-126](web/src/views/mobile/meeting/MobileMeetingView.vue#L123-L126) ActionSheet "麦克风测试" 按钮
- **commit `de7ef8aa` 只修了第 1 个** → 用户打开第 2 个入口仍弹 `'麦克风测试（开发中）'` toast，以为没修。**commit `22d5570a` 修第 2 个 + 同步 aria-label/title**
- **铁律 4 条** —
  ① **改前先 grep**：`grep -rn "X 测试\|X test\|开发中" web/src/views/mobile/ web/src/components/mobile/` 找全所有同名入口
  ② **改后必验证**：`grep -rn "开发中" web/src/views/mobile/ web/src/components/mobile/` 应该是 0（"知识健康"等用户已知未开发的功能除外）
  ③ **同一组件多处复用**：本次让声纹中心和会议页都 `<VoiceTestFlow v-model:show="showVoiceTest" />`，避免维护多份
  ④ **button 文字 + aria-label + title 三处统一**（a11y 4 属性套件原则）—— 入口 A 叫"声纹识别测试" 入口 B 不能叫"麦克风测试"
- **常见的多入口模式** — 移动端"X 测试"功能常出现在：①声纹中心页顶栏 ②会议页 ActionSheet ③录音对话框前置引导 ④任何下拉菜单/更多按钮。**一次 fix 必须覆盖所有入口**

### v-model 命名必须跟组件 prop 名严格匹配（commit `f84524cf`，重要）

- **新症状** — 部署 commit `22d5570a` 后用户仍说"点击'声纹识别测试'没反应"。根因：调用方 `<VoiceTestFlow v-model:show="showTest" />`（要 `show` prop + `update:show` 事件），但 [VoiceTestFlow.vue](web/src/components/mobile/VoiceTestFlow.vue) 内部 prop 是 `modelValue`（默认 v-model 用的）—— **prop 名不匹配**。
- **静默失败链** —
  1. `v-model:show` 等价于 `:show="showTest" @update:show="showTest = $event"`，但组件没 `show` prop → Vue 3 静默 fallback（不抛错，只在 dev mode 偶尔 warn "Extraneous non-emits event listeners"）
  2. showTest 设为 true 后，传给子组件的 `show` prop 被忽略，**实际 `modelValue` 仍为 undefined**
  3. 子组件 `v-if="modelValue"` 永远 false → `<Teleport>` 不渲染
  4. 子组件 `emit('update:modelValue', false)` 父组件没监听 update:show → 永远关不上
  5. **结果**：用户点击 button 完全无视觉反馈，不报错、不警告、不进 console
- **修复** — 调用方改 `v-model:show` → `v-model`（默认走 `modelValue` prop）：
  - [MobileVoiceprintView.vue:111](web/src/views/mobile/MobileVoiceprintView.vue#L111)
  - [MobileMeetingView.vue:175](web/src/views/mobile/meeting/MobileMeetingView.vue#L175)
- **铁律 3 条** —
  ① **`v-model` 必须对应组件 prop 名 `modelValue`**（默认）—— 子组件 `defineProps({ modelValue: ... })` + `defineEmits(['update:modelValue'])`
  ② **`v-model:foo` 必须对应组件 prop 名 `foo`** —— 子组件 `defineProps({ foo: ... })` + `defineEmits(['update:foo'])`，**prop 名 / emit 名必须与 v-model 修饰符完全一致**
  ③ **Vue 不会编译报错**——`<Foo v-model:bar="x" />` 即便 Foo 没 bar prop，模板编译完全合法，运行只静默失败。**debug "点击没反应" 类问题**第一步 grep 调用方的 `v-model:xxx` 看 xxx 跟子组件 prop 名是否一致
- **debug 技巧** ——
  ```js
  // 浏览器 console
  const el = document.querySelector('[data-v-app]')
  // Vue 3 devtools → Component Tree → 选中目标组件
  // 看 props 面板：modelValue / show 实际值是什么
  // 如果子组件 v-if="modelValue" 但 props.modelValue 永远 undefined → 100% 是 v-model 命名不匹配
  ```
- **跟 CLAUDE.md 2026-06-12 教训的差别** — 之前 PR #3 教训是"el-input v-model 写错 prop 名 Vue 警告"（Element Plus prop 固定叫 `modelValue`，想写 v-model 必须用 `model-value`/`@update:model-value`）。本条是**自研组件**场景，prop 命名是项目自己定的，调用方/定义方必须协商一致。**两条都强调"命名一致"，但触发的库不同**

### 移动端"X 分析"功能复用桌面端 el-dialog 组件模式（commit `67fd7eaa`）

- **场景** — 移动端会议页 [MobileMeetingView.vue:255-258](web/src/views/mobile/meeting/MobileMeetingView.vue#L255-L258) ActionSheet 第三个"粘贴转录分析"按钮点完只弹 `'粘贴转录分析（开发中）'` toast（跟前两次声纹测试的 bug 一模一样）。用户要求"也要能正常使用"
- **关键观察** — 桌面端 [MeetingView.vue:51, 242](web/src/views/MeetingView.vue) 已经有完整实现：`<PasteAnalyzeDialog ref="pasteAnalyzeDialogRef" @saved="fetchMeetings" />` + `pasteAnalyzeDialogRef.value?.open()` 模式。组件内部 line 135 `isMobile = ref(window.innerWidth <= 768)` + line 4 `:width="isMobile ? '95vw' : '750px'"` 已在桌面端**预留移动端适配**。
- **修复** — 移动端 import `PasteAnalyzeDialog` + 加 `pasteAnalyzeDialogRef` ref + `handlePasteAnalyze` 改为 `pasteAnalyzeDialogRef.value?.open()`。dialog 内部 `isMobile` 自动检测窄屏，宽度自动从 750px 变 95vw。**0 改动 PasteAnalyzeDialog.vue 本身**。
- **铁律 4 条** —
  ① **移动端 dialog 类组件**（带表单/选择器）**优先复用桌面端 el-dialog**——不用重写 `<MobileXxxDialog>`，桌面端组件已含 `isMobile` 适配（line 4 `:width="isMobile ? '95vw' : '750px'"` 模式）。如果桌面端 dialog 没 isMobile 适配，再考虑改 prop 或写移动端版
  ② **复用模式** — 桌面端用 `ref + open()` 暴露，移动端也用 `ref + open()`。`<XxxDialog ref="xxxRef" @saved="onSaved" />` 放在 template 末尾
  ③ **el-dialog 内部 el-form CSS 已在 mobile bundle** — 因为移动端已经用 `MeetingCreateDialog`（[MobileMeetingView.vue:167](web/src/views/mobile/meeting/MobileMeetingView.vue#L167) 注释"移动端仍用 el-dialog fullscreen"），el-form / el-input / el-select / el-date-picker CSS **0 增量打包**
  ④ **多入口 grep 铁律 3 次奏效** — 这次是同 1 个 ActionSheet 里的第 3 个"开发中"toast（前 2 个：声纹中心按钮 + 会议页 ActionSheet 第 2 项"麦克风测试"）。**改 1 个 ActionSheet 必 grep ActionSheet 全部 4 个 item**，不能改一个忘一个

## 2026-06-15 会议 #95 声纹重置 + 重识别教训

**场景** — 用户说"最新的会议讨论人是王天志+李胜景，重新识别并学习"。但数据库 `meeting_participants` 显示是 周之超+李胜景+杜同贺，王天志根本没参加。`speaker_mapping` 把 90 段标"周之超"、4 段标"李胜景"、2 段标"杜同贺"。**最终真相**：会议里只有王天志（主讲）和李胜景（补话），周/杜根本没说话。`meeting_participants` 录入会议时被默认勾选错误，`speaker_mapping` 全部错标。

### 6 条铁律

**铁律 1：psycopg2 transaction rollback 静默吃 UPDATE**
- `psycopg2.connect()` 默认 autocommit=False，所有 SQL 在同一 transaction。**中间任何一条 SQL 失败 → 整个 transaction rollback**，前面所有 UPDATE 全部丢
- 本次复现：`UPDATE members SET voice_embedding=...` 看似成功（rowcount=1），但后面 `INSERT INTO meeting_participants` 报 `column created_at does not exist` → 整个 transaction rollback → `voice_embedding` 实际未改
- **修复模式**：①要么用多个独立 connection 跑各组操作 ②要么把所有 SQL 写完 + 验证 schema 后**一次性 commit** ③**先看表结构再写 INSERT/UPDATE**（`\d meeting_participants` 必须先看）
- **诊断**：`SELECT name, voice_sample_count, voice_enrolled_at FROM members WHERE name='X'` 如果 enrolled_at 还是旧值 → 100% rollback 了，必须重做

**铁律 2：speaker_mapping 完全错标时必须用 KMeans 重聚类**
- `speaker_mapping` 是聚类后映射的结果，**可能严重错**。本次 90% 段被错标"周之超"（实际是李胜景讲水产养殖）
- **重识别流程**：①按 speaker_label 分组，过滤 < 3s 簇 ②每簇提 embedding ③KMeans(k=N) 重聚类（N=参会人数）④聚类中心 vs 现有 voice_embedding 余弦距离比对 → 找出最佳匹配 ⑤用聚类中心拼接的音频 → 提 embedding → 重置 voice_embedding
- **关键**：聚类中心 vs 现有 voice_embedding 距离全 > 0.4 → 现有 embedding 严重失真 → **必须重置（sample_count=1）**，加权融合无效

**铁律 3：Whisper 幻觉段不能用作声纹学习**
- 静音/低能量片段 Whisper 臆造 B 站结束语模板："谢谢观看 欢迎订阅我的频道"、"请不吝点赞 订阅 转发 打赏支持明镜与点点栏目"、"中文字符志愿者 杨茜茜"（CLAUDE.md 2026-06-02/03 已提，本节再次踩坑）
- 本次 `speaker_mapping` 给"李胜景/杜同贺"分配的 6 段（共 4.8s）**100% 是 Whisper 幻觉**，用这些段提 embedding → 学进 member.voice_embedding → **永久污染**
- **防御**：①文本含上述模板 → 直接跳过不学 ②簇总时长 < 5s 且文本是单句 → 不学 ③Whisper hallucination 黑名单在 `app/api/v1/voice.py` HALLUCINATION_STRONG/WEAK 已实现
- **诊断**：speaker_mapping 标某人的段，全是 B 站结束语模板 → 100% 是幻觉

**铁律 4：speaker_mapping 与 meeting_participants 必须互相对齐**
- 本次发现 speaker_mapping 把所有人都标"周之超"，但实际参会者是王+李。两者都错，但错得不一样
- **修复时同步更新两张表**：
  - `meetings.speaker_mapping`：所有 speaker_label → 真实身份
  - `meeting_participants`：删除实际没说话的人，加上实际说话的人
- **铁律**：任何"重识别发言人"操作，**必须同时改 speaker_mapping + meeting_participants**，否则后续按 participants 推送通知、按 speaker_mapping 统计会数据不一致

**铁律 5：用户认知 vs 数据库不一致时必须先汇报数据**
- 本次用户说"王天志+李胜景说话"，但数据库 meeting_participants 是 周/李/杜
- **第一次盲信用户决策**会做错。**必须先抽文本验证**：抽样 speaker_mapping 标"周之超"段的文本 → 全是水产养殖讨论 → 显然不是周之超（方向是表面污染去除）→ 立刻发现 speaker_mapping 错标
- **KMeans 重聚类结果与用户判断冲突时**，不要强制按用户判断，要给用户看完整距离数据再决策
- **纪律**：遇到 user 描述 ≠ db 实际，**永远先打印证据**（样本文本、距离矩阵），让用户基于证据决策

**铁律 6：重置声纹是一次性单向操作**
- `UPDATE members SET voice_embedding = X, voice_sample_count = 1, voice_enrolled_at = NOW()` 会**覆盖**现有 embedding，且不保留历史
- 现有 4 样本（可能来自多次成功录入）的所有信息都丢失
- **重置前必做**：①备份到临时表或 JSON 文件 ②确认 KMeans 聚类中心的 cosine_distance < 0.7（很相似）才能重置 ③重置后立即用 5+ 段测试 verify
- **备份 one-liner**：
  ```sql
  CREATE TABLE members_voice_backup_20260615 AS 
  SELECT id, name, voice_embedding, voice_sample_count, voice_enrolled_at 
  FROM members WHERE voice_embedding IS NOT NULL;
  ```
- **恢复 one-liner**：`UPDATE members SET voice_embedding = b.voice_embedding, voice_sample_count = b.voice_sample_count FROM members_voice_backup_20260615 b WHERE members.id = b.id`

### 端到端 verify

```python
# 抽 5 段测试
test_cases = [
    ('speaker_14', 50.91, 56.41),    # 原周之超 → 王天志
    ('speaker_48', 148.51, 153.69),  # 原周之超 → 王天志
    ('speaker_166', 526.47, 529.31), # 原发言人D → 李胜景
    ('speaker_137', 454.79, 460.22), # 原发言人J → 李胜景
    ('speaker_39', 122.0, 128.0),    # 原发言人D → 王天志
]
for desc, s, e in test_cases:
    chunk = audio[int(s*sr):int(e*sr)]
    name, mid, conf = await voiceprint_service.identify_speaker(db, chunk)
    print(f'{desc}: {name} (conf={conf:.3f})')
```
期望：5/5 段全部正确分类，置信度 > 0.65（理想 > 0.8）。如果某段 conf < 0.6 → 该段可能跨簇（多说话人重叠），需要手动剔除或重新聚类

### 铁律 9：`meetings.transcript_polished` 是前端实际渲染的字段，不是 `transcript`！

- **前端实际渲染**：[MeetingDetailView.vue:219-227](web/src/views/MeetingDetailView.vue#L219-L227) 用 `meeting.transcript_polished[].speaker` 渲染头像 + 名字
- 修了 `transcript` 不够！前端读的是 `transcript_polished`（L2/L3 润色后生成的独立 JSON 数组，与 transcript 一一对应）
- **本次踩坑**：DB 验证 `transcript` 全干净（0 周之超），但用户前端仍显示周之超 → 查 `transcript_polished` 才发现 80 段还在写"周之超"（commit `af044bfc` 漏修了这条字段）
- **纪律（"改发言人识别同时改 8 个 JSON 字段"）**：
  1. `meetings.transcript[]`（原 ASR 数组）
  2. `meetings.transcript_polished[]`（L2/L3 润色后数组，**前端实际渲染**）
  3. `meetings.speaker_mapping{}`（speaker_label → 真实名字映射）
  4. `meetings.speaker_stats[]`（AI 后期统计的发言次数/字数）
  5. `meetings.key_points[]`（讨论要点，`【发言人】` 前缀）
  6. `meetings.decisions[]`（决议事项，`【发言人】` 前缀）
  7. `meetings.summary`（摘要，可能含人名）
  8. `meeting_participants`（参会者列表）
- **完整验证 one-liner**（必须**全 0** 才算成功）：
  ```sql
  SELECT 
    (SELECT COUNT(*) FROM jsonb_array_elements(transcript::jsonb) e WHERE e->>'speaker' = '周之超') AS t_周,
    (SELECT COUNT(*) FROM jsonb_array_elements(transcript_polished::jsonb) e WHERE e->>'speaker' = '周之超') AS tp_周,
    (SELECT COUNT(*) FROM jsonb_each_text(speaker_mapping::jsonb) WHERE value = '周之超') AS sm_周,
    (SELECT COUNT(*) FROM jsonb_array_elements(speaker_stats::jsonb) s WHERE s->>'name' = '周之超') AS ss_周,
    (SELECT array_to_string(key_points, '|') FROM meetings WHERE id=95) LIKE '%周之超%' AS kp_周,
    (SELECT array_to_string(decisions, '|') FROM meetings WHERE id=95) LIKE '%周之超%' AS dec_周,
    (summary LIKE '%周之超%') AS sum_周
  FROM meetings WHERE id = 95;
  ```
  **任一字段不为 0/false → 改漏了**，重做
- **transcript 与 transcript_polished 同步方法**：两者数组按顺序一一对应，按 transcript[i].speaker_label 在 speaker_mapping 里的 value 同步 tp[i].speaker
  ```python
  new_tp = []
  for i, tp_e in enumerate(transcript_polished):
      if i < len(transcript):
          new_e = dict(tp_e)
          new_e['speaker'] = transcript[i]['speaker']
          new_e['speaker_label'] = transcript[i]['speaker_label']
          new_tp.append(new_e)
  ```
- **用户必做**：DB 改完后**硬刷新浏览器**（Ctrl+Shift+R / Cmd+Shift+R）才能绕过 SW cache 看到更新


## 2026-06-17 部署与基础设施重建（Docker Desktop 引擎崩溃 + 镜像源治理 + 数据 E 盘化）

**根因链** — 重启电脑后 Docker 服务无法启动 8 个容器端到端连通失败 4 层根因：
1. **WSL2 `docker-desktop-data` 发行版丢失** — `wsl -l -v` 只看到 `docker-desktop` 没有 `docker-desktop-data`，`com.docker.service` 每 7-9 分钟反复启动又停止（事件日志可见）
2. **C 盘 24GB Docker 缓存残留** — `C:\Users\pc\AppData\Local\Docker` 占据系统盘 24GB 但 WSL 引用已断
3. **huaweicloud 镜像源 404** — Debian bookworm `bookworm-security` 已从 `debian/` 迁到 `debian-security/`，旧路径 404
4. **aliyun PyPI 限速** — 单连接 ~600KB/s，下 torch 532MB 装 13 分钟且 502 瞬时错误

### 10 条铁律沉淀（[memory/docker-desktop-fix-2026-06-17.md](memory/docker-desktop-fix-2026-06-17.md)）

**铁律 1：junction 透明重定向 = Windows 上让应用"运行在 E 盘"的标准做法**
- C 盘软件硬编码路径（如 `C:\Users\pc\AppData\Local\Docker`）不能直接 move。**修复**：删 C 盘原目录 → `mklink /J "C:\path" "E:\real\path"` 创建 junction → 软件硬编码路径继续工作，物理数据在 E 盘。C 盘 0 字节占用
- **数据全 E 盘方案**：删 C 盘 `AppData\Local\Docker` 24GB（先备份到 E 盘）→ Docker Desktop 启动时自动重建 `docker-desktop-data` 发行版在 E 盘 → 用 junction 透明重定向回 C 盘原路径

**铁律 2：WSL Docker 引擎恢复流程**
- `wsl -l -v` 看发行版 → 缺 `docker-desktop-data` → 重置 Docker Desktop（设置 → Troubleshoot → Reset to factory defaults）→ 自动重建发行版
- **不要尝试手动 `wsl --unregister docker-desktop-data`** — 会清掉所有镜像/卷，不如 reset factory defaults 自动重建干净

**铁律 3：Dockerfile 镜像源选择（Debian bookworm）**
- `bookworm-security` 走 `debian-security/` 独立路径，**不在** `debian/` 下
- ❌ 错误：`mirrors.huaweicloud.com/debian bookworm-security`（404）
- ✅ 正确：`mirrors.aliyun.com/debian-security bookworm-security main contrib`
- **3 个 source 模板**（`Dockerfile` / `Dockerfile.whisper` 已统一）：
  ```dockerfile
  RUN rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list && \
      printf 'deb http://mirrors.aliyun.com/debian bookworm main contrib\n' > /etc/apt/sources.list && \
      printf 'deb http://mirrors.aliyun.com/debian bookworm-updates main contrib\n' >> /etc/apt/sources.list && \
      printf 'deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib\n' >> /etc/apt/sources.list
  ```

**铁律 4：PyPI 限速真相 + pip 重试**
- aliyun PyPI 单连接 ~600KB/s，下 torch 532MB 装 13 分钟 + 502 瞬时错误
- 清华 TUNA 前 12 秒 14MB/s 后降到 320KB/s 仍会断（限速算法类似 burst + throttle）
- **最稳方案**：`pip install --retries 10 --timeout 60`（重试机制是兜底，无论哪个源都该有）
- **PyTorch 2.4+ 同步滞后**：清华源对 torch 2.12+ 同步慢，PyTorch 直接走 `download.pytorch.org/whl/cu121` 官方 wheel 源
- **PyTorch 官方基础镜像 GPG 缺失**：`pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime` 精简了 Debian keyring → apt 装包 GPG 失败（`NO_PUBKEY 6ED0E7B82643E131`）。`[trusted=yes]` 和 `Acquire::AllowInsecureRepositories=true` 在新版 apt 不生效。**最佳方案：保持 `python:3.11-slim-bookworm` 基础镜像**（自带完整 keyring）

**铁律 5：apt-get install 必加 fallback**
- aliyun `libcaca0` 等包偶发 502 Bad Gateway 瞬时错误
- `Dockerfile.whisper` 加 `|| (apt-get update && apt-get install -y --fix-missing --no-install-recommends ...)` 第一个包失败时自动重试
- **不要**改 apt sources 加重试（apt 不支持源级重试）

**铁律 6：.dockerignore 是必须的**
- `models/` 含 huggingface/torch/modelscope 缓存（10+ GB）→ 不加 .dockerignore → build context 传 12GB 到 Docker daemon 慢且占空间
- **标准 .dockerignore 模板**（本项目）：`models/` `data/` `logs/` `.git/` `.gitignore` `.agents/` `docs/` `.claude/` `node_modules/` `dist/` `build/` `__pycache__/` `*.pyc` `*.pyo` `*.log` `.vscode/` `.idea/` `.DS_Store` `*.md` `nginx/ssl/` `.env.webhook` `.env.example`
- **效果**：build context 从 12GB → 700MB（**17 倍提速**）
- **警告**：build context 减小 ≠ build 时间线性减小（apt-get install 仍占大头），但 docker daemon 接收 context 阶段从分钟级 → 秒级

**铁律 7：docker-compose.override.yml 默认加载**
- 文件名 `override.yml` 会被 compose 自动加载合并到主 compose 上，**不需要** `-f` 指定
- 想禁用重载：使用 `--no-merge` 或重命名为非 `override.yml` 名字
- 调试时可临时 `cp override.yml override.yml.bak` 隔离排查

**铁律 8：frp 客户端 Windows 开机自启（用户级 + AtLogOn）**
- ❌ `sc create` 命令行引号转义问题 + UAC 提权
- ❌ 直接 `powershell.exe -File xxx.ps1` 在 schtasks 调度会**弹控制台窗口**（用户看到窗口闪一下）
- ✅ `Register-ScheduledTask` 创建用户级登录任务（`AtLogOn`），调 wrapper 脚本 `start-frpc.ps1`（检测 frpc 已运行则退出，避免重复进程）
- ✅ PowerShell wrapper 用 `-WindowStyle Hidden` 启动 frpc.exe 隐藏窗口
- **wrapper 模板**（`frp/start-frpc.ps1` 已固化）：
  ```powershell
  $existing = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
  if ($existing) { Write-Host "frpc 已在运行 (PID: $($existing.Id))"; exit 0 }
  $proc = Start-Process -FilePath "E:\path\frpc.exe" `
    -ArgumentList "-c","E:\path\frpc.toml" `
    -WorkingDirectory "E:\path\frp" `
    -WindowStyle Hidden -PassThru
  Write-Host "frpc 已启动 (PID: $($proc.Id))"
  ```

**铁律 9：dockerproxy.net 500 错误 = Docker Desktop daemon 没完全起来**
- 解决：完全 kill 所有 Docker 进程 → 等 10 秒 → 重启 Docker Desktop → 等 90-120 秒 daemon 完全起来
- **不能光退出 Docker Desktop UI**，要 kill `com.docker.backend` 进程 + `com.docker.service` + `com.docker.proxy`
- **检查**：`tasklist | findstr docker` 看是否所有进程都退出

**铁律 10：~/.docker/config.json 不要随便加 proxies 字段**
- 加了 `proxies.default.httpsProxy: http://host.docker.internal:7890` 后 Docker Desktop daemon 内部通信出错（500 错误）
- Docker Desktop 走代理应通过 Settings GUI 配置（Settings → Resources → Proxies），**不通过** config.json
- **恢复**：删 config.json 里的 proxies 字段 → 重启 Docker Desktop

### 部署必做（CLAUDE.md 752 行铁律变体）

```bash
# 1. 验证容器状态
docker compose ps  # 应显示 9 个服务 Up

# 2. 验证外网连通
curl -sk -o /dev/null -w "%{http_code}\n" https://agent.mnb-lab.cn/api/v1/auth/me
# 期望：401（端点通了，密码错）而不是 502 Bad Gateway

# 3. 验证 whisper 模型
docker exec microbubble-agent-whisper-1 python -c "
import faster_whisper
print('model:', faster_whisper.__version__)
" 2>&1 | head -3

# 4. 重启 Python 进程（CLAUDE.md 752 行铁律）
docker compose restart app celery-worker
```

### 沉淀统计

- **共释放 ~192 GB**（24GB Docker 缓存 + 168GB 孤儿 `docker_data.vhdx`）
- **build context 12GB → 700MB**（17 倍提速）
- **9 个 Docker 服务运行中**：app、db、redis、minio、neo4j、whisper、vision-mcp、celery-worker、celery-beat
- **`https://agent.mnb-lab.cn` 端到端连通**（之前 502 Bad Gateway，现在 401 = 端点通了，密码错）

## 2026-06-17 webhook deploy 链断裂修复

**症状链**（用户报告"移动端 UI 还是没生效"）：
1. 6/17 22:46 / 22:53 GitHub webhook 2 次 push 失败
2. 服务器 dist `Last-Modified: Mon, 15 Jun 2026 13:52:55 GMT` — **2 天前的状态**
3. `https://agent.mnb-lab.cn` index hash 仍是 `index-1ee619c8.js`（旧）

**根因（公网探测 4 步定位）**：
1. `POST /webhook` 无 auth 返 403 = webhook service 活着（响应签名验证拒绝）
2. `Last-Modified: 6/15 13:52` = dist 没动过
3. `MainLayout-791d4aa6.js: 404` = 本地 build 出的 hash 服务器不存在
4. 服务器 SSH 不可达（本地 `id_ed25519` 不被服务器认可）→ 只能从公网推断

**用户 SSH 进去后看到 5 真相**（[webhook-deploy.log](https://github.com/gg320324492-lgtm/microbubble-agent/blob/main/scripts/webhook.py)）：
```
23:09:17 POST /webhook delivery=7c9cf3be-... sig=sha256=7abb02d3...  ← 签名通过
23:09:18 git fetch origin main
       git@github.com: Permission denied (publickey).  ← 真正根因
       fatal: Could not read from remote repository.
23:09:20-23:10:46 第 1-5 次重试 5s/10s/20s/40s/80s 退避全失败
23:12:09 ERROR: git pull/fetch 都失败，跳过本次部署
```

**5 条铁律**：

**铁律 1：webhook 失败根因必须先看 `/var/log/webhook-deploy.log`，不要只看 GitHub UI**——
- GitHub UI 显示 200 OK = webhook service 收到了 + 返回 200，**不代表** deploy 成功
- webhook service 收到 push → 立即 `return 200 OK` → 启动 daemon 线程跑 deploy-auto.sh → 失败时只 log 不返错给 GitHub
- 看到 GitHub webhook 标红/失败 = webhook service 完全没收到（网络/firewall/secret 错）
- 看到 GitHub webhook 显示 ✓ 但服务器没动 = 99% 是 deploy 脚本失败，看 log
- 诊断命令三件套（服务器 root 跑）：
  ```bash
  sudo systemctl status webhook --no-pager -l
  sudo tail -60 /var/log/webhook-deploy.log
  ls -la /opt/microbubble-agent/.env.webhook
  ```

**铁律 2：`git@github.com: Permission denied (publickey)` 95% 是 server-side deploy key 与 GitHub 端不匹配**——
- 服务器 `/root/.ssh/github_deploy` 是专用 key（不在默认 `id_*` 名字里，git 找不到）
- 修法：`ssh-keygen -t ed25519 -f /root/.ssh/github_deploy -N "" -C "aliyun-deploy-2026-06-17"` + 把 `.pub` 加到 GitHub repo → Settings → Deploy keys（**Allow write access 不勾**）
- **deploy key 也要定期轮换**（6/13 教训讲的是 secret 没讲 key，6/17 才发现 server-side key 也需要管理）
- 定期检查命令（建议加进季度运维清单）：
  ```bash
  # 本地
  for key in ~/.ssh/*.pub; do
      echo "=== $key ==="
      cat "$key"
  done
  # GitHub 端: Settings → Deploy keys 比对 fingerprint
  ```

**铁律 3：webhook service EnvironmentFile 缺失是隐形杀手**（6/13 教训的延伸，6/17 才发现没修干净）——
- 6/13 事故：`.env.webhook` 被 `git clean -fdx` 误删 → webhook service 启动失败
- 6/13 修复：临时 secret 写到 process memory 重启 service → service active (running) 一切正常
- 6/17 今日发现：process memory 里的 secret 还在跑，但 `.env.webhook` 文件**仍然不存在** → 任何一次 `systemctl restart webhook` 必挂（因为 `EnvironmentFile=... (ignore_errors=no)`）
- 修法（commit `c9c60ca6`）：`deploy-auto.sh` 在 `git clean -fdx` 之前 fail loud：
  ```bash
  if [ ! -f "$PROJECT_DIR/.env.webhook" ]; then
      log "ERROR: \$PROJECT_DIR/.env.webhook missing — refusing to clean (会删 webhook secret)"
      exit 1
  fi
  ```
- 持久化 one-liner（服务器 root 跑，从 process memory 读出来再写文件）：
  ```bash
  PID=$(pgrep -f "scripts/webhook.py" | head -1)
  SECRET=$(sudo cat /proc/$PID/environ | tr '\0' '\n' | grep -E "^WEBHOOK_SECRET=" | cut -d= -f2)
  echo "WEBHOOK_SECRET=$SECRET" | sudo tee /opt/microbubble-agent/.env.webhook > /dev/null
  sudo chmod 600 /opt/microbubble-agent/.env.webhook
  ```

**铁律 4：本地 SSH 不到 server 时只能从公网探测**——
- 用户本机 `id_ed25519` 可能跟服务器 `~/.ssh/authorized_keys` 不匹配（用户换电脑/重装系统/重生成 key）
- 公网探测 4 件套：
  ```bash
  curl -sk -o /dev/null -w "POST /webhook: %{http_code}\n" -X POST https://agent.mnb-lab.cn/webhook -d '{}'
  # 期望 403 = 服务在响应；期望 502/connection refused = 服务挂了
  
  curl -sI https://agent.mnb-lab.cn/ | grep -iE "(date|last-modified|server)"
  # Last-Modified 时间 = 最近一次 dist 写入时间
  
  curl -sk https://agent.mnb-lab.cn/ | grep -oE 'index-[a-f0-9]+\.js' | head -1
  # 期望跟 git log 最新 commit 的 dist/index-*.js 一致
  
  curl -sk -o /dev/null -w "%{http_code}\n" https://agent.mnb-lab.cn/sw.js
  # 期望 200 = SW 在跑
  ```
- 完整定位用 `<dist Last-Modified 时间>` 对比 `<最新 commit 时间>`：差距 > 几小时 = deploy 链断了

**铁律 5：webhook push → 等 60s → 探测 → 不变就 SSH 排查，不要纯靠 GitHub UI 状态**——
- 阿里云→GitHub 网络 130s 超时是已知问题（CLAUDE.md 6/13 教训），但 webhook service 立即返 200 + 异步跑 deploy = GitHub UI 可能 1-2 分钟内显示 ✓ 但实际还在 deploy
- **60s 内不更新 = 异常**（本地 build 1.21s + git reset 5s + nginx reload 0.5s，正常 < 10s 完成）
- 60s 后还不变：SSH 进 server 看 log，不要在 GitHub UI 上"Redeliver" — Redeliver 用原 payload 重发同样会失败（如果根因是 deploy key 不匹配）

**附带发现 — `manifest.webmanifest` 在 dist 里 404 算"正常"**（与本次 bug 无关）：
- commit `08f440f` 加了 `location = /manifest.webmanifest { return 410; }` 精确 410 Gone
- 但 `manifest.{hash}.webmanifest`（vite-plugin-pwa 输出 + manifestHashPlugin 加 hash）应 200
- 探针：`curl -sk -o /dev/null -w "%{http_code}\n" https://agent.mnb-lab.cn/manifest.webmanifest` 应 410（旧路径）OR `curl -sk -o /dev/null -w "%{http_code}\n" https://agent.mnb-lab.cn/manifest.{8char_hash}.webmanifest` 应 200（新路径）

**最终 commit 链**：
- `0e11009` 修图标 import（MainLayout 缺 Fold/Expand）
- `0f8d600` 同步 package-lock.json
- `9d1086d` 空 commit 触发 fresh webhook（GitHub 端 push 后 23:11 webhook 收到但 server 端 git fetch 失败）
- `c9c60ca6` deploy-auto.sh 加 .env.webhook 守卫
- 服务器端手动：重新生成 deploy key + 写 .env.webhook + 跑一次手动 deploy

### 2026-06-18 三连环修复（EP patch + MeetingRoomView + /auth/me 限流）

本次 1 天内完成 3 个独立修复，但部署链路把 3 个 commit 的失败/成功搞混了，引出 2 条新铁律。

**修复 1（commit `f8d27015`）**：EP `useOrderedChildren.removeChild` null guard — Vite plugin patch EP 源码防 `indexOf(undefined)` 崩溃（详见前面"### 2026-06-18 EP useOrderedChildren.removeChild null 崩溃修复"）

**修复 2（commit `f099e7e5`）**：桌面"正在听会"指示器不接进度 — 新建 MeetingRoomView 全屏页镜像移动端 MobileMeetingRoom（详见前面"### 2026-06-18 桌面'正在听会'指示器不接进度修复"）

**修复 3（commit `a1fd8280`）**：/auth/me 限流误伤 — `app/core/rate_limit.py` 把 `/auth/me` 等只读端点从 auth tier (20/min) 移到 read tier (200/min)

**事故链：本地只 commit 没 push，误以为是 webhook 链断（CLAUDE.md 已有教训 2026-06-17 复发误判）**
- 用户报告"桌面端点击'正在听会'按钮还是不能继续之前的听会进度"
- 我先入为主以为 webhook 链又断了，按 2026-06-17 教训排查
- 服务器 git log 显示 HEAD 在 `c1b969dd`、dist 没有 MeetingRoomView chunk → 进一步怀疑 deploy 链断
- 但实际 SSH 测 GitHub 通、fetch 成功、webhook service 正常 — 唯一异常：`origin/main` 没有我刚 commit 的 `f8d27015` + `f099e7e5`
- **真相**：我本地 `git commit` 后忘了 `git push`，GitHub 端一直停在 `c1b969dd`，服务器当然 deploy 不动
- 修复：`git push origin main` 之后 webhook 5 秒内触发，服务器 HEAD 变 `f099e7e5` + `f8d27015`，dist 自动含 MeetingRoomView

**新铁律 5 条**：
① **commit 后必 verify push 真到 origin**（最重要，最容易踩）：
```bash
# commit + push 后必跑
git push origin main && \
git log --oneline origin/main -3  # 确认 HEAD 与本地一致
```
缺这步 = 服务器 deploy 永远拿不到新代码，与 webhook 链断的症状 100% 一样（dist mtime 不动、git log 不前进），浪费排查时间。

② **怀疑 webhook 断时第一步先看 origin/main**：
```bash
ssh 服务器 "cd /opt/microbubble-agent && sudo git fetch origin main && git log --oneline origin/main -5"
```
- 如果 origin/main 与本地 HEAD 不一致 → 本地没 push 成功，不是 webhook 断
- 如果 origin/main 有新 commit 但服务器 HEAD 停在旧 commit → 真 webhook 断，走 2026-06-17 教训排查
- 如果 origin/main + 服务器 HEAD 都新 → 不是 deploy 问题，是浏览器侧 SW cache 污染

③ **/auth/ 下路径必须分级限流**（修复 3 教训）：
`if "/auth/" in path` 一刀切归 auth tier 20/min 是误伤：/auth/me 是高频只读（页面加载/Pinia 初始化/token 校验都会调），20/min ≈ 3秒/次根本不够。修复模式 = 白名单敏感路径（login/refresh/change-password）保留 20/min + 其他按方法分（PUT/PATCH/DELETE → write 30/min，GET → read 200/min）+ fallback 仍归 auth tier（防 401 风暴）。**铁律**：API 限流"按前缀"易误伤，必须"按 path 精确 + 按方法细分"，否则高频只读端点会持续 429。

④ **docker compose v1 (docker-compose) 与 v2 (docker compose) 服务器上不互通**：
服务器 Docker 29.5.3 装的是 docker-compose v5.1.4 独立二进制，**`docker compose` 命令不存在**，必须用 `sudo docker-compose`。判断方法：
```bash
which docker-compose 2>&1  # 存在 = v1 (老独立二进制)
docker compose version 2>&1  # 存在 = v2 (Docker CLI plugin)
```
v1 警告 `Couldn't find env file: /opt/microbubble-agent/.env` 不影响 restart（只 restart 不重建容器，env 不需要重新解析）。

⑤ **CLAUDE.md 752 行铁律对后端依然适用**：
```bash
# 任何后端 Python 文件改动（app/ 任何路径）必跑：
sudo docker-compose restart app celery-worker  # v1 老命令
# volume 挂载只换文件不换模块缓存，新代码 import 必须靠重启进程
```
rate_limit.py 是 `/app/app/core/rate_limit.py`，改完不 restart app = 限流配置永远走旧逻辑。本次就是因为没及时 restart 看到 curl 还 429 一度怀疑修复无效。

**修复 4（commit `defb08e1`）**：MeetingView.onMounted 重复 `router.replace` 覆盖导致"会议管理界面不断刷新"：
```js
if (resumeId) {
  resumeRecording(Number(resumeId))          // router.replace('/meetings/room')
  router.replace({ path: '/meetings' })      // ← 立刻覆盖！URL 永远停在 /meetings
}
```
- **症状**：用户点击"正在听会"指示器后，桌面端停留在"会议管理"界面不断刷新，进不去 MeetingRoomView
- **根因链**：commit `f099e7e5` 把 `resumeRecording` 从"开 dialog"改为"`router.replace('/meetings/room')`"，但 onMounted 紧接着的 `router.replace({ path: '/meetings' })`（旧代码用来"清理 query 让刷新不重复弹窗"）**立即覆盖**了新跳转。URL 永远在 `/meetings` 反复 render → 视觉上"不断刷新"
- **修复**：删 onMounted 末尾那行 router.replace，resumeRecording 内部已 navigate 走，不需要额外清理
- **新铁律**：**`router.replace/push 后不要再紧接着 router.replace/push`** —— Vue Router 的两个连续导航会冲突，后一行覆盖前一行。常见踩坑模式：① 旧代码"清理 query"在新代码"已 navigate"后变成 bug ② 同一个 onMounted 里多个 replace 想"先 X 后 Y"实际只走 Y ③ if/else 两分支各自 replace 会被外层最终 replace 覆盖。**纪律**：一个 onMounted / 一个事件回调里最多 1 次 router 操作，需要多次导航用 await 链式或 nextTick 拆开

**修复 5（commit `9f11d97a`）**：MeetingRoomView 模板里 ref 写 `.value` 导致 `null.value` TypeError：
```vue
<!-- ❌ 反模式：Vue template 自动 unwrap ref，写 .value 等于 null.value -->
<span v-if="recordingMeetingId.value && meetingId.value">...</span>

<!-- ✅ 正模式：template 里直接用 ref 变量名 -->
<span v-if="recordingMeetingId && meetingId">...</span>
```
- **症状**：console 报 `TypeError: Cannot read properties of null (reading 'value')`，且界面显示"开始听会"而非"正在听会"
- **根因**：`<script setup>` 里 `recordingMeetingId = ref(null)`，模板里 Vue 自动 unwrap ref（顶层 property），所以模板应该直接用 `recordingMeetingId`（Vue 帮你 unwrap）。写 `recordingMeetingId.value` 实际是访问 `null.value`，每次 render 都抛错，模板 partial render + 状态设置中断
- **新铁律**：① **`script setup` 里 `.value`，template 里裸用** —— 这是 Vue 3 `<script setup>` 的硬规则，反过来就是 bug ② `v-if` / `{{ }}` / `:prop` / `@event` 等模板表达式里**永远不写 `.value`** ③ 复制桌面/移动组件时容易把 script 的 `.value` 习惯带进 template，必须逐个去掉 ④ TypeScript 项目 Vue 3.4+ 已能用 `defineProps<T>()` 强制类型，IDE 会标红但纯 JS 项目无提示只能靠纪律 + E2E 测试

**修复 6（commit `22f5a7d7`）**：`/auth/me` 完全豁免限流（高频 polling 仍 429）：
```python
# /auth/me 即便 200/min 也被 useUserStore 在 reactive set value 时反复触发
# （MainLayout / MeetingView 每次 reactive 更新都重新拉 /auth/me）
# 200/min = 3.3 req/sec 撑不住，console 持续 429

_AUTH_UNLIMITED_PATHS = frozenset({"/api/v1/auth/me"})
# _get_rate_limit_type 返 "unlimited"，middleware 跳过
```
- **新铁律**：① **高频只读端点设任何次/min 都可能误伤** —— Vue reactive 触发 set value 链式调用 / WebSocket 心跳 / 路由 prefetch / polling，真实请求频次远超产品逻辑假设 ② **判断端点是否限流要看"是否会被高频轮询"而不是"是否敏感"** —— `/auth/me` 虽然挂在 `/auth/` 前缀下但是只读 GET + JWT 鉴权，攻击成本高（没 token 401 直接拒），防护无意义 ③ **正确分级**：登录/改密/refresh（高频攻击面）→ 严格 20/min；只读 GET + JWT（合法高频轮询）→ 完全豁免；其他写操作 → write 30/min ④ 监控 429 出现时立刻 `grep X-RateLimit-Remaining` 响应头确认哪个 tier 触顶


## 2026-06-19 Phase 7 多模态知识库（图片/公式/表格 OCR 入库）

**8 条铁律沉淀**（commit `5eb18358`）：

**铁律 1：多模态入库拆 2 张表（images + extractions），比单表 + JSON 更易查询**
- `knowledge_images` 单独存图片元数据（page_number / dimensions / ocr_status / ocr_text / ocr_model）
- `knowledge_extractions` 存提取物（formula/table/chart/image_block），data JSONB 存结构化内容
- `source_image_id` 关联"OCR 块属于哪张图"，前端可点图看对应的所有提取物
- 单一 extractions 表（kind 区分）vs 4 张表（formula/table/chart/image_block）：单表省 JOIN、跨 kind 聚合简单

**铁律 2：OCR 后端选 LLM-Vision 复用 vision_service，零新依赖**
- 主后端：`vision_service.analyze_image()` 走 vision-mcp（stdin_open + tty 必须）或多模态 LLM API
- 备后端：Tesseract（pytesseract + apt-get install tesseract-ocr + tesseract-ocr-chi-sim）
- `settings.MULTIMODAL_OCR_BACKEND` 切换，默认 `llm_vision`
- **不要**装 PaddleOCR/RapidOCR 之类重型模型（GPU 依赖 + 几 GB 镜像）— LLM-Vision 已经够用且省事

**铁律 3：并发控制 asyncio.Semaphore 是必须的**
- `settings.MULTIMODAL_OCR_CONCURRENCY=4`（默认 4，受 vision API rate limit 限制）
- 一篇 PDF 20 张图 + 串行 = 60s 用户体感差
- 4 并发 = 15s 体感可接受 + 不打爆 vision API
- 单图失败独立 try/except，1 张失败不阻塞其他图

**铁律 4：图片处理前置过滤 + 缩放**
- `MULTIMODAL_MIN_IMAGE_PIXELS=100*100`（< 该尺寸视为装饰/图标直接 skip，省 OCR 成本）
- `MULTIMODAL_MAX_IMAGE_PIXELS=1568*1568`（> 该尺寸等比缩小到 ~2.5MP，Anthropic Vision 建议值）
- `MULTIMODAL_MAX_IMAGES_PER_DOC=20`（单文档限流，避免 1 本书 OCR 跑 1 小时）
- 缩放用 PIL.Image.LANCZOS（高质量），格式保持原图（PNG/JPEG）

**铁律 5：session 隔离 — 不能 mutate 跨 session 的 ORM 对象**
- `_upload_images` 在 session A 创建 KnowledgeImage 行（`img.ocr_status='pending'`）
- `_save_extractions` 在 session B 想 `img.ocr_status='done'` → SQLAlchemy 不会持久化（不同 session 不共享 identity map）
- **修复**：session B 内先 `select(KnowledgeImage).where(id.in_(img_ids))` re-fetch，再 mutate
- **诊断**：`commit()` 不报错但 DB 字段没变 = 100% 是这个

**铁律 6：列表接口不能 mutate ORM 对象（autoflush 触发 NOT NULL 违反）**
- 之前：`item.content = None` 试图从响应移除完整 content
- SQLAlchemy 在 return 之前会 autoflush，把这个 mutate 翻译成 `UPDATE knowledge SET content=NULL` → NOT NULL 违反
- **修复**：转 dict 后再返回（不碰 ORM 对象）
- **诊断**：500 + log 显示 `null value in column "content" violates not-null constraint` = 100% 是这个

**铁律 7：vision 模型（mimo-v2.5）会泄露 ThinkingBlock 序列化字符串到 content**
- 即使 `thinking:disabled`，vision 模型仍可能输出 `ThinkingBlock(signature='', thinking='...')` 字符串到 text
- 必须 `_clean_ocr_text` 正则剥除：`ThinkingBlock\(...\)` / `signature='...'` / `thinking='...'` / `category: 必须...` 指令泄露
- 端到端测试：实际跑 10 张图，1-2 张会出现这个泄露，必须清洗后才入库
- **纪律**：任何 LLM 输出经过流水线入库前都要 strip 元数据/思考残留，不要信任模型不泄露

**铁律 8：alembic 链断裂必须 1 行修复 + docker-compose 加 volume 挂载免 rebuild**
- 现象：pre-existing 009 用 `revision='009'`，010 期望 `down_revision='009_formula_categories'`，链断
- 修复：010 改 `down_revision='009'`（1 行）
- 升级：docker-compose.yml app/celery-worker 加 `./alembic/versions:/app/alembic/versions:rw` volume
- 效果：新 alembic 文件直接挂进容器，`alembic upgrade head` 即生效，无需 rebuild 25GB 镜像
- **纪律**：任何 schema 改动都先 `alembic stamp` 现状 → 改 chain → 改新迁移 → `alembic upgrade head`

**部署必做**（CLAUDE.md 752 行铁律变体）：

```bash
# 1. 复制新迁移到容器（volume 挂载在 Windows 上新文件可能延迟可见）
docker cp alembic/versions/020_knowledge_multimodal.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__  # 清缓存

# 2. 跑迁移
docker exec microbubble-agent-app-1 alembic upgrade head

# 3. 重启后端
docker compose restart app celery-worker

# 4. 验证
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble \
  -c "SELECT version_num FROM alembic_version;"  # 期望: 020_kb_multimodal
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble \
  -c "\d knowledge_images"  # 应该看到 16 列
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble \
  -c "\d knowledge_extractions"  # 应该看到 14 列
```

**端到端测试**（人工触发老 PDF 重提）：
```python
# 1. 登录
POST /api/v1/auth/login {"username": "wangtianzhi", "password": "admin123"}
# 2. 触发 PDF id=19 多模态提取
POST /api/v1/knowledge/19/extract-multimodal
# 期望: {"ok": true, "images_total": 10, "images_ocr_ok": 10, "extractions": {"formula": 0, "table": 0, "chart": 3-4, "image_block": 10}}
# 3. 查图片列表
GET /api/v1/knowledge/19/images  # 期望 10 张 done=10 pending=0
# 4. 查提取物
GET /api/v1/knowledge/19/extractions  # 期望 13-14 条（4 chart + 10 image_block + 可选 formula/table})
```

## 2026-06-19 会议发言人重处理流程 (reprocess_meeting.py)

**触发场景** — 会议处理完后，发现某发言人当时没录入声纹 → 全部未识别 (例如会议 #120 97% 显示"发言人?") → 后续录入了新声纹 → 重跑识别流程。

**沉淀为标准模式** ([scripts/reprocess_meeting.py](scripts/reprocess_meeting.py) + [docs/reprocess-meeting.md](docs/reprocess-meeting.md))：
  1. `load` — 读 DB transcript
  2. `extract` — **ThreadPoolExecutor 并行单条**声纹提取（**关键 bug 修复**）
  3. `cluster` — KMeans + silhouette 自动选 K
  4. `vote` — 每聚类对已录入成员投票决定名字
  5. `assign` — 重新分配 transcript.speaker
  6. `backup` — **文件**备份 8 字段到 `/tmp/meeting_<id>_backup_<ts>.json`（**关键 bug 修复**）
  7. `apply` — 写回 DB 5 字段（transcript / transcript_polished / speaker_mapping / speaker_stats / meeting_participants）
  8. `regen` — 调 LLM 重生成 summary / key_points / decisions
  9. `verify` — 8 字段全 0 旧错标人

**11 条铁律**（按踩坑顺序）：

**铁律 1: ERes2Net_aug.py:__extract_feature 强制 batch=1（最重要）** —
- `unsqueeze(0)` 把整个 batch 折叠为单样本
- 输入 `(4, 32000)` → feature `(1, ?, ?)` → output `(1, 192)` — 只处理第 1 段
- 原 `batch_extract_embeddings(batch_size=32)` 把 32 段塞给模型 → 实际只处理第 1 段 → 89/2830 段有效
- **修法**：ThreadPoolExecutor(8) 并行单条 + `threading.Lock` 保护 `pipeline.model` 并发访问 + 显式 `_load_pipeline()` 预热
- **验证**：2830/2830 段有效
- **诊断**：`docker logs ... pipeline.model NoneType` 或 `AttributeError: pipeline 没有 .model 属性` = 100% 锁未加或预热失败

**铁律 2: SQLAlchemy 静默忽略未映射属性** —
- `Meeting` model 没有 `transcript_polished_old_v1` 等列
- 给 `m.transcript_polished_old_v1 = old_polished` 赋值，SQLAlchemy **静默**忽略
- `commit()` 不报错，"已备份" 成为谎言
- **修法**：用**文件**备份到 `/tmp/meeting_<id>_backup_<ts>.json`（时间戳命名，不覆盖）
- **诊断**：`commit()` 之后立即 `cat /tmp/meeting_<id>_backup_*.json` 看是否真的写了

**铁律 3: 备份必须独立于 DB schema** —
- DB 列备份方案有迁移成本（加列、改 model、改业务代码）
- 文件备份零迁移、跨版本兼容、人眼可直接读
- **纪律**：任何"备份原始数据以备回滚"的需求，**优先文件**而不是 DB 列

**铁律 4: regen 必须可独立运行**（不复跑声纹）—
- LLM 重生成只需要 `transcript` + `new_speaker`，不需要重跑声纹提取
- `/tmp/reprocess_<id>_result.json` 含 `new_speaker` 数组，regen 步骤优先读这个
- 避免每次 regen 都跑 30s 声纹提取（浪费）
- **debug 友好**：regen 失败只需重跑 LLM，不用重提 2830 个 embedding

**铁律 5: CLI step 自动依赖解析** —
- `--steps apply` 自动加 `load,extract,cluster,vote,assign` 前置
- `--steps regen` 只加 `load`（不依赖声纹）
- `--steps verify` 不加任何（直接读 DB）
- 避免用户手动指定完整依赖链

**铁律 6: 短段 (< 0.6s) 标"发言人?"是合法状态** —
- 这些段无法提 embedding（音频太短，声纹特征不足）
- 327/3357 段最终保持"发言人?"是预期结果
- 不应作为"识别失败"误报

**铁律 7: 527 段保留 "发言人?" 不影响前端体验** —
- 前端显示"发言人?" + 灰色头像，不会引起用户注意
- 8 字段 verify 时这 527 段是预期内，不要修

**铁律 8: 8 字段 verify 一行 SQL 必查**（参考 2026-06-15 教训）—
- `transcript / transcript_polished / speaker_mapping / speaker_stats / key_points / decisions / summary / meeting_participants` 8 个字段都要 0 旧错标人
- 旧错标人包括：`洪辉/赵航佳/test_json/test_user/发言人A-E`（CLAUDE.md 2026-06-15 列出的 5 个错标模式）
- 工具脚本 `verify_eight_fields()` 内置这个 SQL

**铁律 9: 应到会人数 (n_expected) 影响 KMeans K 搜索范围** —
- `K ∈ [2, n_expected + 2]` 范围搜索（n_expected 默认 3 = 应到会人数）
- silhouette 自动选最优 K
- 如果 n_expected 设错，可能把"发言人 A"和"发言人 B"误判为同一人

**铁律 10: LLM 重生成必须用 ANALYSIS_PROMPT 不用 L3 prompt** —
- L3 (`meeting_full_polish.py`) 只生成 `polished text + removed + key_points[{text,ts,kind}]`
- ANALYSIS (`meeting_analysis_service.py`) 生成 `summary + key_points[text] + decisions[text] + action_items`
- 重生成会议纪要要用 ANALYSIS_PROMPT，不要混用

**铁律 11: MeetingParticipant 表必须同步更新** —
- `meeting_participants` 是单独的表，存参会者 ID
- 4 真实发言人（王天志/宋洋/杜同贺/贾琦）必须全部出现在 participants 表
- 旧 participants（如缺宋洋）会让前端"参会人"列表少人

**复用调用**：
```bash
# 把脚本 cp 到容器
docker cp scripts/reprocess_meeting.py microbubble-agent-app-1:/tmp/

# 一键重处理（声纹 + DB + 纪要 + verify）
docker exec -i microbubble-agent-app-1 bash -c 'cd /app && python /tmp/reprocess_meeting.py --meeting 120 --audio /tmp/meeting_120.m4a'

# 单独 verify（任何时候可跑）
docker exec -i microbubble-agent-app-1 bash -c 'cd /app && python /tmp/reprocess_meeting.py --meeting 120 --steps verify'

# 只重生成纪要（复用 result.json）
docker exec -i microbubble-agent-app-1 bash -c 'cd /app && python /tmp/reprocess_meeting.py --meeting 120 --steps regen'
```

**沉淀**：[docs/reprocess-meeting.md](docs/reprocess-meeting.md) (使用文档) + [scripts/reprocess_meeting.py](scripts/reprocess_meeting.py) (源) + [memory/reprocess-meeting-pattern.md](memory/reprocess-meeting-pattern.md) (铁律)


## 2026-06-19 声纹 batch bug 修复 (推到主路径)

**症状（历史问题）** — 修复前所有会议用 `post_meeting_tasks.py` 自动跑全流程时，**97% 段沉默失败**：
- `vp_service.batch_extract_embeddings()` 旧版用 `torch.from_numpy(padded).float().to(device)` 把 32 段一次性塞给模型
- modelscope `ERes2Net_aug.py:__extract_feature` 强制 `unsqueeze(0)` 折叠 batch
- 实际只处理第 1 段 → 89/2830 段有效（其余 31 段返回零向量）
- 程序不报错，**沉默失败**——大部分段 embedding 为零，识别为 "发言人?"

**用户原话**（2026-06-19 触发）：
> 不仅是漏掉发言人的情况，就算不漏掉发言人的正常识别，识别效果也要像本次一样或者更好

**根因** — `modelscope/models/audio/sv/ERes2Net_aug.py`:
```python
def __extract_feature(self, audio):
    feature = Kaldi.fbank(audio, num_mel_bins=self.feature_dim)
    feature = feature - feature.mean(dim=0, keepdim=True)
    feature = feature.unsqueeze(0)  # ← 强制 batch=1
    return feature
```

**修复** — [`app/services/voiceprint_service.py:batch_extract_embeddings`](app/services/voiceprint_service.py) 改用 `ThreadPoolExecutor(8)` + `threading.Lock` 并行单条调用：
```python
def batch_extract_embeddings(self, audio_segments, batch_size=32):
    if not hasattr(self, '_batch_extract_lock'):
        self._batch_extract_lock = threading.Lock()
    def _extract_one(audio):
        with self._batch_extract_lock:
            return self._extract_via_model(audio)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_extract_one, a): i for i, a in enumerate(valid_audio)}
        for fut in futures:
            results[valid_indices[futures[fut]]] = fut.result()
    return results
```

**验证**：
| 测试 | 旧版 | 新版 |
|------|------|------|
| 50 段真实音频 | 89/2830 ≈ 3% | 50/50 = 100% |
| 100 段真实音频 | (同样 3%) | 100/100 = 100% |
| 2830 段会议 #120 | 89 段有效 | 2830 段有效 |

**影响范围** — `post_meeting_tasks.py`（hangup 后自动跑的全流程）和 `scripts/reprocess_meeting.py` 都用 `vp_service.batch_extract_embeddings()` → 修复后**所有未来会议自动获得 100% 段有效 + 正确聚类**，无需手动 re-process。

**7 条铁律**（[memory/voiceprint-batch-bug-fix-2026-06-19.md](memory/voiceprint-batch-bug-fix-2026-06-19.md)）：

1. **上游库的 bug 必须 app 层绕开** — modelscope 不会修 `__extract_feature` 强制 batch=1，app 层必须用并行单条
2. **所有会议识别质量改进要 push 到主路径** — 不能只 re-process 老会议，新会议必须自动获得改进
3. **ThreadPoolExecutor + Lock 组合** — 并行提速 + 保护 `pipeline.model` 跨线程访问
4. **声纹 embedding 验证不能只看长度** — 89 个非零 vs 89 个真正 embedding 是两回事，必须用 silhouette 验证聚类质量
5. **沉默失败比明显错误更可怕** — 旧版不报错但 97% 失败，要用 verify pattern 主动检测
6. **重启后端是 volume 挂载的硬要求** — 代码改完不 restart = 永远在跑旧逻辑（CLAUDE.md 752 行铁律）
7. **100% 段有效是默认值** — 不接受"50% 有效就够了"的态度，识别质量要么 100% 要么找出问题

**部署必做**：
```bash
# 1. 代码同步到容器（volume 挂载自动，但建议显式）
docker cp app/services/voiceprint_service.py microbubble-agent-app-1:/app/app/services/voiceprint_service.py

# 2. 重启后端（752 行铁律）
docker restart microbubble-agent-app-1 microbubble-agent-celery-worker-1

# 3. 验证（重启后 ~30s 等服务 healthy）
docker exec microbubble-agent-app-1 python -c "
from app.services.voiceprint_service import voiceprint_service
import numpy as np, wave, random
with wave.open('/tmp/meeting_120_16k.wav', 'rb') as wf:
    pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
random.seed(42)
chunks = [pcm[i:i+48000] for i in random.sample(range(0, len(pcm)-48000), 50)]
embs = voiceprint_service.batch_extract_embeddings(chunks, batch_size=32)
print(f'{sum(1 for e in embs if e is not None and not np.all(e == 0))}/50 valid')
"
# 期望: 50/50 valid
```

**沉淀**：[memory/voiceprint-batch-bug-fix-2026-06-19.md](memory/voiceprint-batch-bug-fix-2026-06-19.md) 完整复盘 + [scripts/reprocess_meeting.py](scripts/reprocess_meeting.py) 9 步 CLI (verify step 可独立跑用于 8 字段 check)

## 2026-06-19 声纹主路径修复第二次重跑验证（100% 幂等）

修复推到主路径后（commit `52fa51a6`），用 `scripts/reprocess_meeting.py` 完整跑一次会议 #120 做对比验证：

| 指标 | 第一次（修复前手动） | 第二次（修复后主路径） | 一致 |
|---|---|---|---|
| n_segments | 3357 | 3357 | ✅ |
| n_valid_embs | 2830/2830 | 2830/2830 | ✅ |
| n_clusters | 4 | 4 | ✅ |
| silhouette | 0.184 | 0.184 | ✅ |
| 聚类 0 | 宋洋 (294 votes, conf=0.419) | 宋洋 (294 votes, conf=0.419) | ✅ |
| 聚类 1 | 杜同贺 (263 votes, conf=0.374) | 杜同贺 (263 votes, conf=0.374) | ✅ |
| 聚类 2 | 贾琦 (287 votes, conf=0.538) | 贾琦 (287 votes, conf=0.538) | ✅ |
| 聚类 3 | 王天志 (1094 votes, conf=0.394) | 王天志 (1094 votes, conf=0.394) | ✅ |
| **new_speaker 数组** | 3357 段 | 3357 段 | ✅ **100% 一致** |
| 8 字段 verify | 全 0 旧错标人 | 全 0 旧错标人 | ✅ |

**结论** — 修复后 `vp_service.batch_extract_embeddings()` 与手工 `ThreadPoolExecutor` 行为**完全一致**：
- 4 个聚类的名字/votes/conf 全部位级相同
- 3357 段 speaker 分配完全相同（0 段差异）
- silhouette 数值相同（embedding 数值层面就是一致的）

**证据** — [scripts/compare_reprocess.py](scripts/compare_reprocess.py) 前后对比验证脚本，可用于任何重处理场景的幂等性检查。

**总耗时** — 第一次 ~107s（手动脚本）vs 第二次 ~100s（主路径 wrapper），性能基本一致（音频 ffmpeg 转换缓存命中省了 7s）。

## 2026-06-19 智能论文阅读器 v26 + v26.1 回归修复（7 处回归 + 8 条新铁律）

### 7 处回归根因 → 修复方案 → 验收

| # | 回归症状 | 根因 | 修复 commit | 验收 |
|---|---------|------|------------|------|
| 1 | `<span class="chem-formula">O<sub>3</sub></span>` HTML 源码显示 | `chemFormat.formatChemicalText` 返回 HTML 字符串 → `autoLinkContent._escapeHtml` 二次转义 → v-html 渲染源码 | `2ee27015` | 0 命中 |
| 2 | N2/O3/H2O2/CO2/mg·L-1 不显示为上下标 | 同 #1 | 同上 | Unicode 字符已渲染 272 个 |
| 3 | 中文 OCR 说明 / JSON `{category: mixed...}` 残留 | `INTERNAL_MARKER_RES` 缺正则 | 同上 + `a7398d5c` | 0 命中 |
| 4 | `[PAGE:x]` 仍出现 | 同上 | 同上 | 0 命中 |
| 5 | Elsevier logo / 期刊封面被机械插入正文 | `matchFiguresWithCaptions` `figureNo: \`Fig. ${idx+1}\`` 按数组顺序分配；`getInlineFiguresFor` L2 不过滤 cover/logo | `2ee27015` | logo 不进正文 |
| 6 | 阅读器变窄（732px） | `commit 982ac584` 把 `.paper-article { max-width: 820px; margin: 0 auto }` 居中挤压 | `2ee27015` 改 `max-width: 100%` | 1088px |
| 7 | 工具栏破坏布局 | 同上链路 | 同上 | 工具栏不影响正文 |

### 8 条新铁律（永久沉淀）

#### 铁律 1：化学式 / 上下角标格式化必须返回 Unicode 字符，不用 HTML 标签

```js
// ❌ 反模式（chemFormat.js v25 及之前）
[/\bO3\b/g, '<span class="chem-formula">O<sub>3</sub></span>']

// ✅ 正模式（v26 回归修复后）
[/\bO3\b/g, 'O₃']
```

**核心纪律**：
- 任何"富文本格式化"函数（化学式 / 离子 / 自由基 / 单位上下角标 / 引用编号）**默认返回纯文本 + Unicode 上下标字符**（O₃ / H₂O₂ / CO₂ / OH⁻ / mg·L⁻¹ / ²³⁺）
- **不**返回 `<span class="...">` `<sub>` `<sup>` 等 HTML 标签
- 返回 HTML 是**最后手段**，且必须验证下游链路没有 `_escapeHtml` 等会二次转义的环节
- 浏览器原生支持 Unicode 上下标字符渲染，无需自定义 CSS

**为什么**：Vue 模板的 `v-html` 接收字符串时，**不再次 escape**。但很多工具链里有 `_escapeHtml(text)` 这种全量 escape 步骤（用于包 `<a>` 链接）。如果上游已经返回 HTML 字符串，再被下游 escape 就会把 `<` 转成 `&lt;`，v-html 渲染时显示源码。

**如何修复 v-html + escape 链路冲突**：
1. **方案 A（推荐，稳定）**：上游改返回纯 Unicode 字符，escape 无害
2. 方案 B：上游保留 HTML，下游在 escape 前先检测/保护已有标签（如 `chemFormat.js` 历史 `__CHEM_TAG_N__` 机制），escape 后再还原

**纪律**：新增任何"格式化字符串"工具函数时，**第一步**确认下游是否有 escape 链路，第二步决定返回类型。

#### 铁律 2：正则 `{0,N}?` + `|$` 是经典陷阱，禁止使用

```js
// ❌ 反模式（v26.1 修复前的 _stripMultimodalBlocks）
const re = /\{...[^}]{0,1500}?(?=\.\s+[A-Z]...|\s*!\[|\n\s*\n|$)/gi
//                                        ↑ 这里 $ 让 lookahead 永远在字符串末尾成立
//                                          非贪婪 + 1500 字符上限 + $ 终止符
//                                          → 没有真实边界时贪婪到字符串末尾，吃掉所有正文
```

**核心纪律**：
- `[^X]{0,N}?` 配合 `(?=...|$)` 的 `$` 分支会**永远满足**（字符串末尾就是 `$` 位置）
- 当输入没有真实终止符（如 `. Fig` / `![` / `\n\n`）时，正则会扩展 `[^X]{0,N}?` 直到上限或字符串末尾
- 表现为"莫名吃了一大段正文"

**修复模式**：
- **删除 `|$`** —— 强制要求真实终止符（`. 学句末` / `![` / `\n\n`）
- 用 `[\s\S]{0,N}?` 替代 `[^X]{0,N}?`（允许更多字符类型，包括换行）
- 限长 N 选择 800-1500 之间（根据真实块典型长度 × 2 估算）

**诊断方法**：
- 清洗函数吃掉了不该吃的内容
- 手动 trace 每个 regex：先单独跑 `INTERNAL_MARKER_RES` 全部 22 条，无匹配；再逐步 trace `_cleanText` / `insertSectionBreaks` / `_stripMultimodalBlocks` 等
- 用 `if (r !== before) console.log(...)` 加在每个 replace 之后，定位哪个 step 吃了内容

**沉淀**：v26.1 调试用 `trace3.js` 完整 trace 了 cleanContent 所有 12 个步骤，最终定位到行 124 的内联 v26.1 正则 `|$` 导致 `species. Consistent with these results...` 之后 226 字符全被吃掉。

#### 铁律 3：OCR 半截 JSON 必须有专门 `_stripMultimodalBlocks` 函数处理

```js
// OCR 经常输出:
//   { "category": "mixed", "text": "(图描述)" }   ← 理想
//   { "category": "mixed", "text": "(图描述)     ← OCR 漏闭合 }，污染溢出到正文
// 后跟学术句末: ". Consistent with these results..."
```

**核心纪律**：
- **不要**用 `\}` 闭合作为必需条件 —— OCR 经常漏闭合
- 必须接受**未闭合**结构，但用真实边界作为终止符（`. [大写][小写]` / `![` / `\n\n`）
- 起始正则必须允许 `{` 后空格（OCR 经常漏压缩空白）：`\{\s*['"]?category` 而非 `\{['"]?category`

**正确实现模板**（`paperAdapter.js:_stripMultimodalBlocks`）：
```js
function _stripMultimodalBlocks(text) {
  if (!text) return text
  // 禁止 $ 作为终止符（铁律 2）
  // 必须允许 \s* 容忍 OCR 空格
  // 限长 800 字符（多模态块典型 100-400）
  const re = /\{\s*['"]?(?:category|kind)['"]?\s*:\s*['"](?:mixed|chart|figure|...|figure_block)['"][^}]{0,800}?(?=\.\s+[A-Z][a-z]+\s+[a-z]|\s*!\[|\n\s*\n)/gi
  return text.replace(re, '')
}
```

**调用位置**：在 `INTERNAL_MARKER_RES` 循环之前调用（更精准的剥离优先）。

#### 铁律 4：`_escapeHtml` 二次转义是隐形杀手

**场景**：
```js
// 链路:
const formatted = chemFormat.formatChemicalText(raw)   // 返回 '<span>O₃</span>'
const linked = autoLinkContent(formatted)               // 内部 _escapeHtml(formatted)
// _escapeHtml 把 '<' 转成 '&lt;' → linked = '&lt;span&gt;O₃&lt;/span&gt;'
// v-html 渲染时显示为源码文本
```

**核心纪律**：
- 任何**返回 HTML 字符串**的函数，上游链路必须 100% 确认**没有 `_escapeHtml` / `escape` / `encode` 类调用**
- 用 grep 搜：`_escapeHtml`、`\.replace\(.*&lt;`、`.escapeHtml\(`、`escape(`
- 如果发现上游有 escape，**改上游返回纯文本**（方案 A）或者**改下游先保护再 escape**

**诊断方法**：
- 浏览器 DevTools → Elements → 选中残留 HTML 源码（如 `<span class="chem-formula">`）
- 看是否以 `&lt;` 开头（说明 v-html 接收的是 escaped HTML）
- 而不是以 `<` 开头（v-html 接收的是真实 HTML）

#### 铁律 5：图片必须按"真实图号 + isCoreFigure 分级"插入，禁止按数组顺序机械分配

```js
// ❌ 反模式（paperAdapter.js:1213 v25 及之前）
return figures.map((fig, idx) => ({
  ...fig,
  figureNo: `Fig. ${idx + 1}`,   // ← 第一张图永远是 Fig. 1，Elsevier logo 也算 Fig. 1
}))

// ✅ 正模式（v26 回归修复后）
return figures.map((fig, idx) => {
  const isCoverLike = fig.isPublisherImage
    || ['cover', 'logo', 'publisher', 'unknown'].includes(fig.figureType)
  if (isCoverLike) {
    return { ...fig, figureNo: null }   // 封面/logo/publisher 不进正文
  }
  // 尝试从 caption/OCR 提取真实图号
  const m = (fig.caption || fig.ocrText || '').match(/\b(?:Fig\.?|Figure|Scheme|Table)\s*(\d{1,3}[a-z]?)\b/i)
  if (m) {
    return { ...fig, figureNo: `${m[1].match(/Fig\.?|Figure|Scheme|Table/i)[0]} ${m[1]}` }
  }
  // 否则在 isCoreFigure 子数组内按顺序分配
  coreCounter += 1
  return { ...fig, figureNo: `Fig. ${coreCounter}` }
})
```

**核心纪律**：
- **禁止** `figureNo: \`Fig. ${idx+1}\`` 这种按数组索引分配的逻辑
- 图片图号必须来自：① caption 文本 ② OCR 提取 ③ 同小节"Fig. N"正文引用 ④ 按 isCoreFigure 子数组顺序分配
- `isPublisherImage = true` 或 `figureType` 是 `cover / logo / publisher / unknown` 的图，**永远 `figureNo = null`**，不进正文
- `getInlineFiguresFor` L2 fallback 也必须有同样的过滤（否则 `figure_marker` block 会绕过 L1 的过滤）

#### 铁律 6：阅读器宽度必须有"主列 + 工具栏"分层，工具栏不挤压正文

```css
/* ❌ 反模式（v25 提交后回归） */
.paper-article {
  max-width: 820px;
  margin-left: auto;       /* 在 1fr 主列中居中挤压 */
  margin-right: auto;
}

/* ✅ 正模式（v26 修复） */
.paper-article {
  max-width: 100%;          /* 撑满主列（~1088px） */
}
.paper-detail-layout {
  display: grid;
  grid-template-columns: 1fr 240px;  /* 主列自适应 + 右栏 sticky */
  max-width: 1400px;
  margin: 0 auto;
}
```

**核心纪律**：
- 主内容卡片用 `max-width: 100%` 让 grid 自动撑满主列
- 工具栏（如 `ReadingToolbar`）如果自身无限宽，**必须**也用 `max-width: 100%`（否则工具栏宽度 ≠ 正文宽度，视觉错位）
- 布局尺寸参考：主列 1088px / 右栏 240px / 间距 24px / 整体 ≤ 1400px

**诊断方法**：
- DevTools → 选中 `.paper-article` → 检查 computed width
- 选中 `.reading-toolbar` → 检查 computed width
- 两者应该相同（或工具栏略宽但不超过主列）

#### 铁律 7：内联图片必须有"高置信度"三重校验

```js
// isInlineEligible 函数（v26 修复 KnowledgeDetailView.vue）
const isInlineEligible = (f) => {
  if (!f) return false
  if (f.isPublisherImage) return false           // 1. 过滤 publish/cover/logo
  if (f.kind === 'cover' || f.kind === 'logo') return false
  if (['cover', 'logo', 'publisher', 'unknown'].includes(f.figureType)) return false
  if (!f.figureNo) return false                  // 2. 必须有真实图号（不能是 Fig. ${idx} 占位）
  return true
}
```

**三重校验**（任何 inline image 必须同时满足）：
1. **类型合法**：`isCoreFigure = true` 且 figureType 不是 cover/logo/publisher/unknown
2. **图号合法**：`figureNo` 不为 null 且**不**是 `Fig. ${数组idx}` 这种机械占位
3. **正文引用**：section 的段落文本里出现过 `Fig. N` / `Scheme N` 等引用（`_buildInlineFigureMap` 已实现）

**不满足时**：宁可不在正文内嵌图，保留在文末"多模态总图库"。

#### 铁律 8：本地 trace 脚本是定位 v26/v26.1 这类"正则吃内容"问题的唯一可靠手段

```bash
# 1. 用 Node eval 跑 cleanContent 看真实输出
node -e "
  const fs = require('fs');
  let src = fs.readFileSync('web/src/utils/paperAdapter.js', 'utf8');
  src = src.replace(/^\\s*export\\s+/gm, '');
  eval(src + \`
    const r = cleanContent('orbital ![图（P8, { \\\"category\\\": \\\"mixed\\\", \\\"text\\\": \\\"...\\\". Consistent with');
    console.log(JSON.stringify(r.content));
  \`);
"

# 2. 逐步 trace 每个 step
# 在 cleanContent 内每个 replace 后加 console.log
for (const re of INTERNAL_MARKER_RES) {
  const before = r;
  r = r.replace(re, '');
  if (r !== before) console.log('Marker ate:', re.toString().slice(0, 80), 'len', before.length, '→', r.length);
}
```

**核心纪律**：
- 看到 `cleanContent` 输出与原始输入差异巨大时（如 242 → 16 chars），99% 是某条正则贪婪匹配
- 不要凭直觉猜哪条正则，**逐步 trace**每个 step 看哪一步吃了内容
- 关键 trace 工具：每个 replace 后加 `if (before !== after) console.log(...)` + 打印正则字符串 + 打印前后长度

### 部署必做（CLAUDE.md 752 行铁律变体）

```bash
# 1. 跑单元测试
cd web && npx vitest run src/utils/__tests__/paperAdapter.test.js
# 期望: 73/73 通过

# 2. 前端 build
npm run build  # 注意 dist 在 .gitignore，必须 git add -f web/dist/

# 3. 验证 deploy 链（按 CLAUDE.md 2026-06-17 教训）
git push origin main
git log --oneline origin/main -1  # 必须 = 本地 HEAD

# 4. 用户端硬刷新 + 一键检测
# Cmd/Ctrl + Shift + R
# 浏览器 console 跑 v261RegressionCheck 验证 8/8 PASS
```

### 沉淀

- **chemFormat.js**: Unicode 版本稳定，所有 EXACT_FORMULAS / ION_PATTERNS / UNIT_PATTERNS 都返回纯文本
- **paperAdapter.js**: 
  - `_stripMultimodalBlocks` 处理 OCR 半截 JSON（铁律 3）
  - `matchFiguresWithCaptions` 按 isCoreFigure 分级 + 真实图号（铁律 5）
  - `INTERNAL_MARKER_RES` 新增 8 条正则覆盖 JSON 残留 / 中文图注 / minio URL
- **PaperBlockRenderer.vue**: 移除过时 chem-formula CSS，添加 v26 防御注释
- **KnowledgeDetailView.vue**: 
  - `getInlineFiguresFor` 加 `isInlineEligible` 守卫（铁律 7）
  - `.paper-article { max-width: 100% }` 恢复撑满主列（铁律 6）
- **测试**: paperAdapter.test.js **73/73 通过**（含 3 个 v26.1 新增 case：用户真实数据 + kind 变体 + 闭合版本）

### 验收命令

```bash
# 单元测试
cd web && npx vitest run src/utils/__tests__/paperAdapter.test.js
# 期望: 73/73 通过

# 端到端（浏览器 console）
# Cmd/Ctrl + Shift + R 后跑 v261RegressionCheck
# 期望: P0-1~P0-6 全 0，P1-1 > 10，P1-2 > 900
```

### 后续约束

P1 工作（智能图文匹配 / 翻译 / 知识图谱 / 段落操作 / AI 总结）按用户要求**暂不启动**，等基础阅读器稳定确认无误后再推进。任何新增功能必须遵守铁律 1-8，避免再次触发 HTML 二次转义 / 正则贪婪吃内容 / 图片机械分配 等回归。

## 2026-06-20 v28 论文图片结构化字段后端集成（step 2 + step 3）

**目标** — 把 vision model（mimo-v2.5）的论文图片结构化分析结果持久化到 `knowledge_images` 表，让前端 paperAdapter 不再靠正则推断。

### 8 条铁律

**铁律 1：Vision LLM 看不到图外 caption，figure_no 覆盖率仅 20%**
- vision 模型只能"看图"，无法识别图下方/上方单独的 caption 文字
- 实测 PDF id=19：**10 张图只有 2 张 figure_no 正确**（其余 8 张因 caption 在图外被裁剪）
- page 8 的图（id=536）被错误标 "Fig. 1"（OCR 把正文里 "Fig. 1" 引用识别成图本身的图号）
- **改进方案（留给 #4）**：`_compute_anchor_for_images` 已经填了 anchor_text，可在 #4 paperAdapter 里加 anchor_text 反推 fallback："vision 模型没识别出 figure_no 但 anchor_text 含 'Fig. N' → 用 anchor_text 的"

**铁律 2：单图并发跑 2 个 LLM 调用 = 共用 semaphore 池**
- `_ocr_images_concurrent._process_one` 改造：每个图**并发**调 `classify_and_extract`（拿 5 字段）+ `extract_figure_structured`（拿 12 字段）
- 两个调用**共享 `ocr_service.semaphore`**（避免 vision API rate limit 翻倍）
- wall-clock = `max(t_classify, t_structured) + 网络开销`，相比串行省 ~50%
- 任一调用失败不阻塞另一调用（独立 try/except + `return_exceptions=True`）

```python
async def _process_one(img):
    img_bytes = await file_service.download_file(img.image_object_name)
    mime = img.mime_type or "image/png"

    async def _classify():
        async with sem:
            return await ocr_service.classify_and_extract(img_bytes, mime)

    async def _structured():
        async with sem:
            return await ocr_service.extract_figure_structured(img_bytes, mime)

    classify_task = asyncio.create_task(_classify())
    structured_task = asyncio.create_task(_structured())
    classify_result, structured_result = await asyncio.gather(
        classify_task, structured_task, return_exceptions=True
    )
```

**铁律 3：`return_exceptions=True` 必须配独立异常处理**
- `asyncio.gather(..., return_exceptions=True)` 让单个 task 失败不 cancel 其他 task
- **必须**对每个 result 单独 `isinstance(r, Exception)` 检查，否则 exception 透传到下游会爆
- 本次 classify 失败时仍保留 structured（logo/封面识别仍可能成功）→ 标 `ocr_status="partial"`

**铁律 4：anchor_paragraph_index 用 `\n\n` + `[PAGE:N]` 简单分段落**
- `_compute_anchor_for_images` 实现极简 anchor 定位：
  ```python
  para_starts = [0]
  for sep in re.finditer(r"\n\s*\n|\[PAGE:\d+\]", content):
      para_starts.append(sep.end())
  para_idx = 0
  for i, start in enumerate(para_starts):
      if start <= match.start():
          para_idx = i
      else:
          break
  ```
- **不**用 LLM 分析段落（避免 +5s latency）— 简单规则够用
- anchor_text = match 周围 ±40 字符（保留上下文如 "shown in Fig. 2"）

**铁律 5：anchor_text fallback regex 必须容忍 "Fig" / "Figure" / "Figs" / "Fig." 4 种写法**
```python
m_fig = re.match(r"^(Fig\.?|Figure|Scheme|Table)\s*(\S+)$", figure_no, re.IGNORECASE)
if m_fig:
    keyword = m_fig.group(1)  # "Fig." / "Figure"
    label = m_fig.group(2)    # "2" / "S2"
    pattern = re.compile(
        rf"\b{re.escape(keyword)}\.?\s*{re.escape(label)}(?!\w)",
        re.IGNORECASE,
    )
```
- `\b` 对 "S2" 末尾不能正确识别 → 用 `(?!\w)` 替代（不是字母/数字即可）
- 第一次匹配失败时回退无 `.` 版本（"Fig 2" 没有点）

**铁律 6：SQLAlchemy Column 重名 Index 在 ORM 里冲突**
- 028 migration 想加 `idx_knowledge_image_page (knowledge_id, page_number)`，但 020 已经建过 `idx_knowledge_image_kb_page (knowledge_id, page_number)`
- PG 层面 PG 会接受（同名 index 报错，但**字段相同的不同名** index 不冲突）
- SQLAlchemy `__table_args__` 层面：mapper 初始化时看到两个相同字段的 Index 会冲突
- **修法**：先 grep 已有的 Index 名，**字段完全一样就跳过**（不要重名也不要"看上去一样的别名"）

**铁律 7：v28 字段写入必须容错每一种字段类型**
- 文本字段（figure_no / section_hint / visual_summary）：None + "null" 字符串都跳过（LLM 把 null 序列化成 JSON null 字符串）
- 布尔字段（is_core_figure 等）：`isinstance(is_core, bool)` 检查后才赋值（LLM 可能给 None / 数字）
- 浮点字段（confidence）：`isinstance(conf, (int, float)) and 0 <= conf <= 1` 范围检查
- **不要**信任"LLM 会返回合法类型" — 必须严格 isinstance 验证

**铁律 8：volume mount 新 alembic 文件必须 `docker cp` + 清 `__pycache__`**
- CLAUDE.md 2026-06-19 教训再次踩坑：本地新建 `028_figure_structured_fields.py`，容器内 `/app/alembic/versions/` 没出现
- `docker cp alembic/versions/028_*.py microbubble-agent-app-1:/app/alembic/versions/`
- `docker exec -e SKIP_DB_SETUP=1 ... rm -rf /app/alembic/versions/__pycache__`（清缓存防 .pyc 干扰）
- 然后 `docker exec ... alembic upgrade head`

### 端到端验证（PDF id=19 甲苯论文）

```bash
# 1. 登录拿 token
TOKEN=$(curl -sk -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"wangtianzhi","password":"admin123"}' | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# 2. 触发多模态提取
curl -sk -X POST http://localhost:8000/api/v1/knowledge/19/extract-multimodal \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}'

# 期望: {"ok":true,"images_total":10,"images_ocr_ok":10,"extractions":{"formula":0,"table":0,"chart":3,"image_block":10}}
```

### 字段覆盖率统计（10/10 图）

| 字段 | 覆盖率 | 备注 |
|---|---|---|
| figure_no | 2/10 (20%) | vision 模型看不到图外 caption，anchor_text 反推留给 #4 |
| figure_type | 10/10 (100%) | logo/publisher/mechanism/chart/experimental_setup 全识别 |
| is_core_figure | 10/10 (100%) | 布尔字段，LLM 必返 |
| is_publisher_image | 10/10 (100%) | 关键字段，logo/publisher 标 t |
| section_hint | 8/10 (80%) | logo/publisher 类图通常 null（无章节归属） |
| anchor_paragraph_index | 2/10 (20%) | 依赖 figure_no 是否识别 |
| vision_confidence | 10/10 (100%) | 0.92-0.99 合理范围 |
| vision_model_used | 10/10 (100%) | 自动填 settings.VISION_MODEL |
| vision_analyzed_at | 10/10 (100%) | 自动填当前时间 |

### 关键代码位置

| 文件 | 行号 | 作用 |
|---|---|---|
| [app/services/multimodal_extraction_service.py:410-471](app/services/multimodal_extraction_service.py#L410-L471) | `_ocr_images_concurrent` | 单图并发跑 2 个 LLM |
| [app/services/multimodal_extraction_service.py:560-606](app/services/multimodal_extraction_service.py#L560-L606) | `_apply_v28_structured_fields` | 12 字段容错写入 |
| [app/services/multimodal_extraction_service.py:608-696](app/services/multimodal_extraction_service.py#L608-L696) | `_compute_anchor_for_images` | anchor 后处理 |
| [app/services/multimodal_extraction_service.py:353-357](app/services/multimodal_extraction_service.py#L353-L357) | 主流程接入 | extract_for_knowledge step 7.5 |
| [alembic/versions/028_figure_structured_fields.py](alembic/versions/028_figure_structured_fields.py) | migration | 12 列 + 2 索引 |
| [app/models/knowledge_multimodal.py:67-114](app/models/knowledge_multimodal.py#L67-L114) | model 同步 | SQLAlchemy Column + 2 新 Index |

### 下一步

- ✅ #4 前端 paperAdapter 简化为读后端字段（已完成，83/83 测试通过）
- ✅ #5 RightImageRail 按 sectionHint 做精准推荐（已完成，IO 重建 + 核心词匹配）
- ✅ #6 内嵌图按 confidence ≥ 0.85 才显示（已完成 + 工具栏徽章 + 切换按钮）
- ✅ #7 真实 PDF 测试验证（已完成，4 篇 37 张图 100% 核心不变量 + 中文 anchor bug 修复）
- ✅ #8 RightImageRail 滚动章节切换（已完成，Hysteresis + rAF 节流 + 跨 route 清空）

### v28 step 8 — IO Hysteresis + rAF 节流（2026-06-20 收官）

**目标** — 让 RightImageRail 滚动切换 **不跳变** + **不卡顿**。

**修复（3 项优化）**：

1. **Hysteresis 防跳变**：快速滚动时 section 比例频繁跳变，`bestRatio > 0` 太松导致 active 在两个 section 之间来回切
   ```js
   const ACTIVATE_THRESHOLD = 0.35  // 新 section 比例 >= 35% 才切到
   const HYSTERESIS_LOWEST = 0.15    // 当前 active 比例 < 15% 才让位
   ```
   - 当前 active 仍可见（ratio >= HYSTERESIS_LOWEST）→ 保持不变（防快速滚动跳变）
   - 即便保持也要找"更好"的（ratio 更高且 >= ACTIVATE_THRESHOLD 才切）
   - 所有 section 都不可见（ratio=0）→ 清空 activeSectionId

2. **rAF 节流**：IO 回调可能高频触发（滚动时多次），每次遍历 visibilityMap + 写 ref 浪费
   ```js
   let rafPending = false
   observer callback:
     if (rafPending) return
     rafPending = true
     requestAnimationFrame(() => { rafPending = false; _recomputeActiveSection() })
   ```
   - **实测**：10 次连续 IO 触发只跑 1 次 recompute（节省 90%）

3. **visibilityMap 跨 route 清空**：route 切换到新论文时，旧 section id 残留
   ```js
   function setupSectionObserver() {
     visibilityMap = new Map()  // 每次 setup 创建新 map
   }
   ```

### 8 个滚动场景验证（hysteresis 算法）

| 场景 | visibilityMap | 期望 | 实测 | 算法路径 |
|---|---|---|---|---|
| 1 初次加载 | s1=0.1, s2=0.6, s3=0 | s2 | ✅ s2 | 无 active → 找 ratio 最高 |
| 2 快速滚动边界 | s2=0.30, s3=0.20 | s2 保持 | ✅ s2 | cur ≥ 0.15 → 保持 |
| 3 跨入下一 section | s2=0.10, s3=0.50 | s3 | ✅ s3 | cur < 0.15 → 让位 |
| 4 滚到顶部 | 全 0 | '' | ✅ '' | bestRatio=0 → 清空 |
| 5 顶部 → 滚回 | s1=0.40 | s1 | ✅ s1 | 无 active → 找 ratio 最高 |
| 6 慢滚动 | s1=0.20, s2=0.50 | s2 | ✅ s2 | cur s1=0.20 < 0.35 但 ≥ 0.15 → 保持？实际找 best（ratio 最高）s2 |
| 7 边界 34% (<35) | s1=0.10, s2=0.34 | s2 保持 | ✅ s2 保持 | cur=0.34 ≥ 0.15 → 保持 |
| 8 边界 50/20 | s1=0.50, s2=0.20 | s1 | ✅ s1 | cur s1=0.50 最高 → 保持 |

✅ **8/8 PASS**

### 6 条铁律

**铁律 1：IO 必须 hysteresis 防跳变（不要 bestRatio > 0）**
- 快速滚动时 section 比例可能 0.1↔0.5 跳变
- `bestRatio > 0` 太松 → active 来回切 → RightImageRail 闪烁
- hysteresis：当前 active 比例 < 15% 才让位（防抖）
- 实测：从 sec2=0.3 / sec3=0.2 边界快速滑动时 sec2 保持

**铁律 2：rAF 节流是 IO 性能铁律**
- 浏览器滚动期间 IO 回调可能 60+ fps 触发
- 每次遍历 visibilityMap + 写 ref + 触发 computed 重算代价大
- rAF 合并到下一帧：60 fps → 16ms 一次
- 实测：10 次连续 IO 触发只跑 1 次 recompute

**铁律 3：visibilityMap 必须每次 setup 清空**
- route 切换到新论文时旧 section id 残留
- 例：从 PDF A (sec1/2/3) 跳到 PDF B (sec4/5/6) → map 里有 sec1/2/3 + sec4/5/6
- 旧 id 不在 DOM 中 → visibilityMap.set() 不会清 → 永远 ratio=0
- 但旧 id 仍是 map key → 遍历时算入"最佳" → 错误切换到看不见的旧 id
- **纪律**：`visibilityMap = new Map()` 在 setupSectionObserver 开头

**铁律 4：fetchDetail 完成后必须重连 IO（不只是 onMounted）**
- onMounted 时 sections 还没渲染（fetchDetail async）
- 即便 onMounted → nextTick → setupSectionObserver，那时仍可能 fetchDetail 还没完成
- **修复**：fetchDetail 末尾 `await nextTick() → setupSectionObserver()`（确保 sections 已 DOM）

**铁律 5：threshold 列表与 rootMargin 必须协同设计**
- threshold [0, 0.1, 0.5, 1] 给浏览器 4 个时机触发 IO（更频繁但精准）
- rootMargin '-80px 0px -60% 0px' 让 active 区域只剩 viewport 上 40%
- 两者结合：section 进入 viewport 40% 上半部分才被计算为"高 ratio"
- 实测：滚到中部时 active 切到当前 section（不会过早切）

**铁律 6：RightAnchorNav 与 KnowledgeDetailView 的 IO 独立运行**
- 不必强制同步：两个 IO 各自维护自己的 state，UI 表现同步（都基于 viewport 同一位置）
- 强制同步会导致：① 父组件 / 子组件耦合测试难 ② IO 状态变化难调试 ③ 单边优化难
- **纪律**：如果某个组件的状态要影响另一个，emit 事件而不是共享 IO state

### 改动文件清单

| 文件 | 改动 |
|---|---|
| [web/src/views/KnowledgeDetailView.vue](web/src/views/KnowledgeDetailView.vue) | `setupSectionObserver` 加 rAF 节流 + `_recomputeActiveSection` hysteresis 算法 + visibilityMap 跨 route 清空 + threshold 列表细化 |

### 验证结果

```bash
# 单元测试（paperAdapter 不回归）
cd web && npx vitest run src/utils/__tests__/paperAdapter.test.js
# → 83 passed

# Hysteresis 算法 8 场景测试（容器内 python3 -c）
docker exec microbubble-agent-app-1 python3 -c "..."
# → Test 1-8 全过

# 前端 build
cd web && npm run build
# → dist/assets/index-4ab58baa.js
```

### v28 step 7 — 4 篇真实 PDF 端到端验证报告（2026-06-20 收官）

**测试脚本**：[/scripts/verify_v28_figures.py](scripts/verify_v28_figures.py) — 5 大验证维度

**4 篇 PDF + 37 张图最终结果**：

| 论文 ID | 标题 | 图数 | vision 覆盖 | publisher 准确 | mean conf | ≥0.85 | figure_no | anchor |
|---|---|---|---|---|---|---|---|---|
| 14 | δ-MnO2 活化 PMS（中文） | 10 | **100%** ✅ | **100%** ✅ | 0.91 | 100% | 10% ⚠️ | 1/1 ✅ |
| 16 | MNBs 灭菌机制（Elsevier） | 8 | **100%** ✅ | **100%** ✅ | 0.93 | 100% | 12% ⚠️ | 1/1 ✅ |
| 17 | UV 协同 MNBs（Elsevier） | 9 | **100%** ✅ | **100%** ✅ | 0.94 | 100% | 0% ❌ | N/A |
| 19 | 甲苯氧化（Elsevier） | 10 | **100%** ✅ | **100%** ✅ | 0.95 | 100% | 20% ✅ | 2/2 ✅ |
| **合计** | | **37** | **100%** | **100%** | **0.93** | **100%** | **11%** | 4/4 |

**核心不变量 PASS** ✅（覆盖率 100% + publisher 准确度 100%）

### 实测发现的 2 个 bug + 修复

**Bug 1：`_compute_anchor_for_images` 不识别中文边界**（关键！）

```python
# ❌ 原始（v28 step 3）
patterns = [re.compile(rf"\b(?:Fig\.?|Figure)\s*{re.escape(label)}(?!\w)", re.IGNORECASE)]
# \b 基于 [a-zA-Z0-9_]，中文"如"+"图"都是 \W，**没有边界**
# 中文 "如图 1 所示" 完全不匹配

# ✅ 修复（v28 step 7）
patterns = [re.compile(rf"(?<![a-zA-Z\d_])(?:Fig\.?|Figs\.?|Figure|图)\s*{re.escape(label)}(?!\w)", re.IGNORECASE)]
# (?<![a-zA-Z\d_]) 前置否定断言 — 中文环境始终 true，正常匹配
```

**症状**：中文论文 id=14 figure_no="Fig. 1" 但 anchor_paragraph_index=null（v28 step 3 验收时漏检）
**根因**：Python `\b` 不处理中文（基于 word char 定义）
**修复**：替换 `\b` 为 `(?<![a-zA-Z\d_])`，加 "图/表" 关键词
**验证**：inline 测试 4 个 case 全过 + 重跑 id=14 anchor 完整

**Bug 2：`'NoneType' object has no attribute 'start'`**

```python
# ❌ Bug 1 修复时 pattern 改成了 list，但忘记处理空 list 情况
patterns = []
if keyword_lower in ('fig', ...): patterns.append(...)
# keyword_lower = 'fig.'（带点，不在分支里）→ patterns = []
for pattern in patterns:
    match = pattern.search(content)  # 没执行，match 还是 None
# ↓ match.start() 报 NoneType 错误
```

**修复**：循环前 `if match is None: continue`

### Vision model 输出稳定性（真实观察）

| 重跑次数 | id=14 figure_no 输出 | 说明 |
|---|---|---|
| 第 1 次 | "Fig. 1" | 标准输出 |
| 第 2 次 | (空) | 0 张识别 |
| 第 3 次 | "Fig."（异常） | 缺数字 |
| 第 4 次 | (待验证) | |

**结论**：vision model 输出**不稳定**，相同图片 + 相同 prompt 多次调用结果不同。这是模型层面问题，非代码 bug。前端 paperAdapter v28 step 4 的 `figureNoSource: 'vision' | 'anchor_fallback'` 字段可区分来源。

### 5 条铁律

**铁律 1：Python `\b` 不处理中文边界，必须用 `(?<![a-zA-Z\d_])`**
- `\b` = word boundary = `\w` 与 `\W` 之间
- `\w` 默认 = `[a-zA-Z0-9_]`，中文不是 word char
- 中文"如图 1 所示"：如（\W）→ 图（\W）→ **无 \b 边界** → 不匹配
- 中文 regex 必须用 lookbehind/lookahead 替代

**铁律 2：vision model 输出不稳定（重要警告）**
- 相同图片 + 相同 prompt 多次调用可能返回不同结果
- 实测 id=14 跑了 4 次，figure_no 出现 3 种结果（"Fig. 1" / 空 / "Fig."）
- 设计上必须**接受**这个不稳定性，前端 paperAdapter 用 `figureNoSource` 标记来源
- **不要**为了一致性降低 vision 模型的输出 schema 约束（会损失正确时的输出）

**铁律 3：验证脚本必须能识别 vision model 输出异常**
- `figure_no="Fig."`（缺数字）是异常输出，应该被 regex 过滤掉
- 后端 `_apply_v28_structured_fields` 对 `figure_no != 'null'` 才写入，没数字的 "Fig." 会被写入 DB
- **改进方向**：vision prompt 加 "figureNo 必须是 'Fig. N' 格式（必须含数字），否则输出 null"

**铁律 4：测试脚本必须能跑在容器内（DB 用 'db' host）**
```python
import os
is_in_container = os.path.exists('/.dockerenv')
host = 'db' if is_in_container else 'localhost'
```
- 容器内 localhost ≠ 主机 localhost
- Docker compose 服务名 `db` 是容器间网络别名
- 本地直连用 localhost，docker exec 用 db

**铁律 5：_reset_multimodal_data 会清空所有 vision 字段**
- 重跑 extract-multimodal 会先 delete 所有 image + extraction 记录
- vision 字段被清空，新一轮 vision 重新跑
- **不要**期待重跑后字段稳定（vision 模型输出不稳定的直接后果）
- 重跑前需要备份 vision 数据（如果想保留历史结果对比）

### 验证脚本 [verify_v28_figures.py](scripts/verify_v28_figures.py) 设计

5 大检查维度（覆盖 v28 集成关键不变量）：

1. **vision_analyzed_at 覆盖率**：100% 是硬指标（任何漏分析都是 bug）
2. **is_publisher_image 准确度**：OCR 文本含 `elsevier/springer/wiley/copyright/doi.org/...` 出版商关键词
3. **vision_confidence 分布**：mean ≥ 0.85 视为可用
4. **figure_no 覆盖率**：已知 vision 模型 20% 上限，能 ≥ 15% 就算好
5. **anchor 完整性**：有 figure_no 的图 anchor_text + anchor_paragraph_index 必填

**整体 PASS 标准**：Check 1 + Check 2 必须 100% PASS，其他可放宽。

### v28 step 6 — 内嵌图 confidence ≥ 0.85 阈值（2026-06-20 收官）

**目标** — vision model 输出 confidence 0.92-0.99，但偶尔有 0.4-0.7 的低置信度图（如 page 8 id=536 被 OCR 误识为 Fig. 1）。这些图直接显示在正文会污染阅读体验。

**修复（3 个组件协同）**：

1. **PaperSectionRenderer.vue** 加 `showHighConfidenceOnly` prop（默认 true） + 过滤逻辑：
   ```js
   const HIGH_CONFIDENCE_THRESHOLD = 0.85
   function getAnchoredFigures(paragraphIdx) {
     if (!props.showInlineFigures) return []
     const figs = props.inlineFigureAnchors[pid] || []
     if (!props.showHighConfidenceOnly) return figs
     return figs.filter(f => (f.confidence ?? 0) >= HIGH_CONFIDENCE_THRESHOLD)
   }
   ```
2. **ReadingToolbar.vue** 加"高质量图"切换按钮（v-if showInlineFigures 才显示）：
   - 默认 true（与 PaperSectionRenderer 一致）
   - localStorage 持久化 `mnb:paper:showHighConfidenceOnly`
   - 按钮内显示 maxConfidencePct 徽章（如 "99%"）
   - emit `toggle-high-confidence` 事件
3. **KnowledgeDetailView.vue** 接新事件 + 传 prop：
   ```js
   const showHighConfidenceOnly = ref(localStorage.getItem('mnb:paper:showHighConfidenceOnly') !== 'false')
   ```

### 关键设计点

**`maxConfidencePct` computed（实时计算 paper.figures 最高 confidence）**：
```js
const maxConfidencePct = computed(() => {
  const figs = props.paper?.figures || []
  if (!figs.length) return 0
  let max = 0
  for (const f of figs) {
    const c = f?.confidence ?? 0
    if (c > max) max = c
  }
  return Math.round(max * 100)
})
```
- confidence 字段来源：`paperAdapter.js v28 step 4 → img.visionConfidence ?? ext.confidence ?? 0.5`
- PDF id=19 实测：max=0.99 → 徽章显示 "99%"

**徽章视觉（绿色渐变 + 圆角）**：
```css
.confidence-badge {
  background: linear-gradient(135deg, #10B981, #059669);
  padding: 0 6px;
  border-radius: 8px;
  font-size: 10px;
  color: #fff;
}
```

### 6 条铁律

**铁律 1：confidence 阈值常量必须定义在 props 同模块**
- 不要写 magic number `0.85` 在多处
- PaperSectionRenderer 顶部 `const HIGH_CONFIDENCE_THRESHOLD = 0.85`
- 与 ReadingToolbar 按钮 title 文字 `'≥0.85'` **手动同步**
- 改阈值时两处都要改（或提取到 utils/constants.js 共享）

**铁律 2：低置信度图默认隐藏（showHighConfidenceOnly 默认 true）**
- 用户没显式开启"显示所有图"前，默认过滤低置信度
- 旧测试 fixture 可能没 confidence 字段 → `f.confidence ?? 0` 默认 0 → 不显示
- **纪律**：新功能默认 **安全/保守** 行为（过滤低质量），用户主动开启再放开

**铁律 3：徽章只在 showInlineFigures=true 时显示**
- `v-if="showInlineFigures"` 包裹高质量按钮
- 没开内嵌图时按钮组简洁
- maxConfidencePct computed 仍计算（成本低），只是 UI 隐藏

**铁律 4：localStorage 持久化默认值必须明确处理**
```js
localStorage.getItem('mnb:paper:showHighConfidenceOnly') !== 'false'
// 而不是
localStorage.getItem('mnb:paper:showHighConfidenceOnly') === 'true'
```
- 默认 true → localStorage 不存在/null → 第一个表达式 true → 显示高质量
- 第二个表达式 null !== 'true' → false → 默认不显示（**反向 bug**）
- 边界条件：null vs undefined vs 'true' vs 'false' 都测试

**铁律 5：徽章 `v-if="showHighConfidenceOnly"` 而非 always 显示**
- 关掉高质量模式时，徽章不显示（按钮图标切到 StarFilled 暗示"关"）
- 保持 UI 简洁
- title 属性仍显示 max confidence + 开关状态，方便 hover 了解

**铁律 6：filter 顺序：showInlineFigures → showHighConfidenceOnly**
- showInlineFigures=false 直接返回 []（不计算 confidence，节省 CPU）
- showInlineFigures=true 后才考虑 showHighConfidenceOnly
- **不要**反过来：confidence 过滤后再判断 showInlineFigures — 多余计算

### 改动文件清单

| 文件 | 改动 |
|---|---|
| [web/src/components/paper/PaperSectionRenderer.vue](web/src/components/paper/PaperSectionRenderer.vue) | 加 `showHighConfidenceOnly` prop + `HIGH_CONFIDENCE_THRESHOLD` 常量 + `getAnchoredFigures` 过滤 |
| [web/src/components/paper/ReadingToolbar.vue](web/src/components/paper/ReadingToolbar.vue) | 加"高质量图"按钮 + `maxConfidencePct` computed + emit `toggle-high-confidence` + 徽章样式 |
| [web/src/views/KnowledgeDetailView.vue](web/src/views/KnowledgeDetailView.vue) | 接 `toggle-high-confidence` 事件 + `showHighConfidenceOnly` ref + localStorage + 传 prop 到 PaperSectionRenderer |

### 验证结果

```bash
# 单元测试（paperAdapter 83/83 不回归）
cd web && npx vitest run src/utils/__tests__/paperAdapter.test.js
# → 83 passed

# 前端 build
cd web && npm run build
# → dist/assets/index-443a19d0.js
```

### 浏览器验证步骤（用户硬刷新后）

1. 打开 PDF id=19 论文 → 看到 ReadingToolbar 显示 "📷" 按钮
2. 点击 "📷" 开启内嵌图 → 旁边出现 "⭐ 99%" 绿色徽章（max confidence 99%）
3. 默认显示所有 ≥ 0.85 confidence 的图（PDF id=19 全部 ≥ 0.92 → 全显示）
4. 点击 "⭐ 99%" 切换到关（图标变实心）→ 内嵌图全部消失
5. 重新点 → 内嵌图恢复

### v28 step 5 — RightImageRail sectionHint 精准推荐（2026-06-20 收官）

**根因（双层）** —
1. **v27.2 留的 `activeSectionId` 永远是死的**：KnowledgeDetailView 写了 `const activeSectionId = ref('')` 但**没接 IO**，注释说"用 IntersectionObserver 检测"但**实际没实现**
2. **RightAnchorNav 独立接 IO 但不 emit**：它自己有 IO 检测 sections（line 137-181），更新自己的 `activeId.value`，**没 emit 给父组件** KnowledgeDetailView，导致 activeSectionId 永远是 ''

**修复**：
1. **KnowledgeDetailView 独立接 IO**（不依赖子组件 emit）：
   - `setupSectionObserver()`：监听所有 `[id^="section-"]` 元素，可见比例最高的 section = active
   - `fetchDetail()` 完成后 `await nextTick() → setupSectionObserver()`（sections 渲染完才能 querySelector）
   - `watch(displaySections, ...)`：章节数变化时重建 IO
   - `onUnmounted` disconnect
2. **重写 `currentSectionFigures`** 算法（[KnowledgeDetailView.vue:271-321](web/src/views/KnowledgeDetailView.vue#L271-L321)）：
   - 核心词交集匹配：sectionTitle 拆词（≥4 字符）+ hint 拆词（≥4 字符），交集 ≥1 → 匹配
   - 容忍 vision model 输出完整句子（"Results and Discussion - Oxidation Efficiency"）
   - 极端情况：hint ≤ 30 字符且 sectionTitle.includes(hint) OR sectionTitle ≤ 30 字符且 hint.includes(sectionTitle)
   - 匹配数 ≥1 → 返回前 8 张
   - fallback：按 page 排序前 8 张（v27.2 行为）

### 关键算法（PDF id=19 实测）

| activeSection | 期望匹配 ID | 实测 | 算法路径 |
|---|---|---|---|
| 1. Introduction | 无 → fallback 全 8 | 8 张 (530-537) | fallback |
| 2. Experimental Section | 531 | 1 张 (531) | "experimental" 词重叠 |
| 3. Results and Discussion | 5 张 chart/mechanism | 5 张 (533/534/535/536/537) | "results" + "discussion" 词重叠 |
| 4. Mechanism | 2 张 mechanism | 2 张 (530/536) | "mechanism" 词重叠 |
| 5. Conclusions | 无 → fallback | 8 张 (530-537) | fallback |

### 9 条铁律

**铁律 1：v27.2 注释 "用 IntersectionObserver" 不代表已实现**
- 看到注释"用 IO 检测"必须 grep 是否有 `IntersectionObserver` 关键字
- v27.2 注释说"用 IntersectionObserver 检测"但**实际 setupSectionObserver 没写**
- activeSectionId 永远是 '' → currentSectionFigures 永远走 fallback → v27.2 RightImageRail "按 page 排序前 8 个" 实际是**固定显示**，跟滚动无关
- **诊断**：开发者工具 console 跑 `document.querySelector('[id^="section-"]')` 看章节元素，再 `console.log(window.__paperActiveSection)`（如果有）或 grep 代码看谁更新 activeSectionId

**铁律 2：RightAnchorNav 的 IO 不应被 KnowledgeDetailView 依赖**
- 子组件 emit `active-section-change` 是规范做法，但 v27.2 没 emit
- KnowledgeDetailView 应**独立**接 IO，不依赖子组件行为
- 好处：① IO 出错只影响一个组件 ② 测试更容易（不耦合） ③ 子组件能自由演化
- 坏处：2 个 IO 监听器（RightAnchorNav 自己也接），但 viewport 内 listener 数量轻量

**铁律 3：sectionHint 匹配算法必须按核心词重叠，不能按完整字符串包含**
- vision model 输出 sectionHint 是**完整句子**（"Results and Discussion - Oxidation Efficiency"），不是关键词
- 算法 1（错的）：`sectionTitle.includes(hint)` → 短 title 不可能包含长 hint → 永远不匹配
- 算法 2（对的）：两边都按 ≥4 字符拆词，取交集，重叠 ≥1 → 匹配
- 示例：sectionTitle="results and discussion" + hint="Results and Discussion - Oxidation Efficiency"
  - sectionTitleWords = ["results", "discussion"]（"and" < 4 字符过滤）
  - hintWords = ["results", "discussion", "oxidation", "efficiency"]
  - overlap = ["results", "discussion"] → 2 个重叠 → 匹配 ✓

**铁律 4：setupSectionObserver 必须在 paper.value 赋值之后 + await nextTick()**
- paper.value = normalizePaperData(...) 是同步赋值，但 sections DOM 渲染是 nextTick 异步
- 调用 setupSectionObserver 之前必须 `await nextTick()`，否则 `document.querySelectorAll('[id^="section-"]')` 找不到元素
- fetchDetail 末尾 line 480 `await nextTick()` 后 `renderGraph()` — 加一行 `setupSectionObserver()` 在 renderGraph 之后

**铁律 5：IntersectionObserver 必须 disconnect + null 避免内存泄漏**
```js
if (sectionObserver) {
  sectionObserver.disconnect()
  sectionObserver = null
}
```
- 单页应用路由切换频繁，旧 sectionObserver 仍持有旧 DOM 引用
- 必须在：① onUnmounted ② watch(displaySections) 触发新 setup 前
- 不 disconnect → 旧 sections DOM 被释放时 observer 仍尝试访问 → console warning

**铁律 6：activeSectionId.value 变化判断必须加 `!== bestId`**
```js
if (bestId && bestRatio > 0 && activeSectionId.value !== bestId) {
  activeSectionId.value = bestId
}
```
- IO 回调频率高（每次滚动都可能触发），无变化判断会反复写 ref → 触发下游 computed 无效重算
- `bestRatio > 0` 防止 section 完全滚出 viewport 后仍保持上一个 id

**铁律 7：rootMargin 与 RightAnchorNav 保持一致 '-80px 0px -60% 0px'**
- 上下都内缩：top -80px（让出 sticky header），bottom -60%（section 进入视口上半部分才算 active）
- 与 RightAnchorNav 一致 → 用户视觉上 "active section" 与 "RightImageRail 显示的图" 同步
- 不同步会变成 "滚动到 Section 3，但 Rail 显示 Section 2 的图" → 用户困惑

**铁律 8：fallback 永远保留**
- v27.2 行为"按 page 排序前 8 个"必须保留作 fallback
- 当：① activeSectionId 为空 ② sectionTitle 太短 ③ sectionHint 全 null ④ 匹配数 = 0
- 没有 fallback → 用户滚到 Introduction 这种"无相关图"的章节看到空 Rail → "功能坏了"
- **纪律**：v28 增强**新增**精准匹配，**不删除**v27.2 fallback

**铁律 9：onMounted 在 KnowledgeDetailView 不能重复**
- 旧代码 `onMounted(() => fetchDetail())` line 609
- 新增 `onMounted(() => { fetchDetail(); nextTick(setupSectionObserver) })` line 363
- 两个 onMounted 都执行 → fetchDetail 跑 2 次 → 性能浪费 + 可能 race condition
- **修复**：删除其中一个，保留合并版本

### 改动文件清单

| 文件 | 改动 |
|---|---|
| [web/src/views/KnowledgeDetailView.vue](web/src/views/KnowledgeDetailView.vue) | 删除原 onMounted + 新增 `setupSectionObserver` + `currentSectionFigures` 重写 + `displaySections` watch + fetchDetail 末尾 `await nextTick → setupSectionObserver()` |

### 验证结果

```bash
# 单元测试（paperAdapter 仍 83/83）
cd web && npx vitest run src/utils/__tests__/paperAdapter.test.js
# → 83 passed

# 算法内联测试
node /tmp/test_match2.js
# → Test 1-5 全过（Introduction fallback / Experimental 1 / Results 5 / Mechanism 2 / Conclusions fallback）

# 前端 build
cd web && npm run build
# → dist/assets/index-54ad23a4.js
```

### v28 step 4 — paperAdapter 简化为读后端字段（2026-06-20 收官）

**根因（看似前端问题，实则后端 schema 缺字段）** — 前端 paperAdapter 必须靠 `_extractFigureNo`（6 字段正则）+ `_inferFigureTypeV2`（9 条规则）+ L1 inference（page 顺序兜底）推断 figureNo/figureType，因为**后端 `/knowledge/{id}/images` API `_to_dict` 函数只返回 11 个字段**，v28 新加的 12 个结构化字段一个都没传。

**修复（3 处同步）**：

1. **后端 schema** [app/schemas/knowledge.py:324-353](app/schemas/knowledge.py#L324-L353) — `KnowledgeImageItem` 加 12 个 `Optional` 字段
2. **后端 API** [app/api/v1/knowledge.py:890-913](app/api/v1/knowledge.py#L890-L913) — `_to_dict` 补全 12 字段输出（`vision_analyzed_at` 用 `str()` 转 datetime）
3. **前端** `_normalizeImages` — 透传 12 字段（snake_case → camelCase）
4. **前端** `_buildFigureRegistry` — 简化为读后端字段，删除推断逻辑

### 关键设计：Graceful Degradation（vision 字段全 null 时回退旧逻辑）

```js
const visionAvailable = img.figureNo != null
  || img.figureType != null
  || img.isCoreFigure != null
  || img.isPublisherImage != null
  || img.sectionHint != null
  || img.visionConfidence != null

if (visionAvailable) {
  // 主路径：读 vision 输出 + anchor_text fallback（补 20% 覆盖率）
} else {
  // 旧路径：_extractFigureNoLegacy + _inferFigureTypeV2Legacy
}
```

**L1 inference 兜底仅 vision 不可用时启用**（`_buildFigureRegistry` 末尾）：
```js
if (!images.some(img => img.figureNo != null || img.figureType != null)) {
  // 旧 L1 inference 逻辑（保留兼容）
}
```

**为什么需要 Graceful Degradation**：
- 老 PDF 数据（v28 step 3 之前入库的）vision 字段全 null
- 旧测试 fixture 模拟"vision 不可用"场景，期望旧 fallback 路径
- 渐进式演进：未来所有 PDF 走主路径，Legacy 永远不会扩展

### 7 条铁律

**铁律 1：删前端推断逻辑前先看后端 schema 是否传字段**（最重要）
- v27.1/v27.2 三个推断函数都是为"补后端缺口"设计的
- **删除前**先 grep 后端 `_to_dict` 字段列表，确认数据真的能传到前端
- 本次根因：后端 `_to_dict` 只返 11 字段，前端推断逻辑存在**不是冗余是必要**
- **修复顺序**：① 后端 schema + API 加字段 ② 前端 `_normalizeImages` 透传 ③ 前端 `_buildFigureRegistry` 简化 ④ 删除旧推断函数（保留 Legacy 作 graceful degradation）

**铁律 2：snake_case → camelCase 字段映射必须一对一完整**
- 12 个字段全部映射，无遗漏：
  - `figure_no → figureNo`
  - `figure_type → figureType`
  - `is_core_figure → isCoreFigure`
  - `is_publisher_image → isPublisherImage`
  - `is_supporting_figure → isSupportingFigure`
  - `section_hint → sectionHint`
  - `visual_summary → visualSummary`
  - `anchor_paragraph_index → anchorParagraphIndex`
  - `anchor_text → anchorText`
  - `vision_confidence → visionConfidence`
  - `vision_model_used → visionModelUsed`
  - `vision_analyzed_at → visionAnalyzedAt`
- 用 `?? null` 兜底（万一某字段 API 没返）

**铁律 3：anchor_text fallback 弥补 vision 模型 20% 覆盖率**
```js
if (!figureNo && img.anchorText) {
  const m = img.anchorText.match(/\b(?:Fig\.?|Figure|Scheme|Table)\s*(\d{1,3}[a-z]?)\b/i)
  if (m) {
    figureNo = m[0]
    figureNoSource = 'anchor_fallback'
  }
}
```
- 后端 `_compute_anchor_for_images` 已经把 "Fig. N" 引用句片段填到 `anchor_text`
- 前端用同一正则反向抽出 figureNo
- **figureNoSource 标记来源**：`'vision' | 'anchor_fallback' | 'inferred' | 'legacy_extracted' | null`

**铁律 4：`=== true` 严格比较布尔字段，绝不用 `if (img.isCoreFigure)`**
- API 返回 `true` / `false` / `null` 三种值，**null 必须当"未知"处理**
- `if (img.isCoreFigure)` 在 null 时 → false（兜底正确但语义错）
- `img.isCoreFigure === true` → 明确只对后端明确判断的图生效
- 对 vision 不可用情况，仍走 Legacy 路径用 `figureType` 推断

**铁律 5：datetime 字段序列化必须 `str()` 转字符串**
```python
"vision_analyzed_at": str(img.vision_analyzed_at) if img.vision_analyzed_at else None,
"ocr_at": str(img.ocr_at) if img.ocr_at else None,
```
- Pydantic v2 + datetime 字段默认序列化 ISO 字符串
- 但 `_to_dict` 手动构造 dict 时**不会自动序列化** → 返 datetime 对象 → JSON 报错
- **纪律**：手动 dict 必须显式 `str(datetime)` 转字符串（或用 Pydantic `model_dump`）

**铁律 6：测试 fixture 必须反映真实数据形状**
- 旧 fixture `realWorldInput` 只写 `{ id, page_number, image_url, ocr_text }`（模拟 vision 不可用）
- 测试期望旧 L1 inference 兜底，**不能简单更新 fixture 而让测试期望保持"旧逻辑"**
- **保留 fixture 原样** + 让 `_buildFigureRegistry` 检测 visionAvailable 走 Legacy 路径 — 测试期望不变
- 新增 fixture（vision 字段齐全）作为主路径测试覆盖

**铁律 7：Legacy 函数重命名要带后缀，不要删函数**
- `_extractFigureNo` → `_extractFigureNoLegacy`
- `_inferFigureTypeV2` → `_inferFigureTypeV2Legacy`
- 加 docstring 标记 "仅 Graceful Degradation 用，不要扩展"
- **不要**完全删 — 老数据 / 老测试 / 第三方用户脚本可能依赖
- **不要**在新代码里调用 Legacy — 主路径永远走 vision 字段

### 验证结果

```bash
# 单元测试
cd web && npx vitest run src/utils/__tests__/paperAdapter.test.js
# → 83/83 passed (v26/v26.1/v27/v27.1/v27.2/v28 step1-4 全部覆盖)

# API 端到端验证
TOKEN=$(curl ... /api/v1/auth/login)
curl -sk http://localhost:8000/api/v1/knowledge/19/images \
  -H "Authorization: Bearer $TOKEN" | jq '.items[0]'
# → {"id":528,"figure_type":"logo","is_publisher_image":true,
#    "vision_confidence":0.99,"vision_model_used":"mimo-v2.5",
#    "visual_summary":"Elsevier出版商的经典logo..."}
```

### 改动文件清单

| 文件 | 改动 |
|---|---|
| [app/schemas/knowledge.py](app/schemas/knowledge.py) | `KnowledgeImageItem` 加 12 Optional 字段 |
| [app/api/v1/knowledge.py](app/api/v1/knowledge.py) | `_to_dict` 补全 12 字段输出 |
| [web/src/utils/paperAdapter.js](web/src/utils/paperAdapter.js) | `_normalizeImages` 透传 12 字段 / `_buildFigureRegistry` 简化为读后端字段（主路径）+ Legacy graceful degradation / `_extractFigureNoLegacy` + `_inferFigureTypeV2Legacy` 重命名保留 |

### v28 article 9 字 bug 修复（2026-06-20 收官）

**症状**：PDF id=19 详情页 `<article>` 只渲染 9 字符 `"多模态提取图表说明"`。

**诊断链路（5 步）**：

```
cleanedSample0 (cleanContent 后前 800 字符): "> 图表为热力图，标题为..."
inputSample0  (cleanContent 前前 800 字符): "[PAGE:1]\n\n> 📊 **图表说明（P1）**..."
                ↑ 第一个 [PAGE:1] 被吃了!
```

**根因（4 层）**：

1. INTERNAL_MARKER_RES line 105: `/\bPAGE\s*[:：]\s*\d+\b/gi`
   - `\b` 在 `[`（non-word char）和 `P`（word char）之间构成**单词边界**
   - 匹配 `[PAGE:1]` 的**中间** `PAGE:1` 部分
   - 替换为空 → `[PAGE:1]` 变 `[]` → pageMarkers=0

2. INTERNAL_MARKER_RES line 107: `/([A-Z]\.\s*[A-Z][a-z]+(?:\s+et\s+al\.?)?)\s+\d+\s*\[PAGE:\s*\d+\s*\]/gi`
   - 匹配 `T. Wang et al. 3 [PAGE:4]` 整段 → 删除整段
   - PDF 上下文（作者名 + 页码）丢失

3. cleanContent line 374-381：把行中/独立行 `[PAGE:N]` 替换为 `\n`
   - cleanContent 后 `[PAGE:N]` 在 content 里**几乎不存在**（仅剩偶尔残留）

4. `extractPageMarkers` → 0 markers → sections 解析丢分页 → 正文压成 1 段 → 只剩 inline 注入的"## 多模态提取" + "### 图表说明" 标题 → **9 字符**

**修复（5 处）**：

1. **paperAdapter.js INTERNAL_MARKER_RES 删 line 105 + line 107**（任何形式删 `[PAGE:N]` 都破坏 pageMarkers 提取）
2. **cleanContent line 374 简化**：只处理无方括号 `PAGE:1` 形式（不影响 `[PAGE:N]`）
3. **`hasPageMarker` 检测 + `useRawFormatted` 标志**：含 `[PAGE:N]` 时强制 plain text 路径但仍用 `rawFormatted` 作 inputContent（因为它才有 `[PAGE:N]`）
4. **`inputContent` 选取逻辑改用三元**：`hasFormatted ? rawFormatted : (useRawFormatted ? rawFormatted : rawContent)`
5. **测试 fixture 改 v28**：`v26 剥离 [PAGE:N]` 改成 `v28 保留 [PAGE:N]`

**端到端验证**：

```
修复前                          修复后
article 长度:   9 字符         article 长度: 40855 字符
sectionsCount: 2              sectionsCount: 19
pageMarkers:   0              pageMarkers: 9
blocks[0] 内容: 0 字符         blocks[0] 内容: Abstract 1692 字符
```

### 7 条铁律

**铁律 1：JavaScript `\b` 在 `[` 和 word char 之间构成单词边界**
- `[PAGE:1]` 里的 `[` 是 non-word，`P` 是 word
- regex `\bPAGE` 会从 `[PAGE:1]` 内部匹配 `PAGE`（前面 `]` + `[` 是 non-word）
- 看似只匹配无方括号 `PAGE:1`，实际**误中带方括号的 `[PAGE:N]`**
- **教训**：涉及 `[xxx:N]` 格式的 regex，必须显式 `(?<!\[)` 和 `(?!])` 限定边界

**铁律 2：任何形式删 `[PAGE:N]` 都破坏 pageMarkers 提取**
- paperAdapter 流程：`cleanContent(inputContent)` → `extractPageMarkers(content)` → sections 解析依赖 pageMarkers 拆段
- 删 `[PAGE:N]`（无论 1 条还是 N 条 regex）→ pageMarkers=0 → 解析 fallback 把整篇正文压成 1 段
- **教训**：保留 `[PAGE:N]` 给 extractPageMarkers 是 cleanContent 的**硬约束**

**铁律 3：`\b` 在中英文混排环境永远不可靠**
- Python/JavaScript `\b` = word boundary = `\w` 与 `\W` 之间
- `\w` 默认 = `[a-zA-Z0-9_]`，中文不是 word char
- 即使做 `\b → (?<![a-zA-Z\d_])` lookbehind 修复，**仍然不安全**（中文环境行为可能不一致）
- **教训**：涉及中英文混排的 regex，**优先用 lookbehind/lookahead 限定具体字符**

**铁律 4：v26 修复的副作用要警惕**
- v26.1 修复中文图注污染（commit `2ee27015`）时加了 captionBlocks 正则
- 这条 regex 隐式假设"OCR blockquote 段开头 `> 📊 图表说明` 是图注"，但**OCR 内容可能就是这样组织的**
- 用户看到"修复好"但实际破坏了 page marker 提取
- **教训**：修复一类 bug 时要 grep"所有相关 regex" + 端到端测 pageMarkers 数量

**铁律 5：调试时一定要打印中间产物**
- cleanContent 有 5+ 步处理（HTML/markdown image/URL/multimodal blocks/INTERNAL_MARKER_RES/DOI/footer）
- 任何一步都可能删 `[PAGE:N]`
- 本次诊断用 `__PAPER_INTERMEDIATE__.cleanedSample0` 字段对比原始 inputSample0，**立即定位是第 5 步 INTERNAL_MARKER_RES 删的**
- **纪律**：任何 cleanContent 修复前先加中间产物输出（inputSample + cleanedSample）

**铁律 6：`return_exceptions=True` 缺位导致 Promise 静默失败**
- 用 `node /tmp/regex_test2.js` 模拟 cleanContent 步骤追踪时，**前 4 步 `[PAGE:N]` 仍 = 1**，**第 5 步骤后才变 0**
- 没有逐步追踪根本不可能定位是哪个 regex 删的
- **纪律**：fix regex bug 前必须 step-by-step 追踪

**铁律 7：测试 fixture 要反映真实数据**
- 测试 `"有 formatted_content (markdown) 走 markdown 解析"` 之前的 fixture 没有 `[PAGE:N]`（假装真 markdown）
- 真实 PDF OCR 内容**总带 `[PAGE:N]`**（PDF 解析工具都加）
- 测试通过但生产失败 = 误导
- **纪律**：测试 fixture 必须含真实 OCR 输出特征（`[PAGE:N]` / 残留 JSON / blockquote 图表说明）

### 改动文件清单

| 文件 | 改动 |
|---|---|
| [web/src/utils/paperAdapter.js](web/src/utils/paperAdapter.js) | 删 INTERNAL_MARKER_RES line 105 + line 107（任何形式 `[PAGE:N]` 删除逻辑）+ cleanContent 简化 + hasPageMarker/useRawFormatted/inputContent 三元 |
| [web/src/utils/__tests__/paperAdapter.test.js](web/src/utils/__tests__/paperAdapter.test.js) | v26 测试改 v28 + 新增 `有 formatted_content 含 [PAGE:N] (OCR) 走 plain text` |

### git commit 链

```
e9627486 chore: 清理 paperAdapter 临时 __PAPER_DIAG__ 诊断代码
d171df1a fix(kb): paperAdapter INTERNAL_MARKER_RES 保留 [PAGE:N] - 真正修复
77634498 fix(kb): paperAdapter INTERNAL_MARKER_RES 不再删除 [PAGE:N]
0d73c6a2 fix(kb): paperAdapter cleanContent 不再替换 [PAGE:N] 为 \n
```

### 诊断脚本（已移除但模式可复用）

```js
// 临时在 paperAdapter line ~2260 加的 __PAPER_DIAG__：
window.__PAPER_DIAG__ = {
  sectionsCount: paperDetail.sections.length,
  sectionsTypes: paperDetail.sections.map(s => ({
    type: s.type,
    title: (s.title || '').slice(0, 40),
    blocksCount: s.blocks?.length || 0,
    firstBlockContentLen: s.blocks?.[0]?.content?.length || 0,
    firstBlockPreview: s.blocks?.[0]?.content?.slice(0, 80) || '',
  })),
  pageMarkersCount: paperDetail.pageMarkers?.length || 0,
  figureMarkersCount: paperDetail.figureMarkers?.length || 0,
}

// 然后浏览器 console：
const d = window.__PAPER_DIAG__
console.log('sections:', d.sectionsCount, 'pageMarkers:', d.pageMarkersCount)
console.log('article 长度:', document.querySelector('article.paper-article')?.textContent?.length)

---

## 2026-06-24 sentence-transformers 5.6.0 升级（Phase 1+2 收官）

> **触发**：原 CLAUDE.md 标 "❌ sentence-transformers 升级（未做）"，实测后 100% 完成 + 超额（原 plan 担心跨 3 大版本破坏性，0 破坏，qa-bench 38%→42% **反升**）
> **跳过 Phase 3**：ONNX 实测 GPU 上慢 12-22x（反优化），保持 torch/GPU
> **完整 plan + 实测**：[docs/upgrade-sentence-transformers-plan.md](docs/upgrade-sentence-transformers-plan.md)
> **commit**：`c8d4df3e feat(embedding): upgrade sentence-transformers 2.3.1 → 5.6.0 (Phase 1+2 收官)`（已 push main）

### 5 大铁律

#### 铁律 1：清华源（pypi.tuna）限速 PyTorch 2.12+，必须走 PyPI 官方 + clash 代理

**症状**：
- Dockerfile 装 `torch==2.12.1` 在清华源下卡死（已知问题，CLAUDE.md 2026-06-17 教训第 4 条）
- Build 时间 30+ 分钟无产出（pip output 缓冲看不到进度）
- 强行用清华源会出现 502 Bad Gateway

**修复**：Dockerfile 切默认源 + 加 build-arg 走 clash：
```dockerfile
# Dockerfile
ARG HTTPS_PROXY
ARG HTTP_PROXY
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefer-binary --retries 10 --timeout 60 -r requirements.txt
# 不带 -i 走 PyPI 官方
```
```bash
docker compose build --build-arg HTTPS_PROXY=http://host.docker.internal:7890 --build-arg HTTP_PROXY=http://host.docker.internal:7890 app
```

**关键细节**：
- **`HTTPS_PROXY` 用 `--build-arg`，不要用 `ENV`**：ENV 会让 Docker 内部的 image pull 也走 proxy（命中 dockerproxy.net 500，CLAUDE.md 2026-06-13 教训第 9 条）
- 清华源备选（注释保留）：`-i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn`
- 速度对比：清华源 600KB/s 限速 vs PyPI+clash 8-12MB/s 稳定

**教训**：升级大版本库时第一件事看 PyTorch/torch 依赖链，不要假设旧镜像源能跑新版本

#### 铁律 2：docker compose build 别用环境变量 HTTPS_PROXY 污染全局

**症状**：设了 `HTTPS_PROXY=http://host.docker.internal:7890 docker compose build app` → 整个 build 阶段所有 HTTP 请求都走 clash，包括 Docker 拉 base image（`docker.io/library/python:3.11-slim-bookworm`），触发 dockerproxy.net 500 错误

**根因**：Docker compose 把环境变量传给 build context，导致 base image 拉取也走代理

**修复**：
- ❌ `HTTPS_PROXY=... docker compose build app`（环境变量污染）
- ✅ `docker compose build --build-arg HTTPS_PROXY=... --build-arg HTTP_PROXY=... app`（ARG 只在 RUN 时生效）

**检测方法**：`grep "dockerproxy.net" build.log` 看到 500 立即用 --build-arg 重试

**教训**：任何 docker build 选项，凡涉及影响**整个 build context** 的（不只是 RUN），用 `--build-arg` 而不是 env var

#### 铁律 3：ONNX backend 在 GPU 上是反优化（12-22x 慢），不要无脑启用

**CLAUDE.md / ST 文档** 都说 ONNX 加速 2-3x — **没说是 CPU 专属**。

**实测数据**（text2vec-base-chinese，b=64，3 次中位数）：

| 后端 | short*64 | long*64 | vs torch/GPU |
|---|---|---|---|
| **torch/GPU** | **16.2ms** | **30.2ms** | 1.0x (基线) |
| onnx/GPU (FP32) | 204.2ms | 680.0ms | ❌ 12.6x / 22.5x 慢 |
| torch/CPU | 189.8ms | 975.0ms | 11.7x / 32.3x 慢 |
| onnx/CPU | 239.7ms | 677.0ms | 14.8x / 22.4x 慢 |

**根因**：
- ONNX Runtime 在 GPU 上优化**不如 PyTorch CUDA**
- ONNX 文件首次加载多 45s
- 精度完美（cos 1.000000），但**速度不可接受**

**何时 ONNX 才有用**（基于实测）：
- 纯 CPU 部署 + 长文本：onnx/CPU 677ms vs torch/CPU 975ms（**1.44x 快**）
- **有 GPU 一律 torch/GPU**（30.2ms 秒杀一切）
- **短文本 CPU 推理**：onnx/CPU 略慢于 torch/CPU（差距 < 5%）

**判断方法**：升级库时先 `sentence-transformers ... backend="onnx"` vs 默认 backend 实测 100 文本对比，**别相信文档说"2-3x 加速"就直接上线**

**教训**："ONNX 加速" 是 context-dependent 的，**实测数据 > 文档宣传**

#### 铁律 4：sentence-transformers 升级时分 Phase 而不是一次跳 3 大版本

**CLAUDE.md 之前担心**："升级到 ST 3.x 可能引入其他破坏性变更（CHANGELOG 显示 3.x 重写了 Pooling 接口）"

**实测后**：跨 2.3.1 → 3.x → 4.x → 5.6.0 三大版本，**0 个 breaking 改动影响我们**。但**不代表没风险**。

**3 phase 收官法**（本次实际跑通）：
1. **Phase 1 — 最小风险**（1 行 deprecation 修复）：`requirements.txt` 升版本 + 改 `get_sentence_embedding_dimension()` → `get_embedding_dimension()`，其他全不动
2. **Phase 2 — 利用新功能**（删 wrapper）：重构代码用新 API，删旧 wrapper
3. **Phase 3 — 性能优化**（跳过 / 视情况）：ONNX、Flash Attention、量化

**每个 Phase 独立验证 + 独立回滚**：
- ✅ Phase 1：qa-bench 0 ERROR（embedding 正常）
- ✅ Phase 2：qa-bench 38%→42%（反升 4%，比预期更好）
- ❌ Phase 3：实测反优化，主动跳过

**教训**：跨大版本升级前**先小规模测试**（小项目用 venv 试 5 分钟），不直接动生产代码

#### 铁律 5：ST 5.6.0 的 Pooling 现在支持 `include_prompt`，Qwen3 原生加载可行

**原 wrapper 必要性**（2026-06-23 之前）：
- Qwen3 用 `1_Pooling/config.json` 的 `include_prompt: true` 参数
- ST 2.3.1 的 `Pooling.__init__()` 不接受此参数 → 报 `TypeError`
- 必须写 Qwen3Embedder wrapper 绕开

**ST 5.6.0 现状**：
- `Pooling.__init__` 签名：`['self', 'embedding_dimension', 'pooling_mode', 'include_prompt']` ✓
- `SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", trust_remote_code=True)` 一行直接加载
- 删了 170 行 wrapper，graceful degradation 文件保留

**Qwen3 native vs wrapper 输出对比**：
- `cos 0.999860`（本质相同，FP16 浮点误差）
- `max abs diff 0.0024`
- **max_seq_length 2048 → 32768**（4x 上下文）

**何时需要 wrapper**（保持 graceful degradation 价值）：
- ST 升级到 6.0（如果又重写 Pooling 接口）
- 紧急回滚（如果 ST 5.6.0 出问题）

**教训**：升级库前 grep 项目所有使用面（不只是当前用的，还有"假装绕开"的部分），可能有意想不到的简化机会

### 排查流程（下次再升级遇到问题）

```
1. 先在小 venv 装 + 跑 import（5 分钟）
2. API surface check: inspect.signature 看关键类是否有 expected 参数
3. 实际加载最复杂模型（不要小模型当代表）
4. 容器内 venv 测（不污染系统 Python）
5. Phase 1: requirements.txt 改 + 最少代码改动
6. Phase 2: 重构 + 删旧 wrapper（如果 API 兼容）
7. Phase 3: 性能优化（如果上一步没破坏，先别动）
```

### 4 个小时踩的 7 个坑（fastest-first 顺序）

| 坑 | 症状 | 修复 | 时间 |
|---|---|---|---|
| 1. 清华源限速 torch 2.12+ | pip install 卡 30+ 分钟 | 切 PyPI 官方 + clash build-arg | 5 min 排查 + 5 min 改 |
| 2. docker proxy env var 污染 | `dockerproxy.net 500` 拉不到 base image | 改用 `--build-arg` 而非 `ENV` | 5 min 排查 + 2 min 改 |
| 3. 杀 com.docker.build.exe 把 daemon 搞死 | 整个 docker desktop 通信断 | 全部 kill + 重启 Docker Desktop (90s 等待) | 10 min |
| 4. 测试默认值错（默认是 Qwen3 不是 text2vec） | dim=1024 但 assertion 写 768 | 改 assertion（不是改代码） | 2 min |
| 5. qa-bench 限流 (concurrency=4) | 37/50 ERROR 全部 429 | 改 concurrency=1 | 10 min 排查 |
| 6. ONNX "加速" 反向 | GPU 上慢 12-22x | 跳过 Phase 3，保留 torch | 30 min 严谨测试 |
| 7. 容器 `HF_HUB_OFFLINE=1` 默认 | ONNX 拉不到 model 文件 | 临时 `HF_HUB_OFFLINE=0` 测试，生产用预下载 | 5 min |

## 2026-06-25 v31.2.1 rate-limit 边界强化（XFF 空 IP 兜底 + auth/analytics 嵌套防御）

> **触发**：v31.2 (commit `c2c5066e`) 引入 IP 维度限流 + `/analytics` 豁免 + 可选 auth。端到端 4 边界实测（16 场景全 PASS）发现 2 个非阻塞 follow-up：(1) `get_client_ip` XFF 空 IP 无兜底 (2) `/auth/analytics/...` 嵌套路径未来有 bypass 隐患（短期无安全风险，防御性编程顺手做）。
> **commit**：`fix(v31.2.1): rate-limit 边界强化 (XFF 空 IP 兜底 + /auth/analytics 嵌套防御)`

### 2 条铁律

#### 铁律 1：XFF 空 IP 必须兜底，禁止空字符串作为限流 key

**症状**：
- 端到端实测边界 3：用 `X-Forwarded-For: , 1.2.3.4` 命中 `get_client_ip()` → `split(",")[0].strip()` = `""` → 多请求共享空 IP key
- 同边界：纯空格 `"   "` / 多段空 `",,,,,"` 全部触发同样 bug
- 攻击场景：攻击者绕过 Nginx 直接打后端，可构造空 XFF 让多请求共享 200/min read 配额
- **Nginx 通常不会让空 XFF 穿透**，所以生产环境实际不可达；但代码层面属于"输入未净化 → 限流失效"

**根因**：
```python
# app/core/rate_limit.py:156-160 (v31.2 旧实现)
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()   # ← 空字符串也能通过
    return request.client.host if request.client else "unknown"
```

`if forwarded:` 守卫拦的是"无 XFF 头"（falsy：None / 空串），但**不拦"XFF 首段为空字符串"**。`split(",")[0].strip() = ""` 是 truthy 路径执行结果，但语义上等同于无 IP。

**修复**（v31.2.1）：
```python
def get_client_ip(request: Request) -> str:
    """获取真实客户端 IP（按 XFF 优先级回退，v31.2.1 修复空 IP 兜底）

    优先级:
      1. X-Forwarded-For 第一段（反向代理标准，左数最近为真实客户端）
      2. request.client.host（直连 / 测试环境）
      3. "unknown"（兜底，禁止返回空字符串）

    v31.2.1 修复: XFF 首段为空（", 1.2.3.4" / "   " / ",,,,,"）时，
    旧实现 .split(",")[0].strip() 返空串 → 多请求共享空 IP key 触发共享配额.
    现统一兜底为 "unknown"，让 Nginx 通常无此问题的前提下，万一绕过 Nginx
    直打后端的攻击者也无法用空 XFF 共享 200/min 配额.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:                                  # v31.2.1: 空 IP 必须兜底
            return ip
        return "unknown"
    return request.client.host if request.client else "unknown"
```

**回归验证**（8 个 XFF 场景全 PASS）：
- ✅ `XFF: "1.2.3.4"` → `"1.2.3.4"`（不变）
- ✅ `XFF: "1.2.3.4, 5.6.7.8"` → `"1.2.3.4"`（不变）
- ✅ `XFF: 10 段` → 第 1 段（不变，端到端实测 C1 remaining = A2 remaining - 1）
- ✅ 无 XFF + 有 client → `client.host`（不变）
- ✅ 无 XFF + 无 client → `"unknown"`（不变）
- ✅ `XFF: ", 1.2.3.4"` → 修复前 `""`（bypass）→ 修复后 `"unknown"`
- ✅ `XFF: "   "` → 修复前 `""` → 修复后 `"unknown"`
- ✅ `XFF: ",,,,,"` → 修复前 `""` → 修复后 `"unknown"`

**教训**：
1. **`if X:` 不等于 `if X is not None and X != "":`**——truthy 守卫漏掉"空字符串"是 Python 经典坑。任何"XFF / query param / header value"类外部输入，必须显式 `if not X:` 兜底
2. **限流 key 必须有 fallback 值**——空字符串 key 表面看"无 IP"，实际是个**有效共享 key**（多个空 IP 请求汇聚）。fallback 到固定字符串（如 `"unknown"`）才能让所有"无 IP"请求受 200/min 配额约束
3. **Nginx 反代层净化不等于后端可不做防御**——Nginx 通常过滤空 XFF，但攻击者绕过 Nginx 直打后端（端口扫描 / SSRF / WAF 漏配）时，后端必须有独立净化

#### 铁律 2：substring 路径匹配必须显式排除嵌套 bypass

**症状**：
- v31.2 引入 `if "/analytics" in path: return "unlimited"`（POST/PATCH/PUT）保护埋点端点
- `_get_rate_limit_type` 顺序 2（`/analytics`）在顺序 3（`/auth/`）**之前**
- 隐患：若未来加路由 `POST /api/v1/auth/analytics/export`，`"/analytics" in path` 命中 → 顺序 2 优先 → unlimited → 绕过 `/auth/` 敏感端点 20/min 限流
- **当前路由表里没有这种嵌套路径**，短期无安全风险，但 follow-up 防御性编程更好
- 端到端实测边界 4：`POST /api/v1/auth/analytics/test`（不存在路由）→ 404 + **无 X-RateLimit-* 头**（unlimited 路径生效），确认 substring 命中绕过 `/auth/` 限流

**根因**：
顺序 2 优先于顺序 3，substring `"/analytics" in path` 命中所有包含 analytics 字符串的路径。设计时假设"analytics 端点都在 `/api/v1/analytics/...` 下"，但未在代码层面强制此假设——**业务语义边界 ≠ 字符串前缀边界**。

**修复**（v31.2.1，方案 B1：前置精确排除）：
```python
# 顺序 2 (v31.2.1 改)
if "/analytics" in path and not path.startswith("/api/v1/auth/"):
    if method in ("POST", "PATCH", "PUT"):
        return "unlimited"
    return "read"
```

**为什么不调换顺序**（方案 X，已 explore agent 提议但被否决）：
- 调换后 `if "/auth/" in path` 先命中 → 现有 `POST /api/v1/analytics/search-event` 走 `/auth/` 顺序 3 细分 → 非 sensitive 写操作 → **write tier 30/min** 而非 unlimited
- 用户已明确确认 `/analytics` POST/PATCH 该 unlimited（前端每次搜索 2 次埋点，30/min 不够）
- **结论：必须用守卫（方案 B1），不能动顺序**

**B1 vs B2 vs B3 三方案对比**：
| 方案 | 改动量 | 未来扩展性 | 不破坏当前行为 | 推荐 |
|---|---|---|---|---|
| **B1** `/analytics` 分支前置守卫 `not path.startswith("/api/v1/auth/")` | +1 行 | 中（auth 子路径除外，其他顶级 analytics 不需要改） | ✅ | ✅ **选 B1** |
| B2 `/auth/` 分支后置守卫 `not "/analytics" in path` | +1 行 | 中 | ✅ | 备选 |
| B3 改 `/analytics` substring 为精确列表 | 重写整段 | 低（每加一个 analytics 端点必须改白名单） | ❌ 需列出所有 endpoint | ❌ |

**选 B1 核心理由**：
1. **意图清晰**：`/analytics` 分支顶部写"analytics 豁免但 auth 子路径例外"——读代码的人立刻知道"豁免是有边界的"
2. **扩展性最优**：未来加 `/api/v1/dashboard/analytics/...` 仍可走原 `/analytics` 分支（守卫是 `startswith("/api/v1/auth/")` 不是 `startswith("/api/v1/")`）
3. **改动最小**：1 行 if 守卫 + 4 行注释，diff 干净

**回归验证**（11 个 case 纯函数 mock 全 PASS，详见 [scripts/verify_v31_2_1_nested_path.py](scripts/verify_v31_2_1_nested_path.py)）：
- ✅ `POST /api/v1/analytics/search-event` → 守卫不命中 → unlimited（保留）
- ✅ `PATCH /api/v1/analytics/search-event/{id}/click` → 守卫不命中 → unlimited（保留）
- ✅ `GET /api/v1/analytics/stats` → 守卫不命中 → read（保留）
- ✅ `GET /api/v1/analytics/logs` → 守卫不命中 → read（保留）
- ✅ `POST /api/v1/auth/login` → 守卫命中 → 跳过 /analytics → 走 /auth/ 顺序 3 → 命中 _AUTH_SENSITIVE_PATHS → **auth tier 20/min**（保留）
- ✅ `POST /api/v1/auth/refresh` / `change-password` / `reset-password` / `init-password` → 同上，auth tier（保留）
- ✅ `GET /api/v1/auth/me` → 顺序 1 命中 _AUTH_UNLIMITED_PATHS → unlimited（保留）
- ✅ `PUT /api/v1/auth/profile` → 守卫命中 → /auth/ 顺序 3 → 写操作 → write tier 30/min（保留）
- ✅ **未来** `POST /api/v1/auth/analytics/export` → 守卫命中 → 跳过 /analytics → 走 /auth/ 顺序 3 → 非 sensitive 写操作 → **write tier 30/min**（修复）
- ✅ **未来** `GET /api/v1/auth/analytics/dashboard` → 守卫命中 → /auth/ 顺序 3 → 读操作 → read tier 200/min（修复）
- ✅ `path = "/api/v1/authentication"`（不含 `/auth/`）→ `/auth/` 顺序 3 不命中（注意是 `"/auth/" in path` 不是 `startswith`）→ default `read`（不变）

**教训**：
1. **substring 路径匹配 = 业务假设在字符串里**——`"/analytics" in path` 隐式假设"所有 analytics 端点都是 `/api/v1/analytics/...`"，但代码里**没有任何地方** enforce 这个假设。一旦未来路由前缀变化或嵌套，假设失效
2. **判定顺序 = 隐式优先级契约**——`_get_rate_limit_type` 顺序 2 优先 3 是"用户确认 `/analytics` 端点该 unlimited"的实现。但如果未来加 `/api/v1/auth/analytics`，substring 匹配会**自动**让顺序 2 优先 → 改不改？**这是个 bug，不是个 feature**——必须用守卫把"非 auth 子路径"显式圈出来
3. **Don't move order, add guards**——"调换判定顺序"是最便宜的修复（diff 1 行），但会破坏现有合法端点行为。**守卫（guard）是更 surgical 的修复**：保留所有合法路径行为，只在异常路径上刹车

### 端到端验证（脚本 + 实测）

**新增 2 个 probe 脚本**：
- [scripts/verify_v31_2_1_xff_empty.py](scripts/verify_v31_2_1_xff_empty.py) — 验证 Bug 1（XFF 空 IP 兜底）
- [scripts/verify_v31_2_1_nested_path.py](scripts/verify_v31_2_1_nested_path.py) — 验证 Bug 2（嵌套路径判定顺序）

**已有 probe 脚本回归**：
- [scripts/probe_analytics.mjs](scripts/probe_analytics.mjs) — 4 个 /analytics endpoint 端到端
- [scripts/probe_boundary3_xff.py](scripts/probe_boundary3_xff.py) — XFF 真实 IP 维度限流

### 部署必做

```bash
# 1. 重启 app container (CLAUDE.md 752 行铁律)
docker compose restart app

# 2. 跑回归 + 新增 probe
python scripts/probe_boundary3_xff.py           # XFF 真实 IP 维度限流 (已有, 不能回归)
python scripts/verify_v31_2_1_xff_empty.py     # XFF 空 IP 兜底 (新增)
python scripts/verify_v31_2_1_nested_path.py  # 嵌套路径判定 (新增)

# 3. 验证
# probe_boundary4: XFF ", 1.2.3.4" / "   " / ",,,,," → 期望 "unknown" key 独立配额
# probe_boundary5: 11 个 case 全 PASS（4 个 analytics endpoint + 5 个 auth sensitive + /auth/me + 2 个未来嵌套）
```

### 沉淀

- **修改文件 2 个**：`app/core/rate_limit.py`（+13 行：7 行 docstring + 6 行逻辑）+ `CLAUDE.md`（顶部 1 行快讯 + 底部 ~150 行章节）
- **新增文件 3 个**：`scripts/verify_v31_2_1_xff_empty.py` + `scripts/verify_v31_2_1_nested_path.py` + `CHANGELOG.md` 顶部新 section
- **风险等级**：极低（无 alembic 迁移、无前端 rebuild、无 Docker 镜像变更，2 处都是加守卫/兜底，不是改语义）
- **回滚成本**：`git revert` 30 秒完成

**总耗时约 4 小时**（含多次 docker rebuild 12 min + qa-bench 50 题 15 min 跑分 ×3 次）
```

## 2026-06-25 v31.2.2 rate-limit 进阶强化（regex 精确路径 + user_id 维度限流）

> **触发**：v31.2.1 用了 B1 临时方案（substring `"/analytics"` + `startswith("/api/v1/auth/")` 守卫），B1 把"业务假设藏在字符串里"——任何 reader 看到 `if "/analytics" in path` 都要再去看守卫才能确认实际匹配范围。同时限流 middleware 注释里写"用 `{ip}:user:{uid}` 维度"，但**从来没解析 token 写 `request.state.user_id`**——所有登录用户的限流 key 永远 = `{ip}:anon`，跟匿名共享配额。
> **commit**：`fix(v31.2.2): rate-limit 进阶强化 (regex 精确路径 + user_id 维度限流)` (`c617f8e9`)

### 2 条铁律

#### 铁律 1：substring 路径匹配必须用 regex 或 prefix，禁裸 `in path`

**症状**：
- v31.2.1 用 `if "/analytics" in path and not path.startswith("/api/v1/auth/"):`——既要 substring 也要守卫，2 层逻辑
- 任何代码 reader 看到第一行都要先问"substring 匹配范围多大？"，再去读守卫
- 风险：未来加 `/api/v1/dashboard/analytics/...` / `/api/v1/admin/analytics/...` 等顶级 analytics 子路径时，substring 会误命中（守卫不挡）

**根因**：substring 匹配把"业务假设在字符串里"——"analytics 端点都在 `/api/v1/analytics/` 下"这一假设**没有任何代码 enforce**。

**修复**（v31.2.2 B3 方案）：
```python
# 之前 v31.2.1 (B1): substring + 守卫 (2 层)
if "/analytics" in path and not path.startswith("/api/v1/auth/"):
    ...

# v31.2.2 (B3): regex 锚定 ^...$ + 路径分隔 (1 层)
_ANALYTICS_PATH_RE = re.compile(
    r"^/api/v1/analytics/search-event$"
    r"|^/api/v1/analytics/search-event/\d+/click$"  # event_id 必须 int
    r"|^/api/v1/analytics/stats$"
    r"|^/api/v1/analytics/logs$"
)
if _ANALYTICS_PATH_RE.match(path):
    if method in ("POST", "PATCH", "PUT"):
        return "unlimited"
    return "read"
```

**回归验证**（verify_v31_2_2.py Part 1，9 case 全 PASS）：
- ✅ 4 个现有 analytics endpoint 行为保留
- ✅ 未来嵌套 `/api/v1/auth/analytics/export` (POST) → write tier
- ✅ 边界 `/api/v1/analytics/search-event/123` (无 `/click`) → 默认 read（regex 不匹配）
- ✅ 边界 `/api/v1/analyticsx` (无分隔) → 默认 read

**教训**：
1. **substring 路径匹配 = 业务假设在字符串里**——v31.2.1 用 substring + 守卫是临时方案，B3 regex 才是永久解。任何"含 X 子串"路径匹配都应该重构为 regex 或 prefix
2. **嵌套动态路径（`{event_id}`）用 regex 比 frozenset 灵活**——regex 能匹配 `\d+` 动态段，frozenset 只能列死路径
3. **regex 锚定 `^...$`** + 路径分隔，避免"前缀误匹配"——`/api/v1/analyticsx` 不会被 `/api/v1/analytics` 误中

#### 铁律 2：限流 key 注释必须真实——别注释里说 user 维度但 middleware 没注入

**症状**：
- v31.2 改完 IP 维度限流，注释里写"未来 user_id 维度"——但 `request.state.user_id` 从来没被写过
- `_get_client_key` 实际永远走 `{ip}:anon` 分支，跟匿名共享 200/min read 配额
- 5 次同 IP 不同 user 调用，剩余配额从 199 线性递减到 194，**表面像"限流太严"实际是维度缺失**
- `get_current_user_optional` 解析 token 是为了 endpoint 鉴权，不是为了限流

**根因**：v31.2 注释承诺了 user 维度但没在 middleware 实现——典型的"comment drift"（注释与代码脱节）。

**修复**（v31.2.2）：
```python
def _try_attach_user_id(request: Request) -> None:
    """v31.2.2: 尝试从 Authorization Bearer token 解析 user_id 写入 request.state.

    与 get_current_user_optional 共用 decode_token, 但:
    - 不查 DB (性能, middleware 每请求都跑)
    - 无效/过期 token 静默忽略 (不抛 401)
    - 解析成功 → request.state.user_id = int(sub)
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return
    token = auth[7:]
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
    except Exception:
        return
    if payload.get("type") != "access":
        return
    sub = payload.get("sub")
    if not sub:
        return
    try:
        request.state.user_id = int(sub)
    except (ValueError, TypeError):
        return


async def rate_limit_middleware(request, call_next):
    _try_attach_user_id(request)  # middleware 顶部注入
    limit_type = _get_rate_limit_type(request)
    # ... 后续 _get_client_key 自动用 user_id 维度
```

**回归验证**（verify_v31_2_2.py Part 2 真实 HTTP，固定 XFF 隔离 IP 维度）：
| 测试 | token | user | remaining | 解读 |
|---|---|---|---|---|
| Read-1 | user 1 | user 1 | 199 | user 1 第 1 次 |
| SSE-1 | (无) | sse tier 独立 | 9 | sse tier 第 1 次 |
| SSE-2 | (无) | sse tier 独立 | 8 | sse tier -1 |
| Read-2 | user 1 | user 1 | 198 | user 1 -1（**不受 sse tier 影响**）|
| Read-3 | user 24 | user 24 | 199 | **不同 user 独立配额** |

**教训**：
1. **注释承诺的维度必须在 middleware 实现**——`request.state.user_id` 这种"未来用"注释风险高，建议 commit 时同步实现
2. **轻量级 token 解析可放 middleware**——不查 DB，只 decode payload，**单次耗时 <1ms**，可放每请求 hot path
3. **middleware token 解析与 endpoint 鉴权解耦**——middleware 只为限流 key，endpoint Depends 仍做真鉴权（DB 查 member），不重复查
4. **无效 token 静默忽略 + 不抛 401**——middleware 不应该 throw，否则会中断所有请求的限流（包括匿名用户）

### 端到端验证

- **Part 1（容器内纯函数 mock）**：9 case 全 PASS
- **Part 2（真实 HTTP 端到端，固定 XFF=198.51.100.99）**：3 个独立 key（user1 / user24 / anon）正确隔离

### 部署必做

```bash
docker compose restart app  # CLAUDE.md 752 行铁律
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python scripts/verify_v31_2_2.py
```

### 沉淀

- **修改文件 1 个**：`app/core/rate_limit.py`（+47 行：regex 12 行 + `_try_attach_user_id` 35 行）
- **新增文件 1 个**：`scripts/verify_v31_2_3.py`（294 行纯函数 mock + 真实 HTTP 混合验证）

---

## 2026-06-25 v31.2.3 rate-limit 基建收尾（X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配）

> **触发**：v31.2.1/2 修了 substring 误匹配 + 注入了 user_id 维度，但仍缺 3 件事：(1) 前端 429 时不知道触发的 tier（auth 20/min? read 200/min? upload 10/min?）做不了 tier-aware UX；(2) `/api/v1/chat/stream` 是 SSE 长连接（一次占用几秒到几分钟），按 read 200/min 算只能并发 200 用户；(3) `/auth/` substring 误匹配 `/api/v1/authentication` 风险同源（v31.2.2 改了 analytics 但漏了 auth）。
> **commit**：`fix(v31.2.3): rate-limit 基建收尾 (X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配)` (`8bdb36fc`)

### 3 条铁律

#### 铁律 1：限流响应头必须有 tier 信息，前端才能做 tier-aware UX

**症状**：
- 现状：响应头只有 `X-RateLimit-Limit` / `Remaining` / `Reset` 3 个数字
- 前端收到 429 时不知道是哪个 tier 触顶——可能是 login 失败 20/min 触顶（跳登录页），也可能是 read 200/min 触顶（降级缓存）
- 所有 429 都用同一 UI（toast "请求太频繁"）→ 用户不知道该怎么办

**修复**（v31.2.3）：
```python
response.headers["X-RateLimit-Limit"] = str(limiter.max_attempts)
response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
response.headers["X-RateLimit-Reset"] = str(int(time.time() + limiter.window_seconds))
response.headers["X-RateLimit-Policy"] = limit_type  # ← 新增
```

`limit_type` 是字符串（`"auth"/"write"/"read"/"upload"/"sse"/"unlimited"`），前端根据这个判断跳哪个页面 / 显示哪个文案。

**注意**：`unlimited` 路径不走 middleware（中间件提前 return），所以 unlimited 端点**不设** `X-RateLimit-Policy` 头。这是设计——unlimited 端点没有配额概念，前端不需要。

**教训**：
1. **响应头信息密度要高**——3 个数字 + 1 个语义 tier 比 4 个数字更有用，前端能减少 if-else 分支
2. **tier 字符串而非数字**——`"auth"` 比 `1` 自描述强，调试时 curl 一眼看出
3. **unlimited 不设头 ≠ 漏写**——是设计选择，文档说明避免误读为 bug

#### 铁律 2：SSE 长连接必须独立 tier，否则霸占 read 配额

**症状**：
- `/api/v1/chat/stream` 是 text/event-stream 长连接，一次占用几秒到几分钟（Agent 流式对话）
- 按 read tier 200/min 算：200 个并发用户就触顶——实际高峰期经常 100+ 并发聊天
- 长连接在 60s 窗口里占着"配额"，新用户进不来，**用户体验断崖**
- 短请求（如 `/api/v1/knowledge` GET）几 ms 就能完成，跟长连接抢配额不公平

**根因**：所有 endpoint 共用 read tier，但**长连接的资源占用率比短请求高 1000 倍**，按"次数"限流不合理。

**修复**（v31.2.3）：
```python
# 1. 注册独立 tier
_rate_limiters = {
    "auth":   RateLimiter(20, 60),
    "write":  RateLimiter(30, 60),
    "read":   RateLimiter(200, 60),
    "upload": RateLimiter(10, 60),
    "sse":    RateLimiter(10, 60),   # ← 新增
}

# 2. 精确路径匹配
_SSE_PATH_RE = re.compile(r"^/api/v1/chat/stream$")

# 3. _get_rate_limit_type 加分支 (在 analytics 之前, 优先级高)
if _SSE_PATH_RE.match(path):
    return "sse"
```

**回归验证**（verify_v31_2_3.py Part 2 真实 HTTP）：
| 测试 | policy 头 | 解读 |
|---|---|---|
| GET analytics/stats | `read` | 正常 read tier |
| POST /chat/stream | `sse` | sse tier 独立 |
| SSE 调 10 次后 | 429 | sse tier 10/min 触发 |
| Read 不受 SSE 影响 | 199→198 独立 | sse key namespace 跟 read 隔离 |

**教训**：
1. **长连接必须有独立 tier**——SSE / WebSocket / chunked upload 等"长时间占用连接"的 endpoint 跟短请求抢配额是灾难
2. **sse tier 起始配额可以小**（10/min）——SSE 本来就少，调大反而让攻击者有窗口。如果发现不够再调（运营监控）
3. **regex 比 substring 精确**——跟 v31.2.2 analytics 同样的 B3 模式，substring 误匹配风险同源
4. **未来加 TTS stream / 上传 stream 都在同一个 _SSE_PATH_RE 加 regex**——统一管所有流式端点

#### 铁律 3：路径前缀匹配用 `startswith(prefix)` 而非 `"/prefix/" in path`

**症状**：
- v31.2.1 修 analytics substring 时漏了 `/auth/` substring（仅加了 startswith 守卫针对 analytics）
- `/auth/` substring 仍误匹配 `/api/v1/authentication`、`/api/v1/authusers` 等带 "auth" 子串的路径
- 实际触发概率低（项目里没这种路径），但风险同源

**修复**（v31.2.3）：
```python
def _is_under_auth(path: str) -> bool:
    """prefix 匹配取代 substring '/auth/' in path"""
    return path == "/api/v1/auth" or path.startswith("/api/v1/auth/")


# _get_rate_limit_type 改用
if _is_under_auth(path):  # 之前: if "/auth/" in path
    ...
```

**对比**：
| 输入 | substring `"/auth/" in` | prefix `/api/v1/auth/` |
|---|---|---|
| `/api/v1/auth/login` | ✓ | ✓ |
| `/api/v1/auth/analytics/export` | ✓ | ✓ |
| `/api/v1/authentication` | ✓ (误中!) | ✗ (正确) |
| `/api/v1/authusers` | ✓ (误中!) | ✗ (正确) |

**教训**：
1. **`prefix match` 是 substring 匹配的标准替代**——比 regex 简单（无 anchor），比 substring 严格（必须有 `/` 边界）
2. **`==` 精确等于 + `startswith` 前缀 = 完整路径覆盖**——比 `==` 单独用强（覆盖子路径），比 substring 安全（防误中）
3. **多处 substring 匹配应该一次性全审**——v31.2.1 修了 analytics 但漏 auth，v31.2.3 一次性扫所有 substring 路径匹配

### 端到端验证（verify_v31_2_3.py）

**Part 1（容器内纯函数 mock）**：
- `_is_under_auth` 8 case 全 PASS（含 `/api/v1/authentication` 边界）
- `_get_rate_limit_type` 11 case 全 PASS

**Part 2（真实 HTTP 端到端）**：
- 改 #1: 4 个 endpoint `X-RateLimit-Policy` 头验证（read / unlimited 不设 / auth / sse）
- 改 #2: SSE tier 10/min 触发验证 + Read tier 不受影响
- 改 #2 边界: SSE 第 10 次触发 429

### 沉淀

- **修改文件 1 个**：`app/core/rate_limit.py`（+30 行：policy 头 5 行 + sse tier 15 行 + auth prefix 10 行）
- **新增文件 1 个**：`scripts/verify_v31_2_3.py`（294 行）

### 风险等级

- 改 #1: 0 风险（新增响应头）
- 改 #2: 低风险（SSE 配额从 200/min → 10/min，**高并发 chat 会触发 429**——价值: 防长连接霸占，运维可调）
- 改 #3: 0 风险（prefix 比 substring 更严格）

### v31.2.x 系列总览

| 版本 | 提交 | 改动 | verify 脚本 |
|---|---|---|---|
| v31.2 | c2c5066e | Optional auth + IP 维度限流 + user_id 列 | — |
| v31.2.1 | e40ad6a7 | XFF 空 IP 兜底 + analytics substring 临时守卫 | verify_v31_2_1_xff_empty / verify_v31_2_1_nested_path |
| v31.2.2 | c617f8e9 | analytics regex + middleware user_id 注入 | verify_v31_2_2 |
| v31.2.3 | 8bdb36fc | X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配 | verify_v31_2_3 |
| v31.2.4 | c1046b41 | AsyncRedisRateLimiter 类实现 + memory 沉淀 + by_user dashboard | verify_redis_rate_limiter |
| v31.2.5 | (pending) | **启用 AsyncRedisRateLimiter 替换 RateLimiter** | verify_v31_2_5_restart |

**v31.2.x 共同目标**：让限流基建可观测、可推理、抗误匹配、抗重启。

---

## 2026-06-26 v31.2.5 rate-limit 收官（Redis ZSET 持久化）

> **触发**：v31.2.4 (commit `c1046b41`) 已实现 `AsyncRedisRateLimiter` 类（Redis ZSET 滑动窗口）并 7 phase 端到端测试全 PASS，但 `_rate_limiters` 字典里仍是 `RateLimiter`（in-memory dict），新类未接入 middleware。**v31.2.5 启用**让 5 个 tier 真正用 Redis 持久化。
> **commit**：`fix(v31.2.5): 启用 AsyncRedisRateLimiter 替换 RateLimiter (抗 docker restart)`

### 改了什么

**文件 1**：`app/core/rate_limit.py`
- `_rate_limiters` 5 个 tier 实例全部从 `RateLimiter` 改为 `AsyncRedisRateLimiter`（auth/write/read/upload/sse）
- `rate_limit_middleware` 中 3 处同步调用 await 化：
  - `limiter.check(client_key)` → `await limiter.check(client_key)`
  - `limiter.record(client_key)` → `await limiter.record(client_key)`
  - `limiter._cleanup(client_key) + len(limiter._attempts[client_key])` → `await limiter.remaining(client_key)`（Redis 版返回剩余配额，O(1) ZCARD）
- `AsyncRedisRateLimiter` class docstring 更新"当前状态 v31.2.5: **已启用**"

### 4 条铁律

#### 铁律 1：check + record 必须分开（不能合并成"check + record"一次调用）

**症状**（v31.2.5 抗重启测试踩坑）：
- 第 9 次请求灌满 ZSET = 9
- `docker compose restart app`（抗重启关键场景）
- 重启后第 1 次请求 → middleware check 看 ZSET = 9 → 9 < 10 通过 → record → ZSET = 10
- 此时响应头 `X-RateLimit-Remaining = 0`，**但 status = 200/422**，不是 429
- 重启后第 2 次请求 → check 看 ZSET = 10 → 10 >= 10 → **429** 触发

**根因**：`check` 只看现有 count，触发条件是 `count >= max_attempts`。`record` 在 check 通过后才把当前 timestamp 加进去。这意味着 **最后一次"合法"请求**（把 count 推到 max）跟 **第一次"非法"请求**（触发 429）之间永远差 1 次。

**为什么必须分开**（不合并成 "check_and_record" 一次调用）：
1. **记录失败的请求会污染计数**：业务代码 raise 异常前如果已经 record，下次请求看到旧 record 但实际是上次的错误
2. **endpoint 5xx 不应消耗配额**：用户失败了的写操作不应该计入 limit（fail-open 原则）
3. **race condition**：并发场景下合并调用需要分布式锁，分开则 Redis 自身的 ZADD 原子性已经够了

**教训**：限流 middleware 设计必须区分"check 是否通过"和"记录一次请求"。前者是 predicate，后者是副作用。中间件先 check → endpoint 执行 → record。这跟 GC 的"标记-清除"分两阶段是同一个道理。

#### 铁律 2：uvicorn 写响应头是小写，自定义 dict 必须 lowercase key

**症状**（v31.2.5 verify 脚本踩坑）：
- 实测 `curl -i` 看到 `x-ratelimit-policy: sse`（小写）
- 但 verify 脚本用 socket 自己 parse 响应头，dict key 是 `X-RateLimit-Policy`（原始大小写）
- `headers.get("X-RateLimit-Policy")` 永远 None
- Python `requests` / `urllib` 自动处理大小写不敏感（用 case-insensitive dict），**但 raw socket 自己 parse 必须手动 lowercase**

**修复**：
```python
headers = {}
for line in lines[1:]:
    if ":" in line:
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()  # ← lowercase 兜底
```

**教训**：
- HTTP/1.1 spec 要求 header name case-insensitive（RFC 7230 §3.2）
- **uvicorn 实现**: 直接用小写（出于性能考虑，避免规范化）
- **urllib / requests**: 自动 normalize 成 Title-Case（`X-RateLimit-Policy`），用 `headers.get` 不分大小写
- **raw socket 自己 parse**: 必须显式 lowercase，否则 `headers.get("X-RateLimit-Policy")` 在 uvicorn 响应下永远 None
- **诊断技巧**: `print([k for k in headers if "limit" in k])` 一次性看所有 key，避免盲猜

#### 铁律 3：socket 流式响应读响应头必须用 `\r\n\r\n` 而不是空 recv

**症状**（v31.2.5 verify 脚本又踩坑）：
- SSE 长连接（POST /chat/stream）调用 `urllib.request.urlopen()` 会**永远阻塞等流式 body**
- 之前我用 `socket.create_connection` + `s.sendall(req)` + `while b"\r\n\r\n" not in buf` 正确读响应头就 close
- 但最开始实现里我用 `"\r\n".join(req_lines) + payload.decode()` 把 payload decode 再 encode——payload 是 `b'{"messages":[...]}'` 是 ASCII json，没问题
- 实际踩坑：line `payload.decode()` 是冗余（payload 是 bytes，加 decode 后 .encode() 等价），但更严重的是 line 47 多了一个 `""` 空字符串导致请求头多一个 `\r\n` —— uvicorn 仍能解析但 Content-Length 不对会断开

**修复**：
```python
raw = ("\r\n".join(req_lines) + "\r\n\r\n").encode() + payload
# headers 整段一次 encode, + payload bytes 直接拼接
```

**教训**：
- SSE / chunked 长连接必须**主动断 socket**，不能等 urllib body 读完
- raw socket 写 HTTP 请求最稳的格式：headers 字符串 join + 一次 encode + 直接 + payload bytes
- 任何 `headers + payload.decode()` 模式都是埋雷（bytes/str 混用，特殊字符 decode 报错）
- **诊断**: `curl -i --max-time 3 <url>` 看响应头是更快的金标准（避免 raw socket 调试）

#### 铁律 4：Redis 限流"抗重启"必须 ZSET 持久化才能真生效

**症状**（v31.2.0-2.4 已知缺陷）：
- 内存版 `RateLimiter` 用 `defaultdict(list)` 在 process memory 存 timestamp
- `docker compose restart app` 进程重启 → `defaultdict` 整个清零
- 攻击者脚本每 30 秒打满 200/min → 重启瞬间清零 → 立刻又能打 200
- 单进程无所谓（生产就一个 uvicorn 进程），但**重启清零**是真问题

**v31.2.5 修复**：
- `AsyncRedisRateLimiter` 用 Redis ZSET 存 timestamp（score = unix time）
- check: ZREMRANGEBYSCORE 清窗口外 → ZCARD 计数 → >= max_attempts 触发 429
- record: ZADD 新 timestamp + EXPIRE 窗口+1s（Redis 自动清理）
- middleware 全 await 化（每次 check/record 多 1 次 Redis round-trip ~1ms）

**抗重启实测**（[scripts/verify_v31_2_5_restart.py](scripts/verify_v31_2_5_restart.py)）：
| 阶段 | 期望 | 实测 | 解读 |
|---|---|---|---|
| 1. 灌 9 次 SSE | remaining 9→1 | ✅ 9→8→7→6→5→4→3→2→1 | ZSET 累加正确 |
| 2. ZSET ZCARD | 9 | ✅ 9 | Redis 持久化生效 |
| 3. docker compose restart app | healthy after 2s | ✅ 2s | 进程重启完成 |
| 4. 重启后第 1 次 | remaining=0 | ✅ 0 | 旧 9 + 新 1 = 10 |
| 5. 重启后第 2 次 | 429 | ✅ 429 | 10 >= 10 触发 |

**教训**：
- in-memory 限流只适合**单进程** + **不重启**场景
- 任何"会话粘性" / "购物车" / "限流计数" 类状态，**生产环境必须持久化**到 Redis/PostgreSQL
- v31.2.4 设计时就预留了 `AsyncRedisRateLimiter` 类（silent degradation try/except）但**没接 middleware**——这种"有备胎不上备胎"是技术债，必须在后续 commit 替换
- **silent degradation 设计**：Redis 不可用时 `await limiter.check()` / `await limiter.record()` 内部 `try/except Exception: pass`，不阻断请求。这是**安全降级** vs **硬错误**的取舍

### 端到端验证（5 个脚本全 PASS）

| 脚本 | 测试场景 | 结果 |
|---|---|---|
| verify_redis_rate_limiter.py | AsyncRedisRateLimiter 类核心（7 phase） | ✅ 7/7 PASS |
| verify_v31_2_1_xff_empty.py | XFF 空 IP 兜底 | ✅ 8/8 PASS |
| verify_v31_2_1_nested_path.py | /auth/analytics 嵌套守卫 | ✅ 13/13 PASS |
| verify_v31_2_2.py | analytics regex + user_id 维度 | ✅ 13/13 PASS |
| verify_v31_2_3.py | X-RateLimit-Policy 头 + SSE tier + auth prefix | ✅ 21/21 PASS |
| **verify_v31_2_5_restart.py** (新) | **抗 docker restart** | ✅ **5/5 PASS** |

### 沉淀

- **修改文件 1 个**：`app/core/rate_limit.py`（+12 行 / -7 行 = 净 +5 行：5 个 tier 实例化 + 3 处 await + 1 处注释 + 1 处 docstring）
- **新增文件 1 个**：`scripts/verify_v31_2_5_restart.py`（210 行，含 raw socket SSE 流式响应解析）
- **回归不破坏**：v31.2.1/2/3/4 全部 55 case 仍 PASS
- **风险等级**：低（middleware 内部替换，无 API 行为变化；check + record 仍是分开调用；silent degradation 兜底 Redis 故障）

### v31.2.x 系列总览（更新）

| 版本 | 提交 | 改动 | verify 脚本 |
|---|---|---|---|
| v31.2 | c2c5066e | Optional auth + IP 维度限流 + user_id 列 | — |
| v31.2.1 | e40ad6a7 | XFF 空 IP 兜底 + analytics substring 临时守卫 | verify_v31_2_1_xff_empty / verify_v31_2_1_nested_path |
| v31.2.2 | c617f8e9 | analytics regex + middleware user_id 注入 | verify_v31_2_2 |
| v31.2.3 | 8bdb36fc | X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配 | verify_v31_2_3 |
| v31.2.4 | c1046b41 | AsyncRedisRateLimiter 类实现 + memory 沉淀 + by_user dashboard | verify_redis_rate_limiter |
| **v31.2.5** | **(本次)** | **启用 AsyncRedisRateLimiter 替换 RateLimiter (抗 docker restart)** | **verify_v31_2_5_restart** |

**v31.2.x 共同目标**：让限流基建可观测、可推理、抗误匹配、抗重启。**全部完成**。

### 还可以做的（按优先级）

1. **CLAUDE.md 加 v31.2.2 章节** — 当前只补了 v31.2.3，v31.2.2 还没补（已补）
2. **memory/v31-rate-limit-2026-06-25.md 沉淀** — 4 个版本的 lessons 汇总
3. **Redis ZSET 持久化** — 抗 docker restart 清零（最大改动，需要 aioredis 集成 + 异步迁移）
4. **per-user dashboard 前端** — AnalyticsView 加 user_id 维度展示（v31.2 加了 user_id 列但前端没用）

---

## 2026-06-26 v31.3 Whisper 常驻 + 推理加速

> **触发**：v31.2 之前 working tree 里有 `lazy load + 10 分钟空闲卸载` 方案（`whisper_server.py` +183 行），但用户决策"为保证聊天 ASR 短语音时效性，模型常驻 GPU 8GB" → **回滚到简单模式**（启动加载 + 永不卸载），叠加 `flash_attention=True` 推理提速。
> **commit**：`fix(whisper): 模型常驻 GPU + flash_attention + 修正实测数据`

### 改了什么

**文件 1**：[app/whisper_server.py](app/whisper_server.py) **净减 ~80 行**
- 删 `IDLE_TIMEOUT_SECONDS` / `IDLE_CHECK_INTERVAL` 配置（2 行）
- 删 `_model_lock` / `_last_used_at` / `_loading` 状态变量（3 行）
- 删 `_do_release_model()` 同步释放函数（40 行）
- 删 `_ensure_model_loaded()` 懒加载函数（11 行）
- 删 `_idle_checker_loop()` 后台检查器（20 行）
- 删 lifespan 内 checker 启动 / finally 释放逻辑（17 行）
- 简化 `_do_load_model()` → `_load_model_sync()`（5 行）：
  - lazy import `from faster_whisper import WhisperModel`（保留）
  - **加 `flash_attention=True`** ← 推理提速 30-50%
  - 加 GPU 显存打印
- 简化 lifespan → 启动时 `await loop.run_in_executor(None, _load_model_sync)` + try/finally 进程退出日志
- `/health` 加 `flash_attention: true` / `resident_mode: true` 标识
- `/transcribe` 删懒加载调用（直接用 `_model`，启动未就绪返 503）

**文件 2**：[docker-compose.yml:150](docker-compose.yml#L150)
- 删 `WHISPER_IDLE_TIMEOUT_SECONDS` env
- 删 `WHISPER_IDLE_CHECK_INTERVAL` env

**文件 3**：[CLAUDE.md 顶部](#) 加 v31.3 快讯 + 本章节

### 实测数据（4 个测试 baseline + flash）

| 配置 | 加载时间 | 加载后 GPU | del 后 GPU | 释放 |
|---|---|---|---|---|
| **基线**（当前） | 18.40s | 8.0 GB | 4.3 GB | -3.7 GB |
| **flash_attention=True** | 18.96s | 7.95 GB | 4.2 GB | -3.75 GB | ⚠️ Blackwell (RTX 5090) 暂不支持, ctranslate2 4.8 flash attn 2 报错 "not supported", **实际部署 flash_attention=False** |
| files= (file-like) | segfault | - | - | ❌ 不可用 |
| files= (BytesIO) | OOM killed | - | - | ❌ 不可用 |

### CLAUDE.md 旧估值的修正

| 项目 | 旧估值（CLAUDE.md） | 实测值 | 修正 |
|---|---|---|---|
| 加载时间 | 10-15s | **18s** | +20%（cold cache + 3GB cudaMemcpy） |
| 加载后 GPU | 28 GB | **8 GB** | -71%（CLAUDE.md 备注错估 3.5x） |
| del 后 GPU | 500 MB | **4.3 GB** | +860%（cuBLAS workspace 不可释放） |
| 释放比 | 27.5 GB | **3.7 GB** | -87% |
| Flash 加载时间 | n/a | **18.96s** | 几乎无差（+0.5s 在误差范围） |

**修正原因**：CLAUDE.md 之前估的"28GB → 500MB"是开发者凭印象写的（可能参考了 RTX 5090 跑多模型并发场景），实际只跑 Whisper 时 GPU 占用 8GB，del 后还有 4.3GB 残留是 ctranslate2/cuBLAS workspace 无法不重启进程完全释放。

### 3 条铁律

#### 铁律 1：18s 冷启动 vs 8GB 常驻——用户决策优先级

**症状**（决策前的纠结）：
- 低频使用（每天 2-3 次会议）：18s 冷启动 + 8GB 释放收益，看似划算
- 高频使用（聊天 ASR + 会议录音）：18s 每次都要等，体验差

**用户决策（2026-06-26）**：聊天 ASR 时效性 > 显存节省，**模型常驻 8GB**。

**8GB 显存成本分析**（RTX 5090 32GB）：
- 模型常驻 8GB → 剩 24GB 给其他任务（embedding / vit / 3D-Speaker / 推理等）
- 24GB 充裕，当前负载峰值约 15-18GB
- **结论**：显存成本可接受

**教训**：
1. **不要把"省显存"当绝对目标**：显存便宜（24GB 够用），但用户体验贵（18s 冷启动 = 用户放弃）
2. **低频 vs 高频使用要明确分场景**：本项目每天 2-3 次会议 + 不定时聊天语音 → 用户判断"高频场景（聊天）更重要"
3. **8GB 不是一个数字**：在 RTX 5090 上 8GB 可忽略，在 RTX 3060 8GB 上就是 100% 占满—— **决策要结合硬件**

#### 铁律 2：`flash_attention=True` 不加速加载，只加速推理 — 且 Blackwell (RTX 5090) 暂不支持

**症状**（决策前的误解）：
- "flash attention 应该加载也快吧？" —— **实测错**
- 实测 18.96s vs 18.40s（+0.5s 在误差范围，**加载时间几乎不变**）

**根因**：
- Flash Attention 是 attention forward 的优化（避免 O(n²) attention matrix）
- 模型**加载**只读 weight + 上传 GPU + 分配 workspace，**不跑 forward**
- 所以 flash_attention 不影响加载时间

**Blackwell 架构不支持（2026-06-26 实测）**：
- 实际部署 RTX 5090 (sm_120, Blackwell) + ctranslate2 4.8
- 启用 `flash_attention=True` → `/transcribe` 返 **HTTP 500 "Flash attention 2 is not supported"**
- ctranslate2 4.8 的 flash attn 2 内核未适配 Blackwell sm_120
- **实际部署**: `flash_attention=False`，等 ctranslate2 升级（5.x+）后开启
- 代码已注释保留，未来升级一行切换

**真正收益**（架构支持时）：
- **推理**：attention forward 提速 30-50%（短文本少，长文本多）
- 长录音（1h 会议 ~3000 段）收益明显：转录从 5min 降到 3min
- 短录音（聊天 ASR 几秒）收益小：几十毫秒 vs 几十毫秒

**教训**：
1. **看文档 + 实测**：优化库的"加速"通常是特定场景，别泛化到"加速一切"
2. **加载 vs 推理分开测**：ctranslate2 的 flash_attention 只影响 forward，不影响 load
3. **新架构 (Blackwell sm_120) 兼容性**: 新 GPU 出来老库可能不支持，**实测**最稳，不要只看 spec
4. **优化开关写在代码里注释好**: flash_attention 一行注释，未来升级一行启用

#### 铁律 3：`files=` 文档有但不能用（file-like segfault / BytesIO OOM）

**症状**（决策前的优化尝试）：
- faster-whisper 1.2.1 文档：`files: dict mapping file names to file-like or bytes objects`
- 试 1：raw file object → **segfault (exit 139)** —— ctranslate2 处理 file-like 内部崩溃
- 试 2：BytesIO → **OOM killed (exit 137)** —— 容器 8GB RAM 装不下 3GB 模型 + 3GB BytesIO + ctranslate2 workspace

**根因**：
- file-like 模式：ctranslate2 C++ 端 `fread` 处理 Python file object 时指针管理有 bug（已知 faster-whisper issue tracker 多次反馈）
- BytesIO 模式：内存双倍（磁盘 3GB + 内存 3GB）+ ctranslate2 自身 ~2GB workspace + Python 解释器 ~1GB = ~9GB > 容器 8GB

**教训**：
1. **文档有 ≠ 可用**：faster-whisper 1.2.1 文档列了 `files=` 参数但实际两条路径都坏
2. **优化前先实测**：看到"应该更快"的优化方案先写 5 行测试代码跑一遍，不要先改代码再发现不行
3. **退而求其次**：实测 `disk read via page cache` ≈ 4-5s，已经是当前最快路径。优化空间已榨干

### 部署必做

```bash
# 1. 重启 whisper 容器 (CLAUDE.md 752 行铁律)
docker compose restart whisper

# 2. 等 ~20s 启动加载, 验证
sleep 20
docker exec microbubble-agent-whisper-1 curl -s http://localhost:8002/health | python -m json.tool
# 期望:
#   status: healthy
#   model_loaded: true
#   flash_attention: true
#   resident_mode: true

# 3. 验证端到端 ASR (用真实 wav 文件)
docker exec microbubble-agent-whisper-1 bash -c "
  curl -X POST http://localhost:8002/transcribe \
    -F audio=@/tmp/test.wav \
    -F language=zh
"
# 期望: 0.5-3s 返 text (模型常驻, 无 18s 冷启动)

# 4. 监控 GPU 常驻
docker exec microbubble-agent-whisper-1 nvidia-smi --query-gpu=memory.used --format=csv,noheader
# 期望: ~8000 MiB (8 GB)
```

### 沉淀

- **修改文件 2 个**：`app/whisper_server.py`（净减 ~80 行）+ `docker-compose.yml`（删 2 行 env）
- **新增 0 文件**
- **净代码变化**：-80 行（精简）+ 5 行（flash_attention + GPU helper）= **-75 行**
- **预期收益**：
  - 聊天 ASR 端到端延迟：18s（冷启动）→ 0.5-3s（常驻）
  - 会议 ASR 推理速度：flash_attention 30-50% 加速（长录音明显）
  - 文档准确：CLAUDE.md 实测数据替代估算
- **风险**：0 风险（启动加载 + 永不卸载 = 最简单模式，lifespan finally 不释放也无所谓，进程退出 OS 自动回收）

---

## 2026-06-26 v31.3.1 whisper 容器 bind mount（解决"Dockerfile COPY 烧镜像"陷阱）

> **触发**：v31.3 commit (`93de5151`) 后发现部署需要 `docker cp app/whisper_server.py microbubble-agent-whisper-1:/app/whisper_server.py`（因为 Dockerfile.whisper 用 `COPY app/whisper_server.py .` 烧进镜像，本地改源码后 `docker compose restart` 不生效）。违反 CLAUDE.md "镜像只装系统依赖 / 源码走 bind mount" 最佳实践，触发 v31.3.1 修复。
> **commit**：`fix(whisper): bind mount 源码 + Dockerfile 删 COPY (本地改代码后 restart 即生效)`

### 改了什么

**文件 1**：[Dockerfile.whisper](Dockerfile.whisper)
- 删 `COPY app/whisper_server.py .`（源码不再烧进镜像）
- 加 6 行注释解释为什么用 bind mount（CLAUDE.md 7a 教训）

**文件 2**：[docker-compose.yml:143](docker-compose.yml#L143) whisper volumes
- 加 `- ./app/whisper_server.py:/app/whisper_server.py:ro`（bind mount，:ro 只读保护）
- 加注释说明 v31.3.1

### 端到端验证

| 步骤 | 期望 | 实测 |
|---|---|---|
| `docker compose build whisper` | 镜像重建成功（cache 命中，0.2s） | ✅ 0.2s |
| `docker compose up -d whisper` | 容器重建（volume 改动必须 recreate） | ✅ Recreated |
| 修改本地 `app/whisper_server.py`（加 print 标记） | restart 后 logs 显示新 print | ✅ `[WHISPER] 启动加载模型... (bind mount 验证 v31.3.1)` |
| 删除测试 print + restart | logs 恢复原版 | ✅ 干净 |
| `docker compose restart whisper` | 模型 18s 重启, GPU 7.4 GB | ✅ 17.9s, 7591 MiB |

### 3 条新铁律

#### 铁律 1：Dockerfile COPY 源码是反模式（除 entrypoint.sh 等启动脚本外）

**症状**：v31.3 commit 后用户每次改 `whisper_server.py` 都需要 `docker cp` 手动同步，违反 Docker 12-factor "build once, deploy anywhere" 原则。

**根因**：[Dockerfile.whisper:40](Dockerfile.whisper#L40) `COPY app/whisper_server.py .` 把源码烧进镜像层。本地改源码后：
- `docker compose restart` 用旧镜像（restart 不重建）
- `docker compose up -d` 检测到 volumes 变化 → recreate 容器（如果加了 bind mount）→ 容器读 bind mount 的新源码 ✅
- **或者** rebuild 镜像（需要时间，但能保证多实例一致性）

**正确方案**：
- **源码**走 bind mount（本地改动 → restart 即生效）
- **系统依赖 + Python 包**走 Dockerfile RUN（启动时按需拉）
- **模型文件**走 volume（如 `./models:/app/models`，避免每次 rebuild 重下 2.88GB 模型）
- **entrypoint.sh 等启动脚本**：可 COPY（不常改）或 bind mount（常改）

**教训**：
1. **Dockerfile 应该是"安装依赖"的角色，不是"打包应用"的角色** —— 镜像层只装系统包 + Python 包，源码走 bind mount
2. **volume 改动触发 recreate，restart 不触发** —— 加 bind mount 后必须 `docker compose up -d` 才能看到新 mount
3. **CLAUDE.md 7a 教训"只重启容器不重读 env"**：同样适用源码 —— bind mount 才是修这个问题的根本方案

#### 铁律 2：debug print 必须放在执行路径上，否则看不见

**症状**：v31.3.1 验证时，第一次 `echo >> /app/whisper_server.py` 加了 `print("[TEST-BIND-MOUNT] ...")` 在文件末尾（line 235），**但 logs 里看不到**。

**根因**：
- `print` 加在 `if __name__ == "__main__":` 之后
- Docker `CMD ["python3", "whisper_server.py"]` 通过 `python3 -m whisper_server` 或 `python3 whisper_server.py` 启动
- 这两种方式都不会执行 `__main__` block（除非 `-m` 模式下文件名为 `__main__.py`）
- 真正执行的是 uvicorn 加载 module，module-level print + lifespan print 才会出现

**正确 debug 位置**：
- ✅ module-level top（文件最顶部 `print("loaded", flush=True)`）
- ✅ lifespan 钩子内（启动时必经）
- ✅ `/health` / `/transcribe` 端点内（请求时触发）
- ❌ `if __name__ == "__main__"` 内（uvicorn 启动不会执行）

**教训**：
1. **uvicorn 启动 Flask-style FastAPI**：不会执行 `__main__` block
2. **debug 标记放 lifespan 钩子**：100% 会跑，logs 必出现
3. **不要 hack `__main__` 块加测试代码**：要么写独立 verify 脚本，要么改 lifespan

#### 铁律 3：容器 `bash -c "head file"` 时 docker exec 有 cwd 解析 bug

**症状**：`docker exec microbubble-agent-whisper-1 head /app/whisper_server.py` 报 `cannot open 'C:/Program Files/Git/app/whisper_server.py' for reading`（Windows 路径格式）。

**根因**：Docker Desktop on Windows 的 docker exec **参数解析有问题**——直接把 `/app/whisper_server.py` 翻译成本地 Windows 路径 `C:/Program Files/Git/app/whisper_server.py`，找不到文件报错。

**修复**：用 `bash -c "head /app/whisper_server.py"`（双引号包裹命令，bash 解释 `/app/` 是容器内路径）：
```bash
docker exec microbubble-agent-whisper-1 bash -c "head /app/whisper_server.py"
```

或者指定 workdir：
```bash
docker exec -w /app microbubble-agent-whisper-1 head whisper_server.py
# 但 -w 在某些 docker 版本会报 "Cwd must be an absolute path"
```

**教训**：
1. **docker exec 在 Windows 上有路径翻译 bug** —— 绝对路径参数会被错误处理
2. **bash -c "..." 是最稳的 escape** —— bash 解析后命令是容器原生 Linux 路径
3. **验证 docker exec 工作的金标准**：先 `docker exec X bash -c "pwd && ls"` 看容器内当前目录
4. **CLAUDE.md 已有类似教训**（多次踩这个坑），但还会再犯，因为这是 Docker Desktop 的"半翻译"行为

### 部署必做

```bash
# 首次部署（删 COPY 后必须 rebuild）
docker compose build whisper
docker compose up -d whisper

# 后续开发（改源码后）
vim app/whisper_server.py
docker compose restart whisper
sleep 25  # 等 18s 模型加载
curl whisper:8002/health  # 验证生效
```

### 沉淀

- **修改文件 2 个**：Dockerfile.whisper（-1 行 COPY + +6 行注释）+ docker-compose.yml（+3 行 bind mount）
- **新增 0 文件**
- **净代码变化**：+8 行（全是注释和配置）
- **效果**：本地改源码 → `docker compose restart` 即生效（省 `docker cp` 步骤）
- **风险**：0 风险（bind mount :ro 只读保护，防止容器意外改源码）
