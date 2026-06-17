# 移动端 26 commits 全面修复（2026-06-18）

## 背景

2026-06-13 收官的"移动端 PR #1-#10"实际上有 10+ 个隐藏 bug，但因为服务器 6/15 13:52 之后没成功 deploy，**用户从来没机会看到移动端 UI**，bug 被延后到 6/17-6/18 才发现。

## 修复链（按时间顺序）

### Commit 1-2：图标 import 缺失 + 路由 mobile 路径错（08:23-08:34 UTC）
- `0e11009` **fix(mobile): MainLayout 缺 Fold/Expand** — `MainLayout.vue:184` 缺 `@element-plus/icons-vue` 的 `Fold`/`Expand` import，导致 `el-icon` 容器套 `.collapse-btn-mobile` 样式（background + color）显示成红色方块
- `025424ca` **fix(router): 8 条 mobile 路径错** — `router/index.js` 14 条 mobile 路由中 8 条假设组件在子目录（`knowledge/MobileKnowledgeView`），但实际在 `views/mobile/` 根目录。`resolveMobile.js` 找不到 → console 警告"未找到组件"

### Commit 3-5：后端 4 个移动端端点缺失（08:50 UTC）
- `d671c41c` **fix(api): 补 4 个移动端端点** — 移动端用了简化路径（`/formula`/`/hypothesis`/`/memory`/`/dashboard/summary`），但后端只实现了嵌套路径（`/knowledge/formulas` 等）
- `5f5bfd06` **fix(api): /memory ORM 序列化** — `list_memories` 返回 SQLAlchemy ORM 对象，FastAPI `jsonable_encoder` 报 "cannot convert dict" → 用 `MemoryResponse.model_validate().model_dump()` 转换

### Commit 6：TabBar 覆盖输入框（11:30 UTC）
- `7131ad4b` **fix(mobile): /chat 路由隐藏 TabBar** — `MobileInputBar` z-index 100 vs `TabBar` z-index 2500，两者都 `position: fixed; bottom: 0;` 完全重叠。**同时**修 v-model 命名错配（commit 6/15 教训 #5）

### Commit 7-8：resume + 路由 query（12:40 UTC）
- `fc27af59` **fix(mobile): 修重复 const router=useRouter() 导致 build 失败** — 连续 2 个 commit build 失败（4b0ba7b8 修 import 重 + fc27af59 修 const 重），每次都是 `duplicate identifier` 错误。**build 失败但 commit 仍然成功**（npm run build exit code 非 0 没被 git commit 检测到）
- `fc27af59` 内容：MobileMeetingView onMounted 读 `route.query.resume` → `router.replace('/meetings/room')`（MobileMeetingRoom 已有从 useRecordingState 恢复 meetingId 的逻辑 line 200-203）

### Commit 9-10：v-model:show 命名错配（CLAUDE.md 教训 #5 重复踩坑 11 处）
- `6b4f57d0` 修 1 处：MobileSessionDrawer
- `20df60db` 修 4 处：MobileKnowledgeView (2x) + MobileSettingsView + MobileMemberView
- `607e7b06` 批量 sed 修 8 处：MobileSettingsView (3x) + MobileMemberView + MobileTaskView (2x) + MobileVoiceprintView

### Commit 11：TabBar 恢复 + input 浮在 TabBar 上方（12:00 UTC）
- `c94d0603` 用户偏好 persistent nav（iMessage 风格全屏 chat 不符合用户偏好），恢复 TabBar + input bar `bottom: var(--tabbar-height)` + z-index 1100 + `messagesPaddingBottom` 加 56px

### Commit 12：ASR 500 + passive event listener（15:35 UTC）
- `3cd88d4a` **fix(ASR+passive)**:
  - ASR 500 真实根因：用户录音 110 字节（MediaRecorder 录几毫秒 / swipe cancel），whisper 容器 ffmpeg 转 110 字节 webm 失败（"EBML header parsing failed"）
  - **修客户端**：`useChatStream.ts:587-595` `blob.size < 1024` 提示"录音太短"，不发请求
  - **修服务端**：`app/api/v1/voice.py:55-65` `len(audio_data) < 1024` 返 400 + 友好错误
  - **修 passive patch**：`main.js:3-15` 之前强制 `wheel/mousewheel/touchstart/touchmove` 都为 passive，**误伤** mobile voice button `@touchstart.prevent` 和 Element Plus 内部 `preventDefault` 调用。改为只对 `wheel/mousewheel` 强制

### Commit 13：知识 3 action 接通后端（15:40 UTC）
- `33608c9c` 之前 `onCreateAction` 全是 `ElMessage.info('...开发中')` 占位。接通后端真实端点：
  - **手动添加**：MobileFormSheet (title/content/category) → `POST /api/v1/knowledge`
  - **上传文件**：file input → `POST /api/v1/knowledge/upload`
  - **AI 研究**：MobileFormSheet (topic) → `POST /api/v1/knowledge/research`

### Commit 14：MemberAvatar 组件 + 头像同步（15:45 UTC）
- `33608c9c` 新建 `web/src/components/mobile/MemberAvatar.vue`（接受 memberId + size，从 `memberStore.getMemberAvatar(id)` 查 URL，缺 avatar 时显示首字母 + 背景色 hash 选色，与桌面 `getAvatarColor` 逻辑一致）
- `CardList.vue` 加 `avatarField` prop（function returning memberId）
- 集成到 3 个 View：
  - `MobileTaskView` 任务分配人头像：`avatarField: (t) => t.assignee_id`
  - `MobileMemberView` 成员头像：`avatarField: (m) => m.id`
  - `MobileSettingsView` 用户头像：直接用 `<MemberAvatar :member-id="userInfo?.id" :size="72" />`

## 12 条铁律

### 铁律 1：v-model 命名必须严格匹配 prop 名（CLAUDE.md 6/15 教训 #5 升级版）
- `v-model` ↔ prop `modelValue` + emit `update:modelValue`（默认）
- `v-model:foo` ↔ prop `foo` + emit `update:foo`（命名）
- **11 处踩坑**（commit 6/4d57d0 + 20df60db + 607e7b06 都为同一模式），都是 `v-model:show="X"` 但组件 prop 是 `modelValue`
- **症状**：`v-if="modelValue"` 永远 false → 组件静默不显示，"点击无反应"无 console 错误
- **修复模式**：批量 `sed 's/v-model:show=/v-model=/g' web/src/views/mobile/`
- **预防**：新增 mobile sheet/dialog 组件时，调用方必须先看 defineProps/defineEmits 决定 v-model 形式

### 铁律 2：useRecordingState + 路由 query 必须双向打通
- 之前 6/17 webhook 失败是因为 `MobileMeetingView.onMounted` 没读 `route.query.resume`（同路由 query 变化不重渲 → 用户看到"点击无反应"）
- **所有浮动胶囊/全局指示器跳转的目标 View 都必须在 onMounted 处理 query**：
  ```js
  onMounted(() => {
    if (route.query.X) router.replace('/path/...')
  })
  ```
- **或者用 `watch(() => route.query.X)`** 监听变化（处理重复点击同一 query）

### 铁律 3：build 失败必须停止 commit（不能再 commit 错代码）
- `4b0ba7b8` + `fc27af59` 连续 2 个 commit build 失败（duplicate const router 错误），**但都 commit 成功**（npm run build 退出码非 0 没被 git commit 检测到）
- **修复**：pre-commit hook 加 `npm run build` 检查（未来 PR）
- **临时方案**：commit message 末尾加 `[build-pending]` 标记，下次跑 build 时优先回滚

### 铁律 4：Z-index 冲突用 UX 解决，不要 z-index arms race
- `TabBar` (2500) vs `MobileInputBar` (100) → 第一次解决是 `/chat` 隐藏 TabBar
- 用户测试后反馈"覆盖导航栏" → 改方案：恢复 TabBar + MobileInputBar `bottom: var(--tabbar-height)` 浮在 TabBar 上方
- **不靠 z-index 数字互相比**（2500+1+1+1...），靠布局（一个 fixed 在另一个 fixed 上面）

### 铁律 5：ASR/上传类端点必须在服务端做 size guard
- 用户上传 110 字节 webm → ffmpeg 失败 → 500 误导用户"识别失败"
- **前后端都要 guard**：
  - 前端 `blob.size < MIN_SIZE` → toast 提示，不发请求
  - 后端 `len(audio_data) < MIN_SIZE` → 400 + 友好 detail
- **MIN_SIZE 标准**：
  - 录音：1KB（≈ 0.1s 16kHz mono PCM）— 1 秒以上才能识别
  - 上传文件：根据业务（10MB / 50MB / 100MB）
- **错误信息必须明确**："录音太短（N 字节），请长按说话至少 1 秒" 比 "识别失败: ffmpeg exit 1" 有用

### 铁律 6：passive event listener 全局 patch 必须最小化
- 之前 `main.js` 强制 `wheel/mousewheel/touchstart/touchmove` 4 个事件为 passive
- Element Plus popover/dialog 内部某些 handler 调 `preventDefault` 但没显式 `passive:false` → patch 强制 `passive:true` → `preventDefault` 失效 → "Unable to preventDefault inside passive" 警告
- 同样：mobile 组件 `@touchstart.prevent='...'` 也失效
- **修复**：只对 `wheel/mousewheel` 强制（Chrome 滚轮性能警告的真正根因）
- **预防**：任何 monkey patch 改默认行为要 list 所有可能受影响的库 + 留出 opt-out 机制

### 铁律 7：新建 mobile 组件先 grep 桌面端孪生
- 移动端多数组件有桌面端孪生（VoiceTestFlow、MeetingCreateDialog 等）
- **修改前必看桌面端实现** — 不要凭想象造 mobile 专用版本
- 桌面端已有 dialog/menu 改 `isMobile` 检测（line 4 `:width="isMobile ? '95vw' : '750px'"`）就够复用

### 铁律 8：占用 toast 占位是反模式
- 之前 `onCreateAction` 三个分支全 `ElMessage.info('...开发中')` — 看起来"动了一下"但用户啥都不能做
- **修复模式**：要么真正接通后端，要么用 disable 灰按钮 + tooltip"该功能在桌面端可用"
- **永远不要"假装工作"** — 用户信任会丢失

### 铁律 9：头像/卡片组件必须跨端复用
- 桌面 `MemberView` line 67-71 有完整 `el-avatar` 渲染 + 字母 fallback
- 移动端没复用，导致"除了右上角其他都不显示头像"
- **修复**：新建 `MemberAvatar.vue` 移动版（接受 memberId，从 store 查），桌面已有逻辑移植
- **不要每个 View 重复写 el-avatar 模板**

### 铁律 10：route component 假设的子目录要 grep 验证
- `router/index.js` 写 `path: 'knowledge/MobileKnowledgeView'` 假设子目录
- 但 `find web/src/views/mobile` 显示实际是 `views/mobile/MobileKnowledgeView.vue`（根）
- **预防**：router 写完后跑 `find web/src/views/mobile` 验证路径 + bundle 检查"未找到组件" 警告

### 铁律 11：webhook deploy 失败 = 先看 /var/log/webhook-deploy.log
- 6/17 22:46 / 22:53 两次 webhook 失败，根因是 server-side GitHub Deploy key 失效
- GitHub UI 显示 "✓ Delivered" 但 server code 没动 = webhook service 返 200 + 后台 deploy 线程失败
- **永远不要纯靠 GitHub UI 判断 deploy 成功** — 服务器 SSH 看 log + git log + dist Last-Modified
- 详见 `memory/docker-desktop-fix-2026-06-17.md` 5 条铁律

### 铁律 12：v-model 重命名（`:show` → ``）触发 4 处 silent failure
- 每次修改 v-model 绑定后必须 hard refresh 浏览器（SW cache 会保留旧版本）
- 浏览器可能还在用旧 JS（即使 server dist 已更新），点击没反应会误判为"修复失败"
- **预防**：PR 描述里写 "请 hard refresh 后再测试"

## 测试

- 端到端手动测试：登录 → /chat（看 TabBar + 输入框）→ 点菜单（session drawer 弹出）→ 发文字 → 录 1s+ 语音（ASR 成功）→ /knowledge 加号（3 action 都通）→ /members 看头像 → /tasks 看分配人头像 → /settings 改密码/资料/通知（3 Sheet 弹出）
- 自动化测试：未来需补 `useChatStream.test.js` 加 v-model 命名检查 + `useRecordingState.test.js` 加 resume 路由测试

## 文件清单

新增/修改文件（按 commit 顺序）：
1. `web/src/layouts/MainLayout.vue` — Fold/Expand import
2. `web/src/router/index.js` — 8 mobile 路径
3. `app/api/v1/dashboard.py` — 5 新端点（summary/formula/hypothesis/memory）
4. `app/main.py` — mobile_router 引入
5. `web/src/views/mobile/chat/MobileChatView.vue` — v-model 修
6. `web/src/views/mobile/chat/MobileInputBar.vue` — bottom + z-index
7. `web/src/composables/chat/useKeyboardInset.ts` — messagesPaddingBottom +tabbar-height
8. `web/src/views/mobile/meeting/MobileMeetingView.vue` — onMounted resume
9. `web/src/views/mobile/chat/MobileSessionDrawer.vue` — 无（之前就对）
10. `web/src/views/mobile/MobileKnowledgeView.vue` — 2x v-model + 3 action 真实接通
11. `web/src/views/mobile/MobileSettingsView.vue` — 3x v-model + MemberAvatar
12. `web/src/views/mobile/MobileMemberView.vue` — v-model + avatarField
13. `web/src/views/mobile/MobileTaskView.vue` — v-model + avatarField
14. `web/src/views/mobile/MobileVoiceprintView.vue` — v-model
15. `web/src/composables/chat/useChatStream.ts` — blob<1KB guard
16. `web/src/main.js` — passive patch 收窄
17. `app/api/v1/voice.py` — audio size<1KB → 400
18. `web/src/components/mobile/MemberAvatar.vue` — **新建**
19. `web/src/components/mobile/CardList.vue` — avatarField prop

## 统计

- commit 数：1058 → 1084（+26）
- 总行数：156,021 → 156,809（+788）
- 文件数：630（不变）
- dev_days：33
