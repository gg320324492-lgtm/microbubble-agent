# MicroBubble Agent - 完善路线图

> 最后更新: **2026-06-13（推进 18 commits）** — 移动端 10 PR 全栈定制收官（PR #1 基建 → PR #10 视觉回归测试）+ Webhook 偶发 499 失败加固（git reset --hard 模式 + socket.timeout(15)）+ webhint meta-theme-color JS 动态注入

## 📋 目录（按时间倒序）

### 最新完成（2026-06-13 移动端收官）
- [📱 移动端 10 PR 全栈定制](#移动端-10-pr-全栈定制2026-06-13-收官)（18 commits：PR #1 基建 → PR #10 视觉回归测试，18 页面 + 12 组件 + 4 PWA 策略 — commit `9026c07` 收官）
- [🛡️ Webhook 偶发 499 失败加固](#webhook-偶发-499-失败加固2026-06-13)（`git reset --hard` 模式 + `socket.timeout(15)` + 手动 redeliver trick — commit `7e41577`）
- [🎨 webhint meta-theme-color 静态 → JS 动态注入](#webhint-meta-theme-color-静态--js-动态注入2026-06-12)（dark mode 主题切换时动态创建 meta — commit `0bbc12d`）
- [📊 项目统计本地 Python 准确化](#项目统计本地-python-准确化2026-06-13)（剔除 .meta/.log/.wav/.gz 等非源代码，965 提交 / 138K 行 / 617 文件 / 29 天）

### 最新完成（2026-06-12 深夜 +1）
- [🚀 多会话并行架构（修复 4）](#多会话并行架构修复-42026-06-12)（per-session 数据隔离 + targetSessionId 闭包 + activeAssistantMap 引用 + 切走不打断后台生成 — commit 662a6ea）
- [🐛 切会话丢数据修复（修复 1）](#切会话丢数据修复修复-12026-06-12)（onSwitchSession 切前 persistMessages 保存当前会话 — commit 662a6ea）
- [🛡️ AbortController 取消旧 SSE 流（修复 2）](#abortcontroller-取消旧-sse-流修复-22026-06-12)（sseFetch 加 signal + per-session abortControllers — commit 662a6ea）
- [♻️ watch(sessionId) 兜底 reload（修复 3）](#watchsessionid-兜底-reload修复-32026-06-12)（外部代码改 sessionId 触发 rebuild — commit 662a6ea）
- [♿ chat `<textarea>` 补 a11y 4 属性](#chat-textarea-补-a11y-4-属性2026-06-12)（id/name/aria-label/title — commit 662a6ea）
- [🐛 RichBlock.type=None Literal 验证失败](#richblocktype-none-literal-验证失败2026-06-12)（17 个 tool schema 默认 None + chat_engine 不分青红皂白构造 — commit 3852755）
- [🐛 search_knowledge Dict 导入缺失](#search_knowledge-dict-导入缺失2026-06-12)（模块加载级 NameError 让整个 hybrid_retriever import 失败 — commit 3852755）
- [🐛 time.monotonic / time.time 混用](#timemonotonic--timetime-混用2026-06-12)（duration_ms=1780984477934 错乱数字 — commit 3852755）

### 最新完成（2026-06-12 深夜）
- [🐛 SSE brief 事件重复输出修复](#sse-brief-事件重复输出修复2026-06-12-深夜)（增量 token + 完整快照塞同 append 分支 — commit cf70ff5）
- [🐛 /chat/stream 404 双层根因：Docker 模块缓存 + 隐藏 NameError](#chatstream-404-双层根因docker-模块缓存--隐藏-nameerror2026-06-12-深夜)（commit 4ba7390 + docker restart）
- [🐛 聊天误显"网络已断开" composable 解构字段名拼写](#聊天误显网络已断开-composable-解构字段名拼写2026-06-12-深夜)（{ isOnline } vs { online } — commit 13ba305）
- [♿ 5 个 file input 补 a11y 4 属性](#5-个-file-input-补-a11y-4-属性2026-06-12-深夜)（id/name/aria-label/title — commit c97071c）

### 最新完成（2026-06-12 晚）
- [🐛 会议查询 bug 双层根因修复](#会议查询-bug-双层根因修复2026-06-12-晚)（`app/agent/core.py:911` UnboundLocalError + LLM 撒谎模式 + prompts.py 工具调用黄金规则）

### 最新完成（2026-06-12 下半场）
- [🎨 webhint CSS @keyframes paint 警告深度治理](#webhint-css-keyframes-paint-警告深度治理2026-06-12)（独立 scale/rotate 替代 transform，8 类 keyframes 10 个文件清理 — 2 commits）
- [🐛 会议详情页 transcriptEntries undefined.length 崩溃修复](#会议详情页-transcriptentries-undefinedlength-崩溃修复2026-06-12)（merge 循环左右两侧都防 undefined）
- [🐛 polish-text 400 空白堆积修复](#polish-text-400-空白堆积修复2026-06-12)（_needsPolish 改用 trim().length 判定 + 双层兜底）

### 最新完成（2026-06-12 上半场）
- [🛡️ 会议录音全栈防御机制 5 阶段完成](#会议录音全栈防御机制2026-06-12)（解决 2026-06-12 会议 #84 案例：58 分钟录音断网丢失 — 5 commits, 21 个新测试, 4 个新字段迁移, 4 个新端点, 1 个孤儿会议清理 job）
- [Vite hash 改 hex 真正消除 webhint cache-busting 误报](#vite-hash-改-hex-真正消除-webhint-cache-busting-误报2026-06-12)（49 条报告清零 — Vite 默认 base64 改 hex）
- [项目统计重新生成](#项目统计重新生成2026-06-12)（914 提交 / 184,955 行 / 638 文件 / 28 天开发）

### 最新完成（2026-06-11）
- [会议 L2 润色 prompt 升级](#会议-l2-润色-prompt-升级2026-06-11)（5 行 "只加标点" → 允许清理幻觉 + 修正同音错字 + 验证放宽至 10% 差异）
- [会议 #83 全文重润色](#会议-83-全文重润色2026-06-11)（532 段 → 323 段，删除 154 段 ASR 幻觉，错名/乱码全部修正）
- [会议转录段落智能切分](#会议转录段落智能切分2026-06-11)（主题信号词自动断段 — 最长 1859 字 → 316 字）
- [前端不合并长同发言人段](#前端不合并长同发言人段2026-06-11)（`MeetingDetailView` 合并阈值改为 60 字 — 1849 字独白切成 ~30 个聚焦卡片）
- [el-tab-pane 加 lazy 修复 ARIA 警告](#el-tab-pane-加-lazy-修复-aria-警告2026-06-11)（8 个 tab-pane 懒渲染 — 消除 ARIA hidden focusable）
- [Nginx /api 安全头修复](#nginx-api-安全头修复2026-06-11)（移除与后端重复的 add_header — webhint 看到唯一 header 不再报 missing）
- [Webhook 自动部署三次修复](#webhook-自动部署三次修复2026-06-11)（根除交付失败 — 移除全局 set -e + 子 shell 隔离统计 + exit 0）
- [项目统计自动更新修复](#项目统计自动更新修复2026-06-11)（deploy-auto.sh 路径修正 + 开发天数动态计算）
- [CSS 动画性能全面优化](#css-动画性能全面优化2026-06-11)（4 轮修复 — GPU Composite 替代 Layout/Paint + PostCSS 剥离 EP keyframes）
- [宠物兔子对话消息修复](#宠物兔子对话消息修复2026-06-11)（watch 任务计数变化 → 消息实时更新）

### 最新完成（2026-06-10）
- [🎉 仪表盘宠物乐园](#仪表盘宠物乐园2026-06-10)（两只 3D 兔子自主走动 + XP 成长进化 + 智能对话 + 互动）
- [项目动态代码分布统计升级](#项目动态代码分布统计升级2026-06-10)（4 类 → 12 类，140,459 行 + 柱状图可视化）
- [ElMessageBox/ElMessage CSS 缺失修复](#elmessageboxelmessage-css-缺失修复2026-06-10)（unplugin 不检测 JS 服务 → 手动导入 CSS）
- [开发天数计算修复](#开发天数计算修复2026-06-10)（git log --reverse --max-count=1 陷阱）

### 最新完成（2026-06-09）
- [知识库 API HTTP/2 协议错误修复](#知识库-api-http2-协议错误修复2026-06-09)（列表去 content + snippet + Nginx proxy buffer）
- [Element Plus 图标全面修复](#element-plus-图标全面修复2026-06-09)（全项目扫描补全 20+ 缺失图标导入）
- [前端性能大幅优化](#前端性能大幅优化2026-06-09)（Nginx gzip + Element Plus 按需导入 + 图标按需，首屏 -84%）
- [项目动态页面](#项目动态页面2026-06-09)（侧边栏入口 + 全页面展示 + 数字动画 + 部署自动更新）
- [听会后台录音 + 全局指示器](#听会后台录音--全局指示器2026-06-09)（录音不中断 + 浮动胶囊 + 自动保存 + sessionStorage 验证）
- [Webhook 自动部署修复](#webhook-自动部署修复2026-06-09)（扫描器正则误杀 /webhook — web$ 精确匹配）
- [Nginx 安全防护](#nginx-安全防护2026-06-09)（恶意扫描器屏蔽 — .env/WordPress/云凭证/攻击路径，444 静默关闭）
- [Docker Desktop 更新](#docker-desktop-更新2026-06-09)（4.73.1 → 4.77.0 + 中文汉化语言包）

---

---

## SSE brief 事件重复输出修复（2026-06-12 深夜）

**问题**：聊天回复内容**完全重复输出两次**（"你好！晚上好，杜同贺...你好！晚上好，杜同贺..."），用户视觉上每次都看到同一段话被复述。

### 根因（一行 bug，事件语义不匹配）

后端 [chat_engine.py](app/agent/chat_engine.py) 流式分支按**两种粒度**发送同样的 brief 文本：

| 行号 | 事件 | delta 字段含义 |
|---|---|---|
| [193-199](app/agent/chat_engine.py#L193-L199) | `text_delta` × N | 每个增量 token（如 `"你"`、`"好"`） |
| [244-245](app/agent/chat_engine.py#L244-L245) | `brief` × 1 | `accumulated_text` —— **完整 brief 文本** |

前端 [ChatViewSSE.vue:215](web/src/views/chat/ChatViewSSE.vue#L215) 旧版把三种事件**一视同仁** `append delta`：

```js
if (evt.type === 'text_delta' || evt.type === 'brief' || evt.type === 'detail') {
  assistantMsg.content += evt.delta || ''
}
```

结果：
- `text_delta` × N 累完: `"你好！晚上好..."`（第一遍）
- `brief` 又 append 完整文本: `"你好！晚上好...你好！晚上好..."`（第二遍）

### 修复（前端 3 分支拆分）

```js
if (evt.type === 'text_delta') {
  assistantMsg.content += evt.delta || ''            // 增量 append
} else if (evt.type === 'brief') {
  // 阶段标记，delta 已被 text_delta 累完，不重复 append
  if (!assistantMsg.content && evt.delta) assistantMsg.content = evt.delta  // 容错降级
} else if (evt.type === 'detail') {
  // detail 是 brief 之后的延伸，用 \n\n 分隔
  if (evt.delta) assistantMsg.content += (assistantMsg.content ? '\n\n' : '') + evt.delta
}
```

**好处**：双轨容错。后端正常发 `text_delta + brief` 走主路径；降级只发 `brief` 也能正确显示；为未来 `_append_detail_background` 通过 SSE 发 detail 预留正确语义。

**沉淀**：[sse-event-semantic-mismatch.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/sse-event-semantic-mismatch.md) — SSE/WS 增量 vs 快照事件混用 = 沉默 bug 家族。Commit `cf70ff5`。

---

## /chat/stream 404 双层根因：Docker 模块缓存 + 隐藏 NameError（2026-06-12 深夜）

**问题**：聊天页发消息后 `ChatViewSSE.vue` 抛 `HTTP 404: {"detail":"Not Found"}`，所有对话失败。

### 双层根因（前一个 bug 掩盖了后一个）

**根因 ①（直接）**：Docker Python 模块缓存失配。
- app 容器启动时间：`2026-06-12 08:43 UTC`（北京 16:43）
- `chat.py` 加 `/chat/stream` 路由的 commit 时间：`2026-06-12 17:55 +0800`
- **代码改在容器启动之后** → volume 挂载让文件可见（`docker exec cat chat.py` 找得到），但 Python 进程只 import 一次 → 路由表停留在 16:43 那一刻
- 决定性证据：`curl /openapi.json | grep chat` 只有 `/chat`、`/chat/file`、`/chat/image`、`/chat/history`，**没有 `/chat/stream`**

**根因 ②（隐藏炸弹）**：`search_tools.py` 缺 `from typing import Optional`。
- `WebSearchOutput` 用 `Optional[str]` 但忘记 import → `NameError: name 'Optional' is not defined`
- v4 收官批量改 `tools/` 时引入，但 app 容器一直没重启过（运行旧版 search_tools.py）→ **模块缓存反过来掩盖了 NameError，潜伏数天没人发现**
- 重启时一次性炸：整个 FastAPI 启动失败 → 所有 `/api/v1/*` 路由 404（不是只有 chat/stream）

### 修复

| Step | 动作 |
|---|---|
| 1 | [app/agent/tools/search_tools.py](app/agent/tools/search_tools.py) 加 `from typing import Optional` |
| 2 | 扫全部 `app/agent/tools/*.py`，无其他同类问题（一行 bash 脚本验证） |
| 3 | `docker compose restart app` → 5 秒返 200 |
| 4 | OpenAPI 确认 `/api/v1/chat/stream` 已注册 |
| 5 | 无 token POST 返 401（认证缺失，路由正常）✅ |

### 教训

1. **「文件可见」≠「模块加载」** — `docker exec cat file.py` 总是最新的，但 Python 进程跑的版本是启动那刻的。改路由/import/装饰器后必须 `docker compose restart`，不只是 celery
2. **模块缓存会反向掩盖 NameError** — 文件改了但没人触发重启 = bug 永远不暴露。v4 这种批量改 tools/ 的 commit 后**必须立即手动重启验证**
3. **怀疑路由 404 时先看 OpenAPI** — `curl /openapi.json | grep /your/route`，没有 = 100% 模块缓存问题

**沉淀**：[docker-python-module-cache.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/docker-python-module-cache.md) — 包含诊断三件套 + 防御纪律 + 扫描 typing import 的 bash one-liner。Commit `4ba7390`。

---

## 聊天误显"网络已断开" composable 解构字段名拼写（2026-06-12 深夜）

**问题**：聊天页面横幅**永远显示**"⚠ 网络已断开，正在等待恢复..."，与实际网络状态完全脱钩（本地开发环境网络是好的）。

### 根因（一行 bug，编译期完全沉默）

[ChatViewSSE.vue:48](web/src/views/chat/ChatViewSSE.vue#L48) 写：
```js
const { isOnline } = useNetworkStatus()
```

但 [useNetworkStatus.js:62](web/src/composables/useNetworkStatus.js#L62) 返回 `{ online, effectiveType, status, pendingCount, setPendingCount }`，**根本没有 `isOnline` 字段**。

后果链：
- `isOnline = undefined`
- 模板 `v-if="!isOnline"` ≡ `v-if="!undefined"` ≡ `v-if="true"`
- 横幅**永远显示**

### 修复（最小改动）

```js
const { online: isOnline } = useNetworkStatus()  // 重命名解构，强迫看一眼源字段名
```

### 对照检查

| 文件 | 写法 | 状态 |
|---|---|---|
| [MainLayout.vue:196](web/src/layouts/MainLayout.vue#L196) | `const network = useNetworkStatus()` + `network.online.value` | ✅ 正确 |
| [AudioRecorder.vue:80](web/src/components/AudioRecorder.vue#L80) | `const network = useNetworkStatus()` + `network.online.value` | ✅ 正确 |
| [ChatViewSSE.vue:48](web/src/views/chat/ChatViewSSE.vue#L48) | `const { isOnline } = ...` | ❌ 已修 |

整体接收 `network` 没踩坑，唯独 ChatViewSSE 解构时凭直觉猜了 `isOnline`（合理但错的命名直觉）。

**沉淀**：更新 [frontend-pitfalls.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/frontend-pitfalls.md) 第 4 条「composable 解构字段名拼写错误」— 跟变量名笔误同源（编译期沉默），但更隐蔽（变量永远 undefined → 模板永远 falsy/truthy → 看起来"功能在跑"但条件永错）。Commit `13ba305`。

---

## 5 个 file input 补 a11y 4 属性（2026-06-12 深夜）

**问题**：webhint + axe 在 `/chat` 页报「Form field element should have an id or name attribute」+「Elements must have labels」。

### 修复（统一 4 属性）

扫全项目 5 个 `type="file"` input 一次性补齐：

| 文件 | input | id / name |
|---|---|---|
| [ChatViewSSE.vue:506-526](web/src/views/chat/ChatViewSSE.vue#L506-L526) | 图片+文件上传（活跃 /chat） | `chat-image-upload` / `chat-file-upload` |
| [ChatView.vue:147-168](web/src/views/ChatView.vue#L147-L168) | 图片+文件上传（v1 回滚版） | `chat-image-upload-legacy` / `chat-file-upload-legacy` |
| [SettingsView.vue:16-25](web/src/views/SettingsView.vue#L16-L25) | 头像上传 | `settings-avatar-upload` |

每个 input 补 4 属性：
- `id` + `name` — 满足 webhint「form field needs id or name」+ 浏览器 autofill 友好
- `aria-label` — 满足 axe「elements must have labels」（hidden input 无法走可见 label 路径）
- `title` — webhint 兜底

每个 id 全局唯一（legacy 后缀避免与 SSE 版冲突，浏览器 autofill 不串）。Commit `c97071c`。

---

## 会议查询 bug 双层根因修复（2026-06-12 晚）

**问题**：用户问"有没有相关会议可以学习？"AI 助手回复"会议查询系统暂时无法正常工作"或"数据库中暂无相关记录"。但直接 `curl GET /api/v1/meetings` 验证：API 返回 200 OK，数据库有 7 条会议（IDs 85/83/71/70/68/...）。

### 两层根因

**根因 ①（提示层）**：`prompts.py` 系统提示词**只对 `query_all_member_tasks` 有"必须调用"规则**，`query_meetings` 等其他 10+ 个工具没有强指令。LLM 遇到模糊查询时倾向**自己编造借口**（"系统故障/技术问题/数据库暂无"），而不是老老实实调工具。

**根因 ②（代码层）**：`app/agent/core.py:911` 在 `_execute_tool` 函数内（属于 `summarize_meeting_transcript` elif 分支）有 `from app.services.meeting_service import MeetingService`，Python 编译器**不区分 elif 分支**会扫描整个函数体，看到这个名字就是 local。导致 line 881 `MeetingService(db)` 抛 `UnboundLocalError: cannot access local variable 'MeetingService' where it is not associated with a value`，被外层 `except Exception` 吞掉返回 `{"status":"error","message":"工具 query_meetings 执行失败: ..."}`，LLM 看到这个 error 后又撒谎说"系统故障"。

**这与 CLAUDE.md 已记录的 2026-06-02 声纹会议 WS 闪烁根因（`import asyncio` 函数体内让 Python 把 `asyncio` 当局部变量）是完全相同的一类坑。**

### 三处修复

1. **`app/agent/core.py:911`** — 删除冗余 `from app.services.meeting_service import MeetingService`（顶部 line 16 已有 import）
2. **`app/agent/prompts.py`** — 顶部新增「工具调用黄金规则 (CRITICAL)」+ 明确「Meeting Query Rules (IMPORTANT)」列出所有触发短语 + 严禁编造借口话术
3. **`app/agent/tools.py:147`** — `query_meetings` 描述改为「【必调工具】」+ 列举触发短语（"最近的会议/近期组会/有哪些会议/查会议/会议纪要/有什么会议/哪些会议可以学习/上次会议讲了什么/今天/昨天/上周/本月开过什么会/UV相关会议/远紫外会议/开过哪些学术报告"等）

### 调试过程（值得记录）

1. **直接调 API 验证后端真伪** — `curl GET /api/v1/meetings` 返回 200 + 7 条会议 → 100% 是 LLM 提示层问题，不是后端
2. **添加调试日志** — `_process_response` 加 `logger.warning(f"[DEBUG] tool={name}, input={input_data}")`，`_execute_tool` 顶层加 `[DEBUG-EXEC]`，每个 tool 分支加 `[DEBUG-XYZ]`，外层 except 加 `logger.error(..., exc_info=True)`。3 行日志发现 SQL 日志中**没有 `FROM meetings` 查询**但 `[DEBUG]` 显示 LLM 调了 `query_meetings` → 锁定 `query_meetings` 分支根本没执行
3. **捕获 `UnboundLocalError` 异常** — `logger.error` 显示 `tool=query_meetings failed: UnboundLocalError: cannot access local variable 'MeetingService' where it is not associated with a value` → 锁定根因 ②

### 验证结果

| 测试问句 | 修复前 | 修复后 |
|---|---|---|
| "有没有相关会议可以学习？" | "会议查询系统暂时无法正常工作" + 编造 6 类"获取会议信息的途径" | 真的返回 6+ 场会议（远紫外 #85 学术报告、UV臭氧纳米气泡、臭氧气泡实验、实验数据排查、小气助手适配性测试、持续研究UV臭氧纳米气泡技术）+ 每条给学习价值评级 + 适合学习的方向 |
| "查一下最近的会议" | "数据库中暂无相关记录" | 真的返回 7 条会议按时间倒序 |
| "2026年6月5日到6月10日开过哪些会议" | （未测） | 准确返回 4 场日期范围内会议 + 发言人姓名（周之超、贾琦、杜同贺、陈金薪）真实 |
| SQL 日志 `FROM meetings` | 0 次（工具执行 UnboundLocalError 被 except 吞掉） | 真实执行，返回 `result_count=7, ids=[85, 83, 71, 70, 68]` |
| 异常日志 | `UnboundLocalError: cannot access local variable 'MeetingService'` × N 次 | 0 次 |

### 教训（重要，三条规则）

1. **模块顶部已 import 的名字，函数体内绝不要** `from X import Y` 重新导入 — Python 编译器会把整个函数的同名变量都当 local，导致任何 elif 分支使用同名全局变量都 `UnboundLocalError`。如果函数体内必须 import 用 `from app.X import Y as _Y` 重命名
2. **LLM 撒谎模式防御** — 遇到工具错误，LLM 倾向用 "系统故障/技术问题/数据库暂无/请联系管理员" 搪塞。**所有高频 tool 必须在 `prompts.py` 顶部"工具调用黄金规则 (CRITICAL)" section 显式列出"必须调用"** + 工具描述中标注「【必调工具】」+ 列举触发短语。`query_all_member_tasks` 有规则 → 调；`query_meetings` 没规则 → 拒绝调工具编借口
3. **遇到"AI 说系统坏了"先 `curl` 直接调 API 验证后端真伪** — 绕过 LLM 直接验证后端永远是最快定位"是 LLM 问题还是后端问题"的方法。后端正常 → 100% 是 LLM 提示层问题，不必查后端代码

---

## webhint CSS @keyframes paint 警告深度治理（2026-06-12）

**问题**：Edge DevTools 内置 webhint 报 40+ 条 `'transform' changes to this property will trigger: 'Paint', which can impact performance when used inside @keyframes` 警告，覆盖几乎所有用 `transform` 做动画的 keyframes — `pulse` / `done-bounce` / `confetti-fall` / `mic-pulse-ring` / `spin` / `dot-pulse` / `recording-pulse` / `logo-pop-in` / `rotateIn` / `drawer-slide-*` / `fadeSlideUp` / `slideDownFade` / `slideRightFade` / `el-skeleton-loading` / `msgbox-fade-in` / `dialog-fade-*` / `rotating` 等。

**关键发现**（读 hint 源码 `packages/hint-detect-css-reflows/src/{paint.ts,assets/CSSReflow.json}`）：

| CSS 属性 | paint 标记 | layout 标记 | webhint 判定 |
|----------|----------|----------|----------|
| `transform`（含 `scale()`/`rotate()`/`translate()` 函数） | **true** | false | ⚠️ paint 警告 |
| `translate`（独立属性） | **true** | **true** | ⚠️ paint + layout（更糟）|
| `scale`（独立属性） | **不在 JSON 里** | 同 | ✅ 通过 |
| `rotate`（独立属性） | **不在 JSON 里** | 同 | ✅ 通过 |
| `opacity` | false | false | ✅ 通过 |

**关键约束**：
1. `will-change` 完全不被该 hint 考虑（只扫 keyframes 内属性名，不看元素声明），加 `will-change: transform` 无用
2. 独立 `translate:` 属性比 `transform: translate()` **更糟**，会额外加 layout warning
3. **CSS Transform Module Level 2** 的独立 `scale:` / `rotate:` 属性（2022 年起全浏览器原生支持）是 webhint 公认的干净绕开方案

**两轮修复**：

**第一轮（commit `d25ab05`）— 5 类纯 scale 动画 7 个文件**：
- `ProcessingDialog.vue` — `done-bounce`：`transform: scale()` → `scale:`
- `VoiceTestDialog.vue` — `pulse` / `mic-pulse-ring` / `spin`：`transform: scale/rotate` → `scale:` / `rotate:`
- `MeetingView.vue` / `MeetingDetailView.vue` / `meeting/MeetingStats.vue` — `dot-pulse`：`transform: scale()` → `scale:`
- `UploadStatusBadge.vue` / `VoiceprintEnrollDialog.vue` — `pulse`：`transform: scale()` → `scale:`
- `assets/variables.css` — 全局 `pulse`：`transform: scale()` → `scale:`

**第二轮（commit `9baeb18`）— 3 个剩余清洁 keyframes**：
- `variables.css` — `rotateIn`：`transform: rotate() scale()` 组合 → `rotate:` + `scale:`（拆开两个独立属性都清洁）
- `MainLayout.vue` — `logo-pop-in`：`transform: scale()` → `scale:`
- `MainLayout.vue` — `recording-pulse`：`transform: scale()` → `scale:`

**保留的（webhint 规则本质约束，无清洁替代）**：
- `confetti-fall` — translateY + rotate（位移本质 paint）
- `mb-progress` / `mb-striped-flow` / `mb-indeterminate`（进度条条纹）
- `el-skeleton-loading` / `shimmer`（骨架屏闪烁）
- `fadeSlideUp` / `slideDownFade` / `slideRightFade`（滑入入场）
- `msgbox-fade-in` / `dialog-fade-in/out`（EP 弹窗）
- `drawer-slide-in/out` / `brand-text-in`（移动端抽屉）
- `drawer-item-in/out` / `banner-in/out`（抽屉项 + 横幅）
- `rotating`（EP 旋转图标）

这些动画的核心视觉都是位移（translate/translateY/translateX）或在键帧内伴随位移，webhint 把所有位移属性都标 paint/layout，没有"位移但不 paint"的替代写法。改用 `top`/`left`/`margin` 是 layout 触发，更糟；改用 opacity-only 失去位移效果。**接受为已知 webhint 保守判定**。

**效果**：~46 条 paint 警告中 ~6 类（约 12-16 条）被消除，剩余 ~30 条为 translate 类，已文档化。

**memory**：[webhint-paint-keyframes](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/webhint-paint-keyframes.md) 固化 CSSReflow.json 关键映射表。

---

## 会议详情页 transcriptEntries undefined.length 崩溃修复（2026-06-12）

**线上报错**：
```
MeetingDetailView-f2164f98.js:1
Uncaught (in promise) TypeError: Cannot read properties of undefined (reading 'length')
    at Sn.fn (MeetingDetailView-f2164f98.js:1:4632)
```

**根因**：[MeetingDetailView.vue:420](web/src/views/MeetingDetailView.vue#L420) `transcriptEntries` computed 中合并循环：

```js
if (
  entry.speaker === current.speaker &&
  !entry.removed &&
  (current.text.length + (entry.text?.length || 0)) < MERGE_THRESHOLD_CHARS  // ← 这里
)
```

`entry.text?.length || 0` 只防了右边，左边 `current.text.length` 直接读 — 当 transcript 条目缺 `text` 字段（如纯静音 ASR 返回 null）时，`current.text` 为 `undefined`，立刻爆。

**4 处防御**（commit `0470f55`）：
1. 初始 `current` 强制 `text: raw[0].text || ''`
2. 阈值比较左右两侧都 `?.length || 0` 兜底
3. 字符串拼接两侧都 `|| ''` 防 `'undefined undefined'`
4. else 分支新建 current 同样强制 `text: entry.text || ''`

---

## polish-text 400 空白堆积修复（2026-06-12）

**线上日志**：
```
POST /api/v1/meetings/85/polish-text 400 (Bad Request)  ×2
```

**Bug 链**（上次修复引入的回归）：
1. transcriptEntries 修复时把 `raw[0].text || ''` 默认为空串
2. 同一发言人多个空 text 条目连续 merge 时累加 `'' + ' ' + ''` 全是空格
3. 21 个连续空 text → merged 是 21 空格，`length > 20` 通过 `_needsPolish`
4. 后端 `polish-text` 要求 `strip().length >= 3`，21 空格 strip → 0 字 → 400

**3 处防御**（commit `6fea262`）：
1. **源头** — `_needsPolish` 改用 `trim().length > 20`（不是裸 length），纯空格条目不再标记
2. **自动润色 `autoPolishIfNeeded`** — 发送前再校验 `trim().length >= 3` 兜底
3. **手动按钮 `polishMergedText`** — 同样 trim 校验 + `ElMessage.warning('文本太短，无需润色')` 提示

**经验**：修复 undefined 崩溃时引入的"空串默认值"会在串接场景累积，凡是字符串聚合操作都要在源头过滤空内容（不是聚合后再过滤）。

---

## Vite hash 改 hex 真正消除 webhint cache-busting 误报（2026-06-12）

**问题**：Edge DevTools 内置 webhint 报告 49 条 `Resource should use cache busting but URL does not match configured patterns`，覆盖全部 `/assets/*` 文件（`index-Qec9lxup.css`、`MainLayout-B6AkdWtm.js`、`useRecordingState-DFmcezhN.js` 等）。这些文件都包含 Vite content-hash，本来就是标准缓存破坏方案，但 webhint 内置正则只认 `[0-9a-f]+` 小写 16 进制。

之前 [[vite-hex-hash]] MEMORY 误判为"浏览器端无法消除"（因为 `.hintrc` 配置文件在 Edge 内置 webhint 中不生效），实际上**从工具链上游（Vite 配置）改**就能彻底消除。

**根因**：Vite 8 默认 `output.hashCharacters: 'base64url'`，产出形如 `Qec9lxup`/`B6AkdWtm`（含大小写字母+数字+下划线+连字符），被 webhint 全部拒绝。

**修复**：[web/vite.config.js](web/vite.config.js) 加：

```js
build: {
  rollupOptions: {
    output: {
      hashCharacters: 'hex'
    }
  }
}
```

Rollup 4.x 原生支持 `hashCharacters` 选项（`'base64' | 'base36' | 'hex'`），设 `hex` 后产出 `9ab8129c`/`1079cf65` 等全小写 16 进制，webhint 通过。

**验证**：
- 构建前文件：`index-Qec9lxup.css` / `MainLayout-B6AkdWtm.js` / `useRecordingState-DFmcezhN.js`
- 构建后文件：`index-1079cf65.css` / `MainLayout-b56ff566.js` / `useRecordingState-a27a6772.css`
- `curl https://agent.mnb-lab.cn/` 验证 index.html 引用的文件名已是 hex 格式
- `curl -I https://agent.mnb-lab.cn/assets/index-9ab8129c.js` 验证响应头：`Cache-Control: public, max-age=31536000, immutable` + `X-Content-Type-Options: nosniff`

**效果**：
- 49 条 cache-busting 报告全部清零
- 文件名长度不变（8 字符 hex），CDN/浏览器缓存效果一致
- CDN 兼容性更好（小写 hex 是最通用的命名约定）

**教训**：不要被"工具限制"标签固化思路。遇到工具误报时优先考虑：
1. **工具链上游**：构建工具/CDN/响应头是否可调整
2. **响应头**：Nginx/后端中间件是否可加
3. **配置**：本地 `.hintrc` 能否覆盖（但 Edge 内置不读）
4. **接受误报**：最后才考虑

之前 MEMORY 错把 webhint cache-busting 归类为"必须接受"，实际工具链改造就能消除。

---

## 项目统计重新生成（2026-06-12）

| 维度 | 数值 |
|------|------|
| 总提交 | 902（commit `6339c29`）|
| 总文件 | 628 |
| 总行数 | 172,776 |
| 开发天数 | 27 天（2026-05-16 ~ 2026-06-12）|
| Python | 53,896 行（227 文件）|
| Vue | 23,790 行（86 文件）|
| JavaScript | 4,527 行（44 文件）|
| Markdown | 68,747 行（182 文件，含 docs/skills/memory）|
| Config | 13,083 行（45 文件）|
| HTML | 3,597 行（9 文件）|
| Shell | 2,547 行（21 文件）|
| CSS | 976 行（3 文件）|
| 其他 | 1,249 行（9 文件）|
| SQL | 206 行（1 文件）|
| TypeScript | 158 行（1 文件）|
| Docker | 0 行（无 Dockerfile — 部署用云服务器+本地 docker-compose）|

统计脚本：`scripts/deploy-auto.sh` 末尾子 shell 段，`( ... )` 隔离错误不影响部署。stats.json 写入 `$PROJECT_DIR/app/stats.json`（Docker volume `./app:/app/app` 挂载范围，容器内 `/app/app/stats.json` 可读）。

API 端点：`GET /api/v1/dashboard/project-stats`（Redis 缓存 10min）→ 动态计算 dev_days + 静态数值。

**How to apply**：
- 每次 push 后 webhook 触发 `deploy-auto.sh` 自动重生成 stats.json
- 手动重生成：复制 deploy-auto.sh 的子 shell 段到本地执行
- 路径必须在 `app/` 内，否则容器内 Python 读不到

---

## 🛡️ 会议录音全栈防御机制（2026-06-12）

**事故**：2026-06-12 会议 #84，用户录音 58 分钟，结束时 `axios.post(/upload-audio)` 因 network error 失败。`useGlobalRecorder.js` 的 `audioChunks[]` 纯内存累积，Blob 在弹窗销毁后物理丢失，仅 MinIO 残留 1.6 秒废片段，Whisper 返回 0 段。会议永久卡 `completed`（实际无内容）。用户主动删除 #84 后基于转录文字人工重建为 #85（徐佳乐博士学术报告）。

**5 阶段修复（5 commits）**：

| 阶段 | 内容 | 关键文件 |
|------|------|---------|
| **1** | 前端 IndexedDB 兜底 + 边录边传骨架（1.5 天） | `web/src/utils/idbStore.js`, `useChunkedRecorder.js`, `useChunkedUploader.js` |
| **2** | 上传状态徽章 + NetworkStatus 接入（0.5 天） | `web/src/components/UploadStatusBadge.vue`, `AudioRecorder.vue`, `MainLayout.vue` |
| **3** | 后端 chunked 端点 + 状态机字段 + 迁移（1 天） | `app/services/chunked_upload_service.py`, `meeting_recording.py` |
| **4** | 后端 stop-recording 校验 + Celery 真实重试 + 孤儿清理 + 删会议清 MinIO（0.5 天） | `post_meeting_tasks.py`, `orphan_meeting_cleanup.py`, `meeting.py` |
| **5** | 端到端测试 + 修复 1 个 bug（1 天） | `delete_chunks` 误删 merged.webm → 拆为 `delete_chunks` / `delete_merged` / `delete_all` |

### 防御场景覆盖矩阵

| 失败场景 | 防御层 | 行为 |
|----------|--------|------|
| 录音中浏览器刷新 | 阶段 1 IDB 持久化 | chunks 留 IndexedDB，重连自动补传 |
| 录音中断网 | 阶段 1 chunks 留 IDB + online 事件 | 网络恢复时 `online` 事件触发自动重传 |
| 上传 5xx 失败 | 阶段 1 指数退避（1s→2s→4s→8s→16s, max 5） | 前端 retry，IDB 标记不更新 |
| 上传 4xx 失败 | 阶段 1 不重试 | 立即抛错，前端停止后续 chunk |
| stop-recording 时无 chunk | 阶段 4 硬校验 | 400 + 详细错误，会议保持 recording |
| Celery 后处理 MinIO 瞬时不可用 | 阶段 4 `self.retry(exc=e, countdown=60)` | Celery 真实重试 3 次（之前 `max_retries` 形同虚设）|
| 孤儿会议 recording > 1h 无 chunk | 阶段 4 `orphan_meeting_cleanup` 10min 扫描 | 标 error + 推 WS + 清 MinIO |
| 删会议 MinIO 残留 | 阶段 4 `delete_meeting` 先调 `chunked_upload_service.delete_all` | chunks + merged.webm + 旧版 audio_url 全清 |

### 新增端点（`app/api/v1/meeting_recording.py`）

| 方法 | 路径 | 用途 |
|------|------|------|
| `PUT` | `/meetings/{id}/audio-chunk?chunk_index=N` | 接收单个分片（5s 一片），写 MinIO `recordings/{id}/chunks/chunk_NNNNN.webm` |
| `POST` | `/meetings/{id}/merge-chunks` | 合并所有 chunks 成完整 webm（ffmpeg concat demuxer, `-c copy` 保编码），写 `recordings/{id}/merged.webm` |
| `GET` | `/meetings/{id}/upload-status` | 查询分片上传状态（前端刷新页面后恢复使用）|

### 新增 Meeting 字段（手动 ALTER TABLE 迁移）

```sql
ALTER TABLE meetings
  ADD COLUMN upload_status VARCHAR(20) DEFAULT 'pending',  -- pending/uploading/completed/failed/never_uploaded/partial
  ADD COLUMN last_chunk_index INTEGER DEFAULT -1,            -- -1 表示无 chunk
  ADD COLUMN total_chunks INTEGER,
  ADD COLUMN error_reason TEXT;
```

### 关键设计决策

1. **Timeslice 1s 而非 5s**（计划中提出 5s）— 实际保留 useGlobalRecorder 原有的 `mediaRecorder.start(1000)` 每 1s 切片，与原代码兼容。Chunks 5KB ~ 50KB 量级
2. **Blob 序列化兼容性** — fake-indexeddb 在 jsdom 中反序列化 Blob 为普通对象，需在 `idbStore.putChunk` / `getPendingChunks` 重新包装为 `new Blob([obj], { type: 'audio/webm' })` 否则 `FormData.append` 抛 `parameter 2 is not of type 'Blob'`
3. **fake-indexeddb 不支持复合索引** — 取消 `by_meeting_uploaded` 复合索引，改用 `by_meeting` 单字段 + 内存 filter
4. **Celery self.retry 必须 raise** — 在新 event loop 中 `try/except` 接住后会**阻断** Celery 重试机制，必须 `raise self.retry(exc=e, countdown=60)` 让 Celery 装饰器接住
5. **delete_chunks 不能"顺手删 merged"** — 阶段 5 端到端发现此 bug：merge-chunks 完成后调 delete_chunks 清理源 chunks，但旧版 delete_chunks 内部又删了 merged.webm，导致后处理 NoSuchKey。修复为三个方法：`delete_chunks` / `delete_merged` / `delete_all`

### 测试

- **vitest**：21 个新测试（idbStore 12 + useChunkedUploader 9），全部 59 个测试通过
- **E2E**：3 个真实 5s 静音 webm (27KB each) → PUT → merge → MinIO 出现 merged.webm (80KB) → stop-recording → Celery 成功处理 → meeting status=completed

### 复用现有资产（不要重新造）

- `useNetworkStatus.js`（已实现，0 改动直接 import）— 上线时首次接入
- `useGlobalRecorder.js` 的 `timeslice(1000)` 单例模式 + 阶段 1 新增 `onChunk` 回调钩子（向后兼容）
- `KnowledgeUploadDialog.vue:84-99` 的 catch 错误分类模板
- `reminder_service.process_reminders_task` 的 Celery NullPool event_loop 模式
- `useRecordingState.js` 的 "本地缓存 + 后端校验"双保险模式

### 相关 commits

```
9464726 fix(recording): delete_chunks 误删 merged.webm
838a18d feat(recording): 阶段4 — 后端防御硬化
f458dad feat(recording): 阶段3 — 后端 chunked 端点 + 状态机字段
49de30c feat(recording): 阶段2 — 上传状态徽章 + 网络状态接入
a41dd20 feat(recording): 边录边传骨架 (阶段1) — IndexedDB 兜底 + 指数退避重传
```

---

## 会议 L2 润色 prompt 升级（2026-06-11）

**问题**：L2 聚批润色 prompt（`app/services/prompts/meeting_polish.py`）仅 5 行规则："只加标点、不改内容、不删任何内容"。Whisper 幻觉（YouTube 结束语/字幕组声明/版权信息）、同音错字（"杨词→杨慈"）、重复短句 全部原样保留。同时 `_is_punctuation_only_edit` 验证层会强制回退任何改写，即使合理修正。

**修复**：
- **prompt 升级**：允许 4 类操作 — 加标点 / 删孤立幻觉 / 修明显同音错字（≥95% 字符保留）/ 合并连续重复。明确禁改写、禁增删实质信息、禁改人名。
- **验证层放宽**：`_is_punctuation_only_edit` → `_is_reasonable_edit`，容忍 10% 字符差异或子串匹配。**支持 `removed` 数组**：被删除段不进 polished 但记录 reason。
- **新增 `scripts/repolish_meeting_83.py`**：用 L3 prompt 一次性重润色会议 #83（拆分到 11 个 chunk 并发调 LLM）。
- **新增 `scripts/fix_summary_83.py`**：用 polished 内容重生成会议 summary（修复"全是 ASR 结束语"错误总结）。

**效果（会议 #83）**：
- 532 段 → 323 段（删除 154 段 ASR 幻觉）
- 残留错名/乱码（周之超/王书馨/杨词/优惠价值外/弹牛/游击/丑阳雅雄）全部清零
- key_points 从 12 → 30 条（全部准确）
- summary 从错误结论修正为正确总结

**文件**：
- `app/services/prompts/meeting_polish.py` — 新 L2 prompt
- `app/services/meeting_ai_polish.py` — 验证放宽 + removed 数组
- `scripts/repolish_meeting_83.py` — 一次性重润色脚本
- `scripts/fix_summary_83.py` — summary 重生成

---

## 会议 #83 全文重润色（2026-06-11）

使用新 L2 prompt 对会议 #83「持续研究UV臭氧纳米气泡技术」（2026-06-11 03:53-04:13，20分29秒）做完整重润色。

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| 总段数 | 532 | 323（删除 154 段幻觉）|
| 发言人误识 | 周之超（425段）/ 王书馨（2段）| 王天志（430段）/ 杨慈（2段）|
| Whisper 残留 | MINGPAO CANADA ×N, 中文字幕志愿者 ×N, 试镜需要您的支持 | **全部清零** |
| ASR 乱码 | 优惠价值外 / 弹牛方向 / 游击的 / 丑阳雅雄 | **全部修正** |
| 错名 | 杨词 / 周之超 / 王书馨 | 杨慈 / 王天志 / 王天志 |
| key_points | 12 条（含乱码）| 30 条（全部准确）|
| summary | 错误（"全是 ASR 幻觉"）| 正确（UV 臭氧纳米气泡技术持续研究）|

**修复链路**：
1. 改 speaker_mapping / transcript / polished JSON（周之超→王天志 等）
2. 改参会人表（删除周之超 22，改王书馨 14→杨慈 18）
3. 调 L3 prompt（带 removed 数组支持）跑 11 个 chunk
4. 手动重生成 summary
5. 清理最后残留"感谢观看"

**前端效果**：刷新 `https://agent.mnb-lab.cn/meetings/83` 即可看到干净的转录、正确的参会人、30 条准确要点。

---

## 会议转录段落智能切分（2026-06-11）

**问题**：后端 L3 润色输出后，前端 `MeetingDetailView.vue` 的 `transcriptEntries` computed 把所有连续同发言人段合并成一个超长卡片。1859 字一整块王天志独白压垮阅读体验。

**修复**：`scripts/split_meeting_paragraphs.py`（commit `a487a33`）

按主题信号词自动切段：
- `但是/不过/然而` — 转折
- `那[么是]?/所以/因此/总之` — 推论/总结
- `另外/还有/同时/接着/然后/接下来` — 并列/递进
- `我举个例子/比如说/换句话说/也就是说` — 例证
- `明白吗/对吧/是吧` — 修辞问句（话题切换）
- `第一/第二/第三` — 列表
- `此外/首先/其次/再者/最后` — 列举
- `[一二三四五六七八九十]+、` — 中文列表

短段（<30字）+ 同发言人 → 自动合并避免碎片化。

**效果（会议 #83）**：
- 48 → 64 段
- 最长段 1859字 → 316字
- 平均段长 76字

**用法**：`python scripts/split_meeting_paragraphs.py 83`

---

## 前端不合并长同发言人段（2026-06-11）

**问题**：后端已切分到 64 段，但前端 `web/src/views/MeetingDetailView.vue:415` 显式 `current.text += ' ' + entry.text` 把所有连续同发言人段合并成一个超长卡片。

**修复**：合并阈值改为 60 字
- 短段（"嗯" + "是"）继续合并
- 长段（每段 ≥ 60字）保持独立

**效果**：
- 转录卡片从 ~10 个 → **~30 个聚焦卡片**
- 王天志 1859 字独白 → 16 个主题段落
- 主题切换清晰可见

**文件**：
- `web/src/views/MeetingDetailView.vue` — 合并阈值常量
- `web/dist/` — 重新构建并 commit

---

## el-tab-pane 加 lazy 修复 ARIA 警告（2026-06-11）

**问题**：Element Plus 的 `el-tab-pane` 默认渲染所有 tab 内容，未激活的 tab 设了 `aria-hidden="true"` + `display: none`，但里面的可聚焦元素（按钮/输入框/头像）依然在 DOM 里。触发 axe/webhint "ARIA hidden element must not contain focusable elements" 警告。

**修复**：为 8 个 `el-tab-pane` 加 `lazy` 属性（懒渲染），未激活时不创建内容：

| 文件 | tab-pane |
|------|----------|
| `MeetingDetailView.vue` | 会议纪要 / 转录记录 / 发言统计 |
| `TaskView.vue` | 任务列表 / 垃圾桶 |
| `KnowledgeView.vue` | 知识库 |
| `VoiceprintEnrollDialog.vue` | 麦克风录制 / 上传音频文件 |

之前已经加 lazy 的（实体图谱/科研假设/公式计算）保持不变。

**效果**：webhint 扫 `/meetings/83` 时 ARIA hidden 警告消失。

---

## Nginx /api 安全头修复（2026-06-11）

**问题**：Nginx `/api` location 块（`nginx/conf.d/tunnel.conf`）加的 `add_header X-Content-Type-Options / Cache-Control / Referrer-Policy / X-Request-ID` 与后端中间件（`app/main.py security_headers`）**完全重复**。响应里同时存在小写（后端）和 PascalCase（Nginx）两份 header，webhint 解析时遇到重复 header 判定为 "missing or empty"。

**修复链路**：
- `415a674` Nginx 加 add_header（首版）
- `29982a4` 移除 Nginx 重复 add_header（仅保留后端中间件作为唯一来源）

**验证**（curl 实测阿里云服务器）：
```
x-content-type-options: nosniff      ✅ 唯一
cache-control: max-age=0             ✅ 唯一
referrer-policy: strict-origin-when-cross-origin  ✅
x-request-id: ...                   ✅
```

webhint 扫 `/api/v1/meetings/{id}/polish-text` 时 x-content-type-options 和 cache-control 警告都消失。

---

## 项目统计自动更新修复（2026-06-11）

**问题**：项目动态页面显示的数据始终不更新（857 提交/140K 行），实际项目已 891 提交/181K 行。

**根因链**：
1. `deploy-auto.sh` 写 stats.json 到项目根目录，但 API (`dashboard.py`) 从 `app/stats.json` 读取 — 路径不匹配
2. Docker volume 只挂载 `./app:/app/app`，根目录 stats.json 在容器内不可见
3. `dev_days` 用整数除法截断，首提交在晚上 22:37，完整 24h 周期数偏少 1 天
4. `dev_days` 写死在 stats.json 里，只有部署时才更新

**修复方案**：
- `deploy-auto.sh`: `STATS_FILE="$PROJECT_DIR/stats.json"` → `"$PROJECT_DIR/app/stats.json"`
- `deploy-auto.sh`: `DEV_DAYS` 计算改为 `(diff + 86399) / 86400`（ceil 除法）
- `dashboard.py`: 新增 `first_commit_date` 字段，API 每次请求动态计算 `dev_days`，Redis 缓存 TTL 缩短到 10 分钟
- 本地重新生成 `app/stats.json`：891 提交/181,311 行/678 文件/26 天

**效果**：开发天数每天自动递增，不依赖部署频率。

**文件**：
- `scripts/deploy-auto.sh` — 路径修正 + ceil 除法
- `app/api/v1/dashboard.py` — 动态 dev_days 计算
- `app/stats.json` — 最新统计数据

---

## CSS 动画性能全面优化（2026-06-11）

**问题**：webhint 报告多个 CSS 动画在 `@keyframes` 中使用 `margin-top`/`left`/`background-position`/`box-shadow`，触发 Layout 或 Paint。

**4 轮修复**：

1. **第 1 轮（`5b2471b`）** — 组件级动画：
   - `DashboardPet.vue`: `pet-walk` `margin-top` → `transform: translateY()`，新增 `.bunny-body` wrapper 隔离定位 transform
   - `Dashboard.vue`: `pet-sun-glow` `box-shadow` → 静态阴影 + `opacity` 动画
   - `variables.css`: `shimmer` `background-position` → `::after` 伪元素 + `transform: translateX()`
   - `.skeleton` 改为 `overflow: hidden` + `::after` 滑过渐变

2. **第 2 轮（`c59413f`）** — Element Plus keyframes 被覆盖问题：用 `mb-*` 前缀（`mb-progress`/`mb-striped-flow`/`mb-indeterminate`）+ `!important` 强制覆盖 EP 元素 animation-name

3. **第 3 轮（`94dff5d`）** — PostCSS `stripEpProgressKeyframes` 插件构建时剥离 EP 原版 keyframes，从源头消除 webhint 警告

4. **第 4 轮（`0fc6666`）** — `KnowledgeDashboard.vue` `skeleton-loading` `background-position` → `::after` + `transform: translateX()`

**效果**：webhint CSS 性能警告全部清零（除第三方库不可修改的少量残余）。

**文件**：
- `web/src/components/DashboardPet.vue` — bunny-body wrapper + transform
- `web/src/views/Dashboard.vue` — sun-glow opacity
- `web/src/assets/variables.css` — skeleton/shimmer 伪元素
- `web/src/assets/element-plus-overrides.css` — mb-* keyframes
- `web/src/components/knowledge/KnowledgeDashboard.vue` — skeleton-loading
- `web/vite.config.js` — PostCSS stripEpProgressKeyframes

---

## Webhook 自动部署三次修复（2026-06-11）

**问题**：继 2026-06-09 扫描器正则误杀修复后，webhook 部署仍持续失败。GitHub webhook 交付断断续续标红，部署日志报非零退出码。

**根因链**：
1. `set -e` 全局生效 → `find` 无结果时 `xargs wc -l` 返回非零 → 脚本提前退出
2. 统计函数中用 `$EXCLUDE_DIRS` 字符串展开 → `*/node_modules/*` 被 shell glob 展开 → find 报错 → 退出
3. 上述修复后统计段仍不稳定 → 多种 find/xargs 组合在无匹配文件时返回非零

**三次递进修复**：

1. **第一次（`049c243`）** — 统计段彻底隔离到子 shell `( ... )` + 全部命令加 `|| echo 0` 兜底
   - `find ... -exec wc -l {} +` 无文件时返回非零 → 改为 `|| echo 0`
   - 统计段包裹在子 shell 中隔离，退出码不影响主流程

2. **第二次（`c3b7392`）** — 根除方案：移除全局 `set -e`，改为关键步骤手动 `exit`
   - 只有 `git pull`/`git checkout` 失败才 `exit 1`
   - `npm run build`/`nginx -t && nginx -s reload` 失败也 exit
   - 其他非关键步骤（统计、日志）失败不中断部署

3. **第三次（`3527ba5`）** — 脚本末尾加 `exit 0` 确保返回成功
   - bash 在子 shell 中运行后 `$?` 可能被中间命令覆盖
   - 末尾显式 `exit 0` 确保 webhook 收到成功响应

**效果**：webhook 交付连续成功，不再出现 `delivery failed: time out`。

**文件**：`scripts/deploy-auto.sh`

---

## 宠物兔子对话消息修复（2026-06-11）

**问题**：宠物兔子气泡消息不反映实际任务数据，始终显示初始值（任务数 `N`、逾期数 `N`）。

**根因**：`DashboardPet.vue` 在 `onMounted` 时调用 `rebuildMessages()` 构建消息数组一次，之后任务数据变化时消息内容不更新。

**修复**：
- `DashboardPet.vue` 添加 `watch([() => props.overdueCount, () => props.inProgressCount], ...)` 
- 两个 props 变化时自动触发 `rebuildMessages()` 
- 消息内容随真实任务数据实时更新

**文件**：`web/src/components/DashboardPet.vue`

---

**功能**：欢迎区变身微缩自然世界，两只 3D 立体兔子自主走动，XP 成长进化。

**核心设计**：
- **欢迎区改造** — 天空（渐变背景）+ 云朵 + 太阳 + 草地（底部绿渐变+摇摆小草🌿）+ 花草 emoji 散布
- **两只兔子** — 🐰 个人兔（CSS 3D radial-gradient 球体光影，kawaii 大眼，45px）+ 🐰👑 课题组大兔「小气」（1.4x，Lv30+ 金冠+粒子环绕）
- **60fps 状态机** — 散步→发呆→蹦跳→看光标→追光标→逃跑→睡眠（60s 无操作）
- **互动系统** — 悬停爱心眼+爱心粒子、点击喂食🥕（5❤️+2⭐爆出）、双击逃跑💨、拖拽移动
- **XP 成长** — 个人兔 10 级进化（兔宝→兔+猫+狗+鸡+仓鼠→传奇），8 种配饰解锁，升级金色粒子庆祝
- **智能消息** — 8-12s 轮播（入场问候+任务提醒+50 条科研知识+趣味彩蛋），互斥锁防重叠
- **组内大兔** — 全组 XP 累加成长，排行榜展示贡献 Top3

**踩坑记录**：
- walking keyframe 用 `transform` 覆盖了定位 `translate(-50%,-50%)` → 闪现 → 改用 `margin-top`
- `overflow:hidden` 裁切对话气泡 → 改为 `overflow:visible`
- 说话互斥锁 `boolean` 被 hover 误清 → 改为记录 `props.type` 所有权
- 云服务器 bash 不支持数组语法 `"${arr[@]}"` → 回退为 `set -f` + 字符串变量

**文件**：
- `web/src/components/DashboardPet.vue` — 兔子主组件
- `web/src/components/DashboardPetFacts.js` — 知识库+名字+配饰+成就+等级配置
- `web/src/views/Dashboard.vue` — 欢迎区改造+集成

---

## 项目动态代码分布统计升级（2026-06-10）

**问题**：项目动态页面只统计 4 类文件（.py/.vue/.js/.css），遗漏了大量代码（Markdown/Shell/Config/SQL/Docker 等），总行数仅 57K，与实际规模不匹配。

**修复方案**：
- 统计从 4 类扩展到 **12 类**：Python、Vue、JavaScript、TypeScript、CSS、HTML、Markdown、Shell、Config、SQL、Docker、Other
- `deploy-auto.sh` — `_count_lines`/`_count_files` 函数按语言分类统计，生成 `lines_by_type` + `files_by_type`
- `ProjectStatsView.vue` — 新增「📝 代码分布」卡片：12 行水平柱状图（语言品牌色 + 行数 + 文件数 + 占比进度条）
- `stats.json` — 迁移到 `app/` 目录（Docker volume 挂载 `/app/app/`），`dashboard.py` 双路径回退读取
- 本地 PowerShell 脚本生成 stats.json，兼容 UTF-8 BOM

**效果**：
- 总行数：57,470 → **140,459**（+144%），总文件：315 → **626**（+99%）
- Top 5：Markdown 50,441 / Python 45,712 / Vue 20,097 / Config 12,550 / JS 3,720

**踩坑记录**：
- `EXCLUDE_DIRS` 字符串变量中的 `*/node_modules/*` wildcard 被 shell glob 展开为实际文件 → 全部归零 → 改用 bash 数组 `("${EXCLUDE_DIRS[@]}")`
- PowerShell `Set-Content -Encoding UTF8` 写入 BOM → Python `json.loads` 报错 → API 改用 `utf-8-sig`
- `deploy-auto.sh` 编辑时误删 `STATS_FILE="$PROJECT_DIR/stats.json"` 定义 → `cat: : No such file or directory`

**文件**：
- `scripts/deploy-auto.sh` — 扩展统计逻辑
- `web/src/views/ProjectStatsView.vue` — 代码分布卡片
- `app/api/v1/dashboard.py` — 多路径 + BOM 兼容
- `app/stats.json` — 本地生成的统计数据

---

## ElMessageBox/ElMessage CSS 缺失修复（2026-06-10）

**问题**：任务管理中删除任务时，确认弹窗的「确定」和「取消」按钮位置偏移异常，没有 Element Plus 样式。

**根因**：`ElMessageBox.confirm()` 和 `ElMessage.success()` 是 JS 服务调用，不是 Vue 模板组件。`unplugin-vue-components` 的 `ElementPlusResolver` 只能静态分析模板中使用的 `<el-*>` 标签来自动导入 CSS，**无法检测 JS 服务调用**。结果 `el-message-box.css` 和 `el-message.css` 完全没有被打包进 dist。

**修复方案**：在 `main.js` 中手动导入：
```js
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
```

**文件**：`web/src/main.js`

---

## 开发天数计算修复（2026-06-10）

**问题**：开发天数始终显示 0。

**根因**：`git log --reverse --max-count=1` — Git 先应用 `--max-count=1`（只取最新 1 条），然后 `--reverse` 反转这个只有 1 条的列表，结果仍是 HEAD 的日期（今天），不是项目最早提交。

**修复**：改用 `git rev-list --max-parents=0 HEAD` 找到根提交，再 `git log --format=%ai -1 $ROOT_SHA` 取日期。

**文件**：`scripts/deploy-auto.sh`

---

## 知识库 API HTTP/2 协议错误修复（2026-06-09）

**问题**：`GET /api/v1/knowledge?page=1&page_size=20` 返回 20 条完整 content（可达数 MB），穿过 FRP 隧道时 HTTP/2 帧损坏，浏览器报 `ERR_HTTP2_PROTOOL_ERROR`。

**修复方案**：
- 新增 `KnowledgeListItem` schema（不含 `content`/`formatted_content`），列表 API 改为 `snippet`（前 200 字符）+ `content=None`
- `KnowledgeCard.vue` 卡片预览改为 `item.summary || item.snippet`
- Nginx `/api` location 移除 `Connection: upgrade`（仅用于 WebSocket）+ 添加 `proxy_buffer_size 16k` + `proxy_buffers 8 64k` + `proxy_max_temp_file_size 128m`

**效果**：列表 API 响应体积 -99%，不再触发 HTTP/2 协议错误。

---

## Element Plus 图标全面修复（2026-06-09）

**问题**：改为 Element Plus 按需导入后，`unplugin-vue-components` 的 resolver 无法解析动态 `<component :is="string">` 和部分静态 `<IconName />`，导致侧边栏/仪表盘/logo/铃铛等图标不显示。

**修复方案**：
- 全项目扫描 40+ 个 Vue 组件，找出所有模板中使用但未显式 import 的图标
- `MainLayout.vue`：显式 import 14 个图标（Aim/Bell + 路由 meta 10 个 + ArrowRight/DataBoard），创建 `iconMap` 映射
- `Dashboard.vue`：补全 Clock/CircleCheck/Warning/ChatDotRound/Plus
- `MeetingView.vue`：补全 Search

**教训**：`unplugin-vue-components` + `ElementPlusResolver` 的图标自动解析不完整，所有 `<IconName />` 必须显式 import 最保险。

---

## 前端性能大幅优化（2026-06-09）

**问题**：页面首次加载 1.2MB JS + 355KB CSS，浏览响应缓慢。

**修复方案（三重优化）**：

1. **Nginx gzip 压缩** — 两个 server block（agent + mnb-lab）均开启 gzip，JS/CSS 传输体积减 70%
2. **Element Plus 按需导入** — 使用 `unplugin-vue-components` + `ElementPlusResolver({ importStyle: 'css' })` 自动按需导入组件和样式
3. **图标按需注册** — 移除 `import * as ElementPlusIconsVue` 全量注册 + `app.component` 循环，改为 auto-import

**优化效果**：

| 指标 | 优化前 | 优化后 | 减少 |
|------|--------|--------|------|
| 主 JS bundle | 1.2MB | 199KB | 83% ↓ |
| 主 JS (gzip) | ~400KB | 76KB | 81% ↓ |
| 主 CSS | 355KB | 15.6KB | 96% ↓ |
| 首屏总加载 (gzip) | ~500KB | ~80KB | 84% ↓ |

**技术细节**：
- `vite.config.js` — 添加 `Components({ resolvers: [ElementPlusResolver({ importStyle: 'css' })] })`
- `main.js` — 移除 `import ElementPlus from 'element-plus'`、`import 'element-plus/dist/index.css'`、`app.use(ElementPlus)`、全量图标注册
- `AudioRecorder.vue` — 动态 `import('element-plus').then(...)` 改为静态 `import { ElMessageBox } from 'element-plus'`
- `tunnel.conf` — 添加 `gzip on` + `gzip_types` 配置（comp_level 5, min_length 1000）
- Element Plus 组件 CSS 自动拆分为 50+ 个独立文件，仅在对应组件渲染时加载
- ECharts 保持 1MB 独立 chunk（已在懒加载路由中，不影响首屏）

---

## 项目动态页面（2026-06-09）

**功能**：展示项目从建立至今的全历程开发信息。

**实现**：
- **侧边栏入口** — 底部独立「🚀 项目动态」菜单项，点击进入全页面
- **项目体量** — 代码行数、提交次数、开发天数、文件数量，数字递增动画（easeOutExpo 缓动）
- **已解决痛点** — 按分类展示：幻觉（Whisper 三层防护等）、部署（SSH fallback 等）、安全（Nginx 屏蔽等）、性能（声纹修正等）、架构（录音器单例等）
- **待做事项** — Phase 7-12 名称、周期、优先级
- **更新日志** — 从 2026-05-16 项目创建至今的全历程时间线（21 条记录）
- **部署自动更新** — deploy-auto.sh 统计代码数据写入 stats.json，API 读取

**文件**：
- `web/src/views/ProjectStatsView.vue` — 全页面组件
- `web/src/data/changelog.json` — 静态数据（痛点/待做/日志）
- `app/api/v1/dashboard.py` — 后端 API（读取 stats.json）
- `scripts/deploy-auto.sh` — 部署时自动统计代码数据
- `stats.json` — 部署时自动生成的统计数据

---

## 听会后台录音 + 全局指示器（2026-06-09）

**问题**：点击"开始听会"后导航到其他页面，录音对话框消失，无法找回正在录音的会议。

**修复方案**：
- **useGlobalRecorder** — 模块级单例管理 MediaRecorder 生命周期，组件销毁不影响录音
- **useRecordingState** — 全局录音状态 + 浮动胶囊指示器（MainLayout 右下角脉冲动画）
- **AudioRecorder 重构** — 从独立录音器变为全局录音器的纯 UI 壳
- **sessionStorage 验证** — 页面加载时始终查后端确认，避免残留脏数据
- **自动保存** — 关闭对话框时如果录音还在进行，自动停止并上传

技术细节：
- `useGlobalRecorder.js` — 模块级变量（mediaRecorder/audioContext/analyser/timer），响应式 state/elapsed/barHeights
- `useRecordingState.js` — recordingMeetingId + sessionStorage 持久化 + 后端 API 验证
- `MainLayout.vue` — 浮动录音指示器（fixed 右下角，脉冲动画，点击跳转 `/meetings?resume={id}`）
- `MeetingView.vue` — `?resume={id}` query 自动打开录音对话框
- `meeting.py` — 会议列表 API 新增 `status` 过滤参数
- 退出录音状态：结束听会 / 关闭对话框 / 后端确认无录音中会议

## Webhook 自动部署修复（2026-06-09）

**问题**：GitHub webhook 推送到 `https://agent.mnb-lab.cn/webhook` 被 Nginx 返回 444（静默关闭），自动部署完全失效。

**根因**：扫描器屏蔽正则 `^/(...|web|...)` 中的 `web` 匹配到了 `/webhook`。

**修复**：`web` → `web$`，`test` → `test$`，`db` → `db$`，确保只匹配精确路径。

验证：
- `curl -X POST https://agent.mnb-lab.cn/webhook` → `Invalid signature`（到达 webhook 服务）✅
- `git push` → webhook 自动触发 → `部署成功 ✓` ✅

**教训**：Nginx regex location 中关键词可能与合法路径前缀重叠，必须加 `$` 锚定。

---

## Nginx 安全防护（2026-06-09）

服务器访问日志分析发现 2452 条请求中 88% 是恶意扫描器流量，添加 Nginx 屏蔽规则：

- **敏感文件探测** — `.env`, `.git`, `.svn`, `.htaccess`, `.ssh`, `.aws`, `.azure`, `.gcp` → 444
- **WordPress 漏洞路径** — `wp-admin`, `wp-content`, `wp-includes`, `xmlrpc`, `admin`, `phpmyadmin` → 444
- **云凭证探测** — `.azure`, `.aws`, `.gcp`, `credentials`, `service-account` → 444
- **开发文件探测** — `_next`, `__next`, `node_modules`, `vendor` → 444
- **常见攻击路径** — `boaform`, `formLogin`, `servlet`, `nccloud`, `k3cloud`, `easweb`, `owa` → 444

技术细节：
- `return 444` 是 Nginx 特有状态码，静默关闭连接不返回任何响应
- 规则放在 `server {}` 块内，位于 `location / {}` 之前
- 两个站点（agent.mnb-lab.cn + mnb-lab.cn）均已防护
- 配置文件：`nginx/conf.d/tunnel.conf`（本地）→ `/etc/nginx/conf.d/default.conf`（服务器）

验证结果：
- `/.env` → 000（连接被关闭）✅
- `/wp-admin/` → 000 ✅
- `/.azure/credentials` → 000 ✅
- `/` → 200（正常访问）✅
- `/api/v1/auth/me` → 401（API 正常）✅

## Docker Desktop 更新（2026-06-09）

- Docker Desktop 4.73.1 → 4.77.0（Engine 29.5.3）
- 中文汉化语言包：[asxez/DockerDesktop-CN](https://github.com/asxez/DockerDesktop-CN)
- 汉化需替换 3 个文件：`Docker Desktop.exe` + `app.asar` + `app.asar.unpacked`
- 4.74.0+ 版本有 asar 完整性校验，必须同时替换 exe
- 每次 Docker 更新后汉化失效需重装
- WSL 重启后引擎才能正常启动（`wsl --shutdown` 再启动 Docker）

### 最新完成（2026-06-08）
- [Webhint 无障碍+性能+安全头全面优化](#webhint-优化2026-06-08)（ARIA + Cache-Control + CSS 动画 + Nginx 配置 + .hintrc + IE 兼容性确认忽略）
- [垃圾桶批量删除](#垃圾桶批量删除2026-06-08)（编辑按钮 + 勾选 + 单次 API 请求秒级完成）
- [任务列表配对布局](#任务配对布局2026-06-08)（按负责人左右对齐 + 负责人类型修复）
- [精确跳转](#精确跳转2026-06-08)（成员管理/铃铛跳转自动按用户筛选）
- [UI 优化](#ui优化2026-06-08)（铃铛加大 + 垃圾桶 Tab 加大 + 全站图标按钮 aria-label）

### 最新完成（2026-06-06）
- [声纹识别系统重大优化](#声纹识别系统重大优化2026-06-06)（VAD精细化+语义断句+KMeans分裂+同名检测+名字校对+不限人数）
- [转录手动编辑+自动润色](#转录编辑2026-06-06)（每条独立选发言人+合并自动AI加标点）
- [UI全面优化](#ui优化2026-06-06)（el-date-picker全局替换+时区修正+头像间距+纪要合并+发言人独立选）
- [标题自动生成修复](#标题修复2026-06-06)（"未命名会议"/"听会"自动触发AI生成，重试3次）
- [Celery solo pool + 缓存挂载](#celery优化2026-06-06)（避免prefork旧代码+modelscope缓存不丢失）
- [声纹持续学习](#声纹学习2026-06-06)（每次会议加权平均更新 voice_embedding）
- [标题自动生成](#标题生成2026-06-06)（2000字上下文+3次重试+regex兜底，端到端验证通过）
- [pipeline 日志精简](#pipeline优化2026-06-06)（跳过3D-Speaker pipeline直调model）
- [认证限流优化](#认证限流2026-06-06)（auth 5→20次/分钟, read 100→200次/分钟）
- [5090 服务器迁移指南](#5090迁移2026-06-06)（VRAM分配+GPU配置+本地LLM方案）
- [会议纪要标准格式固化](#会议纪要标准格式固化2026-06-06)（摘要/要点/决议按 `2026.5.28 例行例会` 信息密度输出）

### 最新完成（2026-06-05）
- [知识库 UI 全面升级](#知识库-ui-全面升级2026-06-05)（Dashboard+分类系统+实体图谱联动+AI 自动分类+自动假设生成）
- [AI 系统升级路线图](#ai-系统升级路线图)（Phase 7-12：多模态/语音/文献/实验/论文/AI 研究员）
- [极简风格前端项目](#极简风格前端项目2026-06-05)（完全独立的极简主义风格前端，可直接运行）
- [UI 设计风格展示](#ui-设计风格展示2026-06-05)（5 种风格示例：毛玻璃/新拟态/渐变流体/极简/暗黑）
- [垃圾桶 UI 恢复](#垃圾桶-ui-恢复2026-06-05)（重构样式丢失修复 — el-table 7 列 + 两行倒计时 + 实时刷新）
- [会议系统 UI 全面优化](#会议系统-ui-全面优化2026-06-05)（6 模块 — Canvas 波形+仪表盘详情页+头像组件+发言统计+录音回放+Confetti）
- [听会功能全面修复+性能优化+UI中文化](#听会功能全面修复性能优化ui中文化2026-06-055-commit)（datetime 时区 + silero-vad 缓存 + 3D-Speaker 依赖 + 点击响应优化 + 状态中文化 + 声纹验证）

### 2026-06-04
- [代码质量全面升级](#代码质量全面升级2026-06-0430-commit)（30 commit — API规范化+后端测试+前端Composables+子组件拆分+前端测试+View重构）
- [声纹测试修复+DB迁移+Skills升级](#声纹测试修复db迁移skills升级2026-06-04)（VoiceTestDialog AudioContext + meetings 列迁移 + 16 新 Skills）
- [听会功能路由修复+ProcessingDialog阶段同步](#听会功能路由修复processingdialog阶段同步2026-06-04)（路由冲突 + 阶段不匹配）
- [前端优化+对话持久化+PPT支持](#前端优化对话持久化ppt支持2026-06-047-commit)（7 commit — ECharts 升级 + passive 补丁 + Element Plus 修复 + 对话持久化 + PPT + 重复回复修复）

### 2026-06-03
- [声纹会议系统全面修复](#声纹会议系统全面修复2026-06-038-commit)（8 commit — enrolled API + 参会人 + hangup 后处理 + 反幻觉 + Celery 事件循环）
- [会议模板重构](#会议模板重构2026-06-03-commit-d619f33)（commit `d619f33` — 删独立页 + 内嵌 CRUD）
- [Webhook 性能修复](#webhook-性能修复2026-06-03-commit-7ec6ce0)（commit `7ec6ce0`，0.001s 响应）
- [垃圾桶系统全面修复](#垃圾桶系统全面修复2026-06-034-commit-链)（4 commit 链）
- [项目当前状态速查](#项目当前状态速查2026-06-11)

---

## Webhint 优化（2026-06-08）

全面修复 webhint 审计工具报告的无障碍、性能和安全头问题：

- **ARIA 修复** — el-popover 关闭时 v-if 移除内部可聚焦元素；el-tab-pane 加 lazy 避免隐藏标签页包含 focusable 元素
- **表单标签** — el-select/el-button/el-progress 全面补全 aria-label
- **废弃头移除** — Pragma、Expires 头从 voiceprint 端点移除
- **Cache-Control** — API 统一为 `max-age=0`，SPA HTML 同步
- **Nginx 安全头** — proxy_hide_header X-XSS-Protection（API + MinIO）、移除多余 CSP 头、charset_types 去重 text/html
- **CSS 动画** — 新增 element-plus-overrides.css，用 transform 替代 background-position 消除性能警告
- **.hintrc 配置** — 自定义 revving 正则 `[A-Za-z0-9_-]{5,}` 兼容 Vite base64 content-hash 文件名
- **IE 兼容性确认忽略** — 所有 IE 兼容性警告（-ms-grid、flex、sticky 等）确认不需要修复，Vue 3 本身不支持 IE
- **http-cache 说明** — Vite content-hash 文件名已是业界标准缓存方案，webhint 不认是规则缺陷

## 垃圾桶批量删除（2026-06-08）

- 垃圾桶表格新增编辑按钮，切换勾选模式
- 勾选后显示"批量永久删除"按钮
- 后端新增 `POST /api/v1/tasks/batch-permanent-delete` 接口，接收 `{ids: [1,2,3]}`
- 单次请求秒级完成，不触发限流（之前逐个删除会触发 429）

## 任务配对布局（2026-06-08）

- 任务列表从左右独立分组改为按负责人配对：左进行中 ↔ 右已完成
- 新增 `pairedGroups` 计算属性，合并 active/done 按 assignee_id 配对
- 修复 `getMemberName` 类型不匹配 bug：对象 key 是字符串，`===` 比较数字失败，改为 `==` 宽松比较

## 精确跳转（2026-06-08）

- 成员管理"查看任务"跳转 `/tasks?assignee_id=xxx`，TaskView 自动读取 query 参数筛选
- 铃铛"查看我的任务"跳转 `/tasks?assignee_id=当前用户ID`

## UI 优化（2026-06-08）

- 铃铛图标加大（32px）+ 圆形背景 + 边框 + hover 缩放阴影
- 垃圾桶 Tab 加图标（🗑️）+ 加大字号 + hover 背景色

## 会议纪要标准格式固化（2026-06-06）

后续所有会议 AI 分析、手动优化会议内容、历史会议补写，都必须按照 `2026.5.28 例行例会` 的结构和信息密度输出，不能只生成短摘要。

### 标准要求

- **摘要**：3-6 句，必须包含会议背景、讨论过程、关键人物观点、结论和后续方向。
- **讨论要点**：`key_points` 必须使用 `【发言人】内容` 格式；短会议也至少提取 3 条，信息充足时 5-8 条。
- **决议事项**：`decisions` 必须写清楚 `【发言人/双方/全组】决定或共识 + 后续用途`。
- **原始转录保护**：`transcript` 不改，只优化 `transcript_polished`、`summary`、`key_points`、`decisions`。
- **禁止虚构**：声纹无法确认时使用 `【发言人A】` / `【发言人B】`，不要强行猜姓名。

### 已同步文件

- `docs/meeting-minutes-standard.md` — 标准格式完整规范
- `app/services/meeting_analysis_service.py` — 自动会议分析 prompt
- `README.md` / `ROADMAP.md` / `CLAUDE.md` / `AGENTS.md` — 项目上下文与长期记忆

---

## 声纹识别歧义保护（2026-06-06）

针对会议 #64/#68 中“实际多人但声纹模型容易识别成同一人”的问题，新增声纹分配保护层。

### 修复内容

- 新增 `app/services/speaker_assignment.py`，将“聚类 → 发言人姓名”逻辑抽为可测试纯函数。
- 多个聚类命中同一已知成员时，只保留最可信的一簇，其余标为 `发言人X`，避免把两个真实发言人都写成同一个人。
- 参与者自动添加改为信任最终簇判定，避免后续按单段声纹识别又把歧义簇加回同一成员。
- AI 润色增加程序校验：只允许加标点/去少量语气词，疑似改写时逐段回退原文。
- Celery worker 改为 `--pool=solo`，减少 prefork 子进程保留旧代码快照导致的开发调试问题。

### 未完全解决

当两个发言人的 3D-Speaker embedding 距离过近时，模型无法可靠给出真实姓名。系统现在采用保守策略：宁可标为 `发言人B`，也不误认成已知成员。要进一步自动匹配真实姓名，需要补录第二位发言人的干净声纹样本或改善录音环境。

---

## 知识库 UI 全面升级（2026-06-05）

知识库系统 UI 重构，提升可视化和交互体验。

### 新增组件
- **KnowledgeDashboard** — 分类栏 + 知识列表（移除统计卡片，保留简洁布局）
- **KnowledgeCard** — 左侧彩色条 + 分类颜色 + 来源图标 + 悬停效果
- **KnowledgeToolbar** — 整合搜索 + 高级筛选 + 操作按钮组

### 分类系统
- **8 个预设分类**：📄论文 🔬方法 📏标准 📖综述 💡案例 ❓FAQ 📝笔记 📚手册
- **AI 自动分类**：LLM 分析内容后自动分配到预设分类
- **研究方向 topic**：新增 topic 字段存储具体研究方向
- **分类筛选增强**：同时匹配 category 和 tags 字段

### 实体图谱联动
- **左图右表布局**：左侧力导向图 + 右侧实体列表
- **双向高亮**：点击图谱节点 ↔ 高亮列表卡片
- **自动加载**：切换 Tab 时自动加载图谱

### AI 自动化
- **自动分类**：新增知识时 AI 自动分配预设分类
- **自动假设生成**：知识入库时基于实体自动生成科研假设
- **自动图谱加载**：实体图谱 Tab 切换时自动渲染

### API 修复
- **实体图谱路径**：`entity-graph` → `entities/graph`
- **公式分类路径**：`formula-categories` → `formulas/categories`

---

## AI 系统升级路线图

详见 [docs/ROADMAP-AI-ENHANCEMENT.md](docs/ROADMAP-AI-ENHANCEMENT.md) 和 [docs/plans/](docs/plans/) 目录。

### 从浅入深路线图（Phase 7-20）

| Phase | 目标 | 周期 | 优先级 | 说明 |
|-------|------|------|--------|------|
| Phase 7 | 多模态知识库 | 4-6 周 | 🔴 高 | 图片/公式/表格识别入库，OCR + 公式解析 + 表格提取 |
| Phase 8 | 科研数据自动备份 | 2-3 周 | 🔴 高 | 数据库+文件定时备份+异地容灾+恢复测试 |
| Phase 9 | 课题组知识图谱可视化 | 3-4 周 | 🟡 中 | 实体关系网络+交互式探索+路径发现 |
| Phase 10 | 实时语音科研助手 | 6-8 周 | 🟡 中 | 语音对话+实时转录+AI 问答+多语言支持 |
| Phase 11 | 智能实验记录本 | 4-6 周 | 🔴 高 | 结构化实验记录+模板+搜索+版本控制 |
| Phase 12 | 科研协作工作流 | 4-6 周 | 🔴 高 | 任务分配+进度追踪+评审流程+通知提醒 |
| Phase 13 | 自动化文献综述 | 6-8 周 | 🟡 中 | 文献检索+摘要生成+引用管理+综述草稿 |
| Phase 14 | 智能实验方案生成 | 6-8 周 | 🟡 中 | 基于知识库生成实验方案+参数推荐+风险评估 |
| Phase 15 | 实验数据分析平台 | 6-8 周 | 🟡 中 | 数据导入+统计分析+可视化+报告生成 |
| Phase 16 | 深度论文理解 | 4-6 周 | 🔴 高 | 论文解析+关键信息提取+对比分析+趋势发现 |
| Phase 17 | AI 辅助论文写作 | 6-8 周 | 🟡 中 | 大纲生成+内容建议+格式检查+查重辅助 |
| Phase 18 | 智能实验设备管理 | 4-6 周 | 🟢 低 | 设备预约+使用记录+维护提醒+库存管理 |
| Phase 19 | 课题组专属 AI 研究员 | 8-12 周 | 🟢 低 | 自主研究+假设验证+论文草稿+实验设计 |
| Phase 20 | AI 科研助手移动端 | 6-8 周 | 🟡 中 | 移动 App+语音交互+离线模式+推送通知 |

---

## 极简风格前端项目（2026-06-05）

创建完全独立的极简主义风格前端项目 `web-minimal/`，不依赖原项目任何代码。

### 设计理念

- **简洁清晰**：去除多余装饰，突出内容本身
- **留白充足**：呼吸感强，视觉舒适
- **层次分明**：通过间距和分割线区分区域
- **一致性**：统一的设计语言和组件规范

### 设计规范

| 元素 | 规范 |
|------|------|
| 主色调 | #1a1a1a（深灰黑色） |
| 强调色 | #FF7A5C（珊瑚橙） |
| 背景色 | #fafafa（浅灰白） |
| 卡片背景 | #ffffff（纯白） |
| 圆角 | 8px / 12px / 16px |
| 阴影 | 极轻，仅用于悬停状态 |

### 项目结构

```
web-minimal/
├── src/
│   ├── assets/variables.css    # 极简设计系统
│   ├── layouts/MainLayout.vue  # 主布局
│   ├── router/index.js         # 路由配置
│   ├── stores/                 # 状态管理
│   ├── utils/                  # 工具函数
│   ├── composables/            # 组合式函数
│   ├── views/                  # 13 个页面
│   └── components/             # 8 个组件
```

### 页面列表

1. 登录页、仪表盘、任务管理、会议管理、AI 对话
2. 知识库、成员管理、项目管理、长期记忆、声纹库、设置

### 如何使用

```bash
cd web-minimal
npm install
npm run dev
# 访问 http://localhost:3000
```

---

## UI 设计风格展示（2026-06-05）

创建 5 种 UI 设计风格示例文件，用于探索不同设计方向。

### 风格列表

| 风格 | 特点 |
|------|------|
| 毛玻璃风格 | 半透明背景、模糊效果、层次感 |
| 新拟态风格 | 柔和阴影、凹凸感、立体效果 |
| 渐变流体风格 | 动态渐变、流体形状、创意艺术 |
| 极简主义风格 | 简洁、留白、专注内容 |
| 暗黑模式风格 | 深色背景、护眼、专业感 |

### 文件位置

- 项目内：`web/design-showcase/`
- 桌面：`C:\Users\admin\Desktop\UI设计风格展示\`

---

## 垃圾桶 UI 恢复（2026-06-05）

重构子组件时 el-table 被误换为裸 div 导致样式丢失，恢复完整功能。

### 问题根因

commit `94735a3`（TaskView 集成子组件）把垃圾桶从 TaskView 抽成 `TaskTrash.vue` 子组件时：
- `el-table` + `el-card` 被换成裸 `<div class="trash-item">`
- **没有写 CSS 补偿**，导致 UI 变成无样式纯文本列表
- 负责人、优先级、原状态列一起丢失

### 恢复内容

- **el-card + el-table** 完整表格布局，7 列：任务标题（删除线）、负责人（头像）、优先级、原状态、删除时间、自动删除、操作
- **两行倒计时**：相对时间（精确到 "5 小时 23 分后删除"）+ 绝对时间（"06-08 14:30 删除"）
- **响应式实时刷新**：`now` ref 每 30s 更新，倒计时自动滚动
- **5 级颜色分级**：imminent(红脉冲 1.2s) → urgent(深红) → warning(橙) → normal(灰) → safe(浅灰)
- **tabular-nums** 数字等宽字体，倒计时数字不抖动
- **分页增强**：total + sizes(10/20/50) + prev/pager/next
- **权限控制**：admin/创建人/负责人可见操作按钮

### 教训

重构抽子组件时如果替换了 Element Plus 组件（el-table → 裸 div），必须手写等效 CSS。抽完后对比原始 UI 确保视觉一致。

---

## 会议系统 UI 全面优化（2026-06-05）

6 大模块全面升级会议系统 UI，从"开发者风格"提升为"仪表盘式"可视化界面。

### 模块 1：VoiceTestDialog Canvas 波形动画

- 20 根 DOM bar → **Canvas 贝塞尔曲线波形**（60fps 流畅动画）
- 珊瑚橙渐变填充 + 发光描边
- 麦克风按钮脉冲光晕（`mic-pulse` 环形扩散）
- 平滑衰减动画（decay 0.7 / attack 0.3，避免突变）

### 模块 2：ParticipantAvatars 复用组件（新建）

- `web/src/components/ParticipantAvatars.vue`
- 头像堆叠（重叠 -8px）+ 溢出 "+N" 气泡
- hover 放大 + tooltip 姓名
- 全体成员自动识别 → "全体成员（N人）" 徽章

### 模块 3：MeetingList 列表增强

- 每个会议项显示参与者头像行（最多 4 个重叠头像）
- 状态圆点动画（recording/processing 脉冲扩散）
- 🎙️ 录音标识（有 audio_url 的会议）
- 摘要 2 行渐变截断（`-webkit-line-clamp`）

### 模块 4：MeetingDetailView 仪表盘式重设计

- **Hero 区**：大标题（22px）+ 状态徽章（带圆点动画）+ 时间/地点/时长元信息 + 参与者头像行
- **Tab 切换**：会议纪要 / 转录记录 / 发言统计
- **转录记录**：发言人小头像（24px）+ 时间轴竖线样式
- **内联编辑**：点击"编辑"直接在 Hero 区修改标题/时间/地点
- **侧边栏**（320px）：录音回放卡片 + 听会卡片 + 相关会议推荐

### 模块 5：AudioPlayer 增强 + 录音回放

- `web/src/components/AudioPlayer.vue` 全面重写
- Canvas 波形渲染（运行时解码音频或外部传入 waveformData）
- 播放头竖线（已播放珊瑚橙 / 未播放灰色）
- 倍速控制（1x / 1.5x / 2x 循环切换）
- MeetingDetailView 侧边栏集成录音回放卡片

### 模块 6：SpeakerStatsCard 发言统计组件（新建）

- `web/src/components/SpeakerStatsCard.vue`
- 水平进度条 + 头像 + 百分比 + 发言次数/字数
- `fadeSlideUp` stagger 入场动画（每行 60ms 延迟）
- 自动从 memberStore 匹配发言人头像

### 模块 7：MeetingStats 统计页开发

- `web/src/views/meeting/MeetingStats.vue` 从空占位变为完整页面
- 3 个统计卡片（总会议数/本月会议/总录音时长）+ 数字滚动动画
- 最近会议时间线（最近 5 条，状态圆点 + 链接）
- 发言活跃度排行（跨会议聚合 speaker_stats）

### 模块 8：ProcessingDialog 增强

- 完成时 **Confetti 撒花**动画（20 片彩色纸片下落）
- ✅ 弹跳入场动画（`done-bounce`）
- "查看纪要"按钮脉冲光晕（`btn-glow`）

### 新增组件清单

| 组件 | 文件 | 用途 |
|------|------|------|
| ParticipantAvatars | `web/src/components/ParticipantAvatars.vue` | 参与者头像行（堆叠+溢出+全体成员） |
| SpeakerStatsCard | `web/src/components/SpeakerStatsCard.vue` | 发言统计卡片（进度条+头像） |

---

## 听会功能全面修复+性能优化+UI中文化（2026-06-05，5 commit）

| commit | 修复内容 |
|--------|----------|
| `6ae43c8` | datetime 时区修复 — `.replace(tzinfo=None)` 适配 TIMESTAMP WITHOUT TIME ZONE |
| `0244168` | silero-vad 模型缓存 — 预下载到本地 + 回退逻辑 |
| `0428892` | 点击响应优化 — requestAnimationFrame + 非阻塞 API + ElMessageBox |
| `6c83564` | 会议状态中文化 — 6 种状态全部中文显示 |
| （容器内） | 3D-Speaker 依赖修复 — addict/datasets/simplejson/sortedcontainers/soundfile |

**声纹识别验证**：杜同贺声纹录入后，听会 30 秒正确识别发言人 ✅

---

## 代码质量全面升级（2026-06-04，30 commit）

### 第 1 轮：API 规范化（6 commit）

| 改动 | 说明 |
|------|------|
| 统一异常类层次 | AppException/NotFoundException/ValidationException/AuthException/ForbiddenException/ConflictException/RateLimitException |
| 统一分页模型 | PaginationParams + PaginatedResponse + PaginationMeta |
| 全站分级限流 | auth:5次/分, write:30次/分, read:100次/分, upload:10次/分 |
| 安全响应头 | X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy/X-Request-ID |
| 8 个 API 文件改造 | task/meeting/knowledge/member/auth/voiceprint/memory/project/chat |

### 第 2 轮：后端测试补全（3 commit）

| 测试文件 | 测试内容 |
|---------|---------|
| tests/unit/test_task_service.py | CRUD/分页/状态更新/逾期 |
| tests/unit/test_meeting_service.py | 创建/议程/分页/更新/删除 |
| tests/integration/test_api_tasks.py | CRUD/分页/错误格式/认证 |

### 第 3 轮：前端组件拆分（10 commit）

**Composables（3 个）**：
- useTask.js — 任务状态 + API
- useMeeting.js — 会议状态 + API
- useKnowledge.js — 知识库状态 + API

**子组件（18 个）**：
| 模块 | 组件 | 行数 |
|------|------|------|
| Task | TaskList, TaskCreateDialog, TaskTrash | 34 + 89 + 88 |
| Knowledge | KnowledgeDashboard, KnowledgeSearch, KnowledgeEntities, KnowledgeHypotheses, KnowledgeFormulas, KnowledgeHealth, KnowledgeQADialog, KnowledgeUploadDialog | 45+43+30+21+19+5+167+104 |
| Meeting | MeetingList, MeetingCreateDialog, MeetingStats | 43 + 344 + 5 |

### 第 4 轮：前端测试补全（4 commit）

| 测试文件 | 测试数量 |
|---------|---------|
| useTask.test.js | 7 |
| useMeeting.test.js | 8 |
| useKnowledge.test.js | 8 |
| TaskCreateDialog.test.js | 4 |
| KnowledgeQADialog.test.js | 4 |
| MeetingCreateDialog.test.js | 7 |
| **总计** | **38 个测试全部通过** |

### View 重构（6 commit）

| View | 原始行数 | 当前行数 | 减少 |
|------|---------|---------|------|
| TaskView | 1173 | 737 | -436（-37%）|
| KnowledgeView | 2236 | 1920 | -316（-14%）|
| MeetingView | 1086 | 911 | -175（-16%）|
| **总计** | **4495** | **3568** | **-927（-21%）**|

---

## 声纹测试修复+DB迁移+Skills升级（2026-06-04）

### 1. 声纹测试麦克风误报修复

**问题**：王书馨可以正常录入声纹，但测试时显示"麦克风权限被拒绝"，杜同贺手机测试正常。

**根因**：`VoiceTestDialog` 的 `startRecord()` 中，`getUserMedia` 成功后紧接着创建 `AudioContext({ sampleRate: 16000 })` 用于音量可视化。部分手机浏览器（Safari/微信浏览器）的 `AudioContext` 可能处于 `suspended` 状态或不支持指定 `sampleRate`，被外层 catch 兜底捕获后**误报**为"麦克风权限被拒绝"。而 `VoiceprintEnrollDialog` 不需要 `AudioContext`，所以录入正常。

**修复**：
- 分离 `getUserMedia` 和 `AudioContext` 的 try/catch，错误信息精确区分（`NotAllowedError`/`NotFoundError`/其他）
- AudioContext 失败时跳过音量可视化，录音不受影响
- 添加 `webkitAudioContext` 前缀 + `resume()` 处理 suspended 状态
- 录音格式兜底：webm → mp4 → 默认（兼容 Safari）

### 2. meetings 表列迁移

**问题**：创建会议 500 错误，日志报 `column "audio_url" of relation "meetings" does not exist`

**根因**：`Meeting` 模型定义了 `audio_url`/`audio_duration`/`recording_started_at`/`recording_ended_at` 4 列，但数据库 `meetings` 表没有这些列。`Base.metadata.create_all()` 不会给已有表添加新列。

**修复**：手动 ALTER TABLE 添加 4 列。

### 3. Skills 框架升级

从 [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) 下载 16 个新 Skills：

| 技能 | 用途 |
|------|------|
| senior-backend | REST API 设计、数据库优化、认证流程 |
| senior-devops | CI/CD、基础设施自动化、容器化 |
| senior-qa | 单元测试、集成测试、E2E 测试 |
| rag-architect | RAG 流水线设计、向量搜索优化 |
| database-designer | 数据库 schema 设计、迁移规划 |
| performance-profiler | CPU/内存/IO 瓶颈分析 |
| api-design-reviewer | REST API 设计审查 |
| tdd-guide | TDD 红-绿-重构 |
| docker-development | Dockerfile 优化、多阶段构建 |
| llm-cost-optimizer | LLM token 用量优化 |
| migration-architect | 零停机迁移规划 |
| spec-driven-workflow | 先写规格再写代码 |
| codebase-onboarding | 代码库分析、新人上手文档 |
| security-guidance | 安全反模式检测 |
| a11y-audit | WCAG 2.2 无障碍审计 |
| api-test-suite-builder | API 测试生成 |

总计 **37 个 Skills**。

### 4. 代码质量全面升级计划

已完成设计文档和实现计划，待执行：

- **设计文档**：`docs/superpowers/specs/2026-06-04-code-quality-upgrade-design.md`
- **实现计划**：`docs/superpowers/plans/2026-06-04-code-quality-upgrade.md`
- **4 轮 24 任务**：API 规范化（任务 1-8）→ 后端测试（9-15）→ 前端拆分（16-19）→ 前端测试（20-24）
- **执行方式**：子代理驱动

---

## 听会功能路由修复+ProcessingDialog阶段同步（2026-06-04）

**问题**：点击"开始听会"后录音正常，但点击"结束听会"后不会触发自动分析。后端返回 405 Method Not Allowed。

**根因分析**：
1. **路由冲突**：`meeting.py` 的 `/meetings/{meeting_id}` 路由先注册，把 `/meetings/start-recording` 当作 `meeting_id = "start-recording"` 匹配，但该路由只接受 GET，所以 POST 返回 405
2. **ProcessingDialog 阶段不匹配**：前端用的是旧版阶段名（`extracting_transcript`、`polishing_transcript` 等），与后端 `ProgressStage`（`downloading_audio`、`transcribing` 等）完全对不上，导致进度条卡住

**修复清单**：

| 文件 | 修复内容 |
|------|----------|
| `app/main.py` | `meeting_recording.router` 注册顺序移到 `meeting.router` 之前 |
| `web/src/components/ProcessingDialog.vue` | 阶段列表改为与后端一致的 6 阶段 |

**关键教训**：
- FastAPI 按注册顺序匹配路由，固定路径必须在参数路径之前注册
- ProcessingDialog 阶段必须与后端 ProgressStage 枚举保持同步

---

## 声纹会议系统全面修复（2026-06-03，8 commit）

**问题**：声纹会议存在多个阻塞性 bug — enrolled API 解析错误导致声纹状态始终为 0、参会人未传递导致"等待发言"、hangup 后 ProcessingDialog 永远卡住、Celery 后处理事件循环冲突、Whisper 幻觉过滤不足。

**修复清单**：

| commit | 修复内容 |
|--------|----------|
| `8460016` | 声纹全链路测试：`POST /api/v1/voiceprint/test` + `VoiceTestDialog` 组件 |
| `cbc503f` | enrolled API 解析（`vpData.members`）+ 参会人自拉取 + avatar schema + startVoiceCreate 自动添加当前用户 |
| `086db70` | hangup 时触发 `post_meeting_process` Celery 任务 |
| `5a3b864` | hangup 后等待服务器关闭 WS 再关对话框 |
| `fddff52` | hangup 后 `watch(connected)` 等 WS 断开再 emit call-ended |
| `63a3e82` | `batch_polisher` 传入 `_live_loop_inner`（修复 NameError） |
| `00b399b` + `1ed628a` + `095938a` | Celery 后处理独立引擎（NullPool）+ 独立 Redis + `new_event_loop` |
| `1659f55` | 反幻觉强化：重复句阈值 3→2 + 低置信度短文本过滤 + 新增黑名单 |
| `87a33b5` | ProcessingDialog 改为 500px 弹窗 |

**关键教训**：
- `sendHangup()` 不能立即 disconnect，要等服务器处理完
- Celery worker 不能复用主 app 的 async_session / Redis 连接池（事件循环冲突）
- `batch_polisher` 等局部变量必须显式传入内部函数

### 2026-06-02 全面热修
- 声纹会议全方位热修（9 commit 链）
- 声纹系统线上修复（9 个 commit）
- KnowledgeView 白屏修复
- 声纹会议 WS 崩溃循环 + L3 优化（6 commit）
- Webhook SSH 拉取改造（5 commit 链）
- 反幻觉七重过滤（36/36 测试）
- A11y 警告彻底清零
- 本地运维三件套
- 文档与 Memory 同步

### 2026-06-01 声纹会议
- wave 3a/3b（声纹库 + 会议模板）
- wave 2a/2b（实时识别 + AI 互动）

### 早期阶段（2026-05-18 ~ 2026-05-31）
- [第六阶段：会议系统智能升级](#第六阶段会议系统智能升级--实时声纹识别-2026-05-29)
- [Knowledge Brain 二次升级](#knowledge-brain-二次升级--实体图谱--假设生成--量化推理-2026-05-27)
- [知识库自主进化](#知识库深层逻辑系统--自主进化知识大脑-2026-05-26)
- [2026-05-27 Bug 修复记录](#2026-05-27-bug-修复记录)
- [2026-05-25 更新](#2026-05-25-更新)
- [2026-05-24 更新](#2026-05-24-更新)
- [UI 全面升级](#ui-全面升级2026-05-24)
- 早期阶段一~五 + 第六阶段（[第一阶段](#第一阶段让系统真正能用关键) 起）

---

## 🟢 项目当前状态速查（2026-06-12）

| 维度 | 状态 | 最近更新 |
|------|------|----------|
| 后端 | Phase 1-6 + 声纹系统修复 + 反幻觉七重过滤 + 垃圾桶系统 + PPT 解析 + 统一异常类/分页/限流 + datetime 时区修复 + silero-vad 缓存 + 3D-Speaker 依赖修复 + **API 安全响应头中间件**（X-Content-Type-Options/Cache-Control） | 2026-06-12 |
| 知识库 | 自主进化知识大脑（实体图谱+假设+量化推理）+ PPT 上传支持 | 2026-06-04 |
| 会议系统 | 录音机+离线后处理 + 声纹识别验证 + UI 全面优化（6 模块）+ **L2 润色 prompt 升级**（清理幻觉+修同音错字）+ **段落智能切分脚本** | 2026-06-11 |
| 任务管理 | 软删除/垃圾桶 + 3 天后自动清理（1h 调度）+ 精准倒计时双行显示 + 5 级颜色 | 2026-06-03 |
| 前端 | ECharts 5.6.0 + Element Plus 按需导入 + Nginx gzip + 对话持久化 + **🐰 宠物乐园**（两只 3D 兔子 + XP 成长 + 轮播消息）+ Composables + **20 个子组件** + Vitest 测试 + 性能优化（bundle -83%）+ **CSS 动画全面 GPU 化** + **Vite hash 改 hex**（消除 webhint cache-busting 误报） | 2026-06-12 |
| 测试 | 后端 33+ 个测试 + 前端 38 个测试 = 71+ 个测试 | 2026-06-04 |
| 部署 | 阿里云 Nginx+FRP + 本地 Docker 8 services + SSH 拉取 + webhook 多线程 + **三次递进修复**（set -e 移除 + 子 shell 隔离 + exit 0）+ **stats.json 路径修正** + 开发天数动态计算 | 2026-06-11 |
| 性能 | PostCSS 剥离 EP keyframes + 全站 CSS 动画 GPU Composite + Nginx gzip + EP 按需导入（bundle -83%）+ **Vite hashCharacters hex** | 2026-06-12 |
| 代码质量 | API 规范化 + 后端测试 + 前端 Composables + 子组件拆分（-21%）+ 前端测试，30 commit 全部完成 | 2026-06-04 |
| 文档 | README/ROADMAP/CLAUDE.md/MEMORY 已同步 + 更新日志 28→33+ 条 | 2026-06-12 |

---

## 第一阶段：让系统真正能用（关键）

- [x] **接入 Agent 工具执行** -- `_execute_tool` 已连接真实 service 层，10 个工具全部路由到对应 Service
- [x] **修复 session_id bug** -- `_process_response` 已接收 `session_id` 参数，不再硬编码 `"default"`
- [x] **创建 Celery 模块** -- `app/core/celery.py` 已创建，celery-worker/celery-beat 可正常启动
- [x] **配置 pgvector** -- `main.py` 启动时执行 `CREATE EXTENSION IF NOT EXISTS vector`
- [x] **chat_stream 支持工具调用** -- 已传入 `tools=self.tools`，流式对话可触发工具

## 第二阶段：补全缺失的 API

- [x] **给所有 API 路由加认证** -- 31个端点全部加了 `get_current_user`，WebSocket 从 query param 取 token
- [x] **补 meeting PUT/DELETE 端点** -- `meeting.py` 新增 `PUT /meetings/{id}` 和 `DELETE /meetings/{id}`
- [x] **补 project DELETE 端点** -- `project.py` 新增 `DELETE /projects/{id}`
- [x] **实现真正的语义搜索** -- 接入 pgvector + text2vec-base-chinese，embedding_service.py 单例加载模型
- [x] **取消注释微信通知** -- `reminder_service.py` 接入 `wechat_bot.send_message()`
- [x] **补全 member 创建时的 password_hash** -- `MemberCreate` 加 username/password，创建时自动 hash

## 第三阶段：质量和安全

- [x] **Chat session 持久化** -- 迁移到 Redis，`RedisSessionStore` 替代内存 dict，24小时 TTL
- [x] **修复 N+1 查询** -- dashboard 统计改用 `func.count()` + `GROUP BY` 聚合查询
- [x] **清理无用依赖** -- 移除 langchain, langchain-anthropic, chromadb, minio, pyannote-audio
- [x] **SECRET_KEY 启动校验** -- 生产环境检测默认值，未配置则拒绝启动
- [x] **初始化 Alembic 迁移** -- 创建 `alembic/` 目录、`env.py`（async）、初始迁移脚本
- [x] **收紧 CORS** -- 替换 `allow_origins=["*"]` 为显式白名单
- [x] **登录接口加限流** -- 滑动窗口限流器，5分钟内最多5次尝试，按 IP 限制
- [x] **移除登录页硬编码账号** -- 改为"请联系管理员获取账号密码"

## 第四阶段：补全基础设施

- [x] **添加测试** -- `tests/` 新增 conftest.py + test_auth/test_tasks/test_members，覆盖认证、任务 CRUD、成员管理（⚠️ 需真实 PostgreSQL+pgvector 环境才能运行，无 CI 流水线）
- [x] **配置日志系统** -- `app/core/logging.py` 统一配置，生产环境写文件（RotatingFileHandler 10MB×5）
- [x] **前端 Pinia 状态管理** -- 新增 member store（共享成员列表）和 user store（用户信息+通知数），MainLayout 接入
- [x] **voice.py 会议转写保存** -- WebSocket 断开后自动将转写结果保存到 meeting.transcript
- [x] **meeting.py WebSocket 转写** -- 已在 voice.py 实现（/ws/meeting/{id}/transcript），meeting.py 无需重复
- [x] **Docker Whisper 服务与 app 内 Whisper 重复加载** -- asr.py 改为优先调用远程 Whisper 服务，回退到本地模型

## 第五阶段：功能增强

- [x] **企业微信群机器人** -- 5 个部署阻塞项已全部修复（运行时 bug、配置补全、@提及检测、Redis 持久化、结构化日志），代码就绪待上线
- [x] **微信互通（普通微信用户支持）** -- 课题组成员可用私人微信与机器人对话（私聊+群聊），无需下载企业微信。通过企业微信「微信互通」外部联系人功能实现
- [x] **腾讯会议 API 集成** -- 签名算法修正、Agent `create_meeting` 自动创建线上会议、Webhook 回调端点、错误重试。需配置凭据后测试
- [x] **MinIO 文件上传** -- 通用上传 + 会议附件上传 + 删除，自动创建 bucket
- [x] **前端 ECharts 注册** -- `<script setup>` 已自动注册，无需额外配置
- [x] **通知 badge 真实数据** -- 改为从 API 获取待处理提醒数量，user store 管理
- [x] **会议转写自动分析** -- 会议结束自动提取摘要/要点/决定/任务，任务自动创建并关联会议。WebSocket 转写断开和腾讯会议 Webhook 回调均触发分析，支持手动 `POST /meetings/{id}/analyze`
- [x] **CLAUDE_MODEL 可配置** -- 新增 `CLAUDE_MODEL` 配置项，analyzer 和 summary 统一使用，兼容 mimo-v2.5 ThinkingBlock 响应
- [x] **前端图片识别** -- 主对话窗口支持图片上传和识别，使用 mimo-v2.5 多模态能力，支持图片+文字混合消息
- [x] **任务权限控制与自定义提醒** -- 管理员可分配任务给任何人，普通成员只能给自己创建/查看/编辑/删除任务；支持自定义提醒时间点；API/Agent/前端三层权限控制

---

## 已完成

### Phase 1 (2026-05-16)

| 问题 | 修复内容 |
|------|---------|
| `_execute_tool` 返回模拟结果 | 重写为路由分发，10 个工具全部接入 TaskService/MemberService/MeetingService/ProjectService/KnowledgeService |
| session_id 硬编码 "default" | `_process_response` 接收 `session_id` 参数，会话隔离正确 |
| celery 模块缺失 | 创建 `app/core/celery.py`，含 beat 定时任务配置 |
| pgvector 未安装 | `main.py` 启动时 `CREATE EXTENSION IF NOT EXISTS vector` |
| chat_stream 不支持工具 | 传入 `tools=self.tools`，添加工具调用处理逻辑 |
| 同步 Anthropic 客户端 | 切换为 `AsyncAnthropic`，不再阻塞事件循环 |
| follow-up 缺少 tools 参数 | 补上 `tools=self.tools`，支持工具链式调用 |
| assistant history 格式错误 | 存储 content blocks 而非字符串 |
| meeting.py 缺少 ARRAY 导入 | 补上导入，修复 NameError |
| 重复 WebSocket 路由 | 移除 meeting.py 中的 stub，保留 voice.py 实现 |

**新建文件：**
- `app/services/member_service.py` — 成员 CRUD 服务
- `app/services/meeting_service.py` — 会议 CRUD 服务
- `app/services/project_service.py` — 项目+里程碑 CRUD 服务
- `app/services/knowledge_service.py` — 知识库 CRUD + 语义搜索服务
- `app/core/celery.py` — Celery 应用配置

**修改文件：**
- `app/agent/core.py` — 完全重写，修复 7 个 bug
- `app/api/v1/chat.py` — 传入 db session
- `app/api/v1/voice.py` — 传入 db session
- `app/api/v1/meeting.py` — 移除重复路由，generate-minutes 传入 db
- `app/models/meeting.py` — 补上 ARRAY 导入
- `app/main.py` — 启动时初始化 pgvector 扩展
- `app/services/reminder_service.py` — 添加 celery task 包装函数

### Phase 2 (2026-05-16)

| 问题 | 修复内容 |
|------|---------|
| 31个API端点无认证 | 全部加 `get_current_user`，DELETE /members 改用 `get_current_admin_user` |
| WebSocket 无认证 | 新增 `get_current_user_ws`，WS 端点从 query param 校验 token |
| meeting 缺 PUT/DELETE | 新增 `PUT /meetings/{id}` 和 `DELETE /meetings/{id}` |
| project 缺 DELETE | 新增 `DELETE /projects/{id}` |
| 语义搜索是假的 | 接入 pgvector + text2vec-base-chinese，cosine_distance 真实相似度 |
| 微信通知被注释 | 接入 `wechat_bot.send_message()`，加异常守卫 |
| 创建成员无密码 | `MemberCreate` 加 username/password，`get_password_hash` 自动 hash |

**新建文件：**
- `app/services/embedding_service.py` — 向量嵌入服务（单例模型加载 + 异步生成）

**修改文件：**
- `app/core/security.py` — 新增 `get_current_user_ws()` WebSocket 认证
- `app/api/v1/member.py` — 全部端点加认证 + 创建成员支持密码
- `app/api/v1/project.py` — 全部端点加认证 + 新增 DELETE 端点
- `app/api/v1/meeting.py` — 全部端点加认证 + 新增 PUT/DELETE 端点
- `app/api/v1/task.py` — 全部端点加认证
- `app/api/v1/knowledge.py` — 全部端点加认证 + 语义搜索改用 service
- `app/api/v1/chat.py` — POST + WebSocket 加认证
- `app/api/v1/voice.py` — 全部端点加认证
- `app/services/knowledge_service.py` — create/update 生成 embedding，search_semantic 改用 pgvector
- `app/services/reminder_service.py` — 接入 wechat_bot 推送
- `app/schemas/member.py` — MemberCreate 加 username/password 字段
- `requirements.txt` — 加 pgvector==0.2.4

### WeChat Bot (2026-05-17) -- ⚠️ 代码完成，未部署

| 功能 | 说明 | 状态 |
|------|------|------|
| 消息加解密 | AES-256-CBC + PKCS7，支持 URL 验证和消息加解密 | ✅ 代码完成 |
| Webhook 回调 | GET 验证 + POST 接收，异步处理避免 5 秒超时 | ✅ 代码完成 |
| 任务派发 | 老师对话触发 → 创建任务 → 私发给每个负责人 | ✅ 代码完成 |
| 进度回复 | 学生回复"完成/进度50%/遇到问题" → 自动更新任务状态 | ✅ 代码完成 |
| 汇总通知 | 有问题转发老师，全员完成自动汇总通知 | ✅ 代码完成 |
| 群聊+私聊 | 群里 @机器人 或 私聊直接发消息均可触发 | ⚠️ @检测硬编码，不匹配实际企业微信格式 |
| 多信号身份识别 | userid → wechat_id → 手机号 → 昵称模糊匹配，首次匹配自动绑定 | ✅ 代码完成 |
| 群聊被动监听 | 消息缓冲 + 关键词触发 → Claude 分析 → 自动提取任务/会议/决定 | ✅ 代码完成 |
| 主动提醒调度 | Celery 定时（15分钟）检查：即将到期、已逾期、未确认、即将开始的会议 | ✅ 代码完成 |
| 图片识别 | mimo-v2.5 多模态模型分析图片消息，支持任务截图和人物识别 | ✅ 代码完成，已修复 |

**~~部署阻塞项~~（已全部修复）：**
1. ~~`handler.py:259` 调用不存在的 `notifier.notify_meeting_notification()`~~ → 改为 `wechat_bot.send_meeting_notification()`
2. ~~`.env.example` 缺少 `WECHAT_CALLBACK_TOKEN` 和 `WECHAT_ENCODING_AES_KEY`~~ → 已补全
3. ~~`_pending_users` / `_group_buffers` 为内存状态~~ → 已迁移到 Redis（自动过期）
4. ~~异常处理全部用 `print()`~~ → 改用 `logging.getLogger("microbubble.wechat")`
5. ~~Nginx 未配置微信 5 秒超时优化~~ → 异步 `asyncio.create_task` + 立即返回 success

**新建文件：**
- `app/wechat/crypto.py` — 消息加解密（AES-CBC + 签名验证）
- `app/wechat/handler.py` — 消息处理（任务回复识别 + Agent 对话 + 群聊被动监听）
- `app/wechat/notifier.py` — 主动通知（任务分配/完成/问题/汇总）
- `app/wechat/identity.py` — 多信号身份解析（userid/昵称/手机/微信号模糊匹配）
- `app/wechat/analyzer.py` — 对话智能分析（Claude API 提取任务/会议/决定）
- `app/wechat/scheduler.py` — 主动提醒调度器（Celery task，每15分钟执行）
- `app/services/vision_service.py` — 视觉识别服务（Claude Vision 图片分析）
- `app/api/v1/wechat.py` — Webhook 回调端点

**修改文件：**
- `app/config.py` — 新增 WECHAT_CALLBACK_TOKEN、WECHAT_ENCODING_AES_KEY
- `app/main.py` — 注册 wechat 路由
- `app/wechat/bot.py` — 新增 reply_to_user 方法
- `app/core/celery.py` — 新增 proactive-checks 定时任务（每15分钟），autodiscover wechat 模块
- `app/services/reminder_service.py` — 添加 `@shared_task` 装饰器
- `app/models/member.py` — 新增多平台身份字段（wechat_nickname/wechat_remark/personal_wechat_id/wechat_mobile）
- `app/schemas/member.py` — MemberCreate/MemberUpdate/MemberResponse 包含新身份字段
- `app/api/v1/member.py` — 创建成员支持新身份字段

### 微信互通 (2026-05-18) -- 支持普通微信用户

课题组成员可用私人微信与机器人对话，无需下载企业微信。通过企业微信「微信互通」外部联系人功能实现。

| 功能 | 说明 | 状态 |
|------|------|------|
| 外部用户识别 | 通过 `external_userid`（wm 开头）自动识别普通微信用户 | ✅ 完成 |
| 双通道发送 | 内部用户走 `/cgi-bin/message/send`，外部用户走 `/cgi-bin/externalcontact/message/send` | ✅ 完成 |
| 外部群聊 | 外部群（wr 开头）走 `/cgi-bin/externalcontact/groupchat/send_chat_msg` | ✅ 完成 |
| 智能路由 | `smart_send()` / `smart_send_to_group()` 自动选择正确的 API | ✅ 完成 |
| 身份绑定 | 外部用户首次使用时通过姓名/手机号自引导绑定 | ✅ 完成 |
| 通知适配 | 任务提醒、会议通知、进度汇报等全部支持外部用户 | ✅ 完成 |

**新建文件：**
- `alembic/versions/002_add_external_userid.py` — 数据库迁移

**修改文件：**
- `app/models/member.py` — 新增 `external_userid` 列
- `app/schemas/member.py` — 新增 `external_userid` 字段
- `app/config.py` — 新增 `WECHAT_EXTERNAL_SENDER` 配置
- `.env.example` — 新增 `WECHAT_EXTERNAL_SENDER`
- `app/wechat/identity.py` — 新增 `resolve_by_external_userid()`，更新 `resolve_multi_signal()` 和 `bind_identity()`
- `app/wechat/bot.py` — 新增 `send_to_external_user()`、`send_to_external_group()`、`smart_send()`、`smart_send_to_group()`
- `app/wechat/handler.py` — 外部用户检测、身份解析、回复路由、群聊适配
- `app/wechat/notifier.py` — 方法签名改为接收 `Member` 对象，使用 `smart_send()`
- `app/wechat/scheduler.py` — 全部改用 `smart_send()` 支持外部用户
- `app/services/reminder_service.py` — 改用 `smart_send()`，修复 `print()` 为结构化日志

### Phase 3 (2026-05-17)

| 问题 | 修复内容 |
|------|---------|
| Chat session 存内存 | 迁移到 Redis（`RedisSessionStore`），24小时 TTL，重启不丢失 |
| dashboard N+1 查询 | 项目/成员统计改用 `func.count()` + `GROUP BY` 单条 SQL 聚合 |
| 无用依赖 | 移除 langchain, langchain-anthropic, chromadb, minio, pyannote-audio，去重 httpx |
| SECRET_KEY 不安全 | 生产环境检测默认值，未配置则 `sys.exit(1)`；开发环境 `warnings.warn` |
| 无数据库迁移 | 初始化 Alembic，async env.py，初始迁移脚本含全部 9 张表 |
| CORS 全开放 | 替换为显式白名单（localhost:5173/3000 + 生产域名） |
| 登录无限流 | 滑动窗口限流器（`rate_limit.py`），5分钟/5次/IP，失败也计数 |
| 登录页泄露密码 | 移除硬编码账号密码，改为"请联系管理员" |

**新建文件：**
- `app/core/rate_limit.py` — 滑动窗口限流器
- `app/core/redis.py` — 扩展：新增 `RedisSessionStore` 类
- `alembic.ini` — Alembic 配置
- `alembic/env.py` — 异步迁移环境
- `alembic/script.py.mako` — 迁移模板
- `alembic/versions/001_initial.py` — 初始迁移（9张表 + pgvector 扩展）

**修改文件：**
- `app/config.py` — SECRET_KEY 默认值改为空字符串
- `app/main.py` — SECRET_KEY 校验 + CORS 白名单 + Redis 关闭
- `app/api/v1/auth.py` — 登录端点接入限流器
- `app/api/v1/task.py` — dashboard 和 list 改用聚合查询
- `app/agent/core.py` — session 迁移到 Redis（`_load_session`/`_save_session`）
- `web/src/views/LoginView.vue` — 移除硬编码账号密码
- `requirements.txt` — 移除 5 个无用依赖，去重 httpx

### Phase 4 (2026-05-17)

| 问题 | 修复内容 |
|------|---------|
| 无日志配置 | `app/core/logging.py` 统一日志，生产环境 RotatingFileHandler |
| Dashboard ECharts 不显示 | 确认 `<script setup>` 自动注册，无需修改 |
| 通知角标硬编码 | MainLayout 改为从 API 获取提醒数量，user store 管理 |
| 会议转写未保存 | voice.py WebSocket 断开后自动存入 meeting.transcript |
| meeting.py 转写 stub | 已在 voice.py 实现，meeting.py 无需重复 |
| Whisper 双重加载 | asr.py 改为 HTTP 优先调用远程服务，回退本地模型 |
| 无 Pinia store | 新增 user store + member store + format 工具函数 |
| 无测试 | 新增 conftest.py + 3 个测试文件（auth/tasks/members） |

**新建文件：**
- `app/core/logging.py` — 统一日志配置
- `app/core/rate_limit.py` — 滑动窗口限流器
- `web/src/stores/member.js` — 成员 Pinia store
- `web/src/stores/user.js` — 用户 Pinia store
- `web/src/utils/format.js` — 日期格式化工具
- `tests/conftest.py` — 测试 fixtures（db/client/auth）
- `tests/test_auth.py` — 认证测试（登录/刷新/修改密码）
- `tests/test_tasks.py` — 任务测试（CRUD/统计/dashboard）
- `tests/test_members.py` — 成员测试（CRUD/权限）
- `pytest.ini` — pytest 配置

**修改文件：**
- `app/api/v1/voice.py` — 转写断开后保存到数据库
- `app/api/v1/task.py` — 新增 reminders/pending-count 端点
- `app/voice/asr.py` — 改为远程 Whisper 优先 + 本地回退
- `app/main.py` — 引入 logging 模块
- `web/src/layouts/MainLayout.vue` — 接入 user store + member store

### Phase 5 (2026-05-17)

| 功能 | 说明 | 状态 |
|------|------|------|
| 腾讯会议 API | 创建/查询/取消/结束会议，HMAC-SHA256 签名，Webhook 回调，Agent 自动创建线上会议，错误重试 | ✅ 代码完成，待配置凭据测试 |
| MinIO 文件上传 | 通用上传（50MB 限制）+ 会议附件 + 删除，自动创建 bucket | ✅ 完成 |
| 企业微信群机器人 | 完整实现（已在 WeChat Bot 阶段完成） | ⚠️ 代码完成，未部署（见 WeChat Bot 部署阻塞项） |
| 会议转写自动分析 | 转写结束自动调用 Claude 提取摘要/要点/决定，自动创建任务并关联会议，支持手动重新分析 | ✅ 完成 |
| CLAUDE_MODEL 可配置 | 新增配置项，兼容代理服务的 ThinkingBlock 响应 | ✅ 完成 |

**新建文件：**
- `app/services/tencent_meeting_service.py` — 腾讯会议 API 客户端（HMAC-SHA256 签名）
- `app/services/file_service.py` — MinIO 文件存储服务
- `app/api/v1/tencent_meeting.py` — 腾讯会议 API 端点（创建/关联/查询/取消）
- `app/api/v1/upload.py` — 文件上传 API 端点（通用/会议附件/删除）

**修改文件：**
- `app/main.py` — 注册 upload 和 tencent_meeting 路由
- `requirements.txt` — 恢复 minio==7.2.0
- `app/services/meeting_service.py` — 新增 `process_meeting_transcript()`、`_generate_summary()`、`_auto_create_task_from_meeting()`
- `app/api/v1/voice.py` — WebSocket 断开后自动触发会议分析
- `app/api/v1/meeting.py` — 新增 `POST /meetings/{id}/analyze` 手动分析端点
- `app/api/v1/tencent_meeting.py` — Webhook 会议结束时自动触发分析
- `app/wechat/analyzer.py` — 模型改为 `settings.CLAUDE_MODEL`，兼容 ThinkingBlock 响应
- `app/config.py` — 新增 `CLAUDE_MODEL`

### 前端图片识别 (2026-05-19)

| 功能 | 说明 | 状态 |
|------|------|------|
| 图片上传 | 前端支持选择图片文件，预览后发送 | ✅ 完成 |
| 多模态对话 | 使用 mimo-v2.5 模型分析图片内容，支持图片+文字混合消息 | ✅ 完成 |
| 图片消息展示 | 消息列表支持显示图片，点击可全屏预览 | ✅ 完成 |
| API 图片接口 | 新增 `POST /chat/image` 接口，支持 multipart/form-data 图片上传 | ✅ 完成 |
| WebSocket 图片 | WebSocket 支持 base64 编码的图片消息 | ✅ 完成 |
| 企业微信视觉 | vision_service 改用配置的模型（默认 mimo-v2.5） | ✅ 完成 |

**修改文件：**
- `app/agent/core.py` — `chat()` 和 `chat_stream()` 新增 `image_data` 和 `image_media_type` 参数，构建多模态消息
- `app/api/v1/chat.py` — 新增 `POST /chat/image` 接口，WebSocket 支持图片消息
- `app/services/vision_service.py` — `analyze_image()` 改用 `settings.CLAUDE_MODEL` 或 `mimo-v2.5`
- `web/src/views/ChatView.vue` — 新增图片上传按钮、预览功能、图片消息展示、相关样式

### 企业微信图片处理修复 (2026-05-19)

| 问题 | 修复内容 |
|------|---------|
| 微信发送图片显示"图片处理出错了" | vision_service.py 添加异常处理和日志记录 |
| 模型配置错误 | 改用 `settings.CLAUDE_MODEL or "mimo-v2.5"` 替代硬编码的 `claude-sonnet-4-20250514` |
| media_type 硬编码 | 添加 `_detect_media_type()` 方法，根据图片魔数自动检测格式 |
| Docker 容器代码未同步 | 重新构建镜像并重启容器 |

**修改文件：**
- `app/services/vision_service.py` — 添加 try/except 异常处理、结构化日志、更健壮的响应解析、自动检测 media_type

**状态：** ✅ 已修复，图片识别功能正常工作

### 联网搜索 (2026-05-19)

| 功能 | 说明 | 状态 |
|------|------|------|
| 搜狗微信搜索 | 通过 weixin.sogou.com 搜索微信公众号文章，国内可直连 | ✅ 完成 |
| 必应搜索 | 通过 www.bing.com 搜索，作为补充引擎 | ✅ 完成 |
| 双引擎并发 | 两个搜索引擎并发请求，按 URL 去重合并结果 | ✅ 完成 |
| 流式工具调用修复 | 修复 chat_stream 中 input_json 被覆盖而非追加的 bug | ✅ 完成 |
| SDK 方法名修复 | get_final_response 改为 get_final_message（SDK 0.103.0） | ✅ 完成 |
| 回复格式优化 | 系统提示词去除 markdown 格式，避免模型模仿产生混乱排版 | ✅ 完成 |
| 禁止编造网址 | 提示词约束模型只使用搜索结果中的 URL，不自行编造 | ✅ 完成 |

**修改文件：**
- `app/services/search_service.py` — 完整重写：搜狗微信+必应双引擎并发搜索
- `app/agent/core.py` — 修复流式 input_json 拼接 bug + get_final_message 方法名
- `app/agent/prompts.py` — 去除 markdown 格式，添加搜索回复格式规范

### Claude Code 任务通知优化 (2026-05-19)

| 功能 | 说明 | 状态 |
|------|------|------|
| 音量调至最大 | `$synth.Volume = 100`，Rate 调为 -1 更清晰 | ✅ 完成 |
| 提示词加长 | 从"任务完成啦"改为完整提示语 | ✅ 完成 |

**修改文件：**
- `.claude/notify.ps1` — 音量最大 + 语速调整
- `.claude/settings.json` — Stop hook 提示词更新

---

## 部署架构（2026-05-18 确定）

采用 **云服务器 + 本地电脑 FRP 穿透** 方案：

```
用户 → 云服务器 (Nginx + SSL + FRP 服务端) → FRP 隧道 → 本地电脑 (全部 Docker 服务 + GPU Whisper)
```

- **云服务器**（2核 2G）：只运行 Nginx 反向代理 + FRP 服务端，轻量无压力
- **本地电脑**（有 GPU）：运行全部应用服务（app、PostgreSQL、Redis、MinIO、Whisper GPU、Celery）
- **FRP 隧道**：本地 8000 端口穿透到云服务器，用户通过 `https://agent.mnb-lab.cn` 访问

## 待完成：生产部署与上线

### 部署代码准备 ✅

- [x] docker-compose.yml 添加 Nginx 服务 + app 端口映射
- [x] 创建 Nginx 生产配置（HTTP/HTTPS，安全头，WebSocket 代理）
- [x] 部署脚本：`deploy-cloud.sh`（云服务器）、`deploy-local.sh`（本地电脑）
- [x] FRP 内网穿透配置（frps.toml / frpc.toml）
- [x] Whisper 改为 GPU 模式（Dockerfile.whisper 支持环境变量配置）
- [x] Claude API 支持代理地址（`CLAUDE_BASE_URL` 配置项）
- [x] `.env.example` 补全 `WECHAT_CALLBACK_TOKEN` 和 `WECHAT_ENCODING_AES_KEY`

### 云服务器部署 ✅

- [x] FRP 服务端安装（v0.61.1，已配置 systemd 自启动）
- [x] FRP 服务端配置（端口 7000，token 认证）
- [x] Nginx 安装
- [x] 前端构建并部署（本地构建 → 压缩 → 阿里云文件管理上传 → 服务器解压）
- [x] Nginx 配置部署（更新已有 agent 配置，HTTPS + SSL 已有证书）
- [x] 防火墙配置（开放 80/443/7000 端口）
- [x] 恢复之前的网站配置 ✅
- [x] SSL 证书（已有 Let's Encrypt 证书，直接复用）

### 本地电脑部署 ✅

- [x] 安装 Docker Desktop ✅
- [x] 配置 .env 文件（Claude API Key + 代理地址）
- [x] Docker 全服务构建（app/db/redis/minio/celery-worker/celery-beat）
- [x] FRP 客户端连接云服务器
- [x] 通过域名访问测试（API 正常响应）
- [x] Docker 数据迁移到 G 盘（释放 C 盘 68GB，通过符号链接无感迁移）
- [x] 一键启动/停止/状态脚本（start.bat / stop.bat / status.bat）

### 企业微信部署

- [x] 修复 `handler.py:259` 运行时 bug（改为 `wechat_bot.send_meeting_notification()`）
- [x] 内存状态（`_pending_users` / `_group_buffers`）迁移到 Redis（自动过期）
- [x] 异常处理改用结构化日志（`logging.getLogger("microbubble.wechat")`）
- [x] @提及检测改为匹配企业微信实际格式（` @` 分隔符 + AgentID 匹配）
- [x] Nginx 已满足 5 秒超时（异步 `asyncio.create_task` + 立即返回 success）
- [x] 通知消息格式修复（markdown → text，插件端不支持 markdown 渲染）
- [x] `wechat_id` 从昵称同步为真实 UserId（`list_department_members()` API）
- [x] 通知代码独立 try/except + 结构化日志 + errcode 检查
- [ ] 9 位成员未在企业微信通讯录中，需在管理后台添加后才能接收提醒推送

### 微信互通部署（普通微信用户支持） - ✅ 已完成

> **当前方案**：使用企业微信「微信插件」功能，成员只需注册一次企业微信，之后可在普通微信内与小气对话，无需额外配置。
> **微信互通适用场景**：如有外部用户（不愿注册企业微信的人）需要联系小气，再启用此功能。

**微信互通配置步骤（已完成）：**

- [x] 企业微信管理后台创建机器人专属成员账号（如 `xiaoqi`）
- [x] 开通「客户联系」→ 将 `xiaoqi` 加入可使用范围
- [x] 创建「联系我」二维码（单人模式，选 `xiaoqi`）
- [x] 配置回调：勾选客户联系相关事件（`change_external_contact`、`change_external_chat`）
- [x] `.env` 配置 `WECHAT_EXTERNAL_SENDER=xiaoqi`
- [x] 运行数据库迁移：`alembic upgrade head`
- [x] 用普通微信扫码添加「小气」，测试私聊消息收发
- [x] 创建外部群，拉「小气」进群，测试群聊消息收发
- [x] 从日志获取群聊 `wr...` chat_id：`docker compose logs app | grep chat_id`

### 腾讯会议部署

- [x] 修正签名算法（HMAC-SHA256，URI 加 openapi 前缀）
- [x] 添加 `host.userid` 参数（创建会议必须）
- [x] Agent `create_meeting` 工具集成腾讯会议 API（自动创建线上会议）
- [x] 添加 Webhook 回调端点（`/api/v1/tencent-meeting/webhook`）
- [x] 添加错误重试（3 次，指数退避）
- [x] 新增 list/end 端点
- [ ] 申请并配置真实 API 凭据（`TENCENT_MEETING_SDK_ID` / `TENCENT_MEETING_SDK_KEY` / `TENCENT_MEETING_USERID`）
- [ ] 企业微信管理后台配置 Webhook 回调 URL
- [ ] 凭据到位后端到端测试

---

## 第六阶段：功能增强

### 联网搜索

- [x] **Agent 工具集成联网搜索** -- 新增 `web_search` 工具，搜狗微信+必应双引擎并发搜索，无需 API Key
- [x] **搜索结果摘要** -- 搜索结果由 LLM 整理后返回，避免直接返回原始网页内容
- [x] **搜索来源引用** -- 回复中附带信息来源链接，方便用户查证
- [x] **搜索权限控制** -- 搜索功能始终可用，无需额外配置

### 长期记忆 (2026-05-19)

- [x] **用户偏好记忆** -- 记住用户的常用设置、偏好习惯，preference 类型按 key 去重
- [x] **对话历史摘要** -- 对话结束后后台自动提取值得记忆的信息（偏好/实体/摘要）
- [x] **知识图谱构建** -- 从对话中提取实体关系（人员-项目-成果），entity 类型存储
- [x] **记忆检索与更新** -- 新对话自动检索相关记忆注入系统提示词，支持手动编辑/遗忘
- [x] **记忆存储方案** -- PostgreSQL + pgvector 语义搜索，importance 衰减机制

**新建文件：**
- `app/models/memory.py` — Memory 模型（preference/summary/entity 三种类型）
- `app/services/memory_service.py` — 记忆 CRUD + 语义搜索 + LLM 自动提取
- `app/api/v1/memory.py` — 记忆管理 API（列表/编辑/删除）
- `alembic/versions/004_add_memory_table.py` — 数据库迁移
- `web/src/views/MemoryView.vue` — 记忆管理前端页面

**修改文件：**
- `app/models/__init__.py` — 注册 Memory 模型
- `app/agent/tools.py` — 新增 save_memory/search_memory/forget_memory 三个工具
- `app/agent/core.py` — chat() 新增 user_id 参数，记忆注入系统提示词，后台自动提取记忆
- `app/agent/prompts.py` — 添加长期记忆使用规则
- `app/api/v1/chat.py` — 所有端点传递 user_id 给 agent
- `app/main.py` — 注册 memory 路由
- `app/core/celery.py` — 新增 memory-maintenance 定时任务（每小时衰减重要性）
- `web/src/router/index.js` — 新增 /memory 路由

### 对话窗口文件上传 (2026-05-19)

- [x] **前端文件上传组件** -- 对话窗口回形针按钮，支持上传图片、PDF、Word、Excel 等文件
- [x] **图片预览与发送** -- 图片和文件分别显示预览，支持文件名和大小显示
- [x] **文件内容提取** -- 后端 pdfplumber/python-docx/openpyxl 解析文件，提取文本发送给 Agent
- [x] **文件对话上下文** -- 上传的文件内容自动注入对话上下文，支持基于文件内容的问答
- [x] **文件存储管理** -- 上传的文件存储到 MinIO（chat/{session_id}/ 前缀），返回文件 URL

**新建文件：**
- `app/services/file_parser_service.py` — 文件内容提取服务（PDF/Word/Excel/TXT/Markdown）

**修改文件：**
- `app/api/v1/chat.py` — 新增 POST /chat/file 端点，ChatResponse 添加 file_url/file_name
- `web/src/views/ChatView.vue` — 回形针按钮、文件预览、统一发送逻辑

### 知识库增强 (2026-05-19)

- [x] **知识库文件上传** -- 知识库页面新增上传按钮，支持拖拽上传 PDF/Word/TXT/Markdown 文件
- [x] **文件自动解析** -- 上传后自动提取文本内容，后台生成摘要和关键词
- [x] **智能分类分析** -- LLM 自动分析文件内容，自动归类到合适的分类
- [x] **自动标签生成** -- 根据文件内容自动生成标签
- [x] **分类统计面板** -- 知识库页面顶部展示各分类文件数量统计，支持点击筛选

**新建文件：**
- `app/services/llm_analysis_service.py` — LLM 内容分析服务（自动分类+标签+摘要）
- `alembic/versions/003_knowledge_file_upload.py` — 知识表添加文件列

**修改文件：**
- `app/models/knowledge.py` — 新增 file_path/file_name/file_type/summary 列
- `app/schemas/knowledge.py` — KnowledgeResponse 添加文件字段，修复 KnowledgeSearchResult
- `app/services/knowledge_service.py` — 修复 embedding 自动生成 bug，新增 create_from_file()
- `app/api/v1/knowledge.py` — 修复分页 total bug，新增 /upload 和 /stats 端点
- `requirements.txt` — 新增 pdfplumber/python-docx/openpyxl
- `web/src/views/KnowledgeView.vue` — 上传对话框、分类统计面板、文件图标、修复搜索结果显示

### 对话知识自动入库 (2026-05-19)

- [x] **对话知识提取工具** -- 新增 `save_conversation_knowledge` 工具，Agent 可主动将有价值的对话内容保存到知识库
- [x] **后台自动提取** -- 每次对话结束后 LLM 自动分析内容，提取实验方法、研究发现、技术方案等专业知识
- [x] **智能分类打标签** -- 提取的知识自动分类（基础/方法/文献/FAQ）并生成标签和摘要
- [x] **对话来源标记** -- 知识库中来自对话的条目显示 💬 标记，详情页标注"来自对话记录，AI 自动提取"

**修改文件：**
- `app/agent/tools.py` — 新增 save_conversation_knowledge 工具定义
- `app/agent/core.py` — 新增 `_extract_and_save_knowledge` 后台任务，chat() 中触发知识提取
- `app/agent/prompts.py` — 系统提示词新增知识库保存规则
- `app/services/knowledge_service.py` — 新增 `create_from_conversation()` 方法
- `web/src/views/KnowledgeView.vue` — 对话来源标记样式

### 成员身份系统全面升级 (2026-05-20)

| 问题 | 修复内容 |
|------|---------|
| 插件身份冲突 | 微信插件 `from_user` 是真实 ID 时用它识别，是 agent app name 时走验证流程，不绑定 agent ID |
| 验证缓存 key 碰撞 | `_get_plugin_cache_key` 统一缓存 key 逻辑，`from_user` 是真实 ID 时用它做 key |
| 群聊/私聊 user_id 错误 | `_handle_group_message` 和 `_handle_private_message` 改用 `msg["_resolved_user_id"]` |
| bind_identity 永不覆盖 | 新增 `force` 参数，`True` 时覆盖已有值，`False` 时仅填充空字段 |
| 重名返回任意匹配 | `resolve_by_nickname` 改为返回 `List[Member]`，多人同名时进入消歧流程 |
| 验证缓存无失效 | 新增 `invalidate_verified_cache_for_member()`，验证成功/成员停用时清除旧缓存 |
| kf_service open_kfid 未传递 | `_call_agent_for_kf` 增加 `open_kfid` 参数，移除无效的 `hasattr` 判断 |
| _handle_event 未设 _reply_to | 事件处理也设置 `msg["_reply_to"]`，与 handle_message 一致 |

**修改文件：**
- `app/core/redis.py` — 新增 `invalidate_verified_cache_for_member()` 工具函数
- `app/wechat/identity.py` — `resolve_by_nickname` 返回列表 + `bind_identity` 增加 `force` 参数
- `app/wechat/handler.py` — 7 处改动（插件身份、缓存 key、群聊/私聊 user_id、重名消歧、事件回复、客服 open_kfid）
- `app/api/v1/member.py` — 删除成员时清除验证缓存

### 前端体验优化 (2026-05-19)

- [x] **知识库标签美化** -- 分类改为彩色徽章（蓝/绿/橙/紫），标签改为圆角药丸样式
- [x] **分类统计增强** -- 统计面板增加 emoji 图标，点击支持筛选切换，hover 上浮动效
- [x] **分类标签栏** -- 改为圆角药丸样式，选中态蓝色高亮
- [x] **AI 摘要展示** -- 知识详情弹窗 AI 摘要区域独立展示（蓝色渐变背景 + 左侧边框）
- [x] **文件上传提示** -- 上传对话框增加 AI 自动分析提示条
- [x] **对话拖拽上传** -- 小气助手输入区域支持拖拽文件/图片上传，拖入时显示蓝色虚线边框
- [x] **上传按钮优化** -- 上传按钮增加 hover 高亮，文件按钮 tooltip 补充格式说明

**修改文件：**
- `web/src/views/KnowledgeView.vue` — 标签/分类/统计面板/详情弹窗/上传对话框全面美化
- `web/src/views/ChatView.vue` — 拖拽上传支持、Upload 图标导入、上传按钮样式

### 时间精度全面升级 (2026-05-20)

将整个系统的时间处理从"天级"提升到"分钟级"，统一北京时间/UTC 时区处理。

| 改动 | 说明 | 状态 |
|------|------|------|
| 系统提示词注入精确时间 | `get_system_prompt()` 动态注入 `YYYY年M月D日 星期X HH:MM`，Agent 感知当前时间 | ✅ 完成 |
| 用户消息注入时间标签 | 每条消息前加 `[当前时间: YYYY-MM-DD HH:MM]`，防止模型引用历史过期时间 | ✅ 完成 |
| due_date 精度提升 | 工具描述改为 `YYYY-MM-DD HH:MM`，解析先尝试精确格式再 fallback 日期 | ✅ 完成 |
| 提醒消息精确时间 | `_format_reminder_message` 用 `total_seconds()` 替代 `.days`，显示"还有X小时/分钟到期" | ✅ 完成 |
| 时区统一 | 全局 `utcnow()` 返回 naive UTC，Agent 解析时先转北京时间再转 UTC 存储 | ✅ 完成 |
| 默认提醒优化 | 根据距截止时间远近自适应：≤1h→1分钟后提醒，≤24h→提前30分钟，>24h→提前2天+2小时 | ✅ 完成 |
| 前端 datetime 选择器 | Dashboard/TaskView 截止日期改为 `type="datetime"`，支持选择具体时间 | ✅ 完成 |

**修改文件：**
- `app/agent/prompts.py` — `get_system_prompt()` 动态注入当前时间
- `app/agent/core.py` — 用户消息注入时间标签 + due_date/reminders 北京时间→UTC 转换 + `update_task` 支持 due_date
- `app/agent/tools.py` — due_date/reminders 参数描述更新
- `app/models/base.py` — `utcnow()` 改为 `datetime.now(timezone.utc).replace(tzinfo=None)`
- `app/services/reminder_service.py` — `_format_reminder_message` 精确时间显示
- `app/services/task_service.py` — `_create_default_reminders` 自适应提醒策略
- `web/src/views/Dashboard.vue` — datetime 选择器 + 时间显示
- `web/src/views/TaskView.vue` — datetime 选择器
- 约 15 个文件的 `datetime.utcnow()` 替换为 `utcnow()`

### Redis 精确提醒调度 (2026-05-20)

使用 Redis 有序集合（ZSET）实现秒级精度的提醒调度，替代原来纯 DB 15 分钟轮询。

| 功能 | 说明 | 状态 |
|------|------|------|
| Redis ZSET 调度 | 提醒创建时同步到 Redis ZSET，score 为 remind_at 时间戳 | ✅ 完成 |
| 秒级精度检查 | Celery 每 10 秒扫描 Redis ZSET，获取 score ≤ 当前时间的提醒 | ✅ 完成 |
| DB 兜底 | Redis 为空时从 DB 查询待发送提醒，自动同步到 Redis | ✅ 完成 |
| 启动同步 | app 启动时自动将所有 pending 提醒从 DB 同步到 Redis | ✅ 完成 |
| 批量清理 | 提醒处理后从 Redis 批量移除已发送的 ID | ✅ 完成 |

**新建文件：**
- `app/services/reminder_scheduler.py` — Redis 精确提醒调度器

**修改文件：**
- `app/services/task_service.py` — 创建提醒时同步到 Redis
- `app/services/reminder_service.py` — `process_reminders()` 优先从 Redis 获取
- `app/core/celery.py` — `check-reminders` 从 60 秒改为 10 秒
- `app/main.py` — 启动时同步 pending 提醒到 Redis

### Celery 任务连接池修复 (2026-05-20)

修复 Celery worker 中 SQLAlchemy 和 Redis 的跨事件循环连接池冲突。

| 问题 | 修复内容 |
|------|---------|
| SQLAlchemy "another operation is in progress" | 每个 Celery 任务创建独立 engine + `NullPool`，不复用全局连接池 |
| Redis "Event loop is closed" | 每个 Celery 任务创建独立 Redis 客户端，通过 `redis_override` 参数传入 |
| `beijing_tz` 未定义 | 移到 `due_date` 解析块之前，避免仅有 reminders 时 NameError |

**修改文件：**
- `app/services/reminder_service.py` — `process_reminders_task` 创建独立 engine + Redis，`process_reminders` 接受 `redis_override`
- `app/wechat/scheduler.py` — `run_proactive_checks` 创建独立 engine，`run_all_checks` 接受 `db` 参数
- `app/services/memory_service.py` — `maintenance_task` 创建独立 engine

### 微信插件 UserId 自动绑定 (2026-05-20)

修复微信插件用户 `wechat_id` 存储的是显示名而非 UserId 的问题。

| 问题 | 修复内容 |
|------|---------|
| `wechat_id` 是显示名 | 识别到插件用户且 `from_user` 是真实 UserId 时，自动绑定到 `wechat_id` |
| API 发送失败 | `errcode: 81013 "user & party & tag all invalid"` — `touser` 需要 UserId 而非显示名 |
| 多处绑定逻辑 | 验证缓存识别、昵称匹配、handle_message 三处均加入插件用户绑定 |
| 部分成员手动修复 | 通过企业微信 API 查询 UserId，修正张懿/耿嘉栋/张宏魁/吴孟铨的 `wechat_id` |

**修改文件：**
- `app/wechat/handler.py` — 三处添加插件用户 UserId 绑定逻辑
- `app/services/reminder_service.py` — 发送失败时记录 API 响应详情

**待解决：** 部分成员（如邓国祥）未在企业微信通讯录中，需在管理后台添加后才能接收提醒推送。

### 任务权限修复 (2026-05-20)

| 问题 | 修复内容 |
|------|---------|
| assignee 无法编辑自己的任务 | 权限检查从 `created_by` 扩展为 `created_by OR assignee_id` |
| Agent 工具权限 | `_execute_tool` update_task 权限检查加入 `assignee_id` |
| API 权限 | PUT/DELETE 端点同步修复 |

**修改文件：**
- `app/agent/core.py` — update_task 权限检查
- `app/api/v1/task.py` — PUT/DELETE 端点权限检查

### 主动提醒去重 (2026-05-20)

| 问题 | 修复内容 |
|------|---------|
| 同一任务每15分钟重复提醒 | Redis SET 记录已提醒任务，24小时过期后才会再次提醒 |
| check_due_soon/check_overdue/check_unconfirmed | 三个检查方法均加入去重逻辑 |
| Celery Redis 连接 | 创建独立 Redis 客户端，与 reminder_service 同模式（NullPool） |

**修改文件：**
- `app/wechat/scheduler.py` — 新增 `_already_notified`/`_mark_notified` 方法，三个检查方法加去重，Celery task 传入 Redis 客户端

### 管理员身份感知 + Agent 回答准确性 (2026-05-20)

| 功能 | 说明 | 状态 |
|------|------|------|
| 系统提示词注入用户身份 | 当前用户姓名+角色注入系统提示词，管理员权限可见 | ✅ 完成 |
| query_tasks 返回真实人名 | 工具返回增加 `assignee_name` 字段，批量查询成员姓名映射 | ✅ 完成 |
| 禁止编造人名 | 系统提示词约束：必须使用工具返回的真实姓名 | ✅ 完成 |

**修改文件：**
- `app/agent/core.py` — `_build_system_prompt` 注入用户身份，`query_tasks` 返回 `assignee_name`
- `app/agent/prompts.py` — 回复格式增加人名约束

### 企业微信通知可靠化 (2026-05-20)

修复管理员通过 Agent/API 给成员分配任务后，成员收不到企业微信通知的问题。

| 问题 | 修复内容 |
|------|---------|
| `wechat_id` 存的是昵称而非 UserId | 数据库 17/28 成员的 `wechat_id` 是显示名（如"流苏"），企业微信 API 要求 UserId（如"LiuSu"）。通过 `list_department_members()` API 同步真实 UserId |
| 通知结果被静默丢弃 | `notify_task_assigned()` 返回值从未检查，WeChat API errcode 被忽略。添加独立 try/except + errcode 检查 + 结构化日志 |
| 异常被 `_execute_tool` 大 try/except 吞掉 | 通知代码用独立 try/except 包裹，不影响任务创建返回值 |
| markdown 格式不兼容 | `notifier.py` 所有方法从 `msg_type="markdown"` 改为 `msg_type="text"`，企业微信插件端不支持标准 `**bold**` 语法 |
| 时区显示错误 | 提醒消息和任务通知的时间从 UTC 改为北京时间（UTC+8） |
| `check_overdue` 跳过无 wechat_id 的成员 | 分离负责人和创建人通知逻辑，负责人无标识时仍通知创建人 |
| `send_reminder` 静默标记已发送 | 重构为仅在实际发送成功后才标记 `status="sent"`，失败返回 False 供重试 |

**新建文件/接口：**
- `GET /api/v1/debug/wechat-notify/{member_name}` — 调试接口，测试给指定成员发送企业微信通知
- `POST /api/v1/debug/sync-wechat-ids` — 管理员接口，从企业微信 API 同步成员 UserId

**修改文件：**
- `app/wechat/notifier.py` — 6 个通知方法全部从 markdown 改为 text 格式
- `app/wechat/bot.py` — 新增 `list_department_members()` 方法
- `app/wechat/handler.py` — 插件用户 `wechat_id` 自动修复（正则校验 + force 绑定）；会议通知改用 text 格式
- `app/wechat/scheduler.py` — `check_overdue` 修复负责人/创建人独立通知；时区修正
- `app/agent/core.py` — 通知代码独立 try/except + 日志 + errcode 检查
- `app/api/v1/task.py` — 通知代码独立 try/except + 日志 + 调试接口
- `app/services/reminder_service.py` — 时区修正 + 发送失败不标记已发送

**验证结果：** 杨慈（wechat_id=LiuSu）成功收到任务分配通知和到期提醒。

**待解决：** 9 位成员（邓国祥、董昊宇、宋洋、王书馨、李锐远、孟祥琪、吴怡霏、周之超、蒋芦笛）未在企业微信通讯录中或名称不匹配，需在管理后台添加后才能接收提醒推送。

### 任务双向通知模式 (2026-05-20)

升级任务通知模型：管理员创建任务和任务即将到期时，同时通知管理员（创建人）和负责人（assignee）。

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 任务创建 | 仅通知负责人 | 通知负责人 + 通知创建人（派发确认） |
| 即将到期 | 仅通知负责人 | 通知负责人 + 通知创建人 |
| 已逾期 | 通知负责人 + 创建人 | 不变 |

**修改文件：**
- `app/wechat/notifier.py` — 新增 `notify_task_assigned_to_creator()` 和 `notify_due_soon_to_creator()` 方法
- `app/agent/core.py` — 任务创建后增加创建人派发确认通知
- `app/api/v1/task.py` — 同上
- `app/wechat/scheduler.py` — `check_due_soon()` 增加创建人通知

---

## Agent 会议转录总结工具 (2026-05-22)

用户可直接将会议转录文字发给小气助手，自动生成摘要、要点、决议，并永久存入 Agent 长期记忆（与项目记忆共用 `memories` 表）。

| 功能 | 说明 | 状态 |
|------|------|------|
| `summarize_meeting_transcript` 工具 | Agent 新工具，对话中直接触发，无需 API | ✅ 完成 |
| 会议总结存入记忆 | `memory_type="summary"`，与项目讨论共用语义搜索 | ✅ 完成 |
| `_generate_summary` 类方法化 | 改为 `@classmethod` 供 Agent 工具直接调用 | ✅ 完成 |

**修改文件：**
- `app/agent/tools.py` — 新增 `summarize_meeting_transcript` 工具定义
- `app/agent/core.py` — 新增工具处理器（生成摘要 + 提取行动项 + 存入记忆）
- `app/services/meeting_service.py` — `_generate_summary` 改为类方法

---

## 全员任务状况格式化输出 (2026-05-22)

解决 Agent 回答"给我说一下其他成员的任务状况"时输出格式不固定的问题，改为流程化固定格式输出。

| 功能 | 说明 | 状态 |
|------|------|------|
| `query_all_member_tasks` 工具 | Agent 新工具，查询全员任务状况 | ✅ 完成 |
| `get_all_members_workload()` 方法 | TaskService 新增，按成员分组统计 | ✅ 完成 |
| 固定格式输出 | 按状态分组：进行中→待办→已完成，固定三段结构 | ✅ 完成 |
| 权限控制 | 仅 admin/leader 可查，普通成员返回权限错误 | ✅ 完成 |
| 同人任务缩进显示 | 同一成员多条任务时，人名只显示一次，后续任务缩进对齐 | ✅ 完成 |
| pgvector 扩展安装 | 自定义 Dockerfile.db 基于 postgres:16-alpine 安装 pgvector 0.7.0 | ✅ 完成 |
| app 目录挂载 | docker-compose.yml app 服务添加 `./app:/app/app` volume，挂载本地代码 | ✅ 完成 |
| _generate_brief 传 db 参数 | 修复"先简要后详细"模式下简要生成器无法访问数据库的问题 | ✅ 完成 |

## 微信对话响应速度优化 (2026-05-25)

解决用户等待微信回复时间过长（4-16秒）无反馈的问题。

| 功能 | 说明 | 状态 |
|------|------|------|
| 双消息模式 | 用户发送后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台处理完再发正式回复 | ✅ 完成 |
| 异步处理 | Agent 对话改为 asyncio.create_task 后台执行，不阻塞消息发送 | ✅ 完成 |
| 语音重复反馈修复 | 语音消息设置 `_skip_thinking` 标志，避免重复发送思考中消息 | ✅ 完成 |
| 群聊同步优化 | 群聊 @机器人 同样采用双消息模式 | ✅ 完成 |

**修改文件：**
- `app/agent/tools.py` — 新增 `query_all_member_tasks` 工具定义
- `app/agent/core.py` — 新增工具处理器，格式化输出固定三段结构，同人任务缩进显示
- `app/services/task_service.py` — 新增 `get_all_members_workload()` 方法
- `app/agent/prompts.py` — 新增 Task Query Rules 强制 Agent 调用 query_all_member_tasks
- `Dockerfile.db` — 新建，基于 postgres:16-alpine 安装 pgvector 0.7.0
- `docker-compose.yml` — app 服务添加 `./app:/app/app` volume 挂载

---

## UI 全面升级（2026-05-24）

为前端建立统一的设计系统规范，并逐页升级界面。

### 设计系统建立 ✅

| 内容 | 说明 | 状态 |
|------|------|------|
| CSS 设计令牌 | `web/src/assets/variables.css` 全局 CSS 变量（颜色/阴影/圆角/字体/间距/动画） | ✅ 完成 |
| 暖橙珊瑚色系 | 主色 #FF7A5C，辅助色 #FFB347，温馨课题组风格 | ✅ 完成 |
| UI Design Skill | `.claude/skills/ui-design/SKILL.md` 前端设计规范（20个检查项） | ✅ 完成 |

### Dashboard 首页升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 侧边栏玻璃拟态 | 暖白半透明背景 + backdrop-filter 模糊，橙色指示条滑入动效 | ✅ 完成 |
| 欢迎区改版 | 珊瑚橙渐变背景 + 脉冲光晕装饰 + 动画按钮 | ✅ 完成 |
| 统计卡片大数字 | 去掉圆环进度条，改为大数字 + 彩色图标区 + 计数器动画 | ✅ 完成 |
| 任务分组折叠 | 点击负责人头部行展开/收起任务列表（ArrowDown 图标） | ✅ 完成 |
| 完成/编辑按钮 | 进行中/即将到期每行任务添加"完成"和"编辑"按钮 | ✅ 完成 |
| 骨架屏 | 统计卡片、任务列表、会议列表各自显示 shimmer 骨架加载态 | ✅ 完成 |
| 丰富动效 | staggered fadeSlideUp 入场、数字滚动动画、悬停卡片提升 | ✅ 完成 |
| 即将到期分组 | 按紧急程度（今天/明天/后天/逾期）分组，橙色/红色边框高亮 | ✅ 完成 |

### TaskView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| CSS 设计令牌全面应用 | 全部硬编码颜色替换为 CSS 变量 | ✅ 完成 |
| 卡片/按钮/标签样式 | 统一使用 variables.css 的 design token | ✅ 完成 |
| 任务分组折叠/展开 | 点击负责人头部行展开/收起，带 ArrowDown 图标动画 | ✅ 完成 |
| 动效类名统一 | fade-slide-up, stagger-1/2/3 系列入场动画 | ✅ 完成 |
| 负责人头像 hover 效果 | 圆形变圆角方形 scale(1.08) 悬停动效 | ✅ 完成 |

### ChatView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| CSS 设计令牌全面应用 | 全部硬编码颜色替换为 CSS 变量 | ✅ 完成 |
| 消息气泡 hover 动效 | scale + shadow 提升 | ✅ 完成 |
| 快捷按钮胶囊样式 | 圆角胶囊 + hover 上浮 + 颜色翻转 | ✅ 完成 |
| 发送按钮动效 | scale + brightness + shadow | ✅ 完成 |
| 打字指示器颜色 | dots 颜色改为珊瑚橙 | ✅ 完成 |
| 整体卡片入场动画 | fadeSlideUp fadeSlideUp | ✅ 完成 |

### MeetingView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| CSS 设计令牌全面应用 | 全部硬编码颜色替换为 CSS 变量 | ✅ 完成 |
| 会议卡片样式 | border-radius/box-shadow 统一 design token | ✅ 完成 |
| 会议项 hover 动效 | border-color + shadow + translateY(-2px) | ✅ 完成 |
| 日期大数字颜色 | 改为珊瑚橙 | ✅ 完成 |
| 操作按钮动效 | hover scale 动效 | ✅ 完成 |
| 筛选/列表卡片入场动画 | fadeSlideUp staggered | ✅ 完成 |

### KnowledgeView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 统计卡片渐变背景 | 改为珊瑚橙/金橙渐变 | ✅ 完成 |
| 分类标签 hover 动效 | 上浮 + 颜色翻转 | ✅ 完成 |
| 知识项 hover 动效 | border-color + shadow + translateY | ✅ 完成 |
| 标签 chip hover | 变为珊瑚橙 | ✅ 完成 |
| 搜索结果/AI摘要卡片 | 统一 design token | ✅ 完成 |
| 各卡片入场动画 | fadeSlideUp staggered | ✅ 完成 |

### MemberView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 成员卡片 hover 动效 | translateY + shadow + border-color | ✅ 完成 |
| 头像样式 | 圆角方形 + hover 缩放 | ✅ 完成 |
| 详情项图标颜色 | 改为珊瑚橙 | ✅ 完成 |
| 操作按钮 hover 动效 | 背景变为珊瑚橙浅色 | ✅ 完成 |
| 整体入场动画 | fadeSlideUp | ✅ 完成 |

### ProjectView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 项目卡片 hover 动效 | translateY + shadow + border-color | ✅ 完成 |
| 图标颜色 | 改为珊瑚橙 | ✅ 完成 |
| 成员标签 hover 动效 | 变为珊瑚橙 | ✅ 完成 |
| 整体入场动画 | fadeSlideUp | ✅ 完成 |

### MemoryView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 记忆卡片 hover 动效 | translateY + shadow + border-color | ✅ 完成 |
| 操作按钮 hover 动效 | 变为珊瑚橙 | ✅ 完成 |
| 整体入场动画 | fadeSlideUp | ✅ 完成 |

### LoginView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 背景渐变 | 改为珊瑚橙/金橙 | ✅ 完成 |
| 登录按钮 hover 动效 | 上浮 + 亮度提升 | ✅ 完成 |
| 整体卡片入场动画 | fadeSlideUp | ✅ 完成 |

---

**UI 全面升级已全部完成！** 所有页面（Dashboard / MainLayout / TaskView / ChatView / MeetingView / KnowledgeView / MemberView / ProjectView / MemoryView / LoginView）均已使用统一的设计令牌系统。
- [ ] **MeetingView** — 会议卡片样式、会议详情页
- [ ] **KnowledgeView** — 知识库列表、搜索结果样式
- [ ] **MemberView** — 成员卡片、头像样式
- [ ] **ProjectView** — 项目卡片、里程碑样式
- [ ] **MemoryView** — 记忆列表样式
- [ ] **LoginView** — 登录页珊瑚橙主题统一

---

## 待完成

### 开发环境 Docker 配置 (2026-05-20)

- [x] **docker-compose.dev.yml** -- 开发专用配置：app 热重载（`--reload`）、禁用 nginx/whisper、挂载 `./app` 目录
- 使用方式：`docker compose -f docker-compose.dev.yml up -d`

### GitHub Actions CI 流水线 (2026-05-20)

- [x] **ci.yml** -- push/PR 到 main 时自动触发：flake8 语法检查 + Docker 构建测试
- 不跑 pytest（需真实 PostgreSQL+pgvector），不做自动部署（已有 webhook 机制）

**新建文件：**
- `docker-compose.dev.yml` — 开发环境 Docker 配置
- `.github/workflows/ci.yml` — GitHub Actions CI 流水线

---

### 部署文档 + 生产环境加固 (2026-05-20)

| 内容 | 说明 | 状态 |
|------|------|------|
| 部署文档 | `docs/deploy.md` 覆盖架构、云服务器/本地部署、企业微信配置、运维操作 | ✅ 完成 |
| 数据库备份 | `scripts/backup_db.sh` pg_dump + gzip，保留 7 天，支持 cron 定时 | ✅ 完成 |
| Docker 健康检查 | app/minio 添加 healthcheck，db/redis 已有 | ✅ 完成 |
| Docker 资源限制 | app(512m)、db(512m)、redis(256m)、minio(256m) | ✅ 完成 |
| Nginx 限流 | API 10r/s + 登录 5r/m，429 状态码 | ✅ 完成 |
| Nginx 超时优化 | API 超时从 5s/30s 提升到 10s/120s，适配 AI 长请求 | ✅ 完成 |
| JSON 日志 | 生产环境文件日志改为 JSON 格式，便于接入 ELK/Loki | ✅ 完成 |

**新建文件：**
- `docs/deploy.md` — 完整部署文档
- `scripts/backup_db.sh` — 数据库备份脚本

**修改文件：**
- `docker-compose.yml` — 健康检查 + 资源限制
- `nginx/nginx.conf` — 限流 zone 定义
- `nginx/conf.d/tunnel.conf` — API/登录限流 + 超时优化
- `app/core/logging.py` — JSON 日志格式

### 语音识别准确性全面优化 (2026-05-20)

通过代码审查发现 8 项影响识别准确率的问题，包括 1 个关键 bug，全部修复。

| 优化项 | 说明 | 状态 |
|--------|------|------|
| SILK 采样率 bug | PCM 以 24kHz 解码但 WAV header 写 16kHz，导致音频被加速播放，严重影响识别 | ✅ 已修复 |
| 消除重复转码 | `transcribe_wechat_voice` 已转 WAV 后不再重复调 ffmpeg，减少音质损失 | ✅ 已修复 |
| 领域提示词 | 添加 `initial_prompt` 注入课题组常见术语（微纳米气泡、zeta电位等），提升专业词汇识别率 | ✅ 已完成 |
| beam_size 优化 | 从 5 降到 3，准确率几乎无损，速度提升约 40% | ✅ 已完成 |
| 健康检查 TTL | 远程 Whisper 服务缓存 60 秒后自动重试，服务恢复后自动切回 | ✅ 已完成 |
| VAD 参数统一 | `transcribe_stream` 补齐 `vad_parameters`，与其他方法行为一致 | ✅ 已完成 |
| 识别结果后处理 | 过滤 `no_speech_prob > 0.8` 的噪音段 + 连续重复文本去重 | ✅ 已完成 |
| 模型默认值统一 | Dockerfile 和 docker-compose 默认模型统一为 `large-v3` | ✅ 已完成 |

**修改文件：**
- `app/voice/silk.py` — 修复采样率 bug（默认 24kHz→16kHz）
- `app/voice/asr.py` — 添加 INITIAL_PROMPT、健康检查 TTL、skip_convert、beam_size、VAD、后处理
- `app/whisper_server.py` — 添加 INITIAL_PROMPT、beam_size、no_speech_prob 输出、后处理
- `Dockerfile.whisper` — 默认模型 `base`→`large-v3`
- `docker-compose.yml` — 默认模型 `base`→`large-v3`

### Agent 回复完整性优化 (2026-05-21)

解决 Agent 生成较长内容时（如段子集锦、长文列表等）回复被截断、内容说不全的问题。三管齐下：提示词约束 + token 提升 + 截断续写。

| 优化项 | 说明 | 状态 |
|--------|------|------|
| 系统提示词约束 | 新增完整性规则：所有列表项/代码块/分段内容必须全部写完，严禁中途截断 | ✅ 完成 |
| max_tokens 提升 | `chat()` 和 `chat_stream()` 的 4 处 API 调用从 4096 → 8192 | ✅ 完成 |
| 截断自动续写 | `_process_response()` 检测 `stop_reason == "max_tokens"` 时自动追加续写请求（最多 3 次） | ✅ 完成 |
| 流式续写 | `chat_stream()` 新增 `_stream_continuation()` 辅助方法，流式场景同样支持截断续写 | ✅ 完成 |

**修改文件：**
- `app/agent/prompts.py` — 回复质量要求新增完整性规则
- `app/agent/core.py` — max_tokens 提升 + `_process_response()` 截断续写 + `_stream_continuation()` 方法

### 先简要后详细回复 (2026-05-22)

用户提问时先快速返回【简要】核心结论，后台并行生成【详细】展开内容并自动追加到对话。

| 功能 | 说明 | 状态 |
|------|------|------|
| 两阶段并行调用 | 同时发起两次 API 调用（简要 + 详细），简要完成后立即返回 | ✅ 完成 |
| 【简要】回复格式 | 系统提示词约束生成简短核心结论 | ✅ 完成 |
| 【详细】回复格式 | 使用专用 prompt 生成详细展开内容 | ✅ 完成 |
| 后台追加机制 | asyncio.create_task 并行执行，详细内容生成后追加到 Redis 会话 | ✅ 完成 |
| 前端展开按钮 | 【简要】回复显示"点击查看详情"按钮 | ✅ 完成 |
| 轮询检测 | 前端每 2 秒轮询 `/chat/history/{session_id}` 检测详细回复并追加 | ✅ 完成 |
| API is_brief 标记 | ChatResponse 新增 `is_brief` 字段，前端据此显示展开按钮 | ✅ 完成 |

**新建文件：**
- `app/agent/prompts.py` — 新增 `get_brief_prompt()` 和 `get_detail_prompt()` 函数

**修改文件：**
- `app/agent/core.py` — 新增 `_generate_brief()`/`_generate_detail()`/`_append_detail()` 方法，chat() 改为两阶段调用
- `app/core/redis.py` — 新增 `append_message()` 方法
- `app/api/v1/chat.py` — ChatResponse 新增 `is_brief` 字段，新增 `/chat/history/{session_id}` 接口
- `web/src/views/ChatView.vue` — 显示展开按钮、轮询检测详细回复并追加显示

### 代码质量优化 (2026-05-21 审计)

全面代码审查发现 50+ 个问题，按优先级分 4 批执行。

#### 第一批：无效代码清理（零风险）

**后端未使用的导入（11 处）✅**

- [x] `app/config.py:1` — 移除 `import warnings`
- [x] `app/main.py:5` — 移除 `from app.core.logging import logger`（从未使用，用的 print）
- [x] `app/api/v1/voice.py:19` — 移除 `from app.models.meeting import Meeting`（动态导入已覆盖）
- [x] `app/services/file_parser_service.py:6` — 移除 `Dict` from typing import
- [x] `app/wechat/analyzer.py:15` — 移除 `Optional` from typing import
- [x] `app/wechat/crypto.py:6` — 移除 `import socket`
- [x] `app/voice/recorder.py:4` — 移除 `import numpy as np`
- [x] `app/whisper_server.py:3` — 移除 `import io`
- [x] `app/whisper_server.py:8` — 移除 `from fastapi.responses import JSONResponse`
- [x] `app/schemas/auth.py:5` — 移除 `from datetime import datetime`
- [x] `app/models/task.py:3` — 移除 `from datetime import datetime`

**后端未使用的函数/类（13 处）✅**

- [x] `app/wechat/bot.py:123-150` — 移除 `send_task_reminder()`（无人调用，已用 smart_send 替代）
- [x] `app/wechat/bot.py:152-181` — 移除 `send_meeting_notification()`（无人调用）
- [x] `app/wechat/bot.py:183-209` — 移除 `send_meeting_minutes()`（无人调用）
- [x] `app/wechat/bot.py:416-428` — 移除 `reply_to_user()`（冗余别名）
- [x] `app/services/vision_service.py:152-157` — 移除 `identify_person_from_image()`（无人调用）
- [x] `app/core/security.py:181-200` — 移除 `require_role()`（无人调用，所有角色检查用 inline if）
- [x] `app/core/security.py:203-238` — 移除 `get_current_user_ws()`（无人调用，WebSocket 手动 decode_token）
- [x] `app/schemas/meeting.py:67-73` — 移除 `TranscriptEntry`（无人引用）
- [x] `app/services/search_service.py:20-22` — 移除 `is_configured` property（永远返回 True）
- [x] `app/voice/recorder.py:203-207` — 移除 `create_recorder()`/`get_recorder()`/`remove_recorder()`
- [x] `app/voice/recorder.py:118-120` — 移除 `get_audio_data()`
- [x] `app/voice/tts.py:114-126` — 移除 `get_voices()`

**前端未使用的导入/变量/函数 ✅**

- [x] `web/src/views/MemberView.vue:172` — 移除 `ElMessageBox` 导入
- [x] `web/src/views/MeetingView.vue:323-331` — 移除未调用的 `startMeeting()` 函数
- [x] `web/src/components/VoiceRecorder.vue:56-57` — 移除未使用的 `audioContext` 和 `analyser` 变量
- [x] `web/src/stores/member.js:27-29` — 移除未调用的 `getMemberById()` 函数

**未使用的依赖包 ✅**

- [x] `requirements.txt` — 移除 `openai>=1.0.0`（从未 import）
- [x] `requirements.txt` — 移除 `pandas==2.1.4`（从未 import）
- [x] `requirements.txt` — 移除 `matplotlib==3.8.2`（从未 import）
- [x] `requirements.txt` — 移除 `aiofiles==23.2.1`（从未 import）
- [x] `requirements.txt` — 移除 `bcrypt==4.0.1`（passlib[bcrypt] 已包含）
- [x] `requirements.txt` — 移除重复的 `pydantic==2.5.2`（pydantic[email] 已包含）
- [x] `requirements.txt` — 移除 `faster-whisper==1.2.1`（仅 whisper 容器使用，Dockerfile.whisper 已有）
- [x] `web/package.json` — 移除 `@vueuse/core`（从未 import）
- [x] `web/package.json` — 移除 `sass`（无 lang="scss" 使用）

**过时的代码/注释 ✅**

- [x] `app/api/v1/chat.py:229` — "语音功能开发中..." 已过时，语音已实现，改为提示文字
- [x] `app/voice/asr.py:182` — 误导性注释修正（AMR 格式处理逻辑描述不准确）

#### 第二批：重复代码提取（低风险）

**后端重复逻辑**

- [x] 北京时区常量 — 8+ 处 `timezone(timedelta(hours=8))` → 提取 `BEIJING_TZ` 到 `app/models/base.py`，替换 4 个文件 9 处
- [x] Anthropic 客户端工厂 — 6 处重复实例化 → 提取 `get_anthropic_client()` 到 `app/core/llm.py`
- [x] LLM JSON 解析工具 — 4 处 markdown 代码块剥离 → 提取 `parse_llm_json()` 和 `extract_text_from_response()` 到 `app/core/llm.py`
- [x] `_postprocess_result` 完全重复 — `voice/asr.py` 和 `whisper_server.py` → 提取到 `app/voice/postprocess.py`
- [ ] ~~任务通知逻辑重复~~ — `agent/core.py` 和 `api/v1/task.py` → 暂不提取（涉及业务逻辑，改动风险较高）
- [ ] ~~Celery 任务样板代码~~ — 3 处 engine/session/asyncio.run → 暂不提取（影响异步任务稳定性）
- [x] 微信长文本分割 — 3 处相同分割逻辑 → 提取 `_split_long_text()` 辅助函数到 `app/wechat/handler.py`

**前端重复逻辑**

- [x] `fetchMembers` 重复 — 5 个组件各自调 API → 改用 `useMemberStore`
- [x] `getMemberName` 重复 — 2 处相同查找逻辑 → 改用 `memberStore.getMemberName()`
- [x] `formatDate` 重复 — 6 个组件各自定义 → 统一使用 `utils/format.js`（新增 formatRelativeTime/formatCompactDate）
- [x] `formatTime` 重复 — 3 处组件各自定义 → 统一使用 `utils/format.js`
- [ ] `isMobile` 重复 — 8 个组件独立定义 → 待后续统一（需决定是否保留 @vueuse/core）
- [x] `getStatusType` 重复 — 3 个组件相同映射 → 提取到新建 `utils/task.js`
- [x] `getPriorityType` 重复 — 2 个组件相同映射 → 提取到 `utils/task.js`

#### 第三批：配置优化（中等风险）✅

**硬编码提取到 Settings ✅**

- [x] `CLAUDE_MAX_TOKENS=8192` — `agent/core.py` 7 处 → `settings.CLAUDE_MAX_TOKENS`
- [x] `SESSION_WINDOW_SIZE=30` — `agent/core.py` 2 处 → `settings.SESSION_WINDOW_SIZE`
- [x] `WHISPER_SERVICE_URL` — `voice/asr.py` → `settings.WHISPER_SERVICE_URL`
- [x] `CORS_ORIGINS` — `main.py` 支持逗号分隔追加
- [x] `DB_POOL_SIZE=20, DB_MAX_OVERFLOW=10` — `core/database.py` → `settings.DB_POOL_SIZE/DB_MAX_OVERFLOW`
- [x] `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` — `core/security.py` → settings
- [x] `SESSION_TTL` — `core/redis.py` → `settings.SESSION_TTL`
- [x] `MAX_UPLOAD_SIZE_MB=50` — `knowledge.py`, `upload.py` → `settings.MAX_UPLOAD_SIZE_MB`

**.env.example 补全 ✅**

- [x] 新增 `MIMO_API_KEY` / `MIMO_BASE_URL` / `MIMO_MODEL`
- [x] 新增 `MINIO_SECURE=false`
- [x] 新增 `HF_ENDPOINT=`（HuggingFace 镜像源，国内可设 hf-mirror.com）
- [x] 新增 `APP_ENV` 可选值说明（development/production）

**Docker Compose 优化 ✅**

- [x] 移除 `docker-compose.yml` 和 `docker-compose.dev.yml` 中的 `version: '3.8'`
- [x] `celery-worker`/`celery-beat` 添加 `depends_on` 的 `condition: service_healthy`
- [x] `celery-worker` 添加 `mem_limit: 256m`，`celery-beat` 添加 `mem_limit: 128m`
- [x] `whisper` 服务添加 `mem_limit: 4g`

**Nginx 安全加固 ✅**

- [x] `nginx.conf` 添加 `server_tokens off`（隐藏版本号）
- [x] `default.conf` 的 `proxy_read_timeout` 从 5s 提升到 60s（适配 AI 长请求）

**安全问题修复 ✅**

- [x] `scripts/deploy-local.sh:56` — 移除硬编码 API Key
- [x] `scripts/webhook.service` — secret 改用 EnvironmentFile（`.env.webhook`）
- [x] `scripts/deploy-cloud.sh` — 移除 `ufw allow 7500/tcp`

#### 第四批：前端细节优化（低风险）✅

- [x] `Dashboard.vue` — 用 `useUserStore` 替代直接读 localStorage
- [x] `Dashboard.vue` — resize 监听器添加 `onUnmounted` 清理 + `onMounted` 注册
- [x] `LiveTranscript.vue:140` — WebSocket 协议 `ws://` → 根据 location.protocol 动态选择
- [ ] ~~axios `baseURL` 统一~~ — 跳过（改动量大，收益小，风险大于收益）
- [ ] ~~isMobile 响应式修复~~ — 跳过（仅影响 dialog 宽度，用户极少调整窗口时打开 dialog）
- [ ] ~~ProjectView.vue:257~~ — 跳过（功能占位，非 bug）

### MCP 视觉服务架构（2026-05-22）

为切换到 DeepSeek 等不支持图片识别的文本模型，预先实现 MCP 架构解耦视觉能力。

| 组件 | 说明 | 状态 |
|------|------|------|
| MCP 服务器 | stdio 传输的视觉分析 MCP Server | ✅ 完成 |
| MCP 客户端 | VisionMCPClient，连接 MCP 服务器调用工具 | ✅ 完成 |
| VisionService MCP 模式 | `VISION_USE_MCP=true` 时通过 MCP 调用视觉 | ✅ 完成 |
| Agent MCP 视觉 | `chat()`/`chat_stream()` 检测到图片时走 MCP 描述→文本 | ✅ 完成 |
| 配置项 | `VISION_USE_MCP`/`VISION_MCP_TRANSPORT`/`VISION_MCP_SERVER_CMD` | ✅ 完成 |
| Docker 服务 | `vision-mcp` 服务接入 docker-compose | ✅ 完成 |

**新建文件：**
- `mcp_server/` — MCP 服务器包（server.py + tools/vision.py）
- `app/mcp/client.py` — VisionMCPClient（stdio 传输）

**切换 DeepSeek 步骤：**
1. 确保 `vision-mcp` 容器运行中
2. `.env` 设置 `VISION_USE_MCP=true`，`CLAUDE_MODEL=deepseek-xxx`
3. 图片先通过 MCP 调用视觉服务获取描述，再以文本形式发给 DeepSeek

---

## 2026-05-24 更新

### 任务软删除/垃圾桶功能

实现任务的软删除机制，删除的任务进入垃圾桶而非直接删除，支持恢复或永久删除。

| 功能 | 说明 | 状态 |
|------|------|------|
| 软删除字段 | Task.deleted_at 字段，null=未删除，有值=已删除 | ✅ 完成 |
| 删除 API 变更 | DELETE /tasks/{id} 改为设置 deleted_at | ✅ 完成 |
| 恢复 API | POST /tasks/{id}/restore 恢复任务 | ✅ 完成 |
| 永久删除 API | DELETE /tasks/{id}/permanent 彻底删除 | ✅ 完成 |
| 列表查询排除 | GET /tasks 默认排除 deleted_at 非空记录 | ✅ 完成 |
| 仪表盘统计排除 | dashboard/stats 排除已删除任务 | ✅ 完成 |
| 前端垃圾桶 UI | Tab 页切换（任务列表/垃圾桶），显示删除倒计时 | ✅ 完成 |
| 自动删除倒计时 | 显示"还有 X 天自动删除"，最多显示 3 天 | ✅ 完成 |

**修改文件：**
- `app/models/task.py` — deleted_at 字段 + cascade delete-orphan
- `app/schemas/task.py` — deleted_at 响应字段
- `app/api/v1/task.py` — 软删除/恢复/永久删除 API
- `app/services/task_service.py` — 查询排除已删除
- `web/src/views/TaskView.vue` — Tab 页垃圾桶 UI

### 外键 CASCADE 修复

修复删除父记录时外键约束失败的问题，为所有 NOT NULL 外键添加 ondelete="CASCADE"。

| 修复位置 | 说明 |
|----------|------|
| reminders.task_id | → tasks(id) |
| task_dependencies.task_id | → tasks(id) |
| task_dependencies.depends_on_id | → tasks(id) |
| milestones.project_id | → projects(id) |
| meeting_participants.meeting_id | → meetings(id) |
| meeting_participants.member_id | → members(id) |
| memories.user_id | → members(id) |
| feedback.user_id | → members(id) |

**修改文件：**
- `app/models/reminder.py`
- `app/models/task.py` (TaskDependency)
- `app/models/project.py`
- `app/models/meeting.py`
- `app/models/memory.py`
- `app/models/feedback.py`

### TaskView 筛选修复

修复 TaskView 空值筛选参数导致 FastAPI 422 错误的问题。

| 问题 | 修复 |
|------|------|
| filters 为空时发送 status=&assignee_id=&priority= | Object.fromEntries 过滤空值 |

---

## 2026-05-25 更新

### 文件对话存入知识库功能

用户上传文件给小气助手后，Agent 回复后追加"存入知识库？"按钮，可一键将文件提取的文本存入公共知识库。

| 功能 | 说明 | 状态 |
|------|------|------|
| 后端 API | `POST /api/v1/knowledge/from-chat`，接收 title 和 content | ✅ 完成 |
| 前端按钮 | AI 回复后显示"📚 存入知识库"按钮 | ✅ 完成 |
| 知识内容传递 | `ChatResponse` 新增 `knowledge_content` 字段返回提取文本 | ✅ 完成 |
| 权限设计 | 知识库公共（所有人可见），长期记忆私有（按 user_id 过滤） | ✅ 确认 |

**修改文件：**
- `app/api/v1/chat.py` — ChatResponse 新增 knowledge_content 字段，chat_with_file 返回提取文本
- `app/api/v1/knowledge.py` — 新增 `/knowledge/from-chat` 端点
- `web/src/views/ChatView.vue` — 消息展示添加存入知识库按钮，saveToKnowledge 函数

### 知识库前端修复

| 问题 | 修复 | 状态 |
|------|------|------|
| 文件上传失败 | 移除手动设置的 `Content-Type: multipart/form-data`，axios 会自动处理 boundary | ✅ 完成 |
| KnowledgeView 弹窗遮挡 | 添加 `height: 100%; overflow-y: auto` | ✅ 完成 |
| ProjectView 弹窗遮挡 | 添加 `height: 100%; overflow-y: auto` | ✅ 完成 |

**修改文件：**
- `web/src/views/KnowledgeView.vue` — 移除错误 header，设置正确 height/overflow
- `web/src/views/ProjectView.vue` — 设置正确 height/overflow
- `web/src/views/ChatView.vue` — 移除 3 处错误 Content-Type 设置

### MinIO 异步上传修复

| 问题 | 修复 | 状态 |
|------|------|------|
| MinIO 同步调用阻塞事件循环 | 使用 `asyncio.to_thread()` 包装同步的 `put_object` 调用 | ✅ 完成 |

**修改文件：**
- `app/services/file_service.py` — upload_file 改为 async，使用 asyncio.to_thread

### 微信思考消息重复修复

| 问题 | 修复 | 状态 |
|------|------|------|
| 语音消息重复发送思考中消息 | 添加 `_skip_thinking` 标志，语音消息识别和非识别路径均设置 | ✅ 完成 |
| 图片消息重复发送思考中消息 | 同上 | ✅ 完成 |

**修改文件：**
- `app/wechat/handler.py` — `_handle_general_chat`/`_handle_group_chat` 检测 `_skip_thinking`，语音/图片处理设置标志

### 移动端侧边栏修复与动画优化 (2026-05-25)

解决移动端侧边栏菜单只显示图标不显示文字的问题（根因为云服务器部署流水线未生效），以及为侧边栏添加动态过渡特效。

| 功能 | 说明 | 状态 |
|------|------|------|
| 独立 div 抽屉方案 | 移动端抽屉改为 el-container 外部独立 div，彻底绕过 Element Plus aside 全局 CSS | ✅ 完成 |
| 桌面端隔离 | `v-if="!isMobile"` 确保桌面端 el-aside 不被移动端代码影响 | ✅ 完成 |
| 遮罩淡入淡出 | opacity 过渡 + backdrop-filter blur 渐变层次 | ✅ 完成 |
| 抽屉弹性滑入 | translateX + cubic-bezier(0.34,1.56,0.64,1) overshoot 回弹 | ✅ 完成 |
| 菜单项弹簧 stagger | scale(0.9→1) + translateX，每个延迟 60ms，关闭时反向退出 | ✅ 完成 |
| 汉堡图标旋转过渡 | Fold↔Expand 带 rotation + scale 过渡动画 | ✅ 完成 |
| 品牌 logo 独立入场 | logo 缩放弹出 + 文字淡入，各自独立延迟 | ✅ 完成 |

**修改文件：**
- `web/src/layouts/MainLayout.vue` — 模板（独立抽屉 + Transition）+ CSS（6 组 @keyframes + transition classes）

### 移动端顶部栏全面优化 (2026-05-25)

优化移动端顶部栏三个问题：汉堡按钮太小、铃铛点击无反馈、头像显示灰色默认图标。

| 功能 | 说明 | 状态 |
|------|------|------|
| 汉堡按钮增大 | 移动端 24px 图标 + 10px padding = 44px 触控区（iOS/Material 标准）| ✅ 完成 |
| 铃铛改为提醒面板 | el-popover 弹窗：显示提醒数 + "全部标为已读"按钮 + "查看我的任务"链接 | ✅ 完成 |
| 头像读取真实 URL | 从 `userStore.userInfo.avatar` 读取真实头像，无则 fallback 默认图标 | ✅ 完成 |
| 移动端 header 紧凑 | padding 12px，gap 8px，铃铛+头像触控区增大 | ✅ 完成 |

**修改文件：**
- `web/src/layouts/MainLayout.vue` — 模板（el-popover + 动态头像 + 移动端 class）+ 脚本（userAvatar + handleMarkAllRead）+ 样式（通知面板 + 移动端适配）

### 任务权限简化 (2026-05-25)

将所有成员的"我的任务"改为"全部任务"，统一可见范围，降低认知负担。

| 改动 | 说明 | 状态 |
|------|------|------|
| 查询条件移除 member_id 过滤 | 所有成员可查看全部任务，不再限制为"自己的任务" | ✅ 完成 |
| 编辑/删除权限保留 | 仅创建人/负责人/管理员可编辑、删除、恢复、永久删除 | ✅ 完成 |
| 错误提示友好化 | REST + Agent 两种路径均返回清晰的中文权限错误信息 | ✅ 完成 |
| 垃圾桶权限同步放开 | 进入垃圾桶的任务对创建人/负责人/管理员可见 | ✅ 完成 |

**修改文件：**
- `app/api/v1/task.py` — tasks GET 移除 member_id 过滤，PUT/DELETE 保留权限检查
- `app/agent/core.py` — `query_tasks` 和 `query_all_member_tasks` 返回全部任务

### 待办与进行中状态统一 (2026-05-25)

todo（待办）和 in_progress（进行中）语义高度重合，统一为"进行中"。

| 改动 | 说明 | 状态 |
|------|------|------|
| 后端模型默认状态 | `TaskStatus.TODO` → `TaskStatus.IN_PROGRESS` | ✅ 完成 |
| Service/API/Agent 默认状态 | 所有新建任务的 status 默认值从 `todo` 改为 `in_progress` | ✅ 完成 |
| AI 工具枚举 | 从允许的状态列表中移除 `todo` | ✅ 完成 |
| Agent 任务汇总 | 将 todo 任务归入 in_progress_list 输出 | ✅ 完成 |
| 统计合并 | todo 和 in_progress 合并计数 | ✅ 完成 |
| WeChat 调度器 | 查询条件增加 todo 兼容（现有 todo 任务仍被检查） | ✅ 完成 |
| 前端状态标签 | `todo: '待办'` → `todo: '进行中'`，UI 显示统一 | ✅ 完成 |
| 前端选项 | Dashboard/TaskView 状态筛选和编辑对话框移除"待办"选项 | ✅ 完成 |
| 取消完成任务 | 反向状态从 `todo` 改为 `in_progress` | ✅ 完成 |

**修改文件（14 个）：**
- `app/models/task.py` — 模型默认值
- `app/services/task_service.py` — 服务层默认值 + 统计
- `app/wechat/handler.py` — 微信创建任务默认值
- `app/services/meeting_service.py` — 会议创建任务默认值
- `app/agent/core.py` — Agent 创建任务默认值 + 统计 + 汇总
- `app/agent/tools.py` — 工具枚举
- `app/wechat/scheduler.py` — 查询条件
- `app/api/v1/task.py` — 统计接口
- `web/src/utils/task.js` — 状态标签
- `web/src/views/Dashboard.vue` — 状态选项 + 反向状态
- `web/src/views/TaskView.vue` — 状态选项 + 反向状态

### Dashboard/TaskView 一致性修复 (2026-05-25)

修复 Dashboard 首页"进行中任务"数量与 TaskView 显示不一致的问题。

| 问题 | 修复 | 状态 |
|------|------|------|
| TaskView 默认 pageSize=20，Dashboard 统计却包含所有任务 | 默认 pageSize 提升至 100，与 Dashboard 统计范围一致 | ✅ 完成 |
| Dashboard 首页"进行中任务"定义不明确 | 统一定义为 `todo + in_progress + blocked`（所有非 done 状态） | ✅ 完成 |

**修改文件：**
- `web/src/views/TaskView.vue` — pageSize 20→100
- `web/src/views/Dashboard.vue` — 进行中任务定义统一

### 个人设置页面 (2026-05-25)

新增个人设置页面，成员可编辑个人信息和上传头像。

| 功能 | 说明 | 状态 |
|------|------|------|
| 个人信息编辑 | 姓名、邮箱、手机号、角色等字段编辑 | ✅ 完成 |
| 头像上传 | MinIO 存储，公网可读 | ✅ 完成 |
| 头像 URL 修复 | 运行时生成新鲜签名，bucket 名称自动补全，nginx 代理访问 | ✅ 完成 |

**新建文件：**
- `web/src/views/SettingsView.vue` — 个人设置页面

**修改文件：**
- `web/src/router/index.js` — 新增 /settings 路由
- `app/services/file_service.py` — 头像上传逻辑
- `app/core/security.py` — 头像 URL 签名生成
- `app/api/v1/member.py` — 成员更新端点

### 云自动部署修复 (2026-05-25)

诊断并修复 Webhook 自动部署流水线的多个问题，端到端验证通过。

| 问题 | 修复 | 状态 |
|------|------|------|
| Webhook 端点不可达 | 云 Nginx 添加 `/webhook` 代理到 `127.0.0.1:9001` | ✅ 完成 |
| deploy-auto.sh 无错误处理 | 添加 `set -e`、磁盘空间检查（500MB）、构建产物验证、nginx -t 预检 | ✅ 完成 |
| 端口冲突（9000 vs MinIO FRP） | webhook 端口从 9000 改为 9001 | ✅ 完成 |
| SSL 证书路径错误 | tunnel.conf 证书路径修正为 `/etc/letsencrypt/live/` | ✅ 完成 |
| Git remote 使用 SSH 无密钥 | 云服务器改用 HTTPS remote | ✅ 完成 |
| 静态资源无缓存头 | JS/CSS 添加 `expires 7d; Cache-Control: public, immutable` | ✅ 完成 |
| .env.webhook 缺失 | 服务器手动创建 + systemd EnvironmentFile 引入 | ✅ 完成 |
| 缺少 tunnel.conf 模板 | 创建 `nginx/conf.d/tunnel.conf`（HTTPS + WebSocket + 缓存 + 安全头） | ✅ 完成 |
| deploy-cloud.sh 缺少 webhook | HTTP 临时配置添加 /webhook 代理 | ✅ 完成 |
| webhook.py 硬编码默认密钥 | 移除默认值，强制从环境变量读取 | ✅ 完成 |

**修改文件：**
- `scripts/deploy-auto.sh` — 全面加固（set -e + 磁盘检查 + 构建验证 + 本地修改丢弃）
- `scripts/webhook.py` — 端口改为 9001 + 移除硬编码默认密钥
- `nginx/conf.d/tunnel.conf` — 新建（HTTPS + /webhook + /api + /ws + /minio + 缓存头 + 安全头）
- `scripts/deploy-cloud.sh` — HTTP 临时配置添加 /webhook 代理 + 缓存头

### 任务排序优化 (2026-05-25)

Dashboard 首页和 TaskView 任务管理中，同一人的任务排序规则优化。

| 改动 | 说明 | 状态 |
|------|------|------|
| Dashboard 排序 | 从 `in_progress` 状态优先 + `created_at` 降序 → 优先级高→中→低 + 截止时间早→晚 | ✅ 完成 |
| TaskView 排序 | 从 `created_at` 降序 → 优先级高→中→低 + 截止时间早→晚 | ✅ 完成 |
| 无截止日期 | 同优先级中无截止日期的排最后 | ✅ 完成 |

**修改文件：**
- `web/src/views/Dashboard.vue` — `fetchInProgressTasks` 排序逻辑
- `web/src/views/TaskView.vue` — `groupTasksByAssignee` 组内排序逻辑

### Webhook 异步部署 (2026-05-25)

修复 GitHub webhook 持续超时（"时间耗尽"）的问题。

| 改动 | 说明 | 状态 |
|------|------|------|
| 同步→异步 | `subprocess.run` 改为 `threading.Thread` 后台执行 | ✅ 完成 |
| 先返回 200 | HTTP 响应立即返回，部署脚本在后台运行 | ✅ 完成 |
| 错误处理 | 后台线程独立 try/except，日志记录超时和异常 | ✅ 完成 |

**修改文件：**
- `scripts/webhook.py` — `do_POST` 先返回 200，部署移入 `_run_deploy` 线程方法

### Dashboard 完成任务 UI 优化 (2026-05-25)

去除任务行前的复选框，统一为一个绿色"✓ 完成"按钮。

| 改动 | 说明 | 状态 |
|------|------|------|
| 去掉复选框 | 进行中和即将到期任务行前的 `el-checkbox` 全部删除 | ✅ 完成 |
| 按钮样式 | 从 `text` 文字按钮改为 `type="success" round` 绿色实心圆角按钮 | ✅ 完成 |
| 清理代码 | 删除不再使用的 `toggleTaskStatus` 函数 | ✅ 完成 |

**修改文件：**
- `web/src/views/Dashboard.vue` — 模板（进行中/即将到期任务）和脚本（删除 toggleTaskStatus）

### 创建任务不填截止日期修复 (2026-05-25)

前端 `due_date` 初始值为空字符串，Pydantic 无法转为 `datetime` 导致 422 错误。

| 改动 | 说明 | 状态 |
|------|------|------|
| Dashboard.vue | `due_date: ''` → `due_date: null`（3 处） | ✅ 完成 |
| TaskView.vue | `due_date: ''` → `due_date: null`（2 处） | ✅ 完成 |

### Dashboard 列表顺序修复 (2026-05-25)

后端 `list_tasks` 添加 `ORDER BY created_at DESC`，Dashboard `page_size` 从 60 提升至 100，确保新创建任务不会排在分页之外。

| 改动 | 说明 | 状态 |
|------|------|------|
| 后端排序 | `app/api/v1/task.py` `list_tasks` 添加 `.order_by(Task.created_at.desc())` | ✅ 完成 |
| 前端 page_size | Dashboard `fetchInProgressTasks` 从 60→100 | ✅ 完成 |

**修改文件：**
- `app/api/v1/task.py` — list_tasks 添加 ORDER BY
- `web/src/views/Dashboard.vue` — page_size 60→100

### 通知面板显示具体提醒内容 (2026-05-25)

铃铛弹窗只显示"您有 N 条待处理提醒"+ "全部标为已读"按钮，看不到具体是什么提醒。新增后端列表接口，改造前端弹窗为提醒列表。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| 后端 GET /reminders | 新增端点返回待处理提醒列表（含 task_title、remind_at），按时间升序，最多 50 条 | ✅ 完成 |
| 前端 userStore | 新增 `notifications` 数组 + `fetchNotifications()` 方法 | ✅ 完成 |
| 前端弹窗面板 | 显示每条提醒的具体内容（任务标题+提醒时间），点击跳转任务管理 | ✅ 完成 |

**修改文件：**
- `app/api/v1/task.py` — 新增 `GET /reminders` 端点
- `web/src/stores/user.js` — 新增 `notifications` ref 和 `fetchNotifications()`
- `web/src/layouts/MainLayout.vue` — 弹窗模板改为通知列表 + 新增 `handlePopoverShow`/`goToTask`/`formatTime`

### 企业微信回复失败 + Dashboard 500 修复 (2026-05-25)

**问题 1：** 企业微信用户（刘莫菲、杜同贺）给机器人发消息后无回复。根因是 `.env` 中 `WECHAT_API_BASE_URL=https://agent.mnb-lab.cn/wechat-api`，该路径在 Nginx 上无代理规则，所有微信 API 请求（gettoken/message/send）打到前端 HTML，JSON 解析失败导致全部微信功能瘫痪。

**问题 2：** `GET /dashboard/stats` 返回 500 错误。根因是 `get_dashboard_stats` 调用了不存在的 `_get_visible_member_ids` 函数。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| WECHAT_API_BASE_URL | 从 `agent.mnb-lab.cn/wechat-api` 改为 `qyapi.weixin.qq.com` 直接调用企业微信官方 API | ✅ 完成 |
| Dashboard 权限过滤 | 移除 `_get_visible_member_ids` 调用，所有用户统一使用软删除过滤 | ✅ 完成 |

**修改文件：**
- `.env` — WECHAT_API_BASE_URL 修正
- `app/api/v1/task.py` — `get_dashboard_stats` 简化权限过滤

### 成员登录修复 (2026-05-25)

刘莫菲无法登录网页端。排查发现 4 位成员（刘莫菲、孟祥琪、吴怡霏、蒋芦笛）的 `password_hash` 为 `None`，均为批量导入时未设置密码导致。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| 密码补全 | 为 4 位无密码成员设置 bcrypt 哈希后的默认密码 `123456` | ✅ 完成 |

**根因：** 成员批量创建时未调用 `get_password_hash()` 设置密码。

### 头像上传 prefix 参数修复 (2026-05-26)

头像上传后无法正常显示。排查发现前端通过 FormData 发送 `prefix=avatars`，但后端 `app/api/v1/upload.py` 使用 `Query("uploads")` 读取该参数——`Query()` 无法从 multipart/form-data 读取值，导致 prefix 静默回退到默认值 `"uploads"`，所有头像文件存到 `uploads/` 而非 `avatars/`。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| Query → Form | `app/api/v1/upload.py` 中 `prefix` 参数从 `Query("uploads")` 改为 `Form("uploads")` | ✅ 完成 |

**修改文件：**
- `app/api/v1/upload.py` — `Query` 改为 `Form`

**验证：** 端到端测试确认：上传 → `avatars/uuid.png` 前缀正确 → 云代理 HTTP 200 → 保存资料写入 DB → `_resolve_avatar_url` 返回公网 URL。

### mnb-lab.cn SSL 证书修复 (2026-05-26)

`https://mnb-lab.cn` 不可访问，报 `SEC_E_WRONG_PRINCIPAL`。云服务器 Let's Encrypt 证书仅覆盖 `agent.mnb-lab.cn`，`mnb-lab.cn` HTTPS 请求落入 `agent.mnb-lab.cn` 的 server block，证书域名不匹配被浏览器拦截。

**修复：**
1. `certbot --expand` 将 `mnb-lab.cn` / `www.mnb-lab.cn` 加入证书
2. nginx 新增 `mnb-lab.cn` 的 HTTP（301→HTTPS）和 HTTPS server block，指向 `/var/www/mnb-lab`

**教训：** 同服务器新增域名 → 必须扩展 SSL 证书 + 添加 nginx server block。

### mnb-lab.cn 内容更新 + 云服务器 OOM (2026-05-26)

`mnb-lab.cn` 网站内容过期，尝试云服务器构建 Next.js 时 2核2G 内存耗尽导致服务器卡死。改为本地 Windows 构建（`npm run build`）→ MinIO 中转 → 云服务器下载部署。

**教训：** 云服务器严禁运行 `npm run build`，所有构建在本地完成后上传静态产物。

### 铃铛通知去重 (2026-05-26)

用户创建 3 个任务，铃铛显示 6 条通知，每个任务出现两次（内容相同但时间不同）。

**根因：** `_create_default_reminders()` 为截止时间 >24h 的任务创建 2 个提醒（提前 2 天 + 提前 2 小时），`GET /reminders` 返回所有 reminder 行，3 任务 × 2 提醒 = 6 条。后端多提醒是合理的调度策略，但通知面板应按任务去重。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| pending-count 去重 | `func.count(Reminder.id)` → `func.count(func.distinct(Reminder.task_id))` | ✅ 完成 |
| reminders 去重 | 新增 `.distinct(Reminder.task_id)` + `ORDER BY task_id, remind_at` | ✅ 完成 |

**修改文件：**
- `app/api/v1/task.py` — 两个查询（第 546、592 行）

**验证：** 耿嘉栋 3 个任务各有 2 个 pending reminder → count=3（非 6），列表每条 task_id 唯一，mark-read 正常归零。

### Nginx ^~ MinIO 修复 (2026-05-26)

**问题：** Nginx 正则 location `~* \.(png|jpg|jpeg|gif)$` 优先级高于 `/minio/` 前缀 location，导致所有通过 `/minio/` 代理访问的头像图片被正则拦截 → 从文档根目录查找静态文件 → 404。

**根因：** Nginx prefix location 默认优先级低于 regex location。请求 `/minio/microbubble/avatars/xxx.jpg` 同时匹配 `/minio/` 前缀和 `\.jpg$` 正则 → 正则胜出 → nginx 尝试从 `root` 提供静态文件。

**修复：** 给 `/minio/` location 添加 `^~` 修饰符（优先前缀匹配，优先级高于 regex）。

**修改文件：**
- `nginx/conf.d/tunnel.conf` — `location /minio/` → `location ^~ /minio/`
- `nginx/conf.d/default-http.conf` — 同上

### MemberView 管理员编辑污染 DB 头像 (2026-05-26)

**问题：** 管理员编辑成员时，`{ ...member }` 展开运算符将 `_resolve_avatar_url()` 解析后的完整 URL 拷贝到表单，保存时将完整 URL（如 `https://agent.mnb-lab.cn/minio/microbubble/avatars/xxx.jpg`）写回 DB，而不是 raw object_name。

**修改文件：**
- `web/src/views/MemberView.vue` — 编辑成员时排除 `avatar` 字段

### SettingsView 头像自动保存 + 手机端上传修复 (2026-05-26)

**问题 1：** 上传头像后需手动点"保存资料"才能持久化，容易遗漏导致刷新后头像丢失。

**修复：** 上传成功后立即调 `PUT /api/v1/auth/profile` 只传 `avatar` 字段，自动持久化。

**问题 2：** 手机端上传头像间歇性失败。根因之一：手动设置 `Content-Type: multipart/form-data` 缺少 `boundary` 参数，手机浏览器更严格导致请求失败。根因之二：HEIC 格式（iPhone 默认拍照格式）Canvas 不支持，`compressImage` 直接报错。

**修复：**
- 删除手动 Content-Type header，让浏览器自动填写正确的 boundary
- Canvas 压缩失败时静默回退，直接用原文件上传
- 优化上传+保存+获取完整 URL 三步骤：拆分为独立 try/catch，任意步骤失败不影响 localStorage 写入，防止网络波动导致刷新后头像回退

**修改文件：**
- `web/src/views/SettingsView.vue` — 4 处改动（自动保存 + HEIC 回退 + 错误拆分 + Content-Type 删除）

---

## 知识库深层逻辑系统 — 自主进化知识大脑 (2026-05-26)

将知识库从"手动喂入的静态文档库"升级为**自主进化的课题组知识大脑**。

### Phase 1: 动态内容分析 + 知识关联 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 动态 LLM 分析 Prompt | 不再硬编码 `基础/方法/文献/FAQ`，改为 LLM 根据内容自由生成具体方向（如"臭氧气泡消毒动力学"） | ✅ 完成 |
| 模型扩展 | Knowledge 新增 key_concepts、related_topics、knowledge_type、analysis_status、auto_researched、quality_score 6 个字段，category 扩宽至 100 字 | ✅ 完成 |
| 知识关系模型 | KnowledgeRelation 表（source_id/target_id/relation_type/score/reason/created_by），支持 similar/supplements/contradicts/cites/extends/prerequisite | ✅ 完成 |
| 自动关联引擎 | 新入库条目自动与已有条目建关联：pgvector 余弦相似度（>0.65 similar）+ key_concepts 重叠（≥2 supplements）+ related_topics 重叠（≥1 extends），双向写入 | ✅ 完成 |
| 动态分类 API | `GET /knowledge/categories` — 从实际数据 GROUP BY 聚合 | ✅ 完成 |
| 标签云 API | `GET /knowledge/tags` — `unnest(tags)` 频率排序 | ✅ 完成 |
| 知识图谱 API | `GET /knowledge/graph` — BFS 遍历节点+边，支持中心展开和全局视图 | ✅ 完成 |
| 关联知识 API | `GET /knowledge/{id}/related` — 按 relation_type 过滤，score 降序 | ✅ 完成 |
| 增强统计 API | `GET /knowledge/stats/rich` — 类型分布/分析状态/关联数/自动研究数 | ✅ 完成 |

**新建文件：**
- `app/services/knowledge_graph_service.py` — 知识图谱服务（关联发现 + BFS 图谱 + 动态分类 + 标签云 + 统计）
- `alembic/versions/007_knowledge_brain_models.py` — 数据库迁移（6 新列 + 关系表 + 3 个索引）

**修改文件：**
- `app/services/llm_analysis_service.py` — 分析 Prompt 重写（动态分类 + key_concepts + related_topics + knowledge_type）
- `app/models/knowledge.py` — 6 新字段 + KnowledgeRelation 模型
- `app/services/knowledge_service.py` — `_analyze_and_embed` 保存全部新字段 + 分析完成后自动关联
- `app/schemas/knowledge.py` — 新字段 + 5 个新 schema（RelatedKnowledge/GraphNode/GraphEdge/KnowledgeGraph/DynamicCategory/TagCloudItem/KnowledgeStats）
- `app/api/v1/knowledge.py` — 5 个新端点（categories/tags/graph/related/rich-stats）

### Phase 2: RAG 优先问答引擎 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| RAG 合成答案 | 语义搜索 → 阈值分类（高/中/低相关）→ LLM 合成 → 来源引用 | ✅ 完成 |
| 置信度评分 | 基于高相关条目数量判断 high/medium/low | ✅ 完成 |
| 自动研究触发 | 高相关条目 < 2 时自动生成联网搜索查询 | ✅ 完成 |
| 推荐阅读 | 返回相关知识条目 ID 列表 | ✅ 完成 |

**新建文件：**
- `app/services/knowledge_qa_service.py` — RAG 问答引擎（检索 + 阈值 + LLM 合成 + 研究查询生成）

**修改文件：**
- `app/schemas/knowledge.py` — 新增 QASource/QAResponse 结构
- `app/api/v1/knowledge.py` — 新增 `POST /knowledge/qa` 端点

### Phase 3: 自主研究引擎（自我进化核心）✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 联网自动研究 | 对研究查询执行搜索（搜狗+必应）→ 抓取页面 → LLM 提取知识 → 去重 → 入库 → 建立关联 | ✅ 完成 |
| 知识空白检测 | LLM 分析知识库统计 → 识别薄弱领域 → 生成研究查询 → 定向补充 | ✅ 完成 |
| 矛盾检测 | 高分相似条目对 → LLM 判断是否矛盾 → 返回矛盾列表 | ✅ 完成 |
| 重复检测 | 两两计算 pgvector 余弦相似度 > 0.92 → 返回重复对 | ✅ 完成 |
| 过期检测 | 超过 365 天未更新的条目（排除 auto_research） | ✅ 完成 |

**新建文件：**
- `app/services/auto_research_service.py` — 自主研究引擎（研究/空白填充/矛盾检测/重复检测/过期检测）
- `app/services/knowledge_evolution_tasks.py` — Celery 定时任务（每日进化/6h 空白检测/12h 健康检查）

**修改文件：**
- `app/core/celery.py` — 3 个新定时任务 + 自动发现
- `app/schemas/knowledge.py` — 新增 ResearchResultItem/ResearchResponse 结构
- `app/api/v1/knowledge.py` — 6 个新端点（QA/research/gaps/contradictions/duplicates/staleness）

### Phase 4: 动态分类体系 + 知识健康监控 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 涌现分类 | 从已有 category 聚合 + key_concepts 频率统计 → 分类树+热门概念 | ✅ 完成 |
| 分类建议 | 基于最相似条目的 embedding 余弦相似度建议分类 | ✅ 完成 |
| 主题关联网络 | 分类间概念重叠（Jaccard 相似度）→ 关联网络 | ✅ 完成 |
| 分类报告 | Markdown 格式的动态分类报告生成 | ✅ 完成 |

**新建文件：**
- `app/services/dynamic_taxonomy_service.py` — 动态分类体系（涌现分类/建议/网络/报告）

**修改文件：**
- `app/api/v1/knowledge.py` — 2 个新端点（taxonomy/emerging + taxonomy/network）

### Phase 5: 前端改造 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 动态标签云 | 从实际数据聚合的可点击研究主题标签云，字号按频率自适应 | ✅ 完成 |
| RAG QA 问答面板 | 替换旧语义搜索，合成答案 + 来源引用 + 置信度 + 研究触发提示 + 快捷问题 | ✅ 完成 |
| 知识详情增强 | 显示 key_concepts/related_topics 分析结果、analysis_status 标签、auto_researched 标记 | ✅ 完成 |
| 关联知识面板 | 知识详情页显示关联条目（relation_type + score + reason），点击跳转 | ✅ 完成 |
| 知识图谱可视化 | ECharts force-directed graph，节点大小=关联数，颜色=分类，悬停显示详情 | ✅ 完成 |
| 动态分类选择器 | 添加/编辑对话框的分类/标签下拉从 API 动态获取 | ✅ 完成 |

**修改文件：**
- `web/src/views/KnowledgeView.vue` — 完整重写（动态标签云 + RAG QA + 关联面板 + 图谱 + 分析结果展示）

### 新增 API 端点汇总

| 端点 | 说明 | 阶段 |
|------|------|------|
| `GET /knowledge/categories` | 动态分类列表（从实际数据聚合） | P1 |
| `GET /knowledge/tags` | 标签云（频率排序） | P1 |
| `GET /knowledge/graph` | 知识图谱（节点+边） | P1 |
| `GET /knowledge/{id}/related` | 关联知识列表 | P1 |
| `GET /knowledge/stats/rich` | 增强统计 | P1 |
| `POST /knowledge/qa` | RAG 知识问答 | P2 |
| `POST /knowledge/research` | 触发自主研究 | P3 |
| `POST /knowledge/research/gaps` | 分析并填充知识空白 | P3 |
| `GET /knowledge/health/contradictions` | 矛盾检测 | P3 |
| `GET /knowledge/health/duplicates` | 重复检测 | P3 |
| `GET /knowledge/health/staleness` | 过期检测 | P3 |
| `GET /knowledge/taxonomy/emerging` | 涌现分类体系 | P4 |
| `GET /knowledge/taxonomy/network` | 主题关联网络 | P4 |

---

## Knowledge Brain 二次升级 — 实体图谱 + 假设生成 + 量化推理 (2026-05-27)

将知识从"文档附属品"升级为**跨文档可查询、可推理、可计算**的课题组知识大脑。

### P0: 实体级知识图谱 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 跨文档实体融合 | 从文档 entities JSONB 提取 → 精确匹配 → embedding 余弦 ≥0.78 合并 → 新建实体 | ✅ 完成 |
| 共现网络 | 同一文档内的实体对写入 entity_co_occurrence 表，作为图谱边 | ✅ 完成 |
| 实体搜索 | 按 subject/predicate/object/keyword 分页搜索 | ✅ 完成 |
| 实体图谱 API | centered 模式（单实体+邻居）和 global 模式（全部节点+边） | ✅ 完成 |
| 实体详情 | 含来源文档列表（source_knowledge_ids → 文档标题） | ✅ 完成 |
| 每日实体融合 | Celery 定时任务，LLM 批量判定同 predicate 相似实体合并 | ✅ 完成 |
| 前端实体图谱 tab | ECharts 力导向图（节点颜色=predicate 分类，大小=occurrence_count）| ✅ 完成 |
| 前端实体卡片 | subject→predicate→object + condition + 置信度进度条 + 来源数 | ✅ 完成 |

**数据：** 56 个跨文档实体，173 条共现边，从 9 篇文档 54 个文档内三元组融合而来。

**新建文件：**
- `app/models/knowledge_entity.py` — KnowledgeEntity + EntityCoOccurrence 模型
- `app/services/entity_service.py` — 实体融合/搜索/图谱/详情/LLM 合并

**修改文件：**
- `app/models/__init__.py` — 注册新模型
- `app/services/knowledge_service.py` — _analyze_and_embed Step 5 触发实体融合
- `app/api/v1/knowledge.py` — 3 个新端点（entities/list, entities/graph, entities/{id}）
- `app/schemas/knowledge.py` — 4 个新 schema（EntityItem/EntityList/EntityGraph/EntityDetail）
- `app/core/celery.py` — entity-fusion-daily 定时任务
- `app/services/knowledge_evolution_tasks.py` — fuse_entities_task
- `web/src/views/KnowledgeView.vue` — 实体图谱 tab + 搜索 + 卡片 + 弹窗（~300 行）

### P1: 科研假设生成引擎 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| LLM 假设生成 | 收集实体三元组 + 知识空白 + 关系模式 → LLM 生成可验证假设 | ✅ 完成 |
| 假设持久化 | statement + rationale + suggested_experiment + supporting_entity_ids | ✅ 完成 |
| 验证生命周期 | proposed → validated / rejected，记录验证时间 | ✅ 完成 |
| 优先级+标签 | high/medium/low 优先级 + 自由标签 | ✅ 完成 |
| 前端假设 tab | 筛选栏（状态/优先级）+ 生成按钮 + 卡片网格 + 验证/否决操作 | ✅ 完成 |

**新建文件：**
- `app/models/knowledge_hypothesis.py` — KnowledgeHypothesis 模型
- `app/services/hypothesis_service.py` — 假设生成/列表/验证/详情

**修改文件：**
- `app/models/__init__.py` — 注册新模型
- `app/api/v1/knowledge.py` — 4 个新端点（hypotheses POST/GET, hypotheses/{id} GET, hypotheses/{id}/validate）
- `app/schemas/knowledge.py` — 2 个新 schema（HypothesisItem/HypothesisList）
- `web/src/views/KnowledgeView.vue` — 假设 tab（~200 行）

### P3: 公式库增强 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| FormulaCategory 模型 | 二级分类树（6 大类 24 子分类），支持图标+排序+描述 | ✅ 完成 |
| 知识公式关联分类 | knowledge_formulas 新增 category_id FK + source_type（builtin/extracted）+ is_active | ✅ 完成 |
| 内置公式库 | 32 个微纳米气泡领域公式，覆盖气泡动力学/传质/水质/化学动力学/流体力学/统计分析 | ✅ 完成 |
| 幂等种子数据 | 启动时自动初始化 formula_categories + 内置公式，仅首次执行 | ✅ 完成 |
| 分类树 API | GET /knowledge/formulas/categories — 返回树形结构 + 公式计数 | ✅ 完成 |
| 公式筛选增强 | list_formulas 新增 category_id / source_type 参数，支持按分类+来源组合筛选 | ✅ 完成 |
| domain→category 映射 | 40+ 条模糊匹配规则，LLM 提取公式自动归入正确分类 | ✅ 完成 |
| LaTeX 转换增强 | 希腊字母（σ/μ/θ/δ/λ）+ 上标（²/³）+ sum 符号扩展 | ✅ 完成 |
| LLM 提示词优化 | domain 字段引导使用标准化分类名 | ✅ 完成 |
| 前端分类树 | el-tree-select 替换 domain 下拉，支持搜索+层级展开+公式计数 | ✅ 完成 |
| 来源标签 | 公式列表+计算器显示"内置"（绿色）/ "提取"（灰色）标签 | ✅ 完成 |
| 内置公式去知识链接 | 内置公式无父文档时隐藏"来源: 知识条目 #N"链接 | ✅ 完成 |

**新建文件：**
- `app/models/formula_category.py` — FormulaCategory 模型
- `app/seed/formula_library.py` — 内置公式库种子数据（32 条公式）
- `app/seed/seeder.py` — 幂等种子服务
- `alembic/versions/009_formula_categories.py` — 数据库迁移

**修改文件：**
- `app/models/knowledge_formula.py` — 新增 source_type/category_id/is_active，knowledge_id 改为 nullable
- `app/services/formula_service.py` — 新增 get_categories / _resolve_category_name / 增强 list_formulas
- `app/schemas/knowledge.py` — 新增 FormulaCategoryItem + FormulaItem 增强
- `app/api/v1/knowledge.py` — 新增 formulas/categories 端点 + 增强 list_formulas 参数
- `app/services/llm_analysis_service.py` — 提示词 domain 字段优化
- `web/src/views/KnowledgeView.vue` — 分类树 + 来源标签 + 筛选器
- `app/main.py` — 启动时调用 seed_formula_library

**验证：** API 分类树返回 6 个顶级分类 + 24 子分类 + 32 内置公式 ✅ Young-Laplace 计算 2×0.072/0.00005=2880 Pa ✅

### 新增 API 端点汇总（公式增强）

| 端点 | 说明 | 维度 |
|------|------|------|
| `GET /knowledge/formulas/categories` | 获取公式分类树（含公式计数） | P3 |

### 前端改造

KnowledgeView.vue 从 ~2400 行扩展为 ~2450 行，公式计算 tab 改造：
- **分类树浏览**：el-tree-select 替代 domain 下拉，支持层级展开 + 关键字搜索 + 公式计数显示
- **来源筛选**：el-select 切换 全部/内置公式/文档提取
- **公式卡片增强**：显示来源标签（绿色"内置"/灰色"提取"）+ 分类路径
- **计算器面板增强**：显示分类路径 + 来源标签，内置公式无"来源: 知识条目"链接

**后端总新增：** ~300 行（1 模型 + 1 种子数据 + 1 种子服务 + 1 迁移 + 1 API + schema/service 增强）
**前端总新增：** ~50 行（模板 + 样式 + 方法）
**数据库新增：** 1 张表（formula_categories）+ 3 列（knowledge_formulas.source_type/category_id/is_active）

### Dashboard 布局简化 + Webhook 部署修复 (2026-05-27)

| 功能 | 说明 | 状态 |
|------|------|------|
| Dashboard 移除"即将到期" | 删除统计卡片中的"即将到期"数字、"即将到期任务"列表、"最近会议"列表，简化首页 | ✅ 完成 |
| 前端 dist 未构建修复 | Dashboard.vue 源码已修改但 web/dist/ 未重建，线上仍是旧版。本地 npm run build 后提交 dist | ✅ 完成 |
| Webhook 手动触发 | GitHub 报告"未能连接到主机"，确认 webhook.py 服务正常但网络瞬时不畅，手动模拟签名 POST 触发部署 | ✅ 完成 |

**教训：** 前端源码修改后必须 `npm run build` 并提交 dist。dist 在 `.gitignore` 中，需 `git add -f web/dist/` 强制添加。deploy-auto.sh 依赖 git 已提交的 dist 文件，不在服务器构建。

### 新增 API 端点汇总（二次升级）

| 端点 | 说明 | 维度 |
|------|------|------|
| `GET /knowledge/entities` | 搜索实体（subject/predicate/keyword 过滤） | P0 |
| `GET /knowledge/entities/graph` | 实体图谱（nodes + co-occurrence edges） | P0 |
| `GET /knowledge/entities/{entity_id}` | 实体详情（含来源文档列表） | P0 |
| `POST /knowledge/hypotheses` | 生成科研假设 | P1 |
| `GET /knowledge/hypotheses` | 列出假设（status/priority 过滤） | P1 |
| `GET /knowledge/hypotheses/{id}` | 假设详情（含关联实体） | P1 |
| `POST /knowledge/hypotheses/{id}/validate` | 标记验证结果（validated/rejected） | P1 |
| `GET /knowledge/formulas` | 列出公式（domain/keyword 过滤） | P2 |
| `GET /knowledge/formulas/domains` | 公式领域分布 | P2 |
| `POST /knowledge/formulas/calculate` | 计算公式 | P2 |

### 前端改造

KnowledgeView.vue 从 1890 行单文件扩展为 ~2400 行，使用 `el-tabs` 分为四个 tab 页：
- **知识库** — 原有功能（列表+搜索+RAG QA+图谱+关联+分析结果）
- **实体图谱** — 实体搜索+ECharts 力导向图+实体卡片网格+详情弹窗
- **科研假设** — 筛选栏+生成按钮+假设卡片（状态 badge+验证操作）
- **公式计算** — 双栏布局（公式列表+计算器），变量输入+结果显示+步骤展开

**后端总新增：** ~750 行（3 模型 + 3 服务 + 10 API + 6 schema）
**前端总新增：** ~500 行（3 tab + 方法 + 样式）
**数据库新增：** 4 张表（knowledge_entities, entity_co_occurrence, knowledge_hypotheses, knowledge_formulas）

---

## 2026-05-27 Bug 修复记录

### Nginx 多站点配置被覆盖（mnb-lab.cn 下线）

- **现象**：`mnb-lab.cn` 网站无法访问，Nginx 配置中 `mnb-lab.cn` server block 丢失
- **根因**：`deploy-auto.sh` 每次部署时将 `nginx/conf.d/tunnel.conf` 直接覆盖到 `/etc/nginx/conf.d/default.conf`，但 `tunnel.conf` 只包含 `agent.mnb-lab.cn` 配置，每次部署都清掉同服其他站点
- **修复**：`tunnel.conf` 补回 `mnb-lab.cn` + `www.mnb-lab.cn` 完整 HTTPS server block（SSL 独立证书 `/etc/letsencrypt/live/mnb-lab.cn/`，root `/opt/Micro-Nano-Bubble-Technology-Lab/out`）
- **预防**：CLAUDE.md 新增"修改 tunnel.conf 必须验证两个站点"的注意事项

### 侧边栏导航相对路径导致 422 错误

- **现象**：点击左侧任何导航菜单项都提示"获取知识详情失败"，API 返回 422
- **根因**：`MainLayout.vue` 侧边栏 `el-menu-item :index="route.path"` 使用相对路径（如 `dashboard`），当用户在 `/knowledge` 页面点击其他菜单时，Vue Router 解析为 `/knowledge/dashboard`，误匹配 `/knowledge/:id` 路由，KnowledgeDetailView 被错误挂载，调用 `GET /api/v1/knowledge/dashboard` → 422
- **修复**：
  1. 桌面端 `:index` 改为 `'/' + route.path`（绝对路径）
  2. 移动端 `router.push(path)` 改为 `router.push('/' + path)`
  3. `menuRoutes` 过滤 `r.meta?.icon`，排除 `knowledge/:id` 等详情页路由

### KnowledgeView 缺失 Vue 导入导致白屏

- **现象**：知识库页面完全白屏，Console 报 `ReferenceError: watch is not defined`
- **根因**：`KnowledgeView.vue` 中使用了 `watch()`、`nextTick()`、`onUnmounted()` 但 `import { ref, computed, onMounted } from 'vue'` 未包含这三个 API
- **修复**：补全 import 为 `import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'`

---

## 第六阶段：会议系统智能升级 + 实时声纹识别 (2026-05-29)

- [x] **粘贴文本 AI 分析** — `MeetingAnalysisService` 三阶段流程：检测发言者 → 确认映射 → 全量分析（摘要+要点+决策+发言人统计+自动创建任务）
- [x] **发言者自动检测** — 支持 3 种格式：对话转录（`【张三】`/`张三说`）、结构化摘要（`发言人：张三、李四`）、纯文本 → Claude AI 回退。文档结构标签黑名单过滤
- [x] **标题 AI 自动生成** — 不填标题时 Claude 根据内容自动生成 15 字以内标题
- [x] **3 个新 API 端点** — `POST /meetings/detect-speakers`、`POST /meetings/analyze-text`、`POST /meetings/{id}/speaker-map`、`GET /meetings/{id}/analytics`
- [x] **声纹识别基础设施** — 3D-Speaker ERes2Net (ModelScope) 256 维嵌入 + pgvector 余弦相似度匹配 + silero-vad 语音活动检测
- [x] **实时声纹会议 WebSocket** — `/ws/meeting/{id}/live`：音频流 → VAD → 声纹识别 → ASR → 实时回传发言人标签 + 置信度
- [x] **AI 实时对话** — 通话中呼叫"小气"，Claude 实时回复
- [x] **声纹录入** — `POST /voiceprint/enroll/{member_id}` 上传语音 → 提取嵌入 → 存储到 Member.voice_embedding。Agent `enroll_voice` 工具支持对话触发
- [x] **全屏炫酷通话界面** — 暗蓝黑渐变背景 + 粒子浮动 + 中央大头像 + 涟漪波纹 + 频谱跳动 + 毛玻璃转写面板 + 半透明操作栏
- [x] **AudioWorklet 低延迟采集** — 替代 ScriptProcessor，16kHz 重采样在独立线程完成
- [x] **前端粘贴分析对话框** — 三阶段：输入 → 发言者映射 → 结果展示 + 内联编辑
- [x] **Agent 工具升级** — 新增 `analyze_meeting_transcript`、`enroll_voice` 工具，升级会议分析提示词
- [x] **数据库扩展** — Member: +voice_embedding(Vector 256), +voice_enrolled_at, +voice_sample_count; Meeting: +speaker_mapping(JSON), +speaker_stats(JSON)
- [x] **Docker GPU 支持** — app 容器添加 nvidia GPU device reservation，celery-worker 内存升至 2g
- [x] **Nginx WebSocket 升级** — /api location 添加 Upgrade/Connection 头支持 WebSocket

**新建文件：**
- `app/services/meeting_analysis_service.py` — AI 分析服务（发言者检测 + 结构化分析 + 统计数据 + 标题生成）
- `app/services/voiceprint_service.py` — 声纹录入/识别/匹配服务
- `app/voice/vad.py` — silero-vad 语音活动检测封装
- `app/voice/pipeline.py` — VAD → 声纹 → ASR 实时流水线
- `app/api/v1/voiceprint.py` — 声纹录入 API
- `web/src/components/PasteAnalyzeDialog.vue` — 三阶段粘贴分析对话框
- `web/src/components/SpeakerMappingPanel.vue` — 发言者映射表
- `web/src/components/AnalysisResultPanel.vue` — 分析结果展示+内联编辑
- `web/src/components/MeetingRoom.vue` — 全屏炫酷声纹通话界面
- `web/src/composables/useAudioCapture.js` — AudioWorklet 音频采集

**修改文件（12个）：**
- `app/models/member.py` — +voice_embedding, +voice_enrolled_at, +voice_sample_count
- `app/models/meeting.py` — +speaker_mapping(JSON), +speaker_stats(JSON)
- `app/schemas/meeting.py` — 新请求/响应模型（SpeakerDetectRequest/Response, TranscriptAnalyzeRequest/Response 等）
- `app/api/v1/meeting.py` — 4 个新端点 + 路由重排序 + minutes 404 修复
- `app/api/v1/voice.py` — 新 WebSocket `/ws/meeting/{id}/live` + 动态发言者切换
- `app/services/meeting_service.py` — process_pasted_transcript(), reanalyze_with_speakers(), _link_speakers_to_participants()
- `app/agent/tools.py` — +analyze_meeting_transcript, +enroll_voice
- `app/agent/core.py` — 新工具分发 + 声纹感知会议提示词
- `app/main.py` — 注册 voiceprint 路由
- `web/src/views/MeetingView.vue` — 集成 PasteAnalyzeDialog + MeetingRoom 对话框
- `web/src/components/LiveTranscript.vue` — 发言者选择下拉菜单
- `requirements.txt` — +modelscope, +torch, +torchaudio, +addict, +datasets, +faster-whisper
- `docker-compose.yml` — app 容器 GPU support + celery-worker mem_limit 2g
- `nginx/conf.d/tunnel.conf` — /api location WebSocket 支持

### 垃圾桶系统修复 (2026-05-31)

- [x] **垃圾桶 API 过滤修复** — `include_deleted=true` 时加 `deleted_at IS NOT NULL`，不再混入活跃任务
- [x] **提醒查询过滤已删除任务** — pending-count / mark-read / GET reminders 三个端点加 `Task.deleted_at.is_(None)`
- [x] **自动清理 Celery 任务** — 每 6 小时永久删除垃圾桶中超过 3 天的任务
- [x] **前端倒计时精确化** — 按小时/分钟显示剩余时间，< 12h 红色高亮提醒

### Dashboard 体验优化 (2026-05-31)

- [x] **文案优化** — "您有X项逾期任务" → "团队共有X项逾期任务"，避免对个人的责备感
- [x] **逾期卡片可点击** — 点击「已逾期」统计卡片直接跳转任务列表并自动过滤逾期任务

### 会议系统深度审计 + 全面修复 (2026-05-31)

- [x] **12 个 Bug 一次性修复** — 崩溃级4个（音频管道/db=None/process_meeting_transcript缺失/3D-Speaker任务类型）+ 功能级5个 + 功能缺失3个
- [x] **会议编辑/删除按钮** — 圆形图标按钮+色彩编码+Tooltip，创建/编辑复用同一对话框
- [x] **跳过映射修复** — 空dict不再被误判为"未提供映射"
- [x] **发言者映射增强** — 映射列改为成员下拉选择器，支持手动输入
- [x] **任务负责人选择** — 分析结果中任务负责人列改为成员下拉选择器
- [x] **手动添加发言人** — 阶段2新增按钮，可添加AI未检测到的发言人
- [x] **删除会议修复** — 先清理关联参与者+解除任务外键约束

### ChatView UI 深度升级 (2026-05-31)

- [x] **沉浸式布局** — 去掉外框卡片，渐变背景+毛玻璃顶栏/底栏
- [x] **欢迎页重设计** — 大图标浮动动画+圆环脉冲+胶囊按钮
- [x] **Markdown增强** — marked.js 支持代码块/列表/表格/引用/链接
- [x] **消息气泡** — 用户珊瑚橙渐变+AI白卡阴影

---

## 声纹会议系统 — 第二波（2a）实时识别全流程 (2026-06-01)

把"声纹识别"从"已有"变成"真正在跑"：从 VAD 检测到声纹匹配到未识别弹窗到声波条可视化，全链路贯通。

- [x] **声纹识别真正启用** — `/live` 端点接入 `MeetingPipeline`，声纹嵌入 → pgvector 匹配 → 实时返回 speaker_name
- [x] **声纹录入整合** — `SpeakerUnidentifiedDialog` 弹窗，未识别说话人时弹出候选成员列表，选人后写入 `speaker_mapping`
- [x] **audio_level 推送** — `/live` 端点 0.1s 间隔推送当前 active speaker 的音量级别，前端声波条跳动
- [x] **SpeakerStrip 声波条** — 5 根 CSS 高度条根据 `audioLevels[memberId]` 实时跳动
- [x] **speaker_claim 消息处理** — 前端 `useMeetingRoomWS` 处理 `speaker_claim_ack`，确认后端已写入映射
- [x] **DB 迁移 010** — 补 `members.voice_embedding` 字段（vector(192)）+ `voice_sample_count` 默认 0
- [x] **VAD per-instance** — 移除 VAD 单例，改为 per-pipeline 实例，避免事件循环绑定冲突
- [x] **MeetingPipeline 注入改造** — Pipeline 通过依赖注入接收 VAD/声纹/ASR 实例，支持单测 mock
- [x] **SpeakerUnidentifiedService** — 新增服务：查询未录入声纹的活跃成员 + 提交 speaker_claim 写入映射
- [x] **前端 MeetingRoom 集成** — `audioLevels` ref + `unidentified` ref 接入弹窗与声波条
- [x] **Float32→Int16 转换** — `useAudioCapture` 输出 Float32，WS 协议用 Int16 PCM，转换放在 MeetingRoom 层
- [x] **MeetingRoom onMounted 修复** — 删除重复的 `})`，让 WS 连接 + 音频采集正确包含在 onMounted 内

## 声纹会议系统 — 第二波（2b）实时 AI 互动 + 声音质量 (2026-06-01)

在声纹实时识别全流程基础上，加上"AI 主动介入"能力与"声音质量"工程化。

- [x] **实时 AI 互动（总结 30s / 翻译 / 纪要 / 提问 + TTS）** — 4 个 AI 触发按钮：📝 总结最近 30 秒、🌐 中英翻译、📋 现在总结、🤔 AI 提问，结果通过 Edge-TTS 实时播报
- [x] **声音质量（MinIO opus 音频存档 + 多设备同步）** — 会议关闭时 audio.opus 上传 MinIO，新加入设备自动从 MinIO 同步缺失片段
- [x] **Admin DELETE audio 端点** — `DELETE /admin/meetings/{id}/audio` 清理音频存档（GDPR/隐私合规）
- [x] **Redis 滑窗 + 多设备广播** — `transcript_buffer` 200 条上限 + LTRIM + 24h TTL，Redis pub/sub 跨设备广播 transcript/ai_response/audio_archive 事件
- [x] **db=None 修复 + AI 工具调用工作** — 修复 chat_stream/db 链路，Agent 工具调用 17 个全部走 service 层

## 声纹会议系统 — 第三波（3a）声纹库 + 跨会议关联 (2026-06-01)

在 wave 2b 实时识别基础上，建设"声纹库中心"和"会议间智能关联"两大基础能力。

- [x] **声纹库中心（256 竖条指纹图 + 置信度历史 + 跨会议搜索）** — 新增 `/voiceprint/fingerprints` 返回所有成员 256 维 embedding + 元数据，`/voiceprint/{member_id}/history` 返回该成员置信度历史，`/voiceprint/search` 跨会议搜索发言片段
- [x] **跨会议相似度推荐（pgvector cosine）** — 会议详情页末尾展示 top-3 相关会议卡片（`Meeting.embedding` + pgvector 余弦相似度匹配）
- [x] **5 分钟前会议提醒（企业微信）** — 创建会议时勾选"提前 5 分钟提醒"，自动创建 `Reminder(target_type='meeting')` 记录，Celery 调度器（10 秒精度）触发企业微信通知
- [x] **voice_embedding / meeting.embedding HNSW 索引** — `members.voice_embedding` HNSW 索引（vector_cosine_ops）支持快速匹配，`meetings.embedding` 同上支持跨会议检索
- [x] **DB 迁移 012/013/014/015** — voice_embedding 256 维、meeting.embedding 768 维、reminder.target_type 支持 meeting、reminder.meeting_id 外键
- [x] **3 个新模型** — `Meeting.embedding`/`related_meeting_ids`/`agenda`、`Reminder.target_type`/`meeting_id`、`VoiceprintHistory`（每次识别一行历史）
- [x] **VoiceprintCard 256 竖条冷暖色指纹图** — 冷色（蓝/青）→ 暖色（橙/红）渐变，0.1~1.0 confidence 映射
- [x] **/live 集成历史记录** — 每次声纹识别 → 写一行 `VoiceprintHistory`，支持声纹库中心的置信度历史曲线
- [x] **5 个 REST 端点** — `/voiceprint/fingerprints`、`/voiceprint/{member_id}/history`、`/voiceprint/search`、`/meetings/{id}/related`、`/meetings` 支持 `remind_5min` 参数
- [x] **5 个前端任务** — VoiceprintView 中心 + ConfidenceChart + SpeakerSearch、MeetingDetailView 相关会议推荐、MeetingView 创建会议提醒复选框、router 加 /voiceprint 路由
- [x] **修复 Meeting.VoiceprintHistory mapper 错误** — `app/models/__init__.py` 缺少 `VoiceprintHistory` 导入，导致 SQLAlchemy mapper 初始化失败（500 错误）

- [x] 第三波（3b）：会议模板 + 通话主屏升级 + UX 收尾
  - 会议模板（4 内置：组会/一对一/立项会/自由 + 用户自建 + CRUD）
  - 议程链路：模板 → MeetingCreate → DB → PATCH /agenda → 通话中勾选完成 → MeetingDetailView 展示
  - 通话主屏升级：大头像 + 16 声波条（LiveSpeakerPanel）+ 议程勾选进度（AgendaPanel）+ 5s 轮询发言统计（SpeakerStatsLive）+ 时间轴跳转（TimelineScrubber）
  - 静音全屏遮罩（MuteOverlay）+ 网络状态条（NetworkStatusBar 显式弱网/离线 + pending 块数）
  - 移动端横屏适配（grid 布局 + media query）
  - 修复 activeSpeaker bug（`onTranscript` 加 `speaker_confidence > 0.45` 阈值判断）
  - 修复 agent/core.py agenda 字段错位（错写到 description → 正确字段）
  - MeetingService.create_meeting + schemas 加 agenda 形参，POST /meetings 端点补 agenda 字段
  - 6 个新组件 + useNetworkStatus composable + MeetingTemplatesView 模板管理页面
  - DB 迁移 016：meeting_templates 表 + 4 内置种子（组会/一对一/立项会/自由）

---

## 文档与 Memory 同步（2026-06-02）

集中更新 README / ROADMAP / CLAUDE.md / MEMORY 文件，统一反映当前项目状态（Phase 1-6 + 知识库两次升级 + 声纹会议系统三波 2a/2b/3a/3b），并将 AI 无法自动完成的部分登记到「待做」区。

---

## 本地运维三件套（方案 A 落地，2026-06-02）

按用户「不要过多占用云服务器资源」原则，把所有能在本地做的运维工作搬到本地 Windows，云服务器职责不变但资源占用更低。

### 实施内容

| 脚本 | 作用 | 触发方式 | 资源消耗（本地）|
|------|------|----------|-----------------|
| `scripts/local-watchdog.ps1` | Docker 服务健康监控（app/db/redis/minio/whisper/celery-worker/celery-beat）| 任务计划每 5 分钟 | < 50MB 瞬时 |
| `scripts/local-backup.ps1` | PostgreSQL 每日备份（gzip → `backups/microbubble_YYYYMMDD_HHMMSS.sql.gz`）| 任务计划每日 02:00 | < 100MB 瞬时 |
| `scripts/local-build-verify.ps1` | 前端 dist 校验（`index.html` / `assets/*.js` / `assets/*.css` / 总体积 ≥ 500KB）| 手动（`npm run build` 后）| 0（纯文件检查）|
| `scripts/install-local-ops.bat` | 一键注册 3 个 schtasks（普通用户即可，管理员权限可选）| 用户双击运行 | 0 |

### 技术要点

- **PowerShell 5.1 兼容**（用 `[ordered]@{}`、`2>$null`、`$inputStream` 替代 7+ 专属语法）
- **结构化 JSON 日志**（`logs/watchdog/*.log` / `logs/backup/*.log`）便于 ELK/Loki 接入
- **Edge-TTS 告警**（参考 `.claude/notify.ps1`）— 用 `Microsoft Huihui Desktop` 中文语音
- **告警去重**（watchdog）— 只在"正常 → 异常"状态切换时 TTS 播报，避免每 5 分钟重复吼叫
- **幂等性**（backup）— 重复跑不报错，备份文件按时间戳命名
- **本地优先**（verify）— 校验失败立即 exit 1，绝不推送坏 dist 到 GitHub

### 踩坑教训

- **`$ErrorActionPreference = "Stop"` 会把 docker compose 的 warning（如 `POSTGRES_PASSWORD not set`）当成 Error 抛异常**。PowerShell 脚本必须用 `$ErrorActionPreference = "Continue"`，需要严格检查时用 `if/throw` 显式控制
- **`2>&1` 会让 `$LASTEXITCODE` 被管道最后一节覆盖**。改用 `2>$null` 抑制 stderr 而不污染退出码
- **`$input` 是 PowerShell 自动变量**，手动赋值会冲突。改名 `$inputStream`
- **未批准的 PowerShell 动词**（如 `Speak-Alert`/`Print-Line`）触发 PSScriptAnalyzer 警告。改用 `Send-Alert`/`Write-Line` 等批准动词
- **TTS 在中文系统上可能没有 `Microsoft Huihui Desktop` 语音**。`try { SelectVoice } catch {}` 优雅降级到默认英语

### 验证结果（2026-06-02 03:32 ✅ 全部通过）

| 项 | 验证时间 | 验证方式 | 结果 |
|----|----------|----------|------|
| watchdog 手动跑 | 03:23 / 03:29 | `& local-watchdog.ps1` | ✅ `All services healthy, 7 services` |
| backup 手动跑 | 03:23 / 03:29 | `& local-backup.ps1` | ✅ 生成 `microbubble_20260602_032334.sql.gz` (950K) |
| build-verify 手动跑 | 03:20 | `& local-build-verify.ps1` | ✅ 24 JS / 17 CSS / 2.82MB / 主入口 1165KB |
| **schtasks 注册** | 03:31 | `cmd /c install-local-ops.bat` | ✅ 3 个任务全部 `Ready`（修复了 `^` 续行符 + 单行 if/else 括号嵌套 bug）|
| **schtasks 自动触发** | 03:32 | `schtasks /Run /TN MicrobubbleWatchdog` | ✅ 任务自动跑，日志显示 03:32:25 写入 `All services healthy` |

### 已注册的 Windows 任务计划

| 任务名 | 触发方式 | 下次运行 | 状态 |
|--------|----------|----------|------|
| `MicrobubbleWatchdog` | 每 5 分钟 | 每 5 分钟滚动 | ✅ Ready |
| `MicrobubbleDBBackup` | 每日 02:00 | 2026/6/3 02:00 | ✅ Ready |
| `MicrobubbleBuildVerify` | 手动（`schtasks /Run`）| on-demand | ✅ Ready |

### 当前部署架构（方案 A 后）

- **本地 Windows (32核+GPU)**：8 个 Docker 服务 + 3 个 schtasks 自动化运维 + Edge-TTS 告警
- **阿里云 ECS 2核2G**：仅 Nginx + FRPS + Webhook（保持不变，**0 负载增加**）
- **数据流**：浏览器 → 云 Nginx → FRP 隧道 → 本地 Docker（不变）
- **运维流**：本地 schtasks → 本地 PowerShell 脚本 → 本地 TTS/日志/备份（**全本地**）

---

## 待做清单（指向主文档）

完整 107 项老清单 + v4 收官 N1-N30 新遗留 + R1-R5 长期路线图见 [README.md「待做清单」](README.md#待做清单107-项老清单--v4-收官新遗留2026-06-12-整合)（含 ✅ 完成状态标记 + 汇总统计表）。

**AI 无法自动完成的部分**（SSH 密钥 / Webhook HMAC / 云服务器 OOM 等需要人工介入）详见 memory: [ai-incomplete-tasks.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/ai-incomplete-tasks.md)

---

## 声纹系统线上修复（2026-06-02 9 个 commit）

继 wave 3b 后线上发现 5 类问题，按 commit 顺序修复：

| Commit | 修复 |
|--------|------|
| `317ab12` | 声纹会议三问题：WS 重连策略健壮化 + 微信 enroll_voice 状态机 + MemberView 加声纹录入入口 |
| `f61432c` | **WS 闪烁真正根因**：`voice.py:_run_live_loop` 函数内冗余 `import asyncio` 触发 UnboundLocalError |
| `3e6b432` | 声纹模型 404（换 ID `_16k-common`）+ 维度 256→192 + 移动端弹窗 + 迁移 017 + 修复 alembic 链断点 |
| `2d1f9ce` | 3D-Speaker pipeline 临时文件传路径 + 固化声纹依赖到 requirements.txt |
| `85ed5ef` | extract_embedding 加 3 层回退（pipeline(路径)→pipeline(numpy)→底层 model） |
| `b76b181` / `ff09baa` / `8dea5d0` | fingerprints API no-cache 头（最终版：`Response` 参数注入，不用 jsonable_encoder）+ get_fingerprints 用 `.tolist()` 转 python float 避免 numpy 序列化崩 |
| `515e203` | 前端 member store `normalizeAvatarUrl` 兜底裸路径 avatar（旧数据 upload.py Query→Form 修复前的脏数据）|
| `7e2ce55` | .gitignore 加 `backups/`（local-backup.ps1 生成的数据库备份不进 git）|
| `8a49b01` | **声纹提取逻辑精修**：`_extract_via_model` 改用 1D tensor（符合 ERes2Net_Pipeline.preprocess 规范）；ConfidenceChart markLine 0.45→0.55 统一前后端阈值；**清空 2 个旧 embedding 让用户重新录入** |

### 关键经验沉淀（已写入 CLAUDE.md）

- 任何函数内的 `import xxx` 都会让 Python 把整个函数的 `xxx` 当局部变量，外部访问会 UnboundLocalError
- FastAPI 默认序列化器**也是**用 `jsonable_encoder`，遇到 numpy 类型会崩
- pgvector SQLAlchemy 读出的是 numpy array，转 list 后元素仍是 numpy.float32
- ModelScope iic 仓库的模型 ID 不稳定，旧 ID 会被新 ID 替换（带 `-common` 后缀）
- 3D-Speaker pipeline 只接受文件路径或 numpy 数组，不接受 bytes
- **3D-Speaker 模型 forward 接收 1D tensor**（不要 `.unsqueeze(0)` 加 batch 维，模型内部自己加）
- 前端 hover 用 `transform` 会创建 containing block，破坏 fixed 定位子元素的渲染
- **ConfidenceChart 里的水平线是 markLine 阈值参考线**（红色虚线 `yAxis`），不是真实数据 — 数据看 `voiceprint_history` 表
- 声纹提取逻辑变更后必须清空旧 DB embedding，让用户重新录入（旧 embedding 是用旧逻辑算的）

---

## 声纹会议全方位热修（2026-06-02，9 commit 链）

一次会话连续修了 9 个生产 bug，按时间倒序：

| Commit | 修复 |
|--------|------|
| `3e1c475` | **A11y daterange 警告**：`el-date-picker type="daterange"` 内部 `<input class="el-range-input">` 没 name（Element Plus 内部渲染，prop 不会传到内部 input）。拆成两个独立 `type="date"` 选择器（`name="...-from"` / `name="...-to"`） |
| `d6ec60b` | 文档同步 |
| `66428c4` | **反幻觉七重过滤**扩展（见下文） |
| `190015f` | **A11y 表单 name**修复：全项目 50+ 个 `el-input/select/textarea/date-picker/checkbox` 加 `name` 属性（5 个 A11y 警告 → 0） |
| `3260bc2` | **Celery worker [tasks] 缺 `post_meeting_process`**（autodiscover `related_name='tasks'` 静默失败 → 显式 `conf.imports` + celery-worker 加 `./app` volume 挂载） |
| `58a4bf2` | 反幻觉**四重过滤** + TimelineScrubber 跳转修复 |
| `9e827a7` | Progress WS snapshot `data=null` 前端崩 |
| `c5ca909` | 声纹会议 live WS 静默断开 + audioLevels 解耦 activeSpeaker |
| `4098d91` | 声纹会议 ASR 幻觉（whisper_server 漏加反幻觉参数） |

### 关键经验沉淀

1. **WS live 静默断开**（`c5ca909`）：`meeting_live_ws` + `_run_live_loop` 必须有**顶层 try/except 兜底**。VAD 加载 / `transcript_history` 发送 / `pubsub.subscribe` / `send_json` 任何异常如果只捕获 `WebSocketDisconnect` 会逃逸到 Uvicorn 静默关闭 WS，**没有错误日志**。验证：改前 1 秒断开，改后 11+ 秒维持
2. **Celery autodiscover `related_name='tasks'` 静默失败**（`3260bc2`）：Celery 5+ 默认 `related_name='tasks'` 会找 `{package}.tasks` 子模块，找不到**静默失败**，`[tasks]` 列表**缺任务**但 worker 启动**不报错**。修复：显式 `celery_app.conf.imports = [...]` + `autodiscover_tasks(related_name=None)`。诊断：`docker logs celery-worker | grep -A 12 "^\[tasks\]$"` 看实际注册列表
3. **Celery 任务失败必须推 progress_update**（`3260bc2`）：`_run_live_loop` 失败时 return error dict 不推 WS，前端永远卡在初始 5 步。修复：失败时在 fail_loop 里 `update_progress(..., status="error")` 推 WS
4. **`audioLevels` 必须解耦 `activeSpeaker`**（`c5ca909`）：之前只在 `activeSpeaker !== null` 时更新 audioLevels，但 activeSpeaker 只在收到 transcript 时才设置。修复：activeSpeaker null 时用 `self` 槽位兜底
5. **Progress WS snapshot 不能发 null**（`9e827a7`）：`get_progress()` 返回 None 时**不发**该消息；前端 `if (msg.data && typeof msg.data === 'object')` 防御性检查
6. **反幻觉必须七重过滤**（`66428c4`）：仅靠 `condition_on_previous_text=False` + `NOISE_PATTERNS` 远远不够。详见上方「Whisper 反幻觉必须三层防护」+「后端七重过滤」条目
7. **TimelineScrubber duration 不能等于 elapsed**（`58a4bf2`）：`meetingDuration = elapsed` 导致 el-slider `max=currentTs` 无法拖动。修复：`meetingDuration = Math.max(MAX_MEETING_DURATION_SEC, elapsed + 60)`
8. **A11y 警告修复双路径**（`190015f` + `3e1c475`）：
   - 普通表单：直接加 `name` 属性（用 Python 脚本跨行扫描 + 按 `v-model` 路径推断 name）
   - **daterange/datetimerange 内部 input 没 name**（Element Plus 已知限制）：拆成两个独立 `type="date"`/`type="datetime"` 选择器

### 完整反幻觉策略（多层防护）

| 层 | 位置 | 修复内容 |
|----|------|----------|
| 1 | `app/whisper_server.py` | `condition_on_previous_text=False` + `no_speech_threshold=0.6` + 过滤 `no_speech_prob > 0.6` 的 segment |
| 2 | `app/voice/asr.py`（本地 fallback） | 同上三件套 |
| 3 | `NOISE_PATTERNS` 黑名单 | 40+ 关键词（明镜与点点/请勿模仿/感谢观看/鲜奶油/锅里/盐巴...） |
| 4 | `_run_live_loop` 7 重过滤 | 短 segment / 短文本 / 字符重复（先去标点）/ 字母数字串 / 乱码启发式 / 句子重复 |

---

## KnowledgeView 白屏修复（2026-06-02 commit `fbffb88`）

线上报 `ReferenceError: chartInstance is not defined`（生产 chunk `KnowledgeView-D0ZcLBJh.js`），路由到 `/knowledge` 切到实体图谱 tab 再离开时 `onUnmounted` 触发崩溃，组件白屏。

- **根因**：`web/src/views/KnowledgeView.vue` 的 `onUnmounted`（原 1083 行）写的是 `chartInstance`，但文件内实际声明的实例变量是 `entityChartInstance`（632 行 `let entityChartInstance = null`，946-970 行 `renderEntityGraph` 中初始化和 `setOption`）。属于闭包内变量名笔误，Vite/Rollup 不会报 undefined 引用错误，运行到 onUnmounted 才崩
- **修复**：onUnmounted 块内 `chartInstance` → `entityChartInstance`（3 处），重新 `npm run build` 提交新 dist
- **经验沉淀**：
  - **变量名笔误也是生产 bug** — `<script setup>` 内任何对未声明标识符的引用，运行到那一行才抛 `ReferenceError`。HMR/esbuild 不会拦下，**只有生产构建 + 触发到对应生命周期才能发现**。任何 `onMounted` / `onUnmounted` / `watch` / `nextTick` 内引用的变量名都要二次核对
  - **同文件多实例变量的命名纪律** — 一旦文件内有 `entityChartInstance` / `meetingChartInstance` / `chartInstance` 多个 echarts 实例，引用前必须打开顶部 `<script setup>` 块确认声明名
  - **CI 防御** — 可在 `web/src/views/**/onUnmounted` 加 lint 规则（eslint-plugin-vue 自定义规则或 `no-undef`），强制 onUnmounted 内引用的变量必须在同文件内声明

## 声纹会议 WS 崩溃循环 + L3 优化（2026-06-02，6 commit）

继三级润色流水线（5 commit）之后的"上线后"修复，按时间倒序：

| Commit | 主题 |
|--------|------|
| `6bc9687` | **WS 崩溃循环根因修复** — BatchPolisher 初始化时访问 `meeting.participants`（lazy relationship）→ async session 触发 sync IO → `sqlalchemy.exc.MissingGreenlet` → WS 关闭 (1011) → 客户端重连 → 服务端又崩 → 循环（用户看到"重连中"永远不停）。修复：传空数组 |
| `e01ffdb` | **L3 3 项优化** — `meeting.key_points` 从 L3 [{text,ts,kind}] 提取纯 text 回写 + `voice.py _broadcast_loop` 订阅 `transcript_polished:{id}` Redis pub/sub 频道（L3 推送给其他设备）+ L3 `_polish_one_chunk` 加 sha1 缓存（24h TTL，重入会话命中）|
| `793d61e` | docs 同步三级润色经验到 CLAUDE.md + memory |
| `3dacea0` | Phase 4+5 前端协议 + UI（useTranscript 状态机 + Tab 切换 + 状态徽章 raw/batch_polished/full_polished + 详情页"AI 精润版转录"section）|
| `8ef1b3b` | Phase 3 L3 全文精润色（alembic 018 加 `transcript_polished` JSON 列 + `meeting_full_polisher.py run_full_polish_pipeline` 分块 + 跨块 context + `prompts/meeting_full_polish.py` L3 专用 prompt 含 `removed` 字段）|

### 关键经验沉淀

7. **async session 中不要访问 lazy relationship**（2026-06-02 教训）— `meeting.participants` / `meeting.related` / `meeting.speaker_stats` 等关系属性在 async session 中**没有**预加载（`selectinload()`）时，访问触发 lazy load → 走同步 IO → `sqlalchemy.exc.MissingGreenlet`。**要么 `await db.refresh(meeting, attribute_names=[...])` 预加载，要么避免访问关系属性**。润色/metadata 上下文**不依赖**关系属性，传空数组/字典即可。**重要 bug 模式**：JS 端"重连中"循环 + 服务端 1011 close code + 完整 traceback 含 `_emit_lazyload` 关键字
8. **SQLAlchemy 异步 lazy load 错误指纹**：`greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place?` + 堆栈含 `strategies.py:1130 _emit_lazyload` → 100% 是这个错
9. **会议上下文 metadata 字段选型**：`meeting_context` / `meeting_metadata` 等**不依赖** lazy 关系。L2/L3 润色需要的 `title` / `participants` / `topic_line` / `context_segments` 应该从已加载字段（`meeting.title` 是 column，**不**触发 lazy load）或显式空值构造

---

---

## 垃圾桶系统全面修复（2026-06-03，4 commit 链）

### 问题
用户报告 5/25 删除的任务到 6/3 仍在垃圾桶中（应 5/28 自动清理），且前端倒计时显示"即将自动删除 / 06-03 03:46 删除"但任务没真正删除。

### 根因（3 个独立 bug + 1 个运维缺陷叠加）

1. **`auto_purge_trash_task` 缺 `@celery_app.task` 装饰器**（commit `dc93bff`）
   - 函数定义是 `async def auto_purge_trash_task():` 但没用 `@celery_app.task` 装饰
   - 验证：`type=function` + `NO NAME` 属性
   - worker 收到任务消息后**找不到**该函数 → 静默丢弃

2. **`celery.py` imports 列表缺 `app.services.task_service`**（commit `dc93bff`）
   - 即便补装饰器，模块不会被 worker 加载
   - 与 2026-06-02 修的 `post_meeting_process` 同类问题（那次修复时漏了本任务）

3. **`celery-beat` 容器缺 `./app:/app/app` volume 挂载**（commit `dc93bff`）
   - 2026-06-02 修复时只给了 `celery-worker`，没给 `celery-beat`
   - beat 容器跑的是构建时烧进镜像的旧代码，新增 schedule 必须 rebuild 25GB 镜像
   - 修复：补 4 个挂载（`./app` + `./data` + `./logs` + `./models/hf_cache`）与 worker 一致

4. **Celery prefork + async session 跨事件循环**（commit `dc93bff`，运行时发现）
   - 一开始用全局 `async_session` 触发 "Future attached to different loop" 错误
   - 改为独立 `create_async_engine(NullPool) + async_sessionmaker`（与 `process_reminders_task` 模式一致）
   - 用 FK `ondelete=CASCADE` 让 DB 自动级联清理 `task_dependencies`（避免访问 lazy relationship 触发 `MissingGreenlet`）

### 调度粒度优化（commit `47fb2c9`）

| 版本 | 调度 | 最大延迟 | retention 3 天时误差 | 用户体验 |
|------|------|----------|----------------------|----------|
| 最初（commit `72d88be`） | 6h | 6h | 8.3% | 用户看到过期但要等 6h 才清理 |
| v1 优化（commit `dc93bff`） | 4h | 4h | 5.5% | 仍会让用户困惑（看到 3.5h 前的"过期"）|
| **v2 优化（commit `47fb2c9`）** | **1h** | **1h** | **1.4%** | **"准点清理"** |

### 前端精准倒计时（commits `b91e429` + `46f04ab` + `47fb2c9`）

- **后端**：`TaskResponse` 新增 `auto_delete_at: Optional[datetime] = None` 字段
  - `list_tasks` / `get_task` 路由用 `setattr` 附加 `deleted_at + settings.TRASH_RETENTION_DAYS`
  - **单一数据源**与 Celery 清理任务共享 `settings.TRASH_RETENTION_DAYS`，不漂移

- **前端** 4 项优化：
  1. 倒计时精度：`< 60min` 精确到分 / `< 24h` X 小时 Y 分 / `>= 24h` X 天 Y 小时
  2. 实时刷新：`setInterval(30s)` 驱动响应式 `now` ref，停留页面不卡住
  3. 5 级颜色分级：imminent/urgent/warning/normal/safe（按剩余小时数）
  4. 双行直接显示：上方相对时间（紧急度颜色）+ 下方绝对时间（具体时刻）
  5. 过期文案：旧"即将自动删除 / 06-03 03:46 删除"误导 → 新"等待下次清理 / 06-03 03:46 到期"明确

- **onUnmounted 缺 import 修复**（与 2026-06-02 KnowledgeView 白屏同源问题）

### 修改文件

- `app/services/task_service.py` — `@celery_app.task` 装饰器 + 独立 NullPool 引擎 + 始终输出日志
- `app/core/celery.py` — `imports` 加 `app.services.task_service` + schedule 4h → 1h
- `app/config.py` — 新增 `TRASH_RETENTION_DAYS: int = 3` 配置
- `app/api/v1/task.py` — 路由附加 `auto_delete_at = deleted_at + retention`
- `app/schemas/task.py` — `TaskResponse` 加 `auto_delete_at` 字段
- `docker-compose.yml` — `celery-beat` 加 `./app` + `./logs` volume 挂载
- `web/src/views/TaskView.vue` — 双行显示 + 5 级颜色 + 实时刷新 + 过期文案

### 验证

- 手动 trigger 第 1 次：🗑️ 永久删除 35 个超过 3 天的过期任务（包含 5/25 那批）
- 手动 trigger 第 2 次：✅ 垃圾桶健康（0 删除，幂等性正确）
- 重启 beat 后 DB 验证：垃圾桶剩余任务数 = 0
- beat 加载新 schedule：`schedule=3600.0`（1h）

### 教训总结

| 类别 | 教训 | 适用 |
|------|------|------|
| Celery 任务添加 | **3 个地方必须同步**：`@task` 装饰器 + `celery.py` imports + **celery-beat 也需 volume 挂载** | 任何新 Celery 任务 |
| Beat 调度粒度 | **要与用户期望对齐**：4h 对 3 天 retention 太粗，1h 才是"准点清理" | 任何时间敏感型清理 |
| Python 模块缓存 | volume 挂载不重载已 import 的模块，**代码改完必须 `docker compose restart worker`** | 任何已 import 模块的修改 |
| async Celery 任务 | 必须独立 `create_async_engine(NullPool)`，**不能用全局 `async_session`** | 任何 async Celery 任务 |
| FK CASCADE 利用 | DB 级 `ondelete="CASCADE"` 已能级联清理，**不要在 async session 中显式遍历 lazy relationship** | 任何关联删除场景 |

---

## Webhook 性能修复（2026-06-03 commit `7ec6ce0`）

### 问题
用户 push `a28d50e` 文档 commit 后，GitHub 报告「**delivery failed: We can't deliver this payload: time out**」。本地 5 次连续 curl `http://agent.mnb-lab.cn:9001/` 验证：

| 次数 | 响应时间 |
|------|----------|
| #1 | 15s |
| #2-5 | 21-22s（线性恶化）|

全部超过 GitHub 10s 超时红线。

### 根因
[scripts/webhook.py:139](scripts/webhook.py#L139) 用 Python `http.server.HTTPServer`（**单线程顺序处理请求**）。即使 `do_POST` 内用 `daemon=True` 启动 deploy 线程（避免单次响应阻塞），**HTTP 请求的接收/响应仍是串行的**。

部署时 git pull 触发 5 次重试 + 75s 指数退避（最坏 200s+），期间所有后续 webhook 健康检查（do_GET）都被 HTTPServer 串行排队 → 全部 10s+ 超时 → GitHub 标记 delivery failed。

### 修复
```python
# 之前
from http.server import HTTPServer, BaseHTTPRequestHandler
server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)

# 之后（2026-06-03）
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
server = ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
```

每个请求独立线程，do_GET 健康检查与 do_POST deploy 完全不阻塞。

### 验证（用户 SSH 阿里云实测）
```
Webhook #1: 200 0.001232s
Webhook #2: 200 0.000968s
Webhook #3: 200 0.000971s
Webhook #4: 200 0.000973s
Webhook #5: 200 0.001036s
```

对比之前 15-22s 改善 **10000 倍**。

### 重要约束（"鸡生蛋"问题）
修改 `scripts/webhook.py` / `deploy-auto.sh` / `webhook.service` 后，**webhook 服务不会自动重启**（deploy-auto.sh 不在重启列表里 — 否则 deploy 流程会被中断）。需要**手动 SSH 阿里云** `systemctl restart webhook` 才生效。这是 webhook 元部署的本质限制。

### 教训
| 类别 | 教训 | 适用 |
|------|------|------|
| Python `http.server` | **`HTTPServer` 是单线程**，daemon 线程只解决"do_POST 内的耗时"，**不解决"多个 HTTP 请求并发"** | 任何对外服务（webhook / health check / 长任务触发）|
| 部署服务的元部署 | webhook 触发 deploy，但 deploy 不能重启 webhook（会自中断）| 任何"部署触发器"型服务（webhook / CI runner）|
| 响应延迟监控 | 持续 10s+ 响应是 webhook 性能问题的早期信号，应在 `local-watchdog.ps1` 加 `WebhookLatency` 监控项 | 部署健康监控 |

---

## 会议模板重构（2026-06-03 commit `d619f33`）

### 问题
用户反馈：会议模板独立页面（`MeetingTemplatesView.vue`）与会议管理（`MeetingView.vue`）功能重叠，且模板功能不完整：
- 自定义模板的**编辑功能是 stub**（`ElMessageBox.alert('编辑功能见后续 PR')`）
- 字段 `default_participant_ids` 和 `default_location` 写但**前端未使用**
- 用户要管理模板必须**切换页面**，使用流程断裂

### 方案
**合并**：删除独立 `MeetingTemplatesView.vue`（91 行）+ `/meeting-templates` 路由，把模板选择/管理**内嵌到 MeetingView 创建会议对话框顶部**。

### 实施

#### 删除
- `web/src/views/MeetingTemplatesView.vue`（91 行孤立页）
- `web/src/router/index.js` 中 `/meeting-templates` 路由

#### MeetingView 视觉重构
| 之前 | 之后 |
|------|------|
| 隐藏式下拉选择器 | **卡片网格**：4 builtin 卡片 + 自定义模板横向排列 |
| 选中态无视觉反馈 | 选中卡片高亮（珊瑚橙边框 + 微渐变背景）|
| 自定义模板需切页面管理 | **行内 CRUD**（hover 显示编辑/删除图标）|
| 创建模板需切页面 | 右上角"存为新模板"按钮，弹窗填字段 |

#### 字段应用修复
`onTemplateChange` 实际已实现完整字段应用（包括 `default_participant_ids` 和 `default_location`），重命名为 `applyTemplate` 并补充 `ElMessage` 提示。

#### 新增模板编辑对话框
字段：`name` / `title_template` / `description` / `default_duration_minutes` / `default_location` / `default_participant_ids` / `agenda`
- 复用会议表单的 `item-list` 样式（议题增删）
- 复用成员的 `el-select multiple`（默认参与人多选）
- 保存：PUT（编辑）/ POST（创建），自动 reload 列表

#### 细节优化
- 关闭对话框时清理 `templateId` 高亮（避免下次打开误显示选中）
- 自定义模板 hover 显示操作按钮（`.template-card.custom:hover` 触发）
- builtin 模板**没有删除按钮**（数据库 `is_builtin` 标记保护）

### 后端
API 完整，无需改动（CRUD 端点 5 个 + `apply_template_to_meeting_data` 服务函数均已实现）。

### 收益
- 减 **91 行**孤立代码
- 减 1 个路由 + 1 个导航菜单项
- 模板管理贴近使用场景（创建会议时管理，**减少 1 次页面跳转**）
- 编辑功能**真正可用**（之前是 stub）

### 教训
- **功能完整性是产品质量的硬指标**：stub 功能（"见后续 PR"）应该被移除或补全，**不应该留在生产**
- **页面拆分要考虑使用流程**：管理 + 使用的强耦合场景应该靠近（如模板管理贴近模板使用），而不是各自为政
- **视觉化优于隐藏**：下拉菜单隐藏信息，卡片网格让用户**看到**所有可用模板（包括 builtin），更易发现价值

---


## v2/v3/v4 全栈架构重构（2026-06-12 收官，17 commits）

> 完整 commit 链 + 按时间倒序的修复记录

### 收官总览

| 阶段 | Commits | 核心成果 |
|---|---|---|
| **v2 核心** (Day 1-8) | 6 | 拆 core.py 1469 行 → 7 模块 + 18 E2E 集成测试 + 部署文档 |
| **v3 深化** (Day 9-15) | 5 | 9 新工具 + 5 Rich Block + 多会话 + dark mode + agent_traces |
| **v4 收官** (Day 17-24) | 6 | 14 legacy 迁完 + ASR 语音 + 代码高亮 + perf + 评估 + core 清理 |
| **合计** | **17** | **160 测试全过**（87 后端 + 73 前端），0 回归 |

### v2 (Day 1-8) 核心架构重构

| Commit | 内容 |
|---|---|
| `8fff43a` | refactor(agent): 拆 core.py 基础设施（5 文件 + 21 测试） |
| `3e81e82` | feat(agent): ChatEngine 双层回复引擎 + v2 主类（+ 23 测试） |
| `371a4fc` | feat(agent): 迁移 3 工具 + 2 新工具（+ 22 测试） |
| `1eb9fce` | feat(api): ChatResponse 扩 4 字段 + /chat/stream SSE 端点 |
| `2f62d51` | feat(chat): 前端 SSE + 4 Rich Block 组件（+ 14 测试） |
| `463d30b` | feat(agent): 兼容 shim + 18 E2E 集成测试 + 部署文档 |

**架构变化**：
- `app/agent/core.py` 1469 行单文件 → 7 个职责清晰模块（`protocol.py` / `tool_registry.py` / `chat_engine.py` / `session_manager.py` / `tracing.py` / `micro_bubble_agent.py` / `llm.py`）
- 工具调度从 26 个 `if/elif` → `@tool` 装饰器 + Pydantic 校验 + 注册表
- 前端 `ChatView.vue` 565 行 → `ChatViewSSE.vue` ~350 行 + 5 个 Rich Block 组件
- 流式从 2s 轮询换全文 → 真实 SSE 流式（`/chat/stream`）
- 响应字段从 6 → 10（+rich_blocks/tool_trace/usage/duration_ms）

### v3 (Day 9-15) 全栈深化

| Commit | 内容 |
|---|---|
| `c3c139a` | feat(agent): 9 v2 工具 + 6 迁移 + 删 tools.py |
| `736a17c` | feat(chat): 5 Rich Block 组件 + 动画 + 网络感知 |
| `0737a44` | feat(chat): 多会话侧栏 + dark mode + Pinia |
| `8c65944` | feat(observability): agent_traces 可观测性闭环 |
| `3a06131` | docs: v3 部署补充 |

**能力新增**：
- 9 个新工具：`get_meeting_detail` / `get_meeting_transcript` / `get_recent_meeting_conclusions` / `get_member_profile` / `get_project_summary` / `list_formulas` / `list_hypotheses` / `query_projects` / `generate_project_plan`
- 5 个 Rich Block：`FormulaBlock`（LaTeX 公式 + 计算）/ `HypothesisBlock`（状态徽章）/ `ProjectSummaryBlock`（任务统计 + 里程碑）/ `TranscriptBlock`（折叠展开）/ `ChartBlock`（ECharts）
- 多会话侧栏：Pinia `chatSessions` store + `SessionSidebar.vue`（240px 折叠 + localStorage 持久化 + 兼容 v1 迁移）
- dark mode：CSS 变量化（`[data-theme="dark"]`）+ 顶栏 toggle（🌙/☀️）
- agent_traces 闭环：Celery 异步写表 + `/admin/agent-traces` 端点 + `AgentTracesView` 管理页

### v4 (Day 17-24) 收官

| Commit | 内容 |
|---|---|
| `4dab542` | feat(agent): 14 legacy 工具迁 @tool 装饰器（`TOOL_REGISTRY` = 34） |
| `a211c56` | feat(chat): ASR 语音完整链路 + 代码高亮（highlight.js 6 种语言） |
| `2c46d0f` | test(perf): 性能基线（`tests/perf/` 6 测试：brief<3s / SSE<1s / tool<5ms） |
| `8d053b1` | feat(eval): LLM-as-judge + RAG 召回率评估体系（20 问标注 + 5 消融） |
| `40cc299` | feat(eval): 20 问标注 + core.py 清理（1469→689 行，-53%） |
| `a8eba51` | docs: 35 项待做清单（v4 收官后） |
| `e92842d` | docs: 整合 140 项待做清单到 README.md |

**收尾亮点**：
- `app/agent/core.py` **1469 行 → 689 行**（-53%），原 794 行 `_execute_tool` 20 个 elif 链替换为 14 行薄壳调 `dispatch_tool`
- ASR 链路：`ChatViewSSE.vue` 点 🎤 → `<VoiceRecorder>` → `onRecordStop` → `POST /api/v1/voice/asr` → 文字 → `sendMessage`；assistent 消息 🔊 按钮 → `POST /api/v1/voice/tts` → `<audio>` 播放
- 代码高亮：`web/src/utils/markdown.ts` 加 `marked-highlight` + 6 语言（python / js / bash / json / sql / yaml）
- 性能基线：`tests/perf/` 4 文件 6 测试 + 阈值（首跑取实测 P95 + 30% buffer）
- 评估体系：`data/eval_queries.jsonl` 20 问标注（`relevant_ids` 占位待部署后人工标真实 ID）+ `scripts/run_llm_judge.py` + `scripts/run_rag_eval.py` + `HybridRetriever.evaluate()` 方法（recall@5 / precision@5 / MRR + 5 消融对比）

### 部署文档

- `docs/agent-v2-deploy.md` — v2 + v3 + v4 完整部署步骤（git pull / docker restart / 验证 / 回滚 / 监控 / 自检命令 / baseline 跑法）
- `docs/pending-tasks-2026-06-12.md`（已删除，合并到 README.md）
- README.md §待做清单（107 项老清单 + 33 项 v4 收官 = 140 项）

### 关键文件索引

**后端核心**：`app/agent/{protocol,tool_registry,llm,session_manager,tracing,chat_engine,micro_bubble_agent}.py`

**工具目录**（13 个文件，34 工具）：`app/agent/tools/{meeting,task,member,project,formula,hypothesis,knowledge,memory,search,feedback,voice,extra_task,research,graph,transcript,meeting_create}_tools.py`

**可观测性**：`app/models/agent_trace.py` + `app/services/agent_trace_tasks.py` + `app/api/v1/admin.py`

**API**：`app/api/v1/chat.py`（8 端点：chat / chat/stream / chat/image / chat/file / ws/chat / chat/history / admin/agent-traces）

**前端**：`web/src/views/chat/ChatViewSSE.vue` + `web/src/components/chat/{RichContent,SessionSidebar}.vue` + `web/src/components/chat/blocks/{10 个 Block}.vue` + `web/src/views/admin/AgentTracesView.vue` + `web/src/stores/chatSessions.ts` + `web/src/utils/markdown.ts`

**评估**：`data/eval_queries.jsonl` + `scripts/{run_llm_judge,run_rag_eval,build_eval_ground_truth}.py`

**性能**：`tests/perf/{test_brief_latency,test_sse_first_byte,test_tool_round_trip}.py`

---

## 多会话并行架构（修复 4，2026-06-12 深夜 +1）

**commit `662a6ea`**（feat(chat): 多会话并行架构 + 切会话丢数据修复 + AbortController + a11y textarea）

**需求**：用户在 A 会话输入"你好"（SSE 开始流式生成）→ 切到 B 会话继续对话 → A 不中断在后台继续 → 切回 A 看到 A 已生成完的内容。多个 SSE 并行互不干扰。

**为什么是架构改造**：旧版 `messages: Ref<Message[]>` 是单一数组，切会话时**直接替换** `messages.value`，导致 ①正在生成的流式内容丢失 ②旧 SSE 流 yield 把内容写到已被覆盖的 `assistantMsg` 引用（白做工）③多个 SSE 流并发会互相打架。

**核心数据结构（per-session 隔离）**：
- `messagesBySession: ref<Record<sessionId, Message[]>>({})` — 每会话独立消息数组
- `messages = computed(() => messagesBySession.value[sessionId.value] || [])` — 模板用
- `activeAssistantMap: ref<Record<sessionId, Message>>({})` — SSE yield 找目标引用
- `abortControllers: Record<sessionId, AbortController>` — per-session 取消
- `sendingSessions: Set<sessionId>` — per-session 锁（不阻止其他会话）
- `loadedSessions: Set<sessionId>` — 防重复加载覆盖后台 SSE 增量
- `persistTimers: Record<sessionId, Timer>` — debounce 100ms 持久化

**关键设计**：
- **`sendMessage` 启动时闭包捕获 `targetSessionId = sessionId.value`**（防止 SSE yield 时外层 `sessionId.value` 已切到 B）
- **SSE yield 通过 `activeAssistantMap.value[targetSessionId]` 找目标 assistantMsg 引用**（即使切到 B，A 的 SSE 仍能写 A 的对象）
- **`scrollToBottom` / `loading` 仅 `targetSessionId === sessionId.value` 时触发**（避免切走后还在滚 A 的消息区）
- **切会话不 abort 任何 SSE**（让 A 后台继续跑），但**组件卸载时 abort 所有**
- **持久化改每次 yield debounce 100ms**（防后台丢数据）

**文件改动**：[web/src/views/chat/ChatViewSSE.vue](web/src/views/chat/ChatViewSSE.vue) 692 → 787 行（架构改造）

**沉淀**：[multi-session-parallel-architecture.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/multi-session-parallel-architecture.md)

---

## 切会话丢数据修复（修复 1，2026-06-12 深夜 +1）

**问题**：用户在 A 会话输入"你好"等流式回复中 → 切到 B 会话 → 切回 A → A 之前生成的回复"消失"了。

**根因**：[web/src/views/chat/ChatViewSSE.vue:79-93](web/src/views/chat/ChatViewSSE.vue#L79-L93) `onSwitchSession` 旧版：
```javascript
const onSwitchSession = (id) => {
  sessionId.value = id
  const saved = localStorage.getItem(`chat_msgs_${id}`)
  if (saved) {
    try { messages.value = JSON.parse(saved) } catch { messages.value = [] }
  } else {
    messages.value = [{...}]
  }
}
```
**没在切换前保存当前会话** → 切走时正在生成的流式回复直接丢。

**修复**：切换前先 `persistSessionSync(sessionId.value)` 把当前会话快照保存到 localStorage（虽然 A 还在后台生成，但**切走时已生成的部分**不丢）。同时归并到修复 4 架构的 `persistSessionSync(id)` 工具函数（同步 + debounce 两个版本）。

**commit**：`662a6ea`

---

## AbortController 取消旧 SSE 流（修复 2，2026-06-12 深夜 +1）

**问题**：
- 多次快速点击"发送"按钮 → 多个 SSE 流并发 → 旧流的 yield 把内容写到新流的 `assistantMsg`
- 切到 B 会话时旧 SSE 仍在跑 → 浪费资源 + yield 到无引用对象
- 组件卸载时 SSE 流没关闭 → reader 没 release

**修复**：
1. [web/src/api/agent/sse.ts](web/src/api/agent/sse.ts) `sseFetch` 加 `signal` 选项 + 内部 `if (signal?.aborted) { await reader.cancel(); return }` 优雅退出
2. `ChatViewSSE` 加 `abortControllers: Record<sessionId, AbortController>` per-session 引用
3. `sendMessage` 启动前 `abortControllers[targetSessionId]?.abort()` + 创建新 controller
4. `onUnmounted` abort 所有 controller + 持久化所有 session

**commit**：`662a6ea`

**关键纪律**：**abort 策略分层**——同视图内重复点击 + 组件卸载要 abort，但**切会话不 abort**（让后台继续跑）。这是修复 4 与旧版"切走就 abort"的关键区别。

---

## watch(sessionId) 兜底 reload（修复 3，2026-06-12 深夜 +1）

**问题**：`sessionId` 可能在 `onSwitchSession` 之外被外部代码改（如 SessionSidebar 调 store action 直接改 currentId），但**没有 watch** 触发 reload，UI 仍显示旧消息。

**修复**：
```javascript
watch(sessionId, (newId, oldId) => {
  if (newId === oldId) return
  if (loading.value) {
    // 正在生成：暂不 reload（避免打断后台流式）
    return
  }
  loadHistory(newId)
  nextTick(scrollToBottom)
})
```

**注意**：`onSwitchSession` / `onCreateSession` 内部手动设的 `sessionId` 走自己的 reload 路径，**不**走 watch（避免双重加载）。

**commit**：`662a6ea`

**参考**：CLAUDE.md 2026-06-11 重点规则「Vue `watch` 响应式数据 — 组件消息/内容依赖 props 数据时只在 onMounted 构建一次会导致数据过时」。

---

## chat `<textarea>` 补 a11y 4 属性（2026-06-12 深夜 +1）

**问题**：webhint 报 `A form field element should have an id or name attribute. A form field element has neither an id nor a name attribute. This might prevent the browser from correctly autofilling the form.`

**根因**：[web/src/views/chat/ChatViewSSE.vue:646-654](web/src/views/chat/ChatViewSSE.vue#L646-L654) chat 输入 `<textarea>` 此前**没** `id` / `name` 属性（历史欠债）。

**修复**：
```html
<textarea
  ref="textareaRef"
  id="chat-input-textarea"
  name="chat-input-textarea"
  v-model="inputText"
  class="input-textarea"
  placeholder="问问小气…"
  rows="1"
  aria-label="聊天输入框"
  title="聊天输入框"
  @keydown="handleKeydown"
  @input="autoResize"
/>
```

**commit**：`662a6ea`（合并到修复 4 架构改造 commit）

**a11y 4 属性铁律**：任何 `<textarea>` / `<input>` / `<el-input>` 都要补齐 `id` + `name` + `aria-label` + `title` 4 属性。**仅 file input 因为 hidden 无法走可见 label 路径，必须显式 aria-label + title 兜底**。参考 [Webhint Optimization](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/webhint-optimization.md) + 2026-06-12 commit `c97071c`（file input 4 属性套件先例）。

---

## RichBlock.type=None Literal 验证失败（2026-06-12 深夜 +1）

**问题**：用户报告"小气助手还在思考 5+ 分钟"。curl `/api/v1/chat/stream` 验证：SSE 事件链完整（thinking → tool_use → tool_result → brief → done），但 `tool_result` 报 `name 'Dict' is not defined` + `done` 事件 `duration_ms: 1780984477934` 错乱。**多层 bug 叠加触发"hang"现象**。

**根因**（[app/agent/chat_engine.py:432-441](app/agent/chat_engine.py#L432-L441) 旧版）：
```python
if "rich_block_type" in result:
    rb_type = result["rich_block_type"]  # None!
    data = {k: v for k, v in result.items() if k != "rich_block_type"}
    return RichBlock(
        type=rb_type,  # Literal[...] 验证失败！rb_type=None
        data=data,
        title=result.get("title"),
    )
```

**问题链**：
1. 17 个 tools/*.py 的 `OutputModel` 都定义 `rich_block_type: Optional[str] = None`（schema 默认值）
2. 工具 `return {"rich_block_type": None, ...}` 把 None 写进 result dict
3. `_extract_rich_block` 只要看到键就构造 `RichBlock(type=None, ...)` → Pydantic Literal 验证失败 → 整个 `chat_stream` 流程**没 yield done 事件** → 前端 SSE 不关闭 → "三个点一直转"

**修复**（[app/agent/chat_engine.py:432-449](app/agent/chat_engine.py#L432-L449)）：
```python
_VALID_RICH_BLOCK_TYPES: frozenset[str] = frozenset(get_args(RichBlockType))

def _extract_rich_block(tool_name, result):
    if not isinstance(result, dict):
        return None
    rb_type = result.get("rich_block_type")
    # 守卫：None 或非法 Literal 值都跳过 → fall through 到 implicit_map
    if rb_type and rb_type in _VALID_RICH_BLOCK_TYPES:
        data = {k: v for k, v in result.items() if k != "rich_block_type"}
        return RichBlock(type=rb_type, data=data, title=result.get("title"))
    # ... implicit_map fallback
    return None
```

**用 `get_args(RichBlockType)` 动态生成集合**——与 [app/agent/protocol.py](app/agent/protocol.py) Literal 自动同步，未来新增 block 类型无需维护。

**commit**：`3852755`

**沉淀**：[richblock-type-none-pitfall.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/richblock-type-none-pitfall.md)

---

## search_knowledge Dict 导入缺失（2026-06-12 深夜 +1）

**问题**：curl 测试 `POST /api/v1/chat/stream` 收到 `tool_result.tool_output.message: "工具 search_knowledge 执行失败: name 'Dict' is not defined"`。

**根因**：[app/services/hybrid_retriever.py:12](app/services/hybrid_retriever.py#L12) 写 `from typing import List, Optional`，但 line 272 `eval_set: List[Dict]` / line 305 `async def _aggregate(per_query: List[Dict]) -> Dict` 用到 `Dict`。

**Python 模块加载时**整个模块的语句都会执行，函数定义体内的类型注解也属于"模块加载期执行"——只要遇到 `Dict` 名称查找，就抛 `NameError: name 'Dict' is not defined. Did you mean: 'dict'?`。**整个 hybrid_retriever 模块根本 import 失败** → search_knowledge 工具一调就报，被兜底 except 吞掉返回 status=error。

**诊断**（在容器内直接 import 测试）：
```python
docker exec microbubble-agent-app-1 python -c "
from app.services.hybrid_retriever import get_hybrid_retriever
"
# 立刻抛 NameError（行号指向 List[Dict] 类型注解）
```

**扫描所有 typing import 漏写**（改进版检查 import 列表是否真含所需名字）：
```bash
for f in app/services/*.py app/agent/tools/*.py; do
  for type_name in Dict List Tuple Optional Union Set FrozenSet; do
    if grep -qE "\b$type_name\b" "$f" 2>/dev/null && ! grep -qE "from typing import.*\b$type_name\b|\*\)" "$f" 2>/dev/null; then
      echo "MISSING $type_name in: $f"
    fi
  done
done
```

**修复**：`from typing import List, Optional` → `from typing import Dict, List, Optional`

**commit**：`3852755`

**沉淀**：[typing-import-missing-bug.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/typing-import-missing-bug.md)

**同类坑**：2026-06-12 commit `4ba7390`（search_tools.py 缺 `Optional`）—— 但那次是 *bare name 出现*，不是 *类型注解中出现*。两类都该用扫描 one-liner 覆盖。

---

## time.monotonic / time.time 混用（2026-06-12 深夜 +1）

**问题**：SSE 流 `done` 事件 `duration_ms: 1780984477934`（**19818 年**——明显错乱）。

**根因**：[app/agent/chat_engine.py:158](app/agent/chat_engine.py#L158) `t0 = time.monotonic()`（启动后的秒数，0.0, 1.5, 100.0...）vs line 253 `int((time.time() - t0) * 1000)`（用 `time.time()` 返回 Unix timestamp 秒数 1780984477.934）—— **两个完全不同的时钟**。

**修复**：
```python
# chat_engine.py:158 (不变)
t0 = time.monotonic()

# chat_engine.py:253 (修复)
# 注意：t0 是 time.monotonic()（line 158），这里必须用 monotonic 配对
# 旧版用 time.time() 配对产生 1780 万亿毫秒的垃圾值（不同时间基准）
duration_ms = int((time.monotonic() - t0) * 1000)
```

**commit**：`3852755`

**验证**：`duration_ms: 2584`（合理——LLM 调用耗时 2.6 秒）。

**纪律**：**时钟必须配对**——`time.monotonic()` 配 `time.monotonic()`（测量经过时间，推荐，避免系统时钟跳变），`time.time()` 配 `time.time()`（Unix timestamp，用于跨进程时间戳）。**永远不要混用**。

---

## 移动端 10 PR 全栈定制（2026-06-13 收官）

> **背景**：项目原版 `web/` 桌面端（Element Plus）已完整交付，移动端只做了"独立抽屉架构 + 横屏 media query + 紧凑顶栏"的局部适配（见 [README 2026-06-02 commit](README.md)）。为满足杜同贺 iPhone + 课题组同学通勤场景，**2026-06-12~13 启动移动端全栈定制**，10 个 PR × 18 commits 完整覆盖。

### 架构总览：路由级双栈 + 4 大基础设施

- **`useIsMobile.js`** — 监听 `window.matchMedia('(max-width: 768px)')` + `navigator.userAgent` 兜底（iPad/iPhone 误判时用 UA 修正）
- **`useSafeArea.js`** — 读 `env(safe-area-inset-*)` 给 iPhone 刘海/底栏留白，包装 `padding-top: max(0px, env(safe-area-inset-top))` 模式
- **`useViewport.js`** — resize 监听 + dynamic viewport units（dvh/dvw）替代 vh/vw 解决 iOS Safari URL bar 抖动
- **`resolveMobile.js`** — 路由解析时根据 `isMobile` 动态 `import('views/mobile/X.vue')` 或 `import('views/X.vue')`，**同一 URL 不同组件**

### PR #1 基建（commit `99bbe6b`）

- `useIsMobile.js` / `useSafeArea.js` / `useViewport.js` 三个 composables
- `resolveMobile.js` 路由适配器
- 路由级双栈骨架：路由表保留，组件 import 延后到路由 resolve 时

**commit**：`99bbe6b feat(mobile): PR #1 基建 — composables + 路由级双栈骨架`

### PR #2 NutUI 4 引入（commit `3c58cb1`）

- `@nutui/nutui` 4.3.14 装包
- MainLayout 移动端分支（`v-if="!isMobile.value"`）：底部 TabBar（4 tab + 中间凸起 +badge）+ 紧凑顶栏 + 安全区适配
- 路由双栈接入：`/chat` 桌面走 `ChatViewSSE.vue`，移动走 `MobileChatView.vue`

**commit**：`3c58cb1 feat(mobile): PR #2 NutUI 4 引入 + 路由级双栈 + MainLayout 移动端`

### PR #3 MobileChatView + ChatViewSSE 重构（commits `c154d86` + `0ed4294`）

- ChatViewSSE 重构出 `useChatStream` composable，桌面移动共享 SSE 客户端（不重复写 SSE 协议层）
- TableBlock 组件：移动端 Rich Block 表格渲染（合并单元格、列宽自适应）
- **build 修复（commit `0ed4294`）** — `import.meta.glob('eager: true, import: 'default')` 在 MobileChatView 引入 12 个 block 组件全部 eager import → Vite 把桌面端代码打进 mobile chunk。**修复**：eager 模式必须包在 `if (!isMobile.value) { ... }` 条件内，让 Vite tree-shake。验证 `web/dist/assets/` 里 grep 桌面组件名不应该出现在 mobile-*.js chunk
- **v-model on prop 误用** — Element Plus `<el-input v-model="localValue">` 在 `:value` 上写 v-model Vue 警告。修复：computed get/set 包装 props

**commit**：`c154d86 feat(mobile): PR #3 MobileChatView + ChatViewSSE 重构 useChatStream + TableBlock` / `0ed4294 fix(mobile): PR #3 build 修复 — import.meta.glob + 修 pre-existing v-model on prop`

### PR #4 会议 3 页（commit `79e445d`）

- `MobileMeetingView`（会议列表 + 状态徽章 + 卡片）
- `MobileMeetingDetailView`（纪要 + 转录 tab 切换 + 录音回放）
- `MobileMeetingRoom`（CSS 3D 声波条 + 麦克风按钮 + 实时字幕）
- 声纹 5 根声波条用 CSS `scale:` 独立属性（不是 `transform: scale()`，避免 webhint paint 警告）

**commit**：`79e445d feat(mobile): PR #4 MobileMeetingView + MobileMeetingDetailView + MobileMeetingRoom`

### PR #5 3 个独立组件（commit `979f4fa`）

- **`CardList.vue`** — 卡片列表 + 下拉刷新（`@touchmove` 监听 + 阈值触发）+ 无限滚动（IntersectionObserver 触发 load more）
- **`LongPressWrapper.vue`** — 长按事件封装（300ms 触发，emit `longpress` 事件，移动端删除/收藏必备）
- **`PageHeader.vue`** — 顶栏统一规范（左侧返回 + 中间标题 + 右侧操作插槽，sticky 定位 + 安全区 padding-top）

**关键决策**：不用 CSS 全屏妥协（`@media (max-width: 768px) { /* 桌面端样式覆盖 */ }`）——独立组件保证可维护性，避免桌面端代码与移动端 CSS 互相污染。

**commit**：`979f4fa feat(mobile): PR #5 3 个独立移动端组件（不用 CSS 全屏妥协）`

### PR #6 4 个浮层组件（commit `f364485`）

- **`MobileFormSheet.vue`** — 表单底部弹出（带 drag-to-dismiss 手势）
- **`MobileActionSheet.vue`** — iOS 风格底部菜单（多个操作 + 取消按钮，v-for 渲染 + emit select）
- **`MobileSearchSheet.vue`** — 搜索浮层（自动 focus + 防抖 300ms + 历史记录）
- **`MobileTaskCreateForm.vue`** — 任务创建 5 字段（标题/描述/负责人/优先级/截止时间），用 MobileFormSheet 包装

**commit**：`f364485 feat(mobile): PR #6 FormSheet + ActionSheet + SearchSheet + TaskCreateForm`

### PR #7 CardList + MobileECharts + TaskTrash 演示集成（commit `ea73cc6`）

- **`MobileECharts.vue`** — 图表懒加载（IntersectionObserver 触发 init，避免非视口图表消耗资源）+ resize 监听
- MobileTaskTrash.vue（垃圾桶页面）用 CardList 渲染 + 恢复/永久删除 ActionSheet
- 完成 PR #5/#6 组件的首次生产集成，验证组件 API 设计

**commit**：`ea73cc6 feat(mobile): PR #7 CardList + MobileECharts + TaskTrash 演示集成`

### PR #8a 6 个移动端页面（commit `0df319e`）

- `MobileDashboard.vue`（欢迎区 + 任务概览 + 宠物兔 + 通知）
- `MobileLoginView.vue`（极简登录 + 验证码 + 主题切换）
- `MobileTaskView.vue`（任务列表 + 状态切换 + 搜索）
- `MobileTaskTrash.vue`（垃圾桶 + 倒计时 + 5 级颜色）
- `MobileMemoryView.vue`（长期记忆列表 + 时间线）
- `MobileSettingsView.vue`（用户设置 + 头像 + 主题）

**commit**：`0df319e feat(mobile): PR #8a 6 个移动端页面（Dashboard/Login/Task/TaskTrash/Memory/Settings）`

### PR #8b 7 个移动端页面（commit `28c4a06`）

- `MobileKnowledgeView.vue`（知识库列表 + 分类筛选 + 搜索）
- `MobileKnowledgeDetailView.vue`（知识详情 + 富文本 + 关联）
- `MobileProjectView.vue`（项目列表 + 进度条）
- `MobileProjectStatsView.vue`（项目统计 + 图表 + 时间线）
- `MobileMemberView.vue`（成员管理 + 卡片 + 声纹录入入口）
- `MobileVoiceprintView.vue`（声纹录入流程 + VoiceprintEnrollFlow 组件）
- `MobileAgentTracesView.vue`（admin 域）

**commit**：`28c4a06 feat(mobile): PR #8b 7 个移动端页面（Knowledge / Project / Member / Voiceprint / AgentTraces）`

### PR #9 PWA + 离线降级 + 骨架屏（commit `2ad3b1e`）

- `vite-plugin-pwa` 1.3.0 装包
- 自动生成 `manifest.json`（name / short_name / theme_color / icons 192+512）
- Service Worker（workbox 7.4）预缓存 app shell（JS/CSS/字体）+ 路由 fallback（offline.html）
- **离线策略 4 件套**：
  1. Service Worker 预缓存 app shell
  2. 路由 fallback：未匹配路由返回 offline.html
  3. `useSafeArea` 动态 viewport units（dvh/dvw）替代 vh/vw
  4. 离线 IndexedDB 兜底：`idbStore` 缓存最近消息
- 骨架屏：移动端首屏加载 < 1.5s 之前显示灰色占位（无 loading spinner，避免闪烁）

**commit**：`2ad3b1e feat(mobile): PR #9 PWA + 离线降级 + 骨架屏`

### PR #10 视觉回归测试矩阵 + 移动端深度定制（commit `9026c07`）

- **`web/tests/visual/visual-regression.spec.mjs`** — Playwright 跨设备截图，**5 viewport × 13 核心页面**：
  - Viewport：iPhone SE (375×667) / iPhone 14 (390×844) / iPhone 15 Pro Max (430×932) / iPad mini (768×1024) / Galaxy S21 (360×800)
  - 13 页面：Dashboard / Chat / Task / TaskTrash / Meeting / MeetingDetail / MeetingRoom / Knowledge / KnowledgeDetail / Project / ProjectStats / Member / Settings
  - 基线截图存 `web/tests/visual/__snapshots__/`，CI 像素对比
- **移动端深度定制**：
  - `TabBar.vue` 底部 4 tab + 中间凸起 + badge 红点
  - `CardList.vue` 卡片大圆角（16px）+ 阴影 + 触摸反馈
  - `SafeArea` 全局 iPhone 刘海/底栏适配
  - 无限滚动（IntersectionObserver sentinel + load more）
  - 下拉刷新（touch 事件链）
- **组件测试**（`web/src/components/mobile/__tests__/`）：
  - `CardList.test.js` — props 渲染 + 滚动事件 + 长按事件
  - `MobileFormSheet.test.js` — open/close 状态 + 字段校验
  - jsdom + Vitest

**commit**：`9026c07 feat(mobile): PR #10 测试矩阵 + 视觉回归 + 移动端深度定制收官`

### 移动端关键纪律

- **路由级双栈** ≠ `v-if` 全局切换：**同一 URL 不同组件**（`/chat` 桌面 `ChatViewSSE.vue` / 移动 `MobileChatView.vue`），store/Pinia 完全独立
- **桌面端 `v-if="!isMobile"` 零影响**：MainLayout 桌面端代码**完全不变**，移动端只是新增分支
- **桌面端 store 不污染**：桌面 `chatSessions` Pinia store 用 Element Plus 主题，移动 `chatSessions` 用 NutUI 主题，两套独立
- **包大小纪律**：mobile chunk 目标 < 250KB gzip，构建后 grep 桌面组件名不应该在 mobile-*.js 出现
- **iOS Safari URL bar 抖动**：用 dynamic viewport units（dvh/dvw）替代 vh/vw
- **iOS 输入法弹起 viewport 变化**：`useViewport` 监听 resize，键盘弹起时重新计算 SafeArea bottom

### 移动端新增文件清单（45 个新文件）

| 类型 | 文件 | PR |
|------|------|------|
| Composable | `useIsMobile.js` / `useSafeArea.js` / `useViewport.js` | #1 |
| Composable | `useChatStream.js`（桌面移动共享） | #3 |
| 路由 | `resolveMobile.js` | #1 |
| 组件 | `CardList.vue` / `LongPressWrapper.vue` / `PageHeader.vue` | #5 |
| 组件 | `MobileFormSheet.vue` / `MobileActionSheet.vue` / `MobileSearchSheet.vue` / `MobileTaskCreateForm.vue` | #6 |
| 组件 | `MobileECharts.vue` / `ProcessingSheet.vue` / `TabBar.vue` / `SafeArea.vue` | #7-9 |
| 组件 | `VoiceTestFlow.vue` / `VoiceprintEnrollFlow.vue` | #8b |
| 页面 | `MobileDashboard.vue` / `MobileLoginView.vue` / `MobileTaskView.vue` / `MobileTaskTrash.vue` / `MobileMemoryView.vue` / `MobileSettingsView.vue` | #8a |
| 页面 | `MobileKnowledgeView.vue` / `MobileKnowledgeDetailView.vue` / `MobileProjectView.vue` / `MobileProjectStatsView.vue` / `MobileMemberView.vue` / `MobileVoiceprintView.vue` / `MobileAgentTracesView.vue` | #8b |
| 页面（chat） | `MobileChatView.vue` / `MobileHeader.vue` / `MobileInputBar.vue` / `MobileMessageBubble.vue` / `MobileMessageList.vue` / `MobileRichCard.vue` / `MobileSessionDrawer.vue` | #2-3 |
| 页面（meeting） | `MobileMeetingView.vue` / `MobileMeetingDetailView.vue` / `MobileMeetingRoom.vue` | #4 |
| 测试 | `CardList.test.js` / `MobileFormSheet.test.js` | #10 |
| 测试 | `visual-regression.spec.mjs`（Playwright 5×13） | #10 |

---

## Webhook 偶发 499 失败加固（2026-06-13）

> **背景**：2026-06-13 12:27:48 GitHub webhook delivery `354e917e` 失败（Nginx 收 499，service 无日志），整套排查+修复。

### 5 步排查流程

1. **查 service 状态** — `systemctl is-active webhook` / `journalctl -u webhook --since "X minutes ago"`。service 还活着 + journal 无对应 delivery = 请求没到 service
2. **查 Nginx access log** — `grep "12:2[5-9]" /var/log/nginx/access.log | grep webhook`。Nginx 收 499 = 客户端主动断开（**不是 service bug**）
3. **查 Nginx error log** — 看是否 `SSL_do_handshake() failed (bad key share)`（阿里云→GitHub TLS 偶发握手失败）
4. **本地 curl 模拟** — `curl -sv http://127.0.0.1:9001/` 验 service 还能响应；构造带正确 X-Hub-Signature-256 的 POST 验整条链路
5. **查服务器 git log** — 看是否落后 main（落后 = 之前有失败 deploy 累积）

### 根因（本次实际）

阿里云→GitHub HTTPS 出口网络瞬时故障（**非代码 bug**）：
- Nginx 收到 GitHub POST → TLS 握手时客户端超时 → Nginx 看到客户端断开返回 499
- service 完全没机会处理（连接都没建立）
- 12:34:51 GitHub 自动重试（`36e23210` delivery）成功部署

### 修复 1：deploy-auto.sh git reset --hard 模式

**根因**：服务器是 immutable infra（部署后不保留本地修改），`git pull` 在 dirty working tree 下会被 untracked 文件阻塞（"Cannot fast-forward"）。

**修复**：
```bash
# 旧（line 32-49）— 5 次重试 + 指数退避，但 dirty 工作区仍会卡
git pull origin main

# 新 — 永远把工作区强制对齐 origin/main
git fetch origin main && git reset --hard origin/main
```

**额外**：`git clean -fd` 改 `git clean -fdx`（也清 .gitignore 内文件，更彻底）

**额外**：`LOG_FILE` 改 `${LOG_FILE:-/var/log/webhook-deploy.log}`（deploy 用户调试时可指定可写路径）

### 修复 2：webhook.py socket timeout

**根因**：rfile.read 无 timeout，GitHub 客户端 10s 超时断开后 service 还在等 body（"幽灵"线程），Nginx 收 499 但 service 无日志（因为日志在 read 之后才打）。

**修复**：
```python
import socket  # 之前缺
self.connection.settimeout(15)  # do_POST 第一行
try:
    payload = self.rfile.read(content_length)
except socket.timeout:
    logger.error(f"读取 body 超时 (15s) ...")
    self.send_response(504)
    self.end_headers()
    return
```

15s = GitHub 默认 10s 客户端超时 + 5s 余量。

### 修复 3：手动 redeliver GitHub webhook（无需 GitHub 介入）

GitHub 自身不重发时，可在本地用真实 commit payload + 真实 secret 模拟 GitHub POST 触发 service 跑 deploy：

```bash
# 1. 取 HEAD SHA
HEAD_SHA=$(git rev-parse HEAD)

# 2. 构造 payload（head_commit / commits / pusher）
PAYLOAD='{"ref":"refs/heads/main","pusher":{"name":"USER"},"head_commit":{"id":"'"$HEAD_SHA"'"},"commits":[{"id":"'"$HEAD_SHA"'"}]}'

# 3. 计算 HMAC-SHA256 签名
SIG=$(printf '%s' "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.*= //')

# 4. POST 到 webhook service（localhost 直连绕过 Nginx）
ssh USER@host "printf '%s' \"$PAYLOAD\" | curl -X POST http://127.0.0.1:9001/webhook \
  -H 'Content-Type: application/json' \
  -H 'X-GitHub-Event: push' \
  -H 'X-GitHub-Delivery: redeliver-$HEAD_SHA' \
  -H \"X-Hub-Signature-256: sha256=\$SIG\" -d @-"
```

service 收到 200 OK 后后台异步跑 deploy，无需等待 GitHub retry 链（5min/30min）。

**commit**：`7e41577 fix(deploy): webhook 偶发 499 失败加固`

**沉淀 memory**：[webhook-debug-2026-06-13.md](../webhook-debug-2026-06-13.md)

**Why:** Webhook 偶发失败是基础设施问题，但脏工作区 + 缺超时是真实代码风险，**两个根因都修才能彻底避免类似事故**。手动 redeliver 是补救手段，不是替代品。

**How to apply:** webhook service 失败时按 5 步排查；deploy-auto.sh 必须用 `git reset --hard` 而非 `git pull`（immutable infra）；webhook.py 必须 `import socket` + `settimeout(15)` + try/except；紧急补部署用 ssh + 真实 payload + HMAC 签名的 curl。

---

## webhint meta-theme-color 静态 → JS 动态注入（2026-06-12）

> **背景**：项目从静态 HTML `<meta name="theme-color" content="#FF7A5C">` 声明主题色，dark mode 切换时静态声明无法跟随主题变化（只能写一个固定值）。

**修复**（commits `0bbc12d` + `3cf8634`）：

- HTML 模板不写静态 meta
- `useThemeStore` 监听 `theme` 变化（'light' / 'dark'）→ 移除旧 meta → 动态创建新 meta 注入 `document.head`
- `.hintrc` 加 `webhint:recommended` 关闭该规则（`hint-meta-theme-color` 只查静态声明，不感知 JS 动态注入）
- `.hintrc` 注释标注决策记录（项目可读性 + 未来决策可追溯）

```javascript
// useThemeStore.js
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  // theme-color 动态注入
  let meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.remove()
  meta = document.createElement('meta')
  meta.name = 'theme-color'
  meta.content = theme === 'dark' ? '#1a1a1a' : '#FF7A5C'
  document.head.appendChild(meta)
}
```

**commit**：`0bbc12d fix(webhint): theme-color 改 JS 动态注入消除 Edge DevTools 误报` / `3cf8634 docs(webhint): .hintrc 标注 meta-theme-color 决策记录`

---

## 项目统计本地 Python 准确化（2026-06-13）

> **背景**：之前 `deploy-auto.sh` 调 `find` + `wc -l` 统计的 stats.json 包含 .meta/.log/.wav/.gz/PostgreSQL data 等**非源代码**，导致 187,220 行 / 2,840 文件数字虚高。本地 Python 脚本按扩展名 + 严格 exclude 目录 + 二进制文件检测，**准确统计源代码**。

**新算法**（本地 Python）：

```python
EXCLUDE_DIRS = ['node_modules', 'dist', '.git', '__pycache__', '.venv', 'venv', 'models', '.agents', '.next', '.cache']
EXCLUDE_FILES = ['package-lock.json', 'yarn.lock', 'pnpm-lock.yaml']

# 按扩展名分类 + 二进制文件检测（'\x00' in text 跳过）
```

**新值**（2026-06-13 13:17:08 重新计算）：
- **总行数**：138,853
- **总文件数**：617
- **总提交数**：965
- **开发天数**：29（5/16 → 6/13）
- **行数分类**：python 35,976 / vue 39,501 / markdown 36,716 / javascript 6,475 / typescript 1,141 / css 1,365 / html 3,517 / shell 2,280 / config 2,651 / docker 56 / other 9,175
- **文件分类**：python 213 / vue 139 / markdown 73 / javascript 63 / typescript 9 / css 5 / html 9 / shell 18 / config 26 / docker 2 / other 60

**对比**（旧值 → 新值）：
- 187,220 → 138,853 行（-26%，剔除 .wav/.gz/.meta/.log/.sql）
- 2,840 → 617 文件（-78%，剔除 PostgreSQL data + 一些测试 fixtures）

**Why:** stats.json 是项目动态页面的数据源，数字虚高会让 184K/2840 看起来不真实（与 git 跟踪的 796 个文件差 3.5x）。准确化让数字可信。
**How to apply:** 后续 stats.json 更新都用本地 Python 脚本生成（deploy-auto.sh 调 `python3 scripts/update-stats.py`），不再用 find+wc 一次性脚本。

---



