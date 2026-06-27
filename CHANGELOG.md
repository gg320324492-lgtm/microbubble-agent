# 更新日志

> 项目所有重要变更记录。详细修复细节见对应 commit 注释和 `memory/` 笔记。

## [2026-06-27] v76.2 视觉回归测试 5 件套收官

### 🧪 v76.2 视觉回归：baseline + ci-mode + max-increase + 组件级 CSS

- **commit** — `f19cb780 test(visual): v76.2 baseline + ci-mode + max-increase + 组件级 CSS 测试 (5 件套收官)`
- **5 件套** — Playwright baseline 截图 + ci-mode（非交互运行）+ max-increase 容差 + 组件级 CSS 测试 + PWA manifest 拆分 spec
- **CI 集成** — `test:visual` 脚本 + `test-results/` 排除 gitignore，PR 即时反馈视觉回归
- **配合 v74 CSS variable 自动化** — 字面色回归即时拦截
- **覆盖组件级 CSS** — 单组件样式独立测（不依赖整页渲染）

## [2026-06-27] v75 测试稳定性 + v76 PWA manifest test

### 🧪 v75/v76 测试稳定性双轨

- **v75 commit** — `ee46c34a test(web): v75 9 个旧 fail 修复 + PR annotation + token orphan pre-commit 拦截`
- **v76 fix** — `a2a11505 fix(visual): PWA manifest test 拆出 visual-regression spec`（独立跑避免被主 spec 阻断）
- **修复 9 个旧 fail** — timeout 配置 + 异步 mock + DOM 节点选择器适配
- **PR annotation** — 测试失败时 GitHub PR 自动 comment 链接到具体失败截图
- **token orphan 拦截** — pre-commit 检测 git tracked 但 reference 不到的 token key（防组件删了但 token 还留着 → build warning 噪音）

## [2026-06-27] v74 CSS variable 6 主题组合自动化测试

### 🎨 v74 CI 拦截字面色回归

- **commit** — `0f77bc29 test(web): v74 CSS variable 6 主题组合自动化测试 + CI hard fail + token 白名单`
- **6 主题组合自动化** — orange/ocean/forest × light/dark 全覆盖
- **CI hard fail** — 任何字面色回归立即阻止合并
- **token 白名单** — 允许的 hex 颜色清单（图标 logo 等例外）

## [2026-06-27] v73 fallback 政策章节补全

### 🎨 v73 fallback orphan 修复 + font-mono token

- **commit 1** — `1707c660 fix(web): v73 fallback orphan 修复 + CI 集成 + font-mono token`
- **commit 2** — `d8ae2a2f docs: v73 fallback 政策章节补全 (1707c660 漏 commit)`
- **fallback orphan 修复** — CSS fallback 变量写法规范化（`var(--token, #hex)` 但 #hex 不在 token 系统 → 警告）
- **CI 集成** — 自动检测孤儿 fallback
- **font-mono token** — 新增 `--font-mono` 统一 SF Mono / Cascadia Code / 系统中文字体

## [2026-06-27] v72 P1 会议纪要"摘要 + 重点摘要"合并

### 🎨 v72 P1 主题色 TL;DR 卡显示摘要段落

- **commit** — `eed0c409 feat(meeting): v72 P1 摘要+重点摘要合并 - 主题色 TL;DR 卡显示摘要段落`
- **用户原话** — "把这两个内容合并，直接显示下面这个橙色底的内容就可以了" + "要根据整体的主题颜色来改变，不一定一直是橙色底，看主题是什么颜色"
- **核心改动** — 删独立"摘要"section（line 133-136） + TL;DR 卡内容从 `meeting.key_points.slice(0,3)` bullet 改为 `meeting.summary` 完整段落 + 卡标题"重点摘要"→"会议摘要"
- **主题色策略** — `color-mix(in srgb, var(--color-primary) 10%/6%/30%, transparent)` 让卡背景/边框跟随当前主题（orange/ocean/forest × light/dark = 6 套组合）
- **dark mode** — 透明度降至 8%/4%/25% 避免在深背景上刺眼
- **零后端 / 零新依赖 / 零 mobile 改动**
- **复用** — v70 P3 的 `.tldr-card` 容器 + v71 P1 的 `.fade-slide-up` 入场动画
- **CSS Color Module Level 5** — `color-mix()` Chrome 111+ / Firefox 113+ / Safari 16.2+ 原生支持

## [2026-06-27] v71 P1 议程 timeline + 每 speaker 8 条常驻

### 🎨 v71 P1 会议纪要视觉迭代

- **commit** — `46c85892 feat(meeting): v71 P1 议程 timeline + 每 speaker 8 条常驻 + per-card 展开全部`
- **议程 timeline** — `el-timeline` 替换旧 `.agenda-list`，金橙圆 dot 显示数字（ProjectView 同款模式）
- **每 speaker 8 条常驻** — 默认折叠改为默认展开，每张发言人卡片常驻前 8 条要点/决议，超过 8 条显示 "▼ 展开全部（剩 N 条）" 按钮
- **per-card 展开状态隔离** — `expandedFullGroups: Set<gi>` + `expandedFullDecisions: Set<gi>`（互不影响）
- **复用 v70 P3 `.speaker-group` / `.fade-slide-up`** — 零新动画
- **dark mode** — 议程 timeline dot 用 `var(--color-primary)` + `box-shadow: 0 0 0 3px var(--color-bg-card)` 维持外圈效果

## [2026-06-27] v70 P0~P3 字面色 → token + 会议纪要 TL;DR

### 🎨 v70 字面色 token 化 4 阶段（P0~P3）

- **commit P0** — `e4b2eec3 feat(web): v70 P0 字面色急修 - 知识卡 + paper 子模块 32 处 #1F2937→token`
- **commit P0.5** — `6d192718 fix(web): v70 P0.5 剩余白边 - el-card 自身重声明 --el-card-bg-color + el-tabs--border-card dark 覆盖`
- **commit P1** — `5ea74dd5 feat(web): v70 P1 主色/状态色/文本色批量替换 ~170 处字面色 → token`
- **commit P2** — `f6a2bc3d feat(web): v70 P2 灰阶/背景/阴影批量替换 ~170 处 + 4 处 dark-mode 冗余删除`
- **commit P3** — `bd41497e feat(meeting): v70 P3 会议纪要视觉精简 - 顶部 TL;DR + 默认折叠发言人卡片`
- **commit P3 预防** — `7ee757cf feat(web): v70 P3 预防机制 - Stylelint 字面色禁用 + docs/color-tokens.md`
- **commit 性能** — `5914a563 perf(meeting): polish-text Redis 缓存 + 前端非阻塞润色` + `9986eb67 perf(meeting): 转录记录 tab 加速 (删除 LLM polish + 替换 el-select 为 popover)`
- **效果** — ~340 处 hex 替换为 `var(--color-*)` token，dark mode 全面修复（之前散落的 `[data-theme="dark"]` 冗余删除）
- **TL;DR 卡** — v70 P3 引入"会议重点摘要"卡，v72 P1 改为显示 `meeting.summary` 段落

## [2026-06-26] pre-commit hook auto-add web/dist/

### 🪝 pre-commit hook：dist 漏 commit 自动兜底

- **commit** — `6565415a feat(hooks): pre-commit auto-add web/dist/ (CLAUDE.md 2026-06-26 教训)`
- **背景** — v70 P2 commit `f6a2bc3d` 漏 add 95 个新 dist 文件 → 服务器 `index-fc61064b.js` 404 + SPA fallback 返 `text/html` → 整站白屏
- **CLAUDE.md 教训第 4 次沉淀** — 2026-06-03 / 2026-06-10 / 2026-06-14 / 2026-06-26 同坑
- **解决方案** — `scripts/check-dist-before-commit.sh` 自动检测 `web/src/` 改动 + 本地有未 tracked 的 `web/dist/assets/` hash 命名文件 → 自动 `git add -f web/dist/`
- **不 hard block** — 只 hash 命名格式（`<name>-<8 hex char>.{js,css}`）被 add，不误 add user 临时文件
- **新成员 setup** — `cp scripts/check-dist-before-commit.sh .git/hooks/pre-commit && chmod +x`

## [2026-06-26] v69 P0+P1 desktop dark mode 全面重构（3 阶段）

### 🎨 v69 dark mode 3 阶段收官

- **P0 commit** — `71bb394a feat(web): v69 P0 dark mode foundation (5 tokens + 14 EP + MainLayout + Dashboard)`
- **P1a commit** — `55865fe2 feat(web): v69 P1a multi-theme system (6 palettes + SettingsView picker)`
- **P1b commit** — `7e0976d8 feat(web): v69 P1b 10 desktop views dark mode coverage`
- **P0 修复 10 处截图问题** — 侧栏奶白→深灰玻璃态 / 任务配对卡对比过强 / EP 组件 dark 覆盖 14 个 / Hero 渐变过曝 / WCAG AA 4.5:1 文字对比
- **P1a 6 套主题** — orange/ocean/forest × light/dark = 6 组合，`<html data-theme data-accent>` 双轴正交，`color-mix(in srgb, var(--color-primary) X%, transparent)` 自适应
- **P1b 10 桌面视图 dark 适配** — ChatViewSSE / TaskView / TaskTrash / MeetingView / MeetingDetailView / KnowledgeView / KnowledgeDetailView / ProjectView / MemberView / admin/AgentTracesView
- **v60-v67 教训最终强化** — dark 模式 + 跨组件覆盖必须**非 scoped** `<style>` 块（Vue scoped 编译器剥 `:global()` 后代选择器）

## [2026-06-26] v68 桌面主题切换按钮 + SettingsView 玻璃态

### 🎨 v68 主题切换 UI 入口

- **commit** — `2cb2287e feat(web): v68 桌面端主题切换按钮 + SettingsView 玻璃态视觉升级`
- **桌面端主题切换按钮** — 顶栏直接挂（v67 PWA 入口 / 移动端 fallback 桌面版）
- **SettingsView 玻璃态** — `backdrop-filter: blur(20px)` + 半透明背景 + 主题色边框
- **铺垫** — v69 P0+P1 多主题切换基建

## [2026-06-26] v31.3.1 whisper 容器 bind mount

### 🔧 v31.3.1 修复：whisper 容器源码自动同步

- **触发** — v31.3 commit (`93de5151`) 后部署需 `docker cp app/whisper_server.py microbubble-agent-whisper-1:/app/whisper_server.py`（因为 [Dockerfile.whisper:40](Dockerfile.whisper#L40) `COPY app/whisper_server.py .` 把源码烧进镜像，本地改源码后 `docker compose restart` 不生效）
- **commit** — `fix(whisper): bind mount 源码 + Dockerfile 删 COPY`
- **修复** — [Dockerfile.whisper](Dockerfile.whisper) 删 `COPY app/whisper_server.py .` + [docker-compose.yml](docker-compose.yml) 加 `- ./app/whisper_server.py:/app/whisper_server.py:ro`
- **效果** — 本地改源码 → `docker compose restart whisper` 即生效（省 `docker cp` 步骤）
- **3 条新铁律沉淀** — Dockerfile COPY 源码是反模式 + debug print 放 lifespan 钩子 + docker exec on Windows 用 `bash -c`

## [2026-06-26] v31.3 Whisper 常驻 + 推理加速（用户决策：chat ASR 时效性优先）

### 🎙️ v31.3 收官：Whisper 模型常驻 GPU + flash_attention 准备

- **触发** — v31.2 之前 working tree 里有 `lazy load + 10 分钟空闲卸载` 方案（`whisper_server.py` +183 行），但用户决策"为保证聊天 ASR 短语音时效性，模型常驻 GPU 8GB" → 回滚到简单模式
- **commit** — `fix(whisper): 模型常驻 GPU 8GB + flash_attention (Blackwell 暂禁用)`
- **改了什么**：
  - `app/whisper_server.py` 净减 ~80 行（删 `_do_release_model` / `_idle_checker_loop` / `_ensure_model_loaded` / 状态变量）
  - lifespan 简化为 `await loop.run_in_executor(None, _load_model_sync)` 启动加载
  - `_load_model_sync` 加 `flash_attention=True`（代码注释保留开关）
  - `/health` 加 `flash_attention` / `resident_mode` 字段
  - `docker-compose.yml` 删 `WHISPER_IDLE_*` env
- **实测数据修正**（CLAUDE.md 之前估的"28GB → 500MB"和"10-15s 加载"严重偏离）：
  - 加载时间：**18s**（CUDA context + 3GB cudaMemcpy）
  - GPU 常驻：**8 GB**（large-v3 FP16 + ctranslate2 workspace）
  - `del` 后：**4.3 GB**（释放 3.7 GB）
- **flash_attention 实测**：ctranslate2 4.8.0 (PyPI latest) + Blackwell sm_120 (RTX 5090) 不支持 — `RuntimeError: Flash attention 2 is not supported` at `faster_whisper/transcribe.py:1446 self.model.generate()`
- **3 条铁律沉淀** — 18s vs 8GB 用户决策优先级 + flash_attention 不加速加载只加速推理 + files= 参数文档有但不能用
- **后续跟踪** — 等 ctranslate2 上游补 sm_120 flash attn 2 内核（GitHub OpenNMT/CTranslate2 当前 0 相关 issue）

## [2026-06-26] v31.2.5 rate-limit 收官（启用 Redis ZSET 持久化）

### 🔒 v31.2.5 启用 AsyncRedisRateLimiter 替换 RateLimiter

- **触发** — v31.2.4 已实现 `AsyncRedisRateLimiter` 类（Redis ZSET 滑动窗口）并通过 7 phase 单元测试，但 `_rate_limiters` 字典里仍是 `RateLimiter`（in-memory dict），新类未接入 middleware
- **commit** — `fix(v31.2.5): 启用 AsyncRedisRateLimiter 替换 RateLimiter (抗 docker restart)`
- **改了什么**：
  - `app/core/rate_limit.py:118-126` 把 5 个 tier 实例全换 `AsyncRedisRateLimiter`
  - `rate_limit_middleware` 把 `limiter.check()` / `limiter.record()` / `len(_attempts)` 全 await 化
  - `remaining` 改用 `await limiter.remaining(key)`（Redis O(1) ZCARD）取代内存 `len(_attempts[key])`
- **关键收益** — 抗 `docker compose restart` 清零（v31.2.0-2.4 内存版一重启全清零，攻击者赶在窗口重置前打满）
- **端到端验证** — [scripts/verify_v31_2_5_restart.py](scripts/verify_v31_2_5_restart.py)：灌 9 次 SSE（ZCARD=9）→ `docker compose restart app` → 重启后第 2 次请求触发 429（旧 9 + 新 1 = 10 ≥ max_attempts）
- **全量回归** — v31.2.1 XFF 空 IP / v31.2.1 nested path / v31.2.2 / v31.2.3 / Redis limiter 5 个 verify 脚本全 PASS
- **4 条新铁律沉淀** — check + record 必须分开 + uvicorn 响应头是小写 + SSE 流式响应必须 raw socket 主动断 + in-memory 限流只适合单进程不重启
- **memory 沉淀** — [memory/rate-limit-redis-2026-06-26.md](memory/rate-limit-redis-2026-06-26.md) reference memory

## [2026-06-26] v31.2.4 rate-limit 进阶（Redis 类 + per-user dashboard + 中文乱码修复）

### 📊 v31.2.4 AsyncRedisRateLimiter 实现 + per-user dashboard

- **commit** — `fix(v31.2.4): AsyncRedisRateLimiter 类实现 + per-user dashboard + 中文乱码修复`
- **AsyncRedisRateLimiter 类** ([app/core/rate_limit.py](app/core/rate_limit.py))：
  - 基于 Redis ZSET 滑动窗口（score=timestamp, value=timestamp str）
  - check 流程：ZREMRANGEBYSCORE 清窗口外 → ZCARD 计数 → ≥ max_attempts 触发 429
  - record 流程：ZADD 新 timestamp + EXPIRE 窗口+1s
  - 优势：抗 docker restart（Redis 默认 RDB 每分钟 snapshot）+ 跨实例共享 + 真实滑动窗口
  - 劣势：多 1 次 Redis round-trip (~1ms) + Redis 不可用时需要 fallback（try/except silent degradation）
- **端到端验证** — [scripts/verify_redis_rate_limiter.py](scripts/verify_redis_rate_limiter.py) 7 phase 全 PASS（ZSET 真在写 + 滑动窗口正确 + 抗 docker restart 模拟）
- **per-user dashboard** — `app/api/v1/analytics.py` 加 `by_user` SQL 聚合（LEFT JOIN members + GROUP BY + HAVING > 0 + ORDER BY searches DESC LIMIT 20），前端 `web/src/views/admin/AnalyticsView.vue` 加用户维度表格（头像 + 姓名 + username + 搜索次数 + 点击次数 + 任何点击率 + 平均位置）
- **中文乱码修复** — `app/core/database.py` 加 `connect_args={"server_settings": {"client_encoding": "utf8"}}` 到 asyncpg engine + `docker compose down app + up -d app` 清连接池（restart 不清池）

## [2026-06-25] v31.2.3 rate-limit 基建收尾（X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配）

### 🛡️ v31.2.3 三件事：policy 头 + SSE tier + auth prefix

- **commit** — `fix(v31.2.3): rate-limit 基建收尾 (X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配)`
- **改 #1: X-RateLimit-Policy 响应头** — 前端能识别触发的 tier（auth/read/upload/sse），用于 tier-aware UX（auth 429 → 跳登录页；read 429 → 降级到缓存）
- **改 #2: SSE 长连接独立 tier** — `sse` tier 10/min（`/api/v1/chat/stream` 一次占用几秒到几分钟，按 read 200/min 只能并发 200 用户，单独给 10/min）
- **改 #3: `/auth/` substring B3 化** — `_is_under_auth(path)` prefix 匹配取代 `"/auth/" in path`（防 `/api/v1/authentication` 等未来路径误中）
- **端到端验证** — [scripts/verify_v31_2_3.py](scripts/verify_v31_2_3.py) 21 case 全 PASS（4 真实 HTTP policy 头 + 9 SSE tier 隔离 + 8 auth prefix 边界）
- **3 条铁律沉淀** — 限流响应头必须有 tier 信息 + SSE 长连接必须独立 tier + 路径前缀匹配用 `startswith(prefix)` 而非 `"/prefix/" in path`

## [2026-06-25] v31.2.2 rate-limit 进阶强化（regex 精确路径 + user_id 维度限流）

### 🔒 v31.2.2 analytics regex 永久化 + user_id 维度

- **commit** — `fix(v31.2.2): rate-limit 进阶强化 (regex 精确路径 + user_id 维度限流)`
- **改 #1: analytics substring → regex 永久化** — `_ANALYTICS_PATH_RE = re.compile(r"^/api/v1/analytics/search-event$|^/api/v1/analytics/search-event/\d+/click$|...")` 锚定 `^...$` + 路径分隔（B3 方案取代 v31.2.1 B1 临时守卫）
- **改 #2: comment drift 修复** — `_get_client_key` 注释说"用 `{ip}:user:{uid}` 维度"但 middleware 从来没解析 token 写 `request.state.user_id` → 新增 `_try_attach_user_id(request)` middleware helper（不查 DB，无效 token 静默忽略）
- **端到端验证** — [scripts/verify_v31_2_2.py](scripts/verify_v31_2_2.py) 12 case 全 PASS（4 analytics regex + 4 user 维度隔离 + 4 真实 HTTP）

## [2026-06-25] v31.2.1 rate-limit 边界强化（XFF 空 IP 兜底 + auth/analytics 嵌套防御）

### 🛡️ v31.2.1 补丁：2 个非阻塞 follow-up 顺手做掉

- **触发** — v31.2 (commit `c2c5066e`) 引入 IP 维度限流 + `/analytics` 豁免 + 可选 auth。端到端 4 边界实测（16 场景全 PASS）发现 2 个非阻塞 follow-up
- **commit** — `fix(v31.2.1): rate-limit 边界强化 (XFF 空 IP 兜底 + /auth/analytics 嵌套防御)`
- **Bug 1 修复** — `app/core/rate_limit.py:156 get_client_ip` 加空 IP 兜底（XFF `", 1.2.3.4"` / `"   "` / `",,,,,"` 全部 → `"unknown"`），防绕过 Nginx 攻击者用空 XFF 共享 200/min 配额 + 7 行 docstring
- **Bug 2 修复** — `app/core/rate_limit.py:72` `/analytics` 分支前置守卫 `not path.startswith("/api/v1/auth/")`，防未来加 `/api/v1/auth/analytics/...` 嵌套路径绕过 `/auth/` 敏感端点 20/min 限流
- **不破坏现有行为** — 4 个现有 analytics 端点（POST search-event / PATCH click / GET stats / GET logs）+ 5 个 auth sensitive 端点 + /auth/me unlimited 全部保留
- **新增 probe 脚本** — [scripts/verify_v31_2_1_xff_empty.py](scripts/verify_v31_2_1_xff_empty.py) + [scripts/verify_v31_2_1_nested_path.py](scripts/verify_v31_2_1_nested_path.py)（纯函数 mock，11 case 全 PASS）
- **2 条新铁律沉淀** — [CLAUDE.md](CLAUDE.md) 新增 "2026-06-25 v31.2.1 rate-limit 边界强化" section：XFF 空 IP 兜底 + substring 路径匹配嵌套排除
- **方案对比** — Bug 2 选 B1（前置守卫）vs B2（后置守卫）vs B3（改精确列表）：B1 改动最小（1 行 if）+ 扩展性最优（未来加 `/api/v1/dashboard/analytics/...` 仍可走原 `/analytics` 分支）+ 不破坏现有行为

## [2026-06-24] sentence-transformers 5.6.0 升级（Phase 1+2 收官，Phase 3 跳过）

### 🎉 P0 升级：跨 3 大版本 ST 升级（29 个月 +）

- **触发** — 原 CLAUDE.md 标"❌ sentence-transformers 升级（未做）"，因 Qwen3 团队用 `include_prompt` 参数 + ST 2.3.1 Pooling 不支持 → 必须用 Qwen3Embedder wrapper 绕开
- **commit** — `c8d4df3e feat(embedding): upgrade sentence-transformers 2.3.1 → 5.6.0 (Phase 1+2 收官)`（已 push main）
- **Phase 1（最小风险）** — `requirements.txt` 升 `sentence-transformers==5.6.0` + 修 1 行 deprecation（`get_sentence_embedding_dimension()` → `get_embedding_dimension()`）
- **Phase 2（用新功能）** — 删 `qwen_embedder.py` (170 行) → 改名 `qwen_embedder_legacy.py` (DEPRECATED 注释保留作 graceful degradation) + `embedding_service.py` 重构为单 ST 路径
- **Phase 3（性能优化）** — 实测 **ONNX 在 GPU 上慢 12-22x**（反优化）→ 主动跳过，保持 torch/GPU
- **关键修复** — Dockerfile 切 PyPI 官方源（清华源限速 torch 2.12+，需 clash 代理 build-arg）
- **收益（vs 原 plan 预估）**：
  - Qwen3 max_seq_length 2048 → **32768** (4x)
  - 删 170 行 wrapper（计划估 130）
  - 单 ST 路径 = 少 bug 表面
  - **0 embedding 错误**
  - qa-bench 50 题：**38% → 42%**（反升 4%，超预期）
- **6 大铁律沉淀** — [CLAUDE.md](CLAUDE.md) 新增 "2026-06-24 sentence-transformers 5.6.0 升级" section：
  - 清华源限速 → PyPI 官方 + clash build-arg
  - docker build env var 污染 → 用 `--build-arg`
  - **ONNX 在 GPU 反优化**（实测数据：torch/GPU 30ms vs onnx/GPU 680ms）
  - ST 跨大版本 3 phase 收官法
  - ST 5.6.0 Pooling `include_prompt` 参数 → Qwen3 native loading 可行
  - Qwen3 native vs wrapper cos 0.999860（实质相同）
- **新文档** — [docs/upgrade-sentence-transformers-plan.md](docs/upgrade-sentence-transformers-plan.md)（完整 plan + 实测结果）
- **新测试** — [tests/test_st5_compat.py](tests/test_st5_compat.py)（8 个 ST 5.6 集成测试，需 `RUN_INTEGRATION=1` 跑）

### 📚 CLAUDE.md 5 大新铁律沉淀（commit `468c2b86`）

- 清华源（pypi.tuna）限速 PyTorch 2.12+ → PyPI 官方 + clash 代理 build-arg
- docker build env var 污染 → 用 `--build-arg` 而非 `ENV`
- ONNX backend 在 GPU 上是反优化（12-22x 慢），不是"2-3x 通用加速"
- ST 跨大版本升级 3 phase 收官法（Phase 1 最小风险 → Phase 2 用新功能 → Phase 3 性能优化）
- ST 5.6.0 Pooling `include_prompt` 参数 → Qwen3 native loading 可行

## [2026-06-24] v29 Qwen3 全量迁移收官（step 3 原子切换）

### 🎉 v29 step 3：embedding 列原子切换（commit `5db74ff3`）

- **背景** — v29 三步走把 embedding 模型从 text2vec-base-chinese (768d) 切换到 Qwen3-Embedding-0.6B (1024d)
- **step 1**（commit `ac29356c`）— GPU 启用 + device 自动检测
- **step 2**（commit `65e612f4` + `641f9cd1`）— Qwen3 wrapper + 双模型 dispatch + alembic 030 双列 + 重算 350/351 条知识
- **step 3**（commit `5db74ff3`）— 原子切换：drop `embedding_v2` 列 + rename `embedding_v2` → `embedding`
- **意义** — 知识库 embedding 全部从 text2vec 升到 Qwen3 1024d，为 ST 5.6.0 升级铺路（同一 session 接着做）

## [2026-06-20~23] v28 论文图片结构化字段 + paper reader 打磨

### 🎉 v28 主体 8 phases 100% 完成

- **Phase 1** — alembic 028 + model + multimodal 集成（12 列 + 2 索引）
- **Phase 2** — schema + API `_to_dict` 加 12 字段
- **Phase 3** — paperAdapter 简化为读后端字段（graceful degradation 保留）
- **Phase 4** — 4 篇 PDF 真实测试验证（37 张图 100% 核心不变量）
- **Phase 5** — 内嵌图 confidence ≥ 0.85 阈值
- **Phase 6** — RightImageRail sectionHint 精准推荐（核心词交集匹配）
- **Phase 7** — IO Hysteresis + rAF 节流（防跳变 + 性能）
- **Phase 8** — article 9 字 bug 修复（深坑：INTERNAL_MARKER_RES line 105 `\bPAGE\s*[:：]\s*\d+\b` 在 `[` 和 word char 之间构边界 → 误删 `[PAGE:N]` → pageMarkers=0 → sections 解析丢分页 → 正文压成 1 段）

### 🛠 v28 step 109.x 持续打磨（40+ commits，2026-06-21~22）

- step 109.30-109.41 paper reader 微调（abstract 提取 / author regex / heading 智能识别 / chemFormat radical 字符集扩展等）
- 最新：`b8d94d4c fix(paper): v28 step 109.41 paragraph 形式子节标题智能识别为 heading`
- **状态**：打磨线**暂停在 109.41**（如无新需求无需继续）

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

### ✅ 主路径修复后第二次重跑验证（2026-06-19 14:40）

修复推到主路径后，再用 `reprocess_meeting.py` 完整跑一次会议 #120：

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

**结论**：修复后 `batch_extract_embeddings` 与手工 ThreadPoolExecutor 行为**完全一致**，证明主路径修复正确。所有未来会议通过 `post_meeting_tasks.py` 自动跑全流程时，无需手动 re-process 即可获得 100% 段有效 + 正确聚类。

- 工具脚本：[scripts/compare_reprocess.py](scripts/compare_reprocess.py) — 前后对比验证脚本

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
