# 微纳米气泡课题组智能Agent系统

"小气" - 微纳米气泡课题组AI智能助手（约20人研究实验室）

## 功能特性

- **智能对话** - 支持文字/语音/图片/文件与Agent交互，多模态识别，拖拽上传，对话记录持久化（切换页面/刷新不丢失）
- **联网搜索** - 搜狗微信+必应双引擎并发搜索，自动获取最新信息
- **任务管理** - 创建、分配、追踪任务，自定义提醒时间，角色权限控制（管理员可分配给任何人，普通成员只能管理自己的任务），支持垃圾桶软删除（**3 天后自动清除**，每小时清理一次，垃圾桶 UI 实时显示精确倒计时：`< 1h` 精确到分钟 + 5 级紧急度颜色 + 双行展示「X 小时 Y 分后删除 / 06-04 14:30 删除」）
- **主动提醒** - 自动检查即将到期、已逾期、未确认的任务，通过企业微信主动提醒成员（每15分钟检查，Redis 去重24小时不重复，北京时间显示）
- **知识库** — 文献管理（支持 PDF/Word/Excel/**PPT**/TXT/Markdown）、语义搜索（pgvector）、AI 自动分类标签（动态生成具体研究方向）、对话知识自动入库、**RAG 优先问答**（基于知识库合成答案+来源引用）、**自主研究**（检测知识空白自动联网搜索补充）、**知识图谱**（自动关联 + ECharts 力导向图可视化）、**CP/动态分类体系**（从实际数据自动聚合涌现分类）、**公式计算**（内置 32 个微纳米气泡领域公式 + 分类树浏览 + 安全计算引擎 + LLM 自动提取映射）
- **长期记忆** - 用户偏好记忆、对话摘要、知识图谱构建
- **项目管理** - 课题管理、进度追踪、里程碑管理
- **成员管理** - 课题组成员信息管理
- **语音交互** - 语音输入自动转文字（faster-whisper GPU large-v3），领域术语提示词优化，AI 回复可语音播报（Edge-TTS）
- **会议系统** — 创建/管理会议、粘贴文本 AI 自动分析、**录音机模式**（点击「开始听会」即录，音量指示器 + 波形渲染 + 回放）、**离线后处理**（ASR 转写 + 声纹识别发言人 + AI 摘要/要点/决议 + 自动创建任务）
- **企业微信集成** - 群机器人对话、任务派发通知、到期/逾期提醒、进度回复（消息格式兼容微信插件端）
- **微信插件支持** - 通过微信插件在普通微信内与机器人对话（需一次性注册企业微信）
- **文件管理** - MinIO 文件上传，支持对话文件
- **自动部署** - GitHub Webhook 触发，push 后自动构建部署
- **🐰 宠物乐园** — 仪表盘欢迎区两只 3D 立体兔子（个人兔 + 课题组大兔），CSS 绘制 + 60fps 自主走动，XP 成长进化 + 配饰解锁 + 智能对话 + 互动喂食

### 近期新增（按时间倒序）

- **🎨 webhint CSS @keyframes paint 警告深度治理（2026-06-12）** — 第二轮全面清理 webhint `detect-css-reflows/paint` 警告。读 hint 源码 `packages/hint-detect-css-reflows/src/{paint.ts,assets/CSSReflow.json}` 后发现关键事实：①`transform` 被标 paint=true，但 `scale`/`rotate` 作为独立属性（CSS Transform Module Level 2，2022+ 全浏览器原生）**不在该 JSON 里**，是干净绕开的官方方案；②`will-change` 完全不被该 hint 考虑（只扫 keyframes 内属性名），加 `will-change: transform` 无用；③独立 `translate:` 属性比 `transform: translate()` **更糟**（同时标 paint AND layout）。**两轮修复**（commits `d25ab05` + `9baeb18`）：8 类 keyframes 10 个文件批量从 `transform: scale()` / `transform: rotate()` 改为独立 `scale:` / `rotate:` — `pulse` / `done-bounce` / `mic-pulse-ring` / `spin` / `dot-pulse` / `recording-pulse` / `logo-pop-in` / `rotateIn`。剩余 translate 系动画（slide-in / shimmer / progress bar / drawer slide）因 webhint 规则本质约束（任何位移属性都被标 paint/layout）保留 transform，已文档化为已知约束
- **🐛 会议详情页 transcriptEntries 合并循环 undefined.length 崩溃修复（2026-06-12）** — 线上报错 `Cannot read properties of undefined (reading 'length')`。根因：[MeetingDetailView.vue:420](web/src/views/MeetingDetailView.vue#L420) `current.text.length` 读取，当 transcript 条目缺 `text` 字段时 `current.text` 为 `undefined`，立刻爆。`entry.text?.length || 0` 之前只防了右边，左边没防。**4 处防御**：初始 `current` 强制 `text: raw[0].text || ''`、阈值比较左右两侧都 `?.length || 0`、字符串拼接两侧都 `|| ''` 防 `undefined undefined`、else 分支新建 current 同样强制 text 兜底（commit `0470f55`）
- **🐛 polish-text 400 空白堆积修复（2026-06-12）** — 上次崩溃修复将 `raw[0].text || ''` 默认为空串后引入新 bug：同一发言人多个空 text 条目连续 merge 时累加 `'' + ' ' + ''` 全是空格，21 个连续空 text → merged 是 21 空格，`length > 20` 通过 `_needsPolish` 触发 polish-text 调用，但后端要求 `strip().length >= 3` → 400。**3 处防御**：[MeetingDetailView.vue](web/src/views/MeetingDetailView.vue) `_needsPolish` 改用 `trim().length > 20`（不是裸 length）+ `autoPolishIfNeeded` 发送前 `trim().length >= 3` 兜底 + 手动按钮 `polishMergedText` 同样 trim 校验 + `ElMessage.warning('文本太短，无需润色')` 提示（commit `6fea262`）
- **🛡️ 会议录音全栈防御机制 5 阶段完成（2026-06-12）** — 解决会议 #84 案例：58 分钟录音因 network error 丢失。完整修复：①前端 IndexedDB 兜底（chunks 全部持久化，断网/刷新不丢）②边录边传（每 1s chunk 立即 PUT，失败 IDB 标记 + 5xx 指数退避 1s→2s→4s→8s→16s，4xx 不重试）③后端 chunked 端点（`PUT /audio-chunk` / `POST /merge-chunks` / `GET /upload-status`）④状态机字段迁移（`upload_status` / `last_chunk_index` / `total_chunks` / `error_reason`）⑤后端 stop-recording 硬校验（无 chunk 返回 400，避免空处理）⑥Celery 真实 self.retry（之前 `max_retries` 形同虚设，瞬时错误自动重试 3 次/60s）⑦孤儿会议清理 job（10 分钟扫一次 `recording > 1h 无 chunk` 标 error + 清 MinIO）⑧删会议清 MinIO（chunks + merged + 旧版 audio_url 全清）。**5 个 commit, 21 个新 vitest, 全部 59 测试通过, 端到端 curl 验证会议 #89 全链路（3 真实静音 webm → merge → 80KB merged → Celery 处理 → completed）**。详见 [ROADMAP 章节](ROADMAP.md#会议录音全栈防御机制2026-06-12)
- **Vite hash 改 hex 真正消除 webhint cache-busting 误报（2026-06-12）** — Vite 8 默认 `hashCharacters: 'base64url'` 产出 `index-Qec9lxup.css`、`MainLayout-B6AkdWtm.js` 等，webhint 内置正则只认 `[0-9a-f]+` 小写 16 进制，导致 **49 条 cache-busting 报告全部报"URL does not match configured patterns"**。修复：[web/vite.config.js](web/vite.config.js) 加 `build.rollupOptions.output.hashCharacters: 'hex'`，文件名变为 `index-9ab8129c.js` 等全小写 hex。Rollup 4.x 原生支持。**效果**：49 条报告清零，文件名长度不变（8 字符），CDN 缓存效果一致
- **项目统计更新（2026-06-12）** — 914 次提交 / 184,955 行代码 / 638 个文件 / 28 开发天数（5/16→6/12 动态计算）。stats.json 写入路径稳定在 `app/`（Docker volume 挂载范围）
- **生产 API 响应头实测（2026-06-12）** — curl 实测 `https://agent.mnb-lab.cn/api/v1/meetings/71/polish-text` 响应包含 `X-Content-Type-Options: nosniff` + `Cache-Control: max-age=0` + `Referrer-Policy` + `X-Request-ID`，全部齐全。后端 `security_headers` 中间件 + Nginx 协同工作正常
- **会议转录段落智能切分 + 前端不合并长同发言人段（2026-06-11）** — 后端 `scripts/split_meeting_paragraphs.py` 按主题信号词（但是/我举个例子/接下来/明白吗/第一/第二/此外/另外/所以/因此 等）自动切段，会议 #83 从 48→64 段，最长段 1859字→316字。前端 `MeetingDetailView.vue` 合并阈值改为 60 字，转录卡片从 ~10 个超长卡片 → **~30 个聚焦卡片**（每张聚焦一个主题）。会议 #83 完整精修版见 `meeting83_final.md`
- **会议 L2 润色 prompt 升级（2026-06-11）** — 5 行 "只加标点不改内容" → 允许清理孤立 ASR 幻觉（YouTube 结束语/字幕组声明）+ 修正明显同音错字（"杨词→杨慈"、"丑阳雅雄→臭氧氧化"）。验证层 `_is_punctuation_only_edit` → `_is_reasonable_edit`（容忍 10% 字符差异），支持 `removed` 数组。polish-text 端点从旧内联 prompt 切换为统一 service。会议 #83 全文重润色：532 段 → 323 段（删除 154 段幻觉），残留错名/乱码（周之超/王书馨/优惠价值外/弹牛/MINGPAO/中文字幕志愿者）全部清零，key_points 12→30 条
- **el-tab-pane 加 lazy + Nginx /api 重复 header 修复（2026-06-11）** — 8 个 `el-tab-pane` 加 `lazy` 属性（未激活时不渲染内容），消除 axe/webhint "ARIA hidden focusable" 警告。Nginx `/api` 移除与后端重复的 `add_header`（避免响应里同时存在小写 + PascalCase 两份 header 触发 webhint "missing" 误报）
- **Webhook 自动部署三次修复（2026-06-11）** — 根除 webhook 交付失败：①移除全局 `set -e`，改为关键步骤手动 `exit` ②统计段隔离到子 shell + 命令加 `|| echo 0` 兜底 ③末尾 `exit 0` 确保返回成功。GitHub webhook 交付稳定。**连带修复**：stats.json 写入路径从项目根修正为 `app/`（Docker volume 挂载范围），开发天数从静态值改为 API 每次请求动态计算（`math.ceil` 向上取整，每天自动递增），项目统计从 857 提交/140K 行更新至 891 提交/181K 行
- **CSS 动画性能全面优化（2026-06-11）** — 4 轮修复消除 webhint 性能警告：①`pet-walk` 用 `.bunny-body` wrapper 隔离 transform 动画 ②`pet-sun-glow` 改 opacity 动画 ③`skeleton`/`shimmer`/`skeleton-loading` 改伪元素 + `transform:translateX()` ④PostCSS `stripEpProgressKeyframes` 插件剥离 Element Plus 原版 `left`/`background-position` keyframes。全部动画走 GPU Composite，无 Layout/Paint 触发
- **宠物兔子对话消息修复（2026-06-11）** — `DashboardPet.vue` watch overdueCount/inProgressCount 变化后触发 `rebuildMessages()`，消息内容随任务数据实时更新
- **仪表盘宠物乐园（2026-06-10）** — 🐰 欢迎区变身微缩自然世界（天空+云朵+草地+太阳），两只纯 CSS 3D 立体兔子自主走动。**个人兔**随个人任务完成 XP 成长进化（10 级阶段：兔宝→兔+猫+狗+鸡+仓鼠→传奇），**课题组大兔**「小气」随全组任务总和成长。60fps 状态机：散步/发呆/蹦跳/追光标/逃跑/睡觉。悬停爱心眼+粒子、点击喂食🥕、双击逃跑💨、拖拽移动。XP 进度条、配饰系统（8 种）、智能消息轮播（50 条科研知识+任务提醒+趣味彩蛋）
- **ElMessageBox/ElMessage 按钮偏移修复 + 项目动态代码分布统计（2026-06-10）** — unplugin-vue-components 无法检测 JS 服务调用 → `el-message-box.css` 手动导入。项目动态新增「代码分布」卡片，12 类语言统计 + 水平柱状图
- **知识库 API 性能修复 + Nginx HTTP/2 协议错误修复（2026-06-09）** — 列表 API 不再返回完整 content，改用 snippet 字段（-99% 响应体积），修复大响应穿过 FRP 隧道时 ERR_HTTP2_PROTOCOL_ERROR。Nginx /api 移除 Connection:upgrade + 添加 proxy_buffer 配置
- **前端性能大幅优化（2026-06-09）** — Nginx 开启 gzip 压缩（JS/CSS 传输体积减 70%）+ Element Plus 按需导入（unplugin-vue-components）+ 图标按需注册。主 JS bundle 从 1.2MB 降至 199KB（-83%），主 CSS 从 355KB 单文件降至 15.6KB 按需拆分（-96%），首屏总加载（gzip）从 ~500KB 降至 ~80KB（-84%）
- **项目动态页面（2026-06-09）** — 侧边栏底部新增「项目动态」入口，点击进入全页面展示：项目体量（代码行数/提交次数/开发天数/文件数量，数字递增动画）、已解决痛点（幻觉/部署/安全/性能/架构分类展示）、待做事项（Phase 7-12）、更新日志（全历程时间线）。统计数据由部署脚本自动生成 stats.json，每次 push 自动更新
- **听会后台录音 + 全局指示器（2026-06-09）** — 录音在后台持续进行，导航到其他页面不中断。右下角浮动脉冲胶囊随时可见，点击返回录音界面（计时器继续）。关闭对话框自动保存录音不丢失数据。sessionStorage 始终与后端验证，避免幽灵胶囊残留
- **Webhook 自动部署修复（2026-06-09）** — Nginx 扫描器屏蔽正则 `web` 误杀 `/webhook`（返回 444），修复为 `web$` 精确匹配。GitHub webhook 恢复正常，push 后自动部署
- **Nginx 安全防护（2026-06-09）** — 添加恶意扫描器屏蔽规则：敏感文件探测（.env/.git/.ssh/.aws）、WordPress 漏洞路径、云凭证探测、开发文件探测、常见攻击路径。扫描器请求返回 444（静默关闭连接），正常访问不受影响。agent.mnb-lab.cn + mnb-lab.cn 双站点均已防护
- **Docker Desktop 更新（2026-06-09）** — 4.73.1 → 4.77.0（Engine 29.5.3）+ 中文汉化语言包安装（asxez/DockerDesktop-CN）
- **Webhint 无障碍+性能+安全头全面优化（2026-06-08）** — 修复 ARIA hidden 包含可聚焦元素（el-popover v-if / el-tab-pane lazy）、全站 el-select/el-button/el-progress 图标按钮补全 aria-label（含 MemoryView/TaskView/KnowledgeView/ProjectView/MemberView）、移除废弃 Pragma/Expires 头、Cache-Control 统一为 max-age=0、Nginx proxy_hide_header X-XSS-Protection、CSS 动画用 transform 替代 background-position 消除 webhint 性能警告、Nginx charset_types 去重、移除多余 CSP 头、添加 .hintrc 自定义 revving 正则匹配 Vite content-hash、IE 兼容性警告确认忽略（Vue 3 不支持 IE）
- **垃圾桶批量删除（2026-06-08）** — 编辑按钮切换勾选模式 + 批量永久删除（后端 POST /api/v1/tasks/batch-permanent-delete 单次请求，秒级完成不触发限流）
- **任务列表配对布局（2026-06-08）** — 按负责人配对：左进行中 ↔ 右已完成，同一人左右对齐。修复负责人显示为"未分配"的 string/number 类型不匹配 bug
- **精确跳转（2026-06-08）** — 成员管理"查看任务"跳转自动按 assignee_id 筛选；铃铛"查看我的任务"自动按当前用户筛选
- **UI 优化（2026-06-08）** — 铃铛按钮加大（32px 图标 + 圆形背景 + hover 缩放阴影）、垃圾桶 Tab 加图标加大
- **声纹识别系统重大优化（2026-06-06）** — VAD 精细化（合并阈值 0.1s + 静音 100ms）+ 语义断句（问答/转折/回应词检测）+ KMeans 强制分裂（std>0.15）+ 同名聚类检测 + 名字校对（谐音+编辑距离+精确匹配）。MATCH_THRESHOLD 0.55→0.7。不限人数真实检测。
- **转录编辑功能（2026-06-06）** — 转录每条独立改发言人（el-select 下拉选人）+ 合并后自动 AI 润色加标点。
- **UI 全面优化（2026-06-06）** — 全项目日期选择器替换为 el-date-picker + 时区修正（UTC→北京时间）+ 参与者头像间距分离 + 纪要发言人合并展示 + 纪要加头像 + 每条要点独立选发言人。
- **标题自动生成修复（2026-06-06）** — "未命名会议"和"听会"标题自动触发 AI 生成，重试 3 次。
- **Celery solo pool + 缓存（2026-06-06）** — 改为 `--pool=solo` 避免 prefork 缓存旧代码 + modelscope 缓存挂载避免每次重建下载 3D-Speaker。
- **声纹持续学习（2026-06-06）** — 每次会议识别出的发言人自动更新 voice_embedding，样本越多越稳定。
- **标题自动生成验证通过（2026-06-06）** — 2000 字上下文 + 3 次重试 + regex 兜底，"臭氧微纳米气泡实验条件的影响"生成成功。
- **认证限流优化（2026-06-06）** — auth 5→20次/分钟，read 100→200次/分钟。
- **3D-Speaker 日志精简（2026-06-06）** — 跳过 pipeline 直调 model，消除噪声日志。
- **5090 服务器迁移指南完善（2026-06-06）** — 详见 [docs/migration-5090-server.md](docs/migration-5090-server.md)，含 GPU 分配、资源配置、本地 LLM 方案。
- **会议纪要标准格式固化（2026-06-06）** — 后续所有会议 AI 分析与手动优化均按 `2026.5.28 例行例会` 的信息密度输出：摘要必须包含背景、过程、关键观点、结论和后续方向；`key_points`/`decisions` 必须使用 `【发言人】内容` 格式并写到可追溯、可执行程度；短会议也不能降级成简单摘要。规范见 [docs/meeting-minutes-standard.md](docs/meeting-minutes-standard.md)
- **极简风格前端项目（2026-06-05）** — 创建完全独立的极简主义风格前端项目 `web-minimal/`，包含完整的页面和组件，可直接运行。设计特点：深灰黑主色调 + 珊瑚橙强调色 + 纯白卡片 + 大圆角 + 轻阴影。详见 [web-minimal/README.md](web-minimal/README.md)
- **UI 设计风格展示（2026-06-05）** — 创建 5 种 UI 设计风格示例文件（毛玻璃/新拟态/渐变流体/极简主义/暗黑模式），放置于桌面 `UI设计风格展示/` 文件夹
- **垃圾桶 UI 恢复（2026-06-05）** — 重构子组件时 el-table 被误换为裸 div 导致样式丢失，恢复完整 el-table 7 列布局（标题/负责人/优先级/原状态/删除时间/自动删除/操作）+ 两行倒计时（相对时间精确到分钟 + 绝对时间 MM-DD HH:mm）+ 响应式 30s 实时刷新 + 5 级紧急度颜色 + 脉冲动画
- **会议系统 UI 全面优化（2026-06-05，6 大模块）** —
  - **VoiceTestDialog Canvas 波形**：20 根 DOM bar → Canvas 贝塞尔曲线波形（60fps），珊瑚橙渐变+发光描边+麦克风脉冲光晕
  - **ParticipantAvatars 复用组件**：头像堆叠+溢出+N+全体成员识别+hover 放大
  - **MeetingDetailView 仪表盘式重设计**：Hero 区（大标题+状态徽章+参与者头像行）+ Tab 切换（纪要/转录/统计）+ 内联编辑 + 录音回放侧边栏
  - **SpeakerStatsCard 发言统计**：水平进度条+头像+百分比+stagger 入场动画
  - **AudioPlayer 增强**：Canvas 波形渲染+播放头+倍速控制（1x/1.5x/2x）
  - **MeetingStats 统计页**：3 统计卡片+数字滚动动画+最近会议时间线+发言活跃度排行
  - **ProcessingDialog**：Confetti 撒花+按钮脉冲光晕
- **听会功能全面修复 + 性能优化 + UI 中文化（2026-06-05，5 commit）** —
  - **datetime 时区修复**：`meeting_recording.py` 的 `datetime.now(timezone.utc)` 创建 tz-aware datetime，但数据库列是 `TIMESTAMP WITHOUT TIME ZONE`，asyncpg 无法写入。修复：添加 `.replace(tzinfo=None)`
  - **silero-vad 模型缓存**：GitHub rate limit 导致模型下载失败（HTTP 403），预下载到本地缓存 + 添加回退逻辑
  - **3D-Speaker 依赖修复**：Celery worker 缺少 `addict`/`datasets`/`simplejson`/`sortedcontainers`/`soundfile`，声纹识别无法工作。修复：容器内安装 + 确认 requirements.txt 已包含
  - **点击响应优化**：`requestAnimationFrame` 延迟初始化 + 非阻塞 API 调用 + `ElMessageBox` 替代原生 `confirm`，消除 `[Violation] 'click' handler took 1043ms` 性能警告
  - **会议状态中文化**：`scheduled`→已预约、`recording`→录制中、`processing`→处理中、`completed`→已完成、`cancelled`→已取消、`error`→处理失败
  - **声纹识别验证通过**：杜同贺声纹录入后，听会 30 秒正确识别发言人
- **代码质量全面升级（2026-06-04，30 commit）** —
  - **API 规范化**：统一异常类层次（7 个异常类）+ 统一分页模型 + 全站分级限流（auth:5次/分, write:30次/分, read:100次/分）+ 安全响应头（X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy/X-Request-ID）+ 8 个 API 文件全部改造
  - **后端测试补全**：conftest fixtures + task_service + meeting_service 单元测试 + 任务 API 集成测试（33+ 个测试）
  - **前端 Composables**：useTask/useMeeting/useKnowledge 提取共享状态 + API 调用
  - **前端子组件拆分**：18 个子组件（Task:3 + Knowledge:8 + Meeting:3），三大 View 精简 21%（4495→3568 行）
  - **前端测试体系**：Vitest 配置 + 3 个 composable 测试（23 个）+ 3 个组件测试（15 个）= 38 个测试全部通过
- **声纹测试麦克风误报修复 + DB 列迁移 + Skills 升级（2026-06-04）** —
  - **声纹测试麦克风误报**：`VoiceTestDialog` 的 `AudioContext` 在部分手机浏览器失败后被 catch 误报为"麦克风权限被拒绝"。修复：分离 `getUserMedia` / `AudioContext` 错误处理 + Safari `webkitAudioContext` 兼容 + `suspended` 状态自动 `resume()`
  - **meetings 表列迁移**：`audio_url`/`audio_duration`/`recording_started_at`/`recording_ended_at` 4 列在模型中定义但数据库缺失（`create_all` 不加新列），手动 ALTER TABLE 补全
  - **Skills 框架升级**：从 [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) 下载 16 个新 Skills，总计 37 个
- **听会功能路由修复 + ProcessingDialog 阶段同步（2026-06-04）** —
  - **路由冲突修复**：`meeting_recording.router` 必须在 `meeting.router` 之前注册，否则 `/meetings/start-recording` 会被 `/meetings/{meeting_id}` 拦截返回 405
  - **ProcessingDialog 阶段同步**：前端阶段列表与后端 `ProgressStage` 完全不匹配（旧版 `extracting_transcript` 等），改为与后端一致的 6 阶段（下载音频 → 语音转写 → 识别发言人 → AI 分析 → 创建任务 → 保存结果）
- **声纹会议系统重构 — 录音机 + 离线后处理（2026-06-04）** —
  - **完全替代**实时 WS 流式处理，改为「录音机 + 离线后处理」模式
  - **零配置开录** — 点击「开始听会」即录，无需填写任何信息
  - **录音中有反馈** — 音量指示器（竖条跳动）+ 计时器
  - **录音后可回放** — Canvas 波形渲染 + 播放/进度拖拽
  - **AI 自动补信息** — 后处理自动填充标题、参会人（声纹匹配）、摘要、要点、决议
  - **6 阶段离线流水线** — 音频转码 → ASR 转写 → 声纹识别 → AI 分析 → 自动任务 → 存储
  - **代码大幅精简** — 删除实时 WS 系统（pipeline/batch_polisher/LiveTranscript 等 3000+ 行）
- **前端优化 + 对话持久化 + PPT 支持（2026-06-04，7 commit）** —
  - **对话记录持久化** — 消息自动保存到 localStorage，切换页面/刷新不丢失，版本升级自动清除旧数据
  - **知识库支持 PPT** — python-pptx 提取文本+表格，按页分隔
  - **对话重复回复修复** — 去掉简要/详细轮询机制，直接显示回复，消除闪烁和常驻"查看详情"
  - **ECharts 升级** — 5.4.3→5.6.0 + vue-echarts 6.6.7→6.7.3
  - **Chrome 性能警告消除** — passive event listener 全局补丁（wheel/mousewheel/touchstart/touchmove）
  - **Element Plus 废弃警告修复** — el-pagination `small`→`size="small"` + el-radio `label`→`value`（6 处）
- **知识库大脑 V2 全面升级（2026-06-03，Phase 1-6）** —
  - **Phase 1: 混合检索** — BM25 关键词检索（jieba 分词 + BM25L）+ Cross-encoder 重排序（ms-marco-MiniLM）+ 三路并发（向量 + BM25 + 图谱）+ 合并去重 + 归一化
  - **Phase 2: 知识图谱** — Neo4j 5 社区版 + Neo4jService（CRUD + Cypher 查询）+ KnowledgeGraphBuilder（LLM 实体/关系提取）+ 8 种实体类型 + 8 种关系类型 + 优雅降级
  - **Phase 3: GraphRAG** — GraphRetriever（实体引导检索 + 多跳推理 + 社区摘要 + 路径发现）
  - **Phase 4: Agent 集成** — 8 个知识工具（search_knowledge/explore_knowledge_graph/find_knowledge_gaps/auto_research/compare_knowledge/summarize_topic/suggest_research）+ 混合检索集成
  - **Phase 5: Self-RAG** — SelfRAGChecker（相关性检查 + 检索判断）+ ContextCompressor（去重 + 摘要压缩）
  - **Phase 6: RAG 评估** — RAGEvaluator（faithfulness/relevancy/precision/recall + DB 持久化）
  - **关键修复** — BM25 改用 BM25L（修复 2 文档返回 0 分 bug）+ RAG 评估器语法修复
- **声纹会议系统全面修复（2026-06-03，8 commit）** —
  - **声纹全链路测试**（`8460016`）：新增 `POST /api/v1/voiceprint/test` 端点 + `VoiceTestDialog` 组件，录音→VAD→ASR→声纹一步验证
  - **声纹 enrolled API 解析修复**（`cbc503f`）：`Array.isArray(vpData)` → `vpData.members`，修复声纹状态始终显示 0
  - **参会人自拉取 + avatar schema 补全**（`cbc503f`）：MeetingRoom onMounted 自拉取 participants，`MeetingParticipant` 新增 avatar property
  - **startVoiceCreate 自动添加当前用户**（`cbc503f`）：声纹创建会议不再产生空参会人列表
  - **hangup 后处理任务派发**（`086db70` + `5a3b864` + `fddff52`）：WS hangup 时触发 `post_meeting_process`，修复 ProcessingDialog 永远卡住
  - **batch_polisher 传参修复**（`63a3e82`）：`batch_polisher` 未传入 `_live_loop_inner` 导致 hangup 处理 NameError
  - **Celery 后处理事件循环隔离**（`00b399b` + `1ed628a` + `095938a`）：独立引擎（NullPool）+ 独立 Redis 连接 + `new_event_loop`，修复 `Event loop is closed` / `Future attached to different loop`
  - **反幻觉过滤强化**（`1659f55`）：重复句阈值 3→2 + 低置信度短文本过滤（`confidence < 0.1 && len < 10`）+ 新增黑名单（"高级化链""空气机器"）
  - **ProcessingDialog 改为弹窗**（`87a33b5`）：从全屏改为 500px 弹窗，不再遮挡侧边栏
  - **头像裸路径修复**：DB 中 2 个 `avatars/xxx` 裸路径修正为完整 MinIO URL
- **声纹会议 WS 崩溃循环修复（2026-06-02 commit `6bc9687`）** — `meeting_live_ws` 在 BatchPolisher 初始化时访问 `meeting.participants` 触发 SQLAlchemy lazy load，在 async session 中走 sync IO 抛 `MissingGreenlet` → WS 关闭 (1011) → 客户端重连 → 服务端又崩 → 循环（用户看到"重连中"永远不停）。**修复**：传空数组（润色 context 不依赖 participants）
- **L3 全文精润色 3 项优化（2026-06-02 commit `e01ffdb`）**：
  - L3 `key_points` 回写到 `meeting.key_points`（从 `[{text,ts,kind}]` 提取纯 text 写 `ARRAY(String)` 列）
  - voice.py `_broadcast_loop` 订阅 `transcript_polished:{id}` 频道，L3 全文精润结果通过 Redis pub/sub 推给其他设备
  - L3 `_polish_one_chunk` 加 Redis 缓存（`key = full_polish:sha1(chunk+model)[:16]`，24h TTL），重入会话/测试环境重复触发命中
- **三级润色流水线（2026-06-02 5 commit `f57abc7..793d61e`）** — 替代逐段单条润色，消除 ASR 幻觉：
  - Phase 1：三级配置 + 消灭 3 处"发言人"硬编码 + buffer 200→1000
  - Phase 2：L2 聚批润色（BatchPolisher 攒批 30s/5段，复用 Redis 锁 + 24h 缓存）
  - Phase 3：L3 全文精润色（alembic 018 + claude-sonnet-4 + run_full_polish_pipeline 分块 + 跨块 context）
  - Phase 4+5：前端协议 + UI（useTranscript 状态机 + Tab 切换 + 状态徽章 + L3 section）
- **Webhook 持续失败 4 小时根因 + SSH 修复（2026-06-02，5 commit）** — 阿里云→GitHub HTTPS 出口 130s 超时（`curl 16 Error in HTTP2 framing layer` / `GnuTLS recv error (-110)` / `Connection timed out after 130051ms`），导致 14+ webhook delivery 失败。**4 步修复**：
  - `cd92ad6` `deploy-auto.sh` 显式 `export GIT_SSH_COMMAND="ssh -i /root/.ssh/github_deploy ..."`（belt-and-suspenders）
  - `1b8429a` `webhook.py` POST 端点加详细诊断日志（`delivery_id` / `event` / `sig_head` / `secret_len` / `payload_head`）
  - `6124b88` `deploy-auto.sh` 5 次重试 + 指数退避 + `git fetch + reset` fallback
  - 服务器端：生成 `~/.ssh/github_deploy` 密钥 + 改 `git remote set-url origin git@github.com:...` + 写 `~/.ssh/config` 让 `Host github.com` 自动用专用 key
  - **效果**：从 130s 超时 → 5s 完成，14+ webhook 全部成功
- **A11y 警告彻底清零（2026-06-02，2 commit）** — Element Plus 2.4.4 的 `el-date-picker` **所有类型**（date/datetime/daterange/datetimerange）内部 input 都用 `el-range-input` 类，prop 不会传到内部 input，没有任何 prop 能加 name。**唯一方案**：全部用原生 `<input type="date">` / `<input type="datetime-local">` + 自定义 CSS。影响 5 个文件 + 11 个 el-date-picker
  - `909eecf` `MeetingDetailView` / `ProjectView` / `TaskView` / `Dashboard` / `PasteAnalyzeDialog` 全部替换
  - `87cdd9c` `MeetingView` / `ProjectView` 改用原生 input（首次尝试 type=date 拆开但仍触发，改用原生彻底解决）
- **声纹会议全方位热修（2026-06-02，9 commit）** — 一次会话连续修了 9 个生产 bug：
  - `c5ca909` 声纹会议 live WS 静默断开（`_run_live_loop` 顶层 try/except 兜底）+ 前端 `audioLevels` 解耦 `activeSpeaker`（用 `self` 兜底，声波条不再卡死）
  - `9e827a7` Progress WS snapshot `data=null` 致前端 `TypeError`（后端不发空快照 + 前端防御性 `if (msg.data && typeof msg.data === 'object')`）
  - `3260bc2` **Celery worker [tasks] 列表缺 `post_meeting_process`**（autodiscover `related_name='tasks'` 静默失败 → 显式 `conf.imports` + `autodiscover_tasks(related_name=None)` + celery-worker 加 `./app` volume 挂载）
  - `190015f` A11y 警告修复：全项目 50+ 个 `el-input/select/textarea/date-picker/checkbox` 加 `name` 属性
  - `3e1c475` `el-date-picker type="daterange"` 内部 input 没 name（拆成两个独立 `type="date"` 选择器）
  - `58a4bf2` 声纹会议反幻觉**四重过滤**（`NOISE_PATTERNS` + segment 时长 + 短文本 + 重复模式）+ TimelineScrubber 跳转修复（`meetingDuration=elapsed` 导致 `max=currentTs`）
  - `4098d91` 声纹会议 ASR 幻觉修复（whisper_server 漏加 `condition_on_previous_text=False`）
  - `66428c4` 反幻觉**七重过滤**扩展（字母+数字纯串 / 乱码启发式 / 句子重复 / `_is_repetitive_text` 先去标点，36/36 单元测试通过）
  - `d6ec60b` 文档同步
- **KnowledgeView 白屏修复（2026-06-02）** — `onUnmounted` 钩子引用了未声明的 `chartInstance` 触发 `ReferenceError: chartInstance is not defined`，路由跳转到 `/knowledge`（实体图谱 tab 渲染后）即白屏。文件内实际变量是 `entityChartInstance`（632 行 `let entityChartInstance = null`），是 onUnmounted 内的变量名笔误。已修并重新构建 dist（`KnowledgeView-B1cCcwL2.js`），commit `fbffb88`
- **声纹系统线上修复（2026-06-02 9 个 commit）** —
  - **微信 enroll_voice 状态机**：Agent `enroll_voice` 工具在微信通道下写 Redis pending_enroll，用户发语音后自动完成声纹录入（无需手动上传音频）
  - **WS 闪烁根因**：`voice.py` 函数内冗余 `import asyncio` 触发 UnboundLocalError，已修
  - **声纹模型 + 维度修正**：旧 ID `iic/speech_eres2net_sv_zh-cn_3dspeaker_16k` 已下线，换成 `iic/speech_eres2net_sv_zh-cn_16k-common`；嵌入维度 256→192（3D-Speaker 实际输出）
  - **3D-Speaker pipeline 健壮化**：3 层回退（临时文件路径 → numpy 数组 → 底层 model）；临时文件传路径 + ffmpeg 转 16kHz mono float32 抽到 `app/utils/audio.py` 复用
  - **成员管理加声纹录入入口**：右上角"声纹✓/未录入"徽章 + 底部"录入声纹"按钮 + 麦克风录制/上传文件两种方式
  - **依赖固化到 `requirements.txt`**：sortedcontainers / simplejson / soundfile 等 modelscope 传递依赖，避免 `docker compose build` 时丢失
  - **声纹库中心缓存修复**：API 注入 `Cache-Control: no-store` + `get_fingerprints` 用 `.tolist()` 避免 numpy.float32 序列化崩
  - **移动端弹窗定位修复**：`VoiceprintEnrollDialog` 显式 `append-to-body lock-scroll`，`.member-card:hover` 用 `margin-top` 代替 `transform`（不创建 containing block）
  - **头像裸路径兜底**：前端 member store `normalizeAvatarUrl` 把脏数据 `avatars/xxx` 转 `/minio/microbubble/avatars/xxx`
  - **声纹提取精修 + 阈值统一**：`_extract_via_model` 改用 1D tensor（符合 ERes2Net 规范）；ConfidenceChart markLine 0.45→0.55 统一前后端阈值；清空 2 个旧 embedding 让用户重新录入
  - **重要提示**：ConfidenceChart 里的"水平线"是 markLine 阈值参考线（红色虚线），**不是真实置信度数据**。真实数据看 `voiceprint_history` 表
- **会议系统第三波 3b（2026-06-02）** — 4 个内置会议模板（组会/一对一/立项会/自由）+ 用户自建模板 + 模板→议程全链路（MeetingCreate → DB → PATCH /agenda → 通话中勾选 → 详情页展示）；通话主屏升级为大头像 + 16 声波条 LiveSpeakerPanel + AgendaPanel 议程勾选进度 + 5s 轮询 SpeakerStatsLive + TimelineScrubber 时间轴跳转；静音全屏遮罩 + NetworkStatusBar 网络状态条（显式弱网/离线 + pending 块数）+ 移动端横屏 media query；修复 activeSpeaker bug（`onTranscript` 加 `speaker_confidence > 0.45` 阈值判断）；修复 agent/core.py agenda 字段错位（写到 description → 正确字段）
- **声纹会议系统第三波 3a（2026-06-01）** — 声纹库中心（256 竖条指纹图 + 置信度历史 + 跨会议搜索）；跨会议相似度推荐（pgvector cosine）；5 分钟前会议提醒（企业微信）；voice_embedding / meeting.embedding HNSW 索引
- **声纹会议系统第二波 2b（2026-06-01）** — 4 个 AI 触发按钮：📝 总结 30s / 🌐 中英翻译 / 📋 现在总结 / 🤔 AI 提问 + Edge-TTS 播报；MinIO opus 音频存档 + 多设备同步；Redis 滑窗 + 多设备 pub/sub 广播
- **声纹会议系统第二波 2a（2026-06-01）** — 声纹识别真正启用（VAD → 3D-Speaker → pgvector → speaker_name 实时回传）；SpeakerUnidentifiedDialog 未识别说话人弹窗 + 候选成员列表；audio_level 0.1s 推送 + SpeakerStrip 5 根声波条实时跳动；speaker_claim 写入映射；VAD per-instance 避免事件循环冲突
- **第六阶段（2026-05-29）** — 粘贴会议文本 AI 自动分析 + 实时声纹通话 + AI 实时对话（VAD → 声纹 → ASR 实时流水线）
- **知识库二次升级（2026-05-27）** — 实体级知识图谱 + 科研假设生成引擎 + 量化推理（32 个内置公式 + 6 大类 24 子分类）
- **知识库升级为自主进化知识大脑（2026-05-26）** — 动态 LLM 分析 + 自动关联引擎 + RAG 优先问答 + 自主研究引擎 + 动态分类体系

---

**📜 详细历史和完整 commit 列表见 [ROADMAP.md](ROADMAP.md)**（按时间倒序的全部修复记录）

## 开发工具

- **Claude Code 任务通知** - 任务完成时语音提醒（Edge-TTS），音量最大，语速适中
- **本地运维三件套** (2026-06-02 已注册) - 3 个 PowerShell 脚本 + 3 个 schtasks 任务计划，云服务器 0 负载增加：
  - `scripts/local-watchdog.ps1` — Docker 服务健康监控（每 5 分钟），异常时 Edge-TTS 告警
  - `scripts/local-backup.ps1` — 数据库每日备份（02:00），保留 7 天，结构化日志
  - `scripts/local-build-verify.ps1` — 前端 dist 校验（`npm run build` 后跑），本地拦截异常 dist
  - `scripts/install-local-ops.bat` — 一键注册上述 3 个 Windows 任务计划
  - ✅ **3 个 schtasks 已注册并验证**（2026-06-02 03:32）：`MicrobubbleWatchdog`（每 5 分钟）/ `MicrobubbleDBBackup`（每日 02:00）/ `MicrobubbleBuildVerify`（手动）
  - 查看：`schtasks /Query /FO TABLE | findstr Microbubble`
  - 卸载：`schtasks /Delete /TN "MicrobubbleWatchdog" /F`（其他两个同理）

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue 3 + Element Plus + Vite + Pinia + ECharts |
| AI | Claude API (支持代理地址) + mimo-v2.5 多模态 |
| 语音 | faster-whisper (GPU) + Edge-TTS + silero-vad |
| 声纹识别 | 3D-Speaker ERes2Net (ModelScope) + pgvector 余弦匹配 |
| 向量搜索 | pgvector + text2vec-base-chinese（余弦相似度语义搜索） |
| 知识图谱 | 自动关联引擎（语义相似 + 概念重叠 + 主题共享），ECharts 可视化 |
| RAG 问答 | 检索增强生成（语义搜索 → 阈值分类 → LLM 合成 → 来源引用） |
| 自主研究 | 知识空白检测 → 联网搜索（搜狗+必应）→ LLM 提取 → 自动入库 |
| 缓存 | Redis (Session + 微信状态 + 提醒调度 ZSET) |
| 存储 | MinIO |
| 任务队列 | Celery + Redis |
| 部署 | Docker Compose + FRP 内网穿透 |

## 部署架构

支持两种部署模式：

### 模式 A：云服务器 + 本地电脑 FRP 穿透（当前）

```
用户 → 云服务器 (Nginx + SSL + FRP 服务端) → FRP 隧道 → 本地电脑 (全部 Docker 服务 + GPU Whisper)
```

- **云服务器**（2核 2G）：只运行 Nginx 反向代理 + FRP 服务端，轻量无压力
- **本地电脑**（有 GPU）：运行全部应用服务（app、PostgreSQL、Redis、MinIO、Whisper GPU、Celery）
- **FRP 隧道**：本地 8000 端口穿透到云服务器，用户通过 `https://agent.mnb-lab.cn` 访问

### 模式 B：单机部署（高性能服务器）

如需迁移到一台高性能服务器独立运行（不再需要云服务器 + FRP），硬件建议：

| 组件 | 最低 | 推荐 |
|------|------|------|
| CPU | 8核16线程 | 9950X3D / 9950X |
| GPU | NVIDIA 8GB VRAM | RTX 5090 32GB |
| 内存 | 32GB | 128GB DDR5 |
| 存储 | 2TB SSD | 1TB NVMe(系统) + 8TB SSD(数据) |

完整迁移指南详见 [docs/deploy.md](docs/deploy.md#八服务器迁移单机部署)，包含数据迁移清单、配置修改列表、Nginx + SSL 配置、运维脚本等。

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的配置
# 必填项：CLAUDE_API_KEY、SECRET_KEY、数据库密码等
```

### 2. 本地电脑部署（一键脚本）

```bash
# Windows
start.bat   # 启动所有服务
stop.bat    # 停止所有服务
status.bat  # 查看服务状态

# 或手动启动
docker compose up -d

# 开发模式（热重载，改代码自动重启）
docker compose -f docker-compose.dev.yml up -d
```

### 3. 云服务器部署

```bash
# 首次部署
sudo bash scripts/deploy-cloud.sh

# 配置自动部署（GitHub Webhook）
cp scripts/webhook.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable webhook && systemctl start webhook
# 然后在 GitHub 仓库 Settings → Webhooks 添加:
# URL: https://agent.mnb-lab.cn/webhook
# Secret: 与 .env.webhook 中 WEBHOOK_SECRET 一致
# Events: Just the push event
```

配置完成后，每次 `git push` 到 main 分支会自动部署。

> **注意**：阿里云服务器偶发无法连接 GitHub，若 push 后未自动部署，可通过 SSH 手动触发：
> ```bash
> # 生成 HMAC 签名
> SIG=$(echo -n '{"ref":"refs/heads/main","pusher":{"name":"fix"},"commits":[{"id":"fix"}]}' | openssl dgst -sha256 -hmac "microbubble-deploy-2026" | awk '{print "sha256="$2}')
> # 触发部署
> ssh deploy@60.205.93.8 "curl -s -X POST http://localhost:9001/webhook -H 'Content-Type: application/json' -H 'X-GitHub-Event: push' -H 'X-Hub-Signature-256: $SIG' -d '{\"ref\":\"refs/heads/main\",\"pusher\":{\"name\":\"fix\"},\"commits\":[{\"id\":\"fix\"}]}'"
> ```

> **警告：Nginx 配置必须与 Git 同步！** webhook 部署时 `deploy-auto.sh` 会用 Git 仓库中的 `nginx/conf.d/tunnel.conf` 直接覆盖云服务器的 `/etc/nginx/conf.d/default.conf`。如果在云服务器上手动修改了 nginx 配置，必须同步更新 Git 中的 `tunnel.conf`，否则下次部署会将手动修改覆盖丢失，导致站点不可用。

### 多站点说明

云服务器同时托管 `agent.mnb-lab.cn`（Vite SPA）和 `mnb-lab.cn`（Next.js 静态导出），Nginx 配置在仓库 `nginx/conf.d/tunnel.conf` 中统一维护。修改此文件时必须确保两个站点配置完整，否则部署时会将另一个站点清掉。

### 4. FRP 穿透配置

```bash
# 本地电脑启动 FRP 客户端
cd frp
./frpc.exe -c frpc.toml
```

### 5. 访问系统

- **生产环境**: https://agent.mnb-lab.cn
- **本地开发**: http://localhost:5173 (前端) / http://localhost:8000 (API)
- **API文档**: https://agent.mnb-lab.cn/docs
- **MinIO控制台**: http://localhost:9001

## 项目结构

```
microbubble-agent/
├── app/                     # 后端应用
│   ├── agent/              # AI Agent核心（工具调用、对话管理）
│   ├── api/                # API接口（31个端点，全部带认证）
│   │   └── v1/            # 版本化API
│   ├── core/               # 核心模块（安全、Redis、Celery、日志、限流）
│   ├── models/             # SQLAlchemy数据模型
│   ├── schemas/            # Pydantic验证模型
│   ├── services/           # 业务服务层（10个服务）
│   ├── voice/              # 语音服务（ASR、TTS）
│   └── wechat/             # 企业微信模块（消息、身份、分析、调度）
├── web/                     # 前端应用
│   └── src/
│       ├── views/          # 页面组件（含ChatView图片识别）
│       ├── layouts/        # 布局组件
│       ├── stores/         # Pinia状态管理
│       └── router/         # 路由配置
├── scripts/                 # 部署和工具脚本
├── frp/                     # FRP内网穿透配置
├── docker-compose.yml       # Docker编排（7个服务）
├── Dockerfile.whisper       # Whisper GPU镜像
├── alembic/                 # 数据库迁移
└── .env.example             # 环境变量示例
```

## 开发指南

### 后端开发

```bash
# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```bash
cd web

# 安装依赖
npm install

# 运行开发服务器
npm run dev
```

## API接口

所有接口均需 JWT 认证（除登录外）。

### 核心模块
- `POST /api/v1/chat` - 智能对话（支持工具调用）
- `POST /api/v1/chat/image` - 图片识别对话
- `POST /api/v1/chat/file` - 文件对话（PDF/Word/Excel）
- `WebSocket /api/v1/chat/ws` - 流式对话

### 业务模块
- `GET/POST /api/v1/tasks` - 任务管理（CRUD + 统计 + Dashboard）
- `GET/POST /api/v1/meetings` - 会议管理（含转写分析）
- `GET/POST /api/v1/members` - 成员管理
- `GET/POST /api/v1/projects` - 项目管理（含里程碑）
- `GET/POST /api/v1/knowledge` - 知识库（语义搜索 + 文件上传 + 动态分类 + 标签云 + 知识图谱）
- `GET/POST /api/v1/memory` - 长期记忆管理

### 集成模块
- `POST /api/v1/wechat/callback` - 企业微信回调
- `POST /api/v1/tencent-meeting/webhook` - 腾讯会议回调
- `POST /api/v1/upload` - 文件上传

### Agent 工具（17个）
- `create_task` / `query_tasks` / `update_task` - 任务管理
- `create_meeting` / `query_meetings` - 会议管理
- `query_members` - 成员查询
- `query_projects` / `generate_project_plan` - 项目管理
- `search_knowledge` / `save_conversation_knowledge` - 知识库
- `web_search` - 联网搜索
- `save_memory` / `search_memory` / `forget_memory` - 长期记忆
- `summarize_meeting_transcript` - 会议转录总结
- `query_all_member_tasks` - 全员任务状况（仅管理员/组长）

详细文档: https://agent.mnb-lab.cn/docs

## 当前状态（2026-06-12）

✅ **已上线运行** — 核心功能已完成，生产环境部署成功（https://agent.mnb-lab.cn）

### 🔧 最新改进（2026-06-12）

- **🛡️ 会议录音全栈防御机制 5 阶段完成** — 解决 #84 案例"58 分钟录音断网丢失"。详见 [ROADMAP](ROADMAP.md#会议录音全栈防御机制2026-06-12)：
  - **阶段 1** 前端 IndexedDB 兜底 + 边录边传（`useChunkedRecorder` + `useChunkedUploader` + `idbStore`，21 个新测试）
  - **阶段 2** 上传状态徽章 `UploadStatusBadge.vue` + `useNetworkStatus` 首次接入 + 浮动胶囊网络提示
  - **阶段 3** 后端 chunked 端点（PUT /audio-chunk / POST /merge-chunks / GET /upload-status）+ 4 字段状态机迁移
  - **阶段 4** stop-recording 硬校验 + Celery 真实 `self.retry` + 孤儿会议清理（10min 扫一次）+ 删会议清 MinIO
  - **阶段 5** 端到端测试 + 修复 `delete_chunks` 误删 merged.webm bug（拆为 3 个独立方法）
- **Vite hash 改 hex 真正消除 webhint cache-busting 误报** — 49 条报告清零。Vite 默认 `hashCharacters: 'base64url'` → 改 `'hex'`，文件名变为全小写 16 进制（`index-9ab8129c.js`），webhint cache-busting 正则通过
- **项目统计更新** — 902 次提交 / 172,776 行代码 / 628 个文件 / 27 开发天数。更新日志 28→33 条
- **生产 API 响应头验证** — `curl /api/v1/meetings/71/polish-text` 实测 `X-Content-Type-Options: nosniff` + `Cache-Control: max-age=0` 全部齐全
- **会议 L2 润色升级**（2026-06-11）— 5 行"只加标点"prompt → 允许清理 ASR 幻觉+修正同音错字（杨词→杨慈、丑阳雅雄→臭氧氧化）。会议 #83 全文重润色：532 段 → 323 段，key_points 12→30 条
- **前端不合并长同发言人段**（2026-06-11）— `MeetingDetailView` 合并阈值 60 字，转录卡片从 ~10 → **~30 个聚焦卡片**
- **段落智能切分脚本**（2026-06-11）— `scripts/split_meeting_paragraphs.py` 按主题信号词自动断段，最长段 1859→316 字
- **el-tab-pane lazy**（2026-06-11）— 8 个 tab-pane 懒渲染，消除 ARIA hidden focusable
- **Nginx /api 重复 header 修复**（2026-06-11）— 移除与后端重复的 add_header，避免 webhint 看到小写+PascalCase 两份 header 误报 missing
- **CSS 动画全面 GPU 化**（2026-06-11）— 4 轮修复（pet-walk/sun-glow/shimmer/skeleton + PostCSS 剥离 EP keyframes），webhint 性能警告清零
- **Webhook 部署彻底修复**（2026-06-11）— 三次递进：移除 `set -e` + 子 shell 隔离统计段 + `exit 0` 保底
- **会议模板重构**（commit `d619f33`）— 删除独立 MeetingTemplatesView 页面（91 行），模板选择/管理内嵌到 MeetingView 创建会议对话框。卡片式选择器（4 builtin + 自定义模板）+ 行内 CRUD（编辑/删除/新建）+ 编辑功能**真正可用**（之前是 stub）
- **Webhook 性能修复**（commit `7ec6ce0`）— `HTTPServer` → `ThreadingHTTPServer` 多线程，0.001s 响应（之前 15-22s）
- **垃圾桶系统全修**（4 commit 链）— 3 bug 全修 + beat 调度 1h + 前端双行精准倒计时

### 后端能力
- **会议系统**（声纹通话）— VAD → 3D-Speaker 声纹（192 维 ERes2Net）→ pgvector 匹配 → ASR 流水线；4 内置会议模板 + 议程全链路；**微信 enroll_voice 状态机**（自动完成声纹录入）
- **知识库**（自主进化知识大脑）— 动态 LLM 分析 / 自动关联引擎 / RAG 优先问答 / 自主研究 / 实体级知识图谱 / 科研假设生成 / 量化推理（32 内置公式）
- **任务管理** — 软删除垃圾桶（3 天后自动清理，**1h 巡检**）+ 精准倒计时（5 级颜色 + 双行显示）+ Redis 精确提醒（10s 精度）+ 双向通知
- **长期记忆** — 用户偏好 / 对话摘要 / 知识图谱
- **企业微信** — 微信插件方案（私聊 + 群聊 + 外部用户兼容）
- **三级润色流水线** — L1 实时透传 / L2 聚批润色（30s 攒批）/ L3 全文精润色（claude-sonnet-4）
- **反幻觉七重过滤** — 36/36 单元测试通过

### 前端能力
- 设计系统：暖橙珊瑚色 CSS 设计令牌（`web/src/assets/variables.css`）
- 9 个页面全部完成 UI 升级：Dashboard / TaskView / ChatView / MeetingView / KnowledgeView / MemberView / ProjectView / MemoryView / LoginView
- 移动端：独立抽屉架构 + 横屏 media query + 紧凑顶栏
- 声纹录入 UI（MemberView 卡片徽章 + 录入弹窗）
- 声纹库中心（256 竖条指纹图 + 跨会议相似度推荐）

### 部署 / 运维
- 阿里云 2核2G：Nginx + FRP 服务端 + Webhook（多线程，0.001s 响应）
- 本地 Windows（32核+GPU）：Docker 8 services + GPU Whisper
- **Webhook 自动部署**：GitHub push → SSH 拉取（130s→5s）+ ThreadingHTTPServer（0.001s 响应）
- 本地运维三件套：watchdog / backup / build-verify（schtasks 注册）

### 详细历史

完整 commit 链和按时间倒序的修复记录见 [ROADMAP.md](ROADMAP.md)（2320 行）

### 待解决问题

- 9 位成员未在企业微信通讯录中，无法接收提醒推送（需在企业微信管理后台添加成员）
- 腾讯会议 API 凭据待配置

### 待做清单（107 项，整合版 2026-06-08）

> MicroBubble Agent 43 项 + AI 文档助手 64 项

**一、知识库 & 文档管理（30 项）**

| # | 待做内容 | 项目 | 优先级 |
|---|---------|------|--------|
| 1 | 向量语义检索 — MicroBubble 已有 pgvector；AI 文档助手需从关键词匹配升级为语义嵌入 | 两者 | ⭐⭐⭐ |
| 2 | 实体级知识图谱 — MicroBubble 需跨文档合并实体+ECharts 可视化 | 两者 | ⭐⭐ |
| 3 | 文档详情页路由化 — MicroBubble 弹窗改路由 | 两者 | ⭐⭐ |
| 4 | 图片占位符替换 — [FIGURE:N] 替换为 MinIO 实际图片 URL | MicroBubble | ⭐⭐ |
| 5 | 删除线兜底 — LLM 返回后正则移除 ~~...~~ | MicroBubble | ⭐⭐ |
| 6 | 实体共现关系表 — entity_co_occurrence 表 | MicroBubble | ⭐⭐ |
| 7 | 实体融合 Celery 任务 — 每日定时批量合并相似实体 | MicroBubble | ⭐⭐ |
| 8 | 假设生成引擎 — LLM 基于已有知识生成可验证研究假设 | MicroBubble | ⭐⭐ |
| 9 | 假设验证管理 — proposed/validated/rejected 状态管理 | MicroBubble | ⭐ |
| 10 | 量化推理引擎 — 公式提取+存储+安全 eval 计算器 | MicroBubble | ⭐⭐ |
| 11 | 公式计算器前端 — 左栏公式列表+右栏变量输入+结果 | MicroBubble | ⭐ |
| 12 | QA 集成假设和公式 — 低置信度返回关联假设 | MicroBubble | ⭐ |
| 13 | 实体 API 端点 — /knowledge/entities, /entities/graph | MicroBubble | ⭐⭐ |
| 14 | 文档持久化 — 数据库+文件系统存储，重启不丢失 | AI 文档助手 | ⭐⭐⭐ |
| 15 | 嵌入模型集成 — OpenAI Embeddings 或本地 transformers | AI 文档助手 | ⭐⭐⭐ |
| 16 | 向量持久化 — 嵌入向量存数据库 | AI 文档助手 | ⭐⭐⭐ |
| 17 | 多文档检索优化 — 相关度排序+去重+合并 | AI 文档助手 | ⭐⭐ |
| 18 | 引用溯源 — 回答标注来源文档+段落位置 | AI 文档助手 | ⭐⭐ |
| 19 | 检索数量可配置 — topK 参数动态调整 | AI 文档助手 | ⭐⭐ |
| 20 | 批量上传+文件夹上传 | AI 文档助手 | ⭐⭐ |
| 21 | 新增格式支持 — Markdown、图片OCR、网页URL | AI 文档助手 | ⭐⭐ |
| 22 | 独立文档库页面 — 列表+搜索+筛选+排序 | AI 文档助手 | ⭐⭐⭐ |
| 23 | 文档标签分类 — 论文/报告/笔记/数据 | AI 文档助手 | ⭐⭐ |
| 24 | 文档批量操作 — 批量删除、打标签、重新索引 | AI 文档助手 | ⭐⭐ |
| 25 | 文档搜索 — 全文搜索+语义搜索 | AI 文档助手 | ⭐⭐ |
| 26 | 文档在线预览 | AI 文档助手 | ⭐ |
| 27 | 论文辅助 — 摘要、参考文献提取、对比分析 | AI 文档助手 | ⭐⭐ |
| 28 | 文献管理 — 按课题/项目分类，打标签 | AI 文档助手 | ⭐⭐ |
| 29 | 写作润色 — AI 润色语言、调整格式 | AI 文档助手 | ⭐⭐ |
| 30 | 批量问答 — 对多篇文档同时提问，汇总答案 | AI 文档助手 | ⭐⭐ |

**二、声纹会议系统（20 项）**

| # | 待做内容 | 优先级 |
|---|---------|--------|
| 31 | 反幻觉系统重构 — 三重判定（黑名单+音频能量+no_speech_prob） | ⭐⭐⭐ |
| 32 | 声纹模型 404 修复 — 模型下线+256维→192维不匹配 | ⭐⭐⭐ |
| 33 | 移动端弹窗错位 — 加 append-to-body + 改 CSS | ⭐⭐ |
| 34 | AI 润色自动提示 — L2 结果到达自动切换+角标 | ⭐⭐ |
| 35 | VAD/ASR 参数优化 — 阈值+双重VAD | ⭐⭐ |
| 36 | VoiceTestDialog Canvas 波形动画 | ⭐⭐ |
| 37 | MeetingDetailView 仪表盘式重设计 | ⭐⭐ |
| 38 | MeetingList 列表卡片优化 — 头像堆叠+脉冲动画 | ⭐⭐ |
| 39 | MeetingStats 统计页开发 — 当前空页面 | ⭐⭐ |
| 40 | 会议录音回放组件 — 波形+播放头+倍速 | ⭐⭐ |
| 41 | ProcessingDialog 进度条增强 — confetti 动画 | ⭐ |
| 42 | 会议预设 — 选模板自动填充 | ⭐⭐ |
| 43 | 转录字号自适应 | ⭐⭐ |
| 44 | 智能分段 — 按语义边界切分 | ⭐⭐ |
| 45 | 关键句高亮 — AI 标出决策和待办 | ⭐⭐ |
| 46 | 发言者切换动画 | ⭐ |
| 47 | 实时 AI 互动 — 重述/翻译/总结/提问 | ⭐ |
| 48 | 通话中声纹录入 | ⭐ |
| 49 | 智能纪要按议题分段 | ⭐ |
| 50 | 声纹画像中心 — 指纹图+置信度+认领 | ⭐ |

**三、对话系统（10 项）**

| # | 待做内容 | 优先级 |
|---|---------|--------|
| 51 | 多轮对话上下文 — 追问/纠正/补充 | ⭐⭐⭐ |
| 52 | 对话历史永久保存 | ⭐⭐⭐ |
| 53 | 对话列表页 — 历史对话+搜索 | ⭐⭐⭐ |
| 54 | 继续对话 — 点击历史对话继续聊 | ⭐⭐ |
| 55 | 自动生成对话标题 | ⭐⭐ |
| 56 | 对话分享 — 分享给组员 | ⭐⭐ |
| 57 | 对话导出 — Markdown / PDF | ⭐⭐ |
| 58 | 对话内搜索 | ⭐⭐ |
| 59 | 更多模型支持 — GPT-4o-mini、Claude Haiku | ⭐⭐ |
| 60 | 流式输出 — 逐字输出 | ⭐⭐ |

**四、Agent 智能工具（10 项）**

| # | 待做内容 | 优先级 |
|---|---------|--------|
| 61 | Agent 架构搭建 — LangChain Agent + Tool Calling | ⭐⭐⭐ |
| 62 | 文档搜索工具 — Agent 自动决定何时搜索 | ⭐⭐ |
| 63 | 摘要生成工具 — 从独立功能改为 Agent 可调用 | ⭐⭐ |
| 64 | 信息提取工具 — 从独立功能改为 Agent 可调用 | ⭐⭐ |
| 65 | 翻译工具 — 中英互译，学术翻译 | ⭐⭐ |
| 66 | 论文大纲生成 | ⭐⭐ |
| 67 | 数学计算工具 | ⭐⭐ |
| 68 | 联网搜索工具 | ⭐ |
| 69 | 多步推理 — 复杂问题自动拆解 | ⭐⭐ |
| 70 | 工具自动选择 — Agent 根据问题选工具 | ⭐⭐ |

**五、用户 & 协作（11 项）**

| # | 待做内容 | 优先级 |
|---|---------|--------|
| 71 | 用户注册 — 邮箱/密码 | ⭐⭐⭐ |
| 72 | 用户登录 — JWT Token 认证 | ⭐⭐⭐ |
| 73 | 个人主页 — 头像、昵称、使用统计 | ⭐⭐ |
| 74 | 路由保护 — 未登录自动跳转 | ⭐⭐⭐ |
| 75 | 多用户支持 — 每人独立空间 | ⭐⭐ |
| 76 | 工作空间 — 课题组共享空间 | ⭐⭐ |
| 77 | 成员管理 — 邀请/移除/角色权限 | ⭐⭐ |
| 78 | 共享文档库 — 空间内文档全员可见 | ⭐⭐ |
| 79 | 文档评论 — 批注和评论 | ⭐⭐ |
| 80 | 知识共享 — 对话分享给组员 | ⭐⭐ |
| 81 | 活动日志 — 谁上传了什么、问了什么 | ⭐⭐ |

**六、任务模块（4 项）** — 82.权限控制 83.自定义提醒 84.API改Service层 85.前端角色感知

**七、Agent 核心 & 微信（3 项）** — 86.微信响应优化 87.任务格式还原 88.工具权限

**八、Dashboard（1 项）** — 89.移除即将到期和最近会议区域

**九、系统管理（11 项）** — 90-100 包含数据持久化、文件持久化、全局错误处理、骨架屏、暗色模式、移动端适配、配置管理、数据备份、docker-compose.dev、CI/CD、极简前端重构

**十、页面建设（7 项）** — 101-107 包含 Dashboard、文档库、独立对话页、对话历史、协作页、设置页、登录注册页

| 优先级 | 数量 |
|--------|------|
| ⭐⭐⭐ 紧急 | 15 项 |
| ⭐⭐ 重要 | 60 项 |
| ⭐ 可以等 | 32 项 |

## 许可证

MIT License
