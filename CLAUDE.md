# MicroBubble Agent - 项目上下文

> **2026-06-15 凌晨更新**：Agent 回答质量 5 大根因修复（14 commits）+ qa-bench 360 题逐个问答闭环 + 知识库 64→247 条（+183）。详见底部 [## 2026-06-15 Agent 质量 + qa-bench 闭环](#2026-06-15-agent-质量--qa-bench-闭环) section。
>
> **2026-06-15 上午更新**：Rich Block 统一包装铁律（杨慈是谁呀 Rich Block 显示"暂无成员"修复 + 顺手修 wechat/handler.py:1031 SyntaxError + members.notification_preferences 列缺失）。详见底部 [## 2026-06-15 Rich Block 统一包装铁律](#2026-06-15-rich-block-统一包装铁律杨慈是谁呀暂无成员修复) section。
>
> **2026-06-15 下午更新**：LLM 元话语/thinking 文本泄露修复（杨慈是谁呀元话语泄露"我需要..."、"用户问的是..."、"开始回答吧"）。双管齐下：prompts.py 硬规则 + 后端 _strip_meta_thinking 兜底 + SSE done.text_without_json + 前端 useChatStream done 替换。详见底部 [## 2026-06-15 LLM 元话语/thinking 文本泄露修复](#2026-06-15-llm-元话语thinking-文本泄露修复双管齐下) section。
>
> **2026-06-15 全天更新**：任务提醒体系 v2 全面优化（commits `223ea74` + `ba75e32`）。所有 reminder 统一在 11:00 AM 北京时间窗口发送，每个任务 1 次推完即结束；任何微信消息 = ack 取消该用户所有 pending 提醒（杜同贺痛点彻底解决）。详见 [## 2026-06-15 任务提醒体系 v2 全面优化](#2026-06-15-任务提醒体系-v2-全面优化)。

## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus（原版 `web/`，极简版 `web-minimal/`）
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前开发阶段

**Phase 1-6 全部完成 + v2/v3/v4 全栈架构重构收官 + 移动端 10 个 PR 全栈定制收官。** 知识库已升级为**自主进化的课题组知识大脑**。会议系统已重构为**录音机 + 离线后处理模式**。**小气助手后端 Agent 架构**：从 1 个 1469 行单文件（`app/agent/core.py`）拆为 7 个职责清晰模块 + 13 个按业务域拆分的 tools/ 文件，**34 个工具全部走 `@tool` 装饰器 + Pydantic 校验**。前端用 ChatViewSSE.vue 接入真实 SSE 流式 + 12 类 Rich Block 组件 + 多会话侧栏 + dark mode + ASR/TTS 完整语音链路 + 代码高亮。**移动端**采用 NutUI 4 + Element Plus **路由级双栈**架构（`useIsMobile.js` 判定 + `resolveMobile.js` 路由适配），**18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略**全部交付，**iOS Safari + Android Chrome 全兼容**。**当前状态（2026-06-13 收官后，commit `9026c07`）**：
- **43 commits 累计**（v1 修复 + v2 6 + v3 5 + v4 6 + 文档 2 + 深夜收尾 4 + 多会话并行 2 + 移动端 PR #1-10 共 10 + 文档/webhint 5 + 部署加固 1）
- **160+ 测试全过**（87 后端 + 73 前端 + 21 录音断网防御 + 2 移动端组件）
- **1014 次提交 / 135K 行代码 / 578 文件 / 30 开发天数**（`app/stats.json` 由本地 Python 准确计算；排除 frp/.git/node_modules/dist/.meta/.log/.wav/.exe 等非源代码）
- **140 项待做清单**已整合到 README.md（107 项老 + 33 项 v4 收官遗留），移动端 10 PR 完成后清单大幅缩短

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

### 2026-06-13 Vue 3.5 升级 + PWA HTML 策略新增

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
