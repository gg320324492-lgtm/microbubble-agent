---
name: v77-p26-f-2-meeting-view-split
description: v77 P2.6-F.2 MeetingView 1088 → 359 行拆分（5 commits: dead code + MinutesDialog + TemplateDialog + 听会全屏化 + style 拆出）+ 19 Vitest 单测 + 听会 UX 弹窗→全屏
metadata:
  node_type: memory
  type: project
  originSessionId: 3ab844b8-7e6c-4ece-93b5-3ffbfe9fb68e
---

# v77 P2.6-F.2 MeetingView 1088 → 359 行拆分

**时间**：2026-06-28（约 3.5h 实施 + docs）
**commits**：`298ed5c5` (Step 1) + `f2eb8cfc` (Step 2) + `a3663d04` (Step 3) + `e5ba60e2` (Step 4) + docs commit
**状态**：✅ 全部已 push origin/main
**沉淀**：本文件 + [CHANGELOG.md](../../../../microbubble-agent/CHANGELOG.md) v77 P2.6-F.2 章节 + ROADMAP.md 更新

## Context

v77 P2.6-A/B/C/D/E/F.1（11 commits）完成视觉/代码质量延伸后，MeetingView 1088 行仍是会议系统最大单文件，4 个 el-dialog + 录音状态机 + 模板 CRUD 全部内嵌。本次 v77 P2.6-F.2 按用户决策做"主 View + 子组件 + CSS 独立"拆分，并优化听会 UX（弹窗 → 全屏）。

**用户决策（4 项）**：
1. 新建 Vitest 单测（推荐）—— TDZ 风险高
2. **听会入口 UI 改全屏**（修正原"听会入口不动"决策，UI 可以优化）
3. **style 块拆到独立 meeting-view.css**（彻底方案，484 行 CSS 独立管理）
4. 深度多轮验证 —— 8 轮验证（编译/grep/端到端/dark mode/Playwright/手测清单）

## 拆分步骤总览（5 commits）

| Step | Commit | 主题 | MeetingView 行数变化 | 风险 |
|---|---|---|---|---|
| 1 | `298ed5c5` | dead code 清理 | 1088 → 1028 (-60) | 低 |
| 2 | `f2eb8cfc` | 抽 MeetingMinutesDialog | 1028 → 1007 (-21) | 低 |
| 3 | `a3663d04` | 抽 MeetingTemplateDialog + TDZ | 1007 → 882 (-125) | **中（TDZ）** |
| 4 | `e5ba60e2` | 听会 UI 全屏化 + style 拆出 | 882 → **359** (-523) | 中 |
| 5 | (docs) | CHANGELOG/ROADMAP/memory | — | 低 |

## Step 1：dead code 清理 (-60 行)

**删除清单**（grep 验证 0 外部引用）：
- `nextTick` / `watch` import / `useUserStore` + 解构 / 5 个未用 icons (Phone/Edit/MagicStick/Clock/List)
- `showTranscriptDialog` / `liveTranscriptRef` refs / `builtinTemplates` / `customTemplates` computed
- `applyTemplate` / `viewMinutes` / `startTranscript` / `onTranscriptComplete` / `generateMinutes` 函数

**保留清单**（MeetingCreateDialog 通过 props 依赖）：
- `templates` ref → 传给 `:templates`
- `editingMeetingId` ref → 传给 `:editing-id`
- `editingMeetingData` computed → 传给 `:editing-data`

## Step 2：MeetingMinutesDialog 子组件（86 行 + 7 测试）

**v-model bridge 模式**（KnowledgeCreateDialog line 96-100）：
```js
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})
```

**测试模式**：参考 MeetingCreateDialog.test.js —— 不注册 el-* 组件，只测脚本逻辑。jsdom + el-dialog 渲染问题通过不挂载 el-* 子组件规避。

## Step 3：MeetingTemplateDialog 子组件 + TDZ 防御（180 行 + 12 测试）

**★ TDZ 防御（commit 7f0ac109 教训第 1 次复用）**：

```js
// ★ 必须 function declaration 而非 const arrow
function resetForm() {
  form.value = defaultForm()
}

// watch(immediate: true) 同步触发调用 resetForm
watch(() => props.editingTemplate, (val) => {
  if (val) form.value = { ...val, agenda: [...(val.agenda || [])] }
  else resetForm()
}, { immediate: true })
```

**为什么 TDZ 会触发**：
- `watch(immediate: true)` 在 setup 阶段**同步**调用回调
- 如果 `resetForm` 用 `const arrow = () => {...}` 定义在 watch **之后**
- 同步调用时 resetForm 还未绑定（const 在 TDZ） → `Cannot access 'resetForm' before initialization`
- function declaration 可 hoist，不受影响

**12 个测试覆盖**：TDZ 防御核心 + watch 回填 + submit POST/PUT + emit + resetForm + 网络失败处理。

## Step 4：听会 UI 全屏化 + style 拆出 (-729 行 + 498 CSS)

### 4.1 听会 dialog 删除 + UX 全屏化

**删除**：
- 听会 `el-dialog` 模板 + `MeetingRoom` import + `meetingRoomRef`
- `showLiveCallDialog` / `liveCallMeeting` refs
- `onCallEnded` / `onLiveCallEnd` / `startLiveCall` 函数
- `useGlobalRecorder` 解构

**新增**：
```js
const handleStartLiveCall = () => {
  router.replace('/meetings/room')
}
```

**保留**：
- `resumeRecording` — ?resume=X 跳全屏（MainLayout 浮动胶囊）
- `checkActiveRecording` (onMounted) — 浮动胶囊恢复逻辑
- `useRecordingState.startRecording/stopRecording` — onMounted 用

### 4.2 MeetingRoomView 自动建会（关键证据）

[MeetingRoomView.vue:124-140](web/src/views/MeetingRoomView.vue#L124-L140)：
```js
async function onRecordingStart() {
  if (meetingId.value) {
    startRecording(meetingId.value, ...)
    return  // 恢复模式
  }
  // 新建模式：调用后端 start-recording 自动创建会议
  const res = await axios.post('/api/v1/meetings/start-recording')
  meetingId.value = res.data.id
  startRecording(res.data.id, ...)
}
```

→ MeetingRoomView **已支持**"无 meetingId 直接录音"，无需后端改动。

### 4.3 style 拆到独立 meeting-view.css

**坑 1：路径写错**
- 错误：`import './meeting-view.css'`（找不到）
- 修复：`import './meeting/meeting-view.css'`

**坑 2：`:deep()` 是 Vue scoped PostCSS 语法**
- scoped `<style>` 编译时 PostCSS 插件把 `:deep(.el-card__body)` 转成 `.el-card__body[data-v-xxx]`
- 全局 css 文件**没有 PostCSS 处理**，stylelint parse 失败
- 修复：sed 全局替换 ` :deep(\(...\))` → ` (...\)`

**坑 3：注释里 `<style scoped>` 字面文本让 stylelint 误判**
- stylelint 看到 `<style` 字面后开始尝试 parse CSS
- 修复：注释里 `<style scoped>` → `scoped style block`

## 5 条新铁律（CLAUDE.md 已沉淀）

1. **v-model bridge 模式可复用**：computed { get, set } 桥接 modelValue prop 是 Vue 3 子组件 dialog 的标准模式
2. **TDZ 防御必须 function declaration**：watch(immediate: true) + resetForm 永远不能 const arrow
3. **scoped CSS → 全局 CSS 时必须验证类名 unique**：grep 全项目确认类名不重名
4. **props 依赖的死代码必须先 grep 验证**：MeetingCreateDialog 通过 `:editing-id`/`:editing-data`/`:templates` 引用父 state
5. **桌面/移动 UX 必须对齐**：录音机这种"长连接 + 后台处理"场景，弹窗 UX 关闭后状态丢失

## Round 1 验证全 PASS

- `npm run build 0 警告`
- `npx stylelint 'src/**/*.{vue,css,scss}' 0 errors`
- `npx vitest run 23 files / 415 tests passed`

## 行数核算（最终）

| 阶段 | MeetingView.vue | 子组件 | CSS | 总代码 |
|---|---|---|---|---|
| 拆前 | 1088 | 0 (MeetingCreateDialog 332 不变) | 0 | 1088 |
| Step 1 dead code | 1028 | 0 | 0 | 1028 (-60) |
| Step 2 MinutesDialog | 1007 | +86 + 7 测试 | 0 | 1090 (+62) |
| Step 3 TemplateDialog | 882 | +180 + 12 测试 | 0 | 1450 (+360) |
| Step 4 style 拆 + 全屏化 | **359** | +0 (保留) | +498 | 1457 (+7) |
| **净变化** | **-729 (-67%)** | **+266 + 19 测试** | **+498** | **+369 (+34%)** |

## 不在本次范围（CLAUDE.md "不在本次范围"）

- agentic_loop.py 1123 行拆分（后端核心模块）
- MeetingView.vue 484 行 dark mode 适配（v77 P2.6-A/B 已完成大部分）
- 后端 alembic 033 / agent_traces 清理
- Web Push / Periodic Background Sync

## commit 链

```
1. 298ed5c5 refactor(meeting): v77 P2.6-F.2 MeetingView 死代码清理 (-60 行)
2. f2eb8cfc refactor(meeting): v77 P2.6-F.2 抽 MeetingMinutesDialog 子组件 (-21 + 86 + 7 测试)
3. a3663d04 refactor(meeting): v77 P2.6-F.2 抽 MeetingTemplateDialog 子组件 + TDZ 防御 (-125 + 180 + 12 测试)
4. e5ba60e2 refactor(meeting): v77 P2.6-F.2 听会 UI 全屏化 + style 拆到独立 meeting-view.css (-729 + 498)
5. (docs) 更新项目动态 (CHANGELOG + CLAUDE + ROADMAP + memory)
```

## 相关链接

- [CHANGELOG.md](../../../../microbubble-agent/CHANGELOG.md) v77 P2.6-F.2 章节
- [ROADMAP.md](../../../../microbubble-agent/ROADMAP.md) 当前状态 F.2 行
- 计划文件：[C:\Users\pc\.claude\plans\v77-p2-75-rustling-avalanche.md](C:/Users/pc/.claude/plans/v77-p2-75-rustling-avalanche.md)
- 前置：[memory/v77-p26-d-swng-anim-css-baseline.md](v77-p26-d-swng-anim-css-baseline.md)
- 前置：[memory/v77-p26-e-and-f-visual-quality.md](v77-p26-e-and-f-visual-quality.md)
- CLAUDE.md 752 行铁律（volume 挂载只换文件不换模块缓存，app + celery-worker restart）
- CLAUDE.md PowerShell UTF-8 BOM 教训（v77 P2.6-D 踩过）→ Node.js 脚本无 BOM 替代