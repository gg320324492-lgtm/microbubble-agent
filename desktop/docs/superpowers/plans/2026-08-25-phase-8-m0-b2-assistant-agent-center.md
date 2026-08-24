# Phase 8-M0-B2 科研助手与 AI 研究团队实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `superpowers:subagent-driven-development` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 以真实 Agent Store 数据升级科研助手与 Agent Center，提供可观察、可访问且不伪造数据的科学 AI 工作台。

**架构：** `Assistant.vue` 是由 Agent Store 会话、消息、事件、证据和引用组成的三栏对话中枢；每条 AI 消息把真实正文置于默认展开的结论分区，其余分区显式以当前会话数据或空态呈现。`AgentCenter.vue` 用两个 props-only 展示组件呈现固定角色、真实事件、证据和工具调用；没有角色标识、队列或耗时数据时，显示中文未知状态而非推断值。

**技术栈：** Vue 3 `<script setup lang="ts">`、Pinia（仅页面）、Vitest、M0-A/B1 研究令牌和 `ResearchState`。

---

## 审计结论

- `useAgentStore()` 已提供 `sessions`、`activeSession`、`messages`、`events`、`citations`、`evidence`、`isLoading`、`isSending`，以及 `loadSessions`、`selectSession`、`sendMessage`、`runResearch`。
- `AgentEvent` 只有 `type`、`label`、`detail`、`timestamp`、`status`；没有 role、queue、duration 或 tool ID。禁止根据事件类型猜测智能体身份。
- `ToolCallResult` 只有 `name`、`status`、`result`、`error`；工具耗时、Agent 和阶段必须保留为未知显示。
- B1 已提供 `ResearchMetricPanel`、`ResearchTimeline`、`AgentStatusPanel`、`EvidencePanel`。这些组件均为 props-only，B2 只添加对应的视图模型转换。

## 文件结构

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `src/renderer/src/components/research/AgentWorkspaceCard.vue` | 创建 | 固定角色的 props-only 工作区卡片；真实值缺失时显示「待接入数据」。 |
| `src/renderer/src/components/research/ToolExecutionPanel.vue` | 创建 | props-only 工具执行记录面板；显示真实工具名、状态、输出和未知字段。 |
| `src/renderer/src/pages/research/Assistant.vue` | 修改 | 三栏科学对话中枢、五个 `details/summary` 回复分区和现有 Store 重试链路。 |
| `src/renderer/src/pages/research/AgentCenter.vue` | 修改 | 可观察研究团队、固定角色卡、真实指标、时间线、证据和工具历史。 |
| `tests/unit/phase-8-m0-b2-assistant-agent-center.dom.test.ts` | 创建 | 220 条 B2 UI 契约，含 props、真实数据边界、中文、a11y、motion 与响应式。 |
| `tests/unit/research-workflow.test.ts` | 修改（仅在旧契约失效时） | 将旧的 Agent Center 角色与虚构工具字段断言迁移到 B2 真实数据语义。 |
| `tests/unit/research-pages.dom.test.ts` | 修改（仅在旧 DOM 契约失效时） | 将页面挂载与布局期望迁移为 B2 结构，不降低现有覆盖。 |

用户要求最终只创建一个实现提交：`Phase 8-M0-B2 Scientific Research OS Assistant Agent Center Upgrade`。实现任务不创建中间提交；设计规格提交 `702d46bf6` 是该计划的起点。

### 任务 1：建立 B2 契约测试基线

**文件：**
- 创建：`desktop/tests/unit/phase-8-m0-b2-assistant-agent-center.dom.test.ts`
- 读取：`desktop/src/renderer/src/pages/research/Assistant.vue`
- 读取：`desktop/src/renderer/src/pages/research/AgentCenter.vue`

- [ ] **步骤 1：编写 220 条失败的 B2 契约**

```ts
describe('Phase 8-M0-B2 科研助手与 AI 研究团队', () => {
  it.each(['结论', '证据', '推理摘要', '引用', '下一步行动'])(
    'Assistant 包含可访问回应分区：%s',
    label => expect(withoutComments(assistantSource)).toContain(label)
  )

  it('Assistant 结论默认展开', () => {
    expect(withoutComments(assistantSource)).toMatch(/<details\s+open[\s\S]*?<summary[^>]*>\s*结论/)
  })

  it.each(['文献智能体', '实验智能体', '分析智能体', '写作智能体', '审稿智能体'])(
    'Agent Center 固定角色：%s',
    role => expect(withoutComments(agentCenterSource)).toContain(role)
  )

  it.each(['AgentWorkspaceCard.vue', 'ToolExecutionPanel.vue'])(
    '%s 不导入 Store 或 Service',
    file => expect(readComponent(file)).not.toMatch(/from\s+['"][^'"]*(stores|services)[^'"]*['"]/)
  )
})
```

覆盖分配：65 条 Assistant、55 条 Agent Center、50 条共享组件、30 条可访问性/动画/1440/1920、20 条反伪造数据。所有源代码断言先用 `withoutComments()` 去掉注释，计数 guard 明确为 `>= 150`。

- [ ] **步骤 2：运行并确认红灯**

运行：`npm run test:unit -- phase-8-m0-b2-assistant-agent-center.dom.test.ts`

预期：FAIL；因为两个组件尚不存在，且两个页面尚无 B2 标签、`details`、新共享组件与真实数据边界。

### 任务 2：实现 `AgentWorkspaceCard`

**文件：**
- 创建：`desktop/src/renderer/src/components/research/AgentWorkspaceCard.vue`
- 测试：`desktop/tests/unit/phase-8-m0-b2-assistant-agent-center.dom.test.ts`

- [ ] **步骤 1：保留失败的 props 与未知状态断言**

```ts
expect(cardSource).toContain('name: string')
expect(cardSource).toContain('role: string')
expect(cardSource).toContain('dataAvailable?: boolean')
expect(cardSource).toContain('待接入数据')
expect(cardSource).not.toMatch(/from\s+['"][^'"]*(stores|services)[^'"]*['"]/)
```

- [ ] **步骤 2：实现最小 props-only 卡片**

```vue
<script lang="ts">
export type AgentWorkspaceStatus = 'pending' | 'running' | 'completed' | 'error'
export interface AgentWorkspaceCardData {
  name: string
  role: string
  status?: AgentWorkspaceStatus
  currentTask?: string
  queue?: string | number
  dataAvailable?: boolean
}
</script>

<script setup lang="ts">
const props = withDefaults(defineProps<AgentWorkspaceCardData>(), {
  dataAvailable: false
})
</script>

<template>
  <article class="agent-workspace-card" :aria-label="`${props.name}工作状态`">
    <h3>{{ props.name }}</h3><p>{{ props.role }}</p>
    <p v-if="!props.dataAvailable" role="status">待接入数据</p>
    <dl v-else>
      <div><dt>状态</dt><dd>{{ props.status ?? '待接入数据' }}</dd></div>
      <div><dt>当前任务</dt><dd>{{ props.currentTask ?? '待接入数据' }}</dd></div>
      <div><dt>队列</dt><dd>{{ props.queue ?? '待接入数据' }}</dd></div>
    </dl>
  </article>
</template>
```

添加 `min-width: 0`、安全换行、`focus-visible`（若未来卡片可交互）和 `prefers-reduced-motion` 下无运行脉冲的令牌化样式。未知状态不得使用 `idle`、`0` 或推断任务。

- [ ] **步骤 3：运行契约确认转绿**

运行：`npm run test:unit -- phase-8-m0-b2-assistant-agent-center.dom.test.ts`

预期：组件 props、中文未知状态、无 Store/Service import 相关测试 PASS；页面集成测试仍可能失败。

### 任务 3：实现 `ToolExecutionPanel`

**文件：**
- 创建：`desktop/src/renderer/src/components/research/ToolExecutionPanel.vue`
- 测试：`desktop/tests/unit/phase-8-m0-b2-assistant-agent-center.dom.test.ts`

- [ ] **步骤 1：保留失败的执行记录契约**

```ts
expect(panelSource).toContain('executions?: ToolExecutionItem[]')
expect(panelSource).toContain('Agent')
expect(panelSource).toContain('工具')
expect(panelSource).toContain('阶段')
expect(panelSource).toContain('暂无耗时数据')
expect(panelSource).toContain('输出')
```

- [ ] **步骤 2：实现最小 props-only 面板**

```vue
<script lang="ts">
export interface ToolExecutionItem {
  id: string | number
  agent?: string
  tool: string
  stage?: string
  duration?: string
  status: 'running' | 'completed' | 'error'
  output?: string
}
</script>

<script setup lang="ts">
const props = withDefaults(defineProps<{ executions?: ToolExecutionItem[]; ariaLabel?: string }>(), {
  executions: () => [], ariaLabel: '工具执行历史'
})
</script>

<template>
  <section class="tool-execution-panel" :aria-label="props.ariaLabel">
    <h2>工具执行历史</h2>
    <p v-if="!props.executions.length" role="status">暂无工具执行记录</p>
    <article v-for="item in props.executions" :key="item.id">
      <dl><div><dt>Agent</dt><dd>{{ item.agent ?? '待接入数据' }}</dd></div>
      <div><dt>工具</dt><dd>{{ item.tool }}</dd></div>
      <div><dt>阶段</dt><dd>{{ item.stage ?? '待接入数据' }}</dd></div>
      <div><dt>耗时</dt><dd>{{ item.duration ?? '暂无耗时数据' }}</dd></div>
      <div><dt>状态</dt><dd>{{ item.status }}</dd></div>
      <div><dt>输出</dt><dd>{{ item.output ?? '暂无工具输出' }}</dd></div></dl>
    </article>
  </section>
</template>
```

使用中文状态标签、`role="status"`、M0-A 令牌、长输出安全换行与 reduced-motion 规则。不得计算耗时或为 Agent、stage 填充虚构值。

- [ ] **步骤 3：运行契约确认转绿**

运行：`npm run test:unit -- phase-8-m0-b2-assistant-agent-center.dom.test.ts`

预期：两个共享组件所有 props、空态、无 Store/Service import 与可访问性契约 PASS。

### 任务 4：升级 Assistant 对话中枢

**文件：**
- 修改：`desktop/src/renderer/src/pages/research/Assistant.vue`
- 测试：`desktop/tests/unit/phase-8-m0-b2-assistant-agent-center.dom.test.ts`
- 读取：`desktop/src/renderer/src/stores/research/agent.store.ts`

- [ ] **步骤 1：保留失败的 Assistant 集成契约**

```ts
expect(withoutComments(assistantSource)).toContain('ResearchTimeline')
expect(withoutComments(assistantSource)).toContain('AgentStatusPanel')
expect(withoutComments(assistantSource)).toContain('EvidencePanel')
expect(withoutComments(assistantSource)).toContain('ToolExecutionPanel')
expect(withoutComments(assistantSource)).toMatch(/<details\s+open[\s\S]*?<summary[^>]*>\s*结论/)
expect(withoutComments(assistantSource)).not.toMatch(/useProjectStore|projectStore/)
```

- [ ] **步骤 2：派生真实视图模型**

在 `<script setup>` 中只保留 `useAgentStore()`：

```ts
const sessionEvidence = computed<EvidencePanelItem[]>(() => agentStore.evidence.map(item => ({
  label: item.label, value: item.value, source: item.source, confidence: item.confidence
})))
const sessionCitations = computed<CitationPanelItem[]>(() => agentStore.citations.map(item => ({
  id: item.id, title: item.title, authors: item.authors, year: item.year, source: item.journal
})))
const eventTimeline = computed<ResearchTimelineItem[]>(() => agentStore.events.map(event => ({
  id: `${event.timestamp}-${event.type}`, title: eventLabel(event), description: event.detail,
  timestamp: new Date(event.timestamp).toISOString(), status: event.status
})))
const toolExecutions = (message: AgentMessage): ToolExecutionItem[] => (message.toolCalls ?? []).map((tool, index) => ({
  id: `${message.id}-${index}`, tool: tool.name, status: tool.status, output: tool.result ?? tool.error
}))
```

`AgentStatusPanel` 只接收标签或消息正文精确包含五个角色中文名称的事件数据；默认传空数组。不得从 `AgentEvent.type` 推断角色、不得制造 stage、duration、queue 或 citation。

- [ ] **步骤 3：替换模板为三栏对话中枢**

保留会话选择、发送、加载和重试函数。加入上下文栏（当前会话、研究模式、AI 状态），然后对每个 assistant 消息使用：

```vue
<details class="assistant__response-section" open>
  <summary>结论<span>默认展开</span></summary>
  <p>{{ message.content }}</p>
</details>
<details class="assistant__response-section"><summary>证据</summary><EvidencePanel :evidence="sessionEvidence" :citations="[]" aria-label="当前会话证据" /></details>
<details class="assistant__response-section"><summary>推理摘要</summary><ResearchTimeline :items="eventTimeline" aria-label="当前会话推理摘要" /></details>
<details class="assistant__response-section"><summary>引用</summary><EvidencePanel :evidence="[]" :citations="sessionCitations" aria-label="当前会话引用" /></details>
<details class="assistant__response-section"><summary>下一步行动</summary><ToolExecutionPanel :executions="toolExecutions(message)" aria-label="当前消息工具执行" /></details>
```

右栏保留一个会话级 `EvidencePanel`；中栏使用 `ResearchTimeline`、`AgentStatusPanel` 和 `ToolExecutionPanel`。所有会话级内容标明「当前会话」，不暗示专属消息关系。

- [ ] **步骤 4：添加桌面与无障碍 CSS**

```css
.assistant { grid-template-columns: minmax(210px, 236px) minmax(0, 1fr) minmax(260px, 320px); min-width: 0; overflow-x: clip; }
.assistant__response-section { min-width: 0; }
.assistant__response-section summary:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
@media (max-width: 1480px) { .assistant { grid-template-columns: minmax(190px, 220px) minmax(0, 1fr) minmax(230px, 270px); } }
@media (min-width: 1720px) { .assistant { grid-template-columns: minmax(230px, 270px) minmax(0, 1fr) minmax(300px, 350px); } }
@media (prefers-reduced-motion: reduce) { .assistant * { scroll-behavior: auto; } }
```

- [ ] **步骤 5：运行 Assistant 契约确认转绿**

运行：`npm run test:unit -- phase-8-m0-b2-assistant-agent-center.dom.test.ts`

预期：Assistant 的中文分区、默认结论、`details/summary`、四个 B1/B2 组件、Store 限制、加载/空/错误/重试和响应式契约 PASS。

### 任务 5：升级可观察 Agent Center

**文件：**
- 修改：`desktop/src/renderer/src/pages/research/AgentCenter.vue`
- 测试：`desktop/tests/unit/phase-8-m0-b2-assistant-agent-center.dom.test.ts`
- 可能修改：`desktop/tests/unit/research-workflow.test.ts`
- 可能修改：`desktop/tests/unit/research-pages.dom.test.ts`

- [ ] **步骤 1：保留失败的 Agent Center 契约**

```ts
expect(withoutComments(agentCenterSource)).toContain('AgentWorkspaceCard')
expect(withoutComments(agentCenterSource)).toContain('ResearchMetricPanel')
expect(withoutComments(agentCenterSource)).toContain('ResearchTimeline')
expect(withoutComments(agentCenterSource)).toContain('EvidencePanel')
expect(withoutComments(agentCenterSource)).toContain('ToolExecutionPanel')
expect(withoutComments(agentCenterSource)).not.toMatch(/useWorkflowStore|workflowStore/)
```

- [ ] **步骤 2：创建真实转换函数与固定角色定义**

```ts
const FIXED_ROLES = [
  { name: '文献智能体', role: '文献检索与证据核验' },
  { name: '实验智能体', role: '实验设计与参数控制' },
  { name: '分析智能体', role: '数据建模与统计分析' },
  { name: '写作智能体', role: 'SCI 叙事与手稿组织' },
  { name: '审稿智能体', role: '质量审阅与风险识别' }
] as const

const roleCards = computed(() => FIXED_ROLES.map(role => {
  const source = [...agentStore.events].reverse().find(event =>
    event.label.includes(role.name) || event.detail.includes(role.name)
  )
  return source
    ? { ...role, dataAvailable: true, status: source.status, currentTask: source.detail }
    : { ...role, dataAvailable: false }
}))
```

将 `messages[].toolCalls` 映射为 `ToolExecutionItem[]`；仅带真实 message ID、工具名、状态和输出。不要把 `designResult`、Workflow task、事件类型或 `Date.now()` 用作角色状态、队列、Agent、阶段或耗时。

- [ ] **步骤 3：替换团队可观察模板**

保留现有 `runResearch`、`loadSessionsSafely`、加载与错误重试，并用本地 `researchError` 取代 Workflow Store 错误。模板必须含：

```vue
<ResearchMetricPanel :items="teamMetrics" aria-label="AI 研究团队概览" />
<section class="agent-center__role-grid" aria-label="AI 研究团队">
  <AgentWorkspaceCard v-for="agent in roleCards" :key="agent.name" v-bind="agent" />
</section>
<ResearchTimeline :items="collaborationTimeline" aria-label="协作时间线" />
<EvidencePanel :evidence="sessionEvidence" :citations="sessionCitations" aria-label="团队证据与引用" />
<ToolExecutionPanel :executions="toolExecutions" aria-label="真实工具执行历史" />
```

`teamMetrics` 仅统计 `sessions.length`、`messages.length`、`events.length` 和 `citations.length`；无数据时显示各组件已有的中文空态。保留真实 `designResult` 的现有结果区，但不把它改写成智能体执行记录。

- [ ] **步骤 4：添加无障碍与宽屏 CSS**

```css
.agent-center__role-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); min-width: 0; gap: var(--research-space-3); }
.agent-center__observability { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(300px, .8fr); min-width: 0; gap: var(--research-grid-gap); }
@media (max-width: 1480px) { .agent-center__role-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 1050px) { .agent-center__role-grid, .agent-center__observability { grid-template-columns: minmax(0, 1fr); } }
@media (prefers-reduced-motion: reduce) { .agent-center * { scroll-behavior: auto; } }
```

给任务表单、团队、时间线、证据和工具历史提供中文 `aria-label`；保留按钮 keyboard、disabled、`aria-busy` 和 `:focus-visible` 样式。

- [ ] **步骤 5：运行 Agent Center 与旧契约确认转绿**

运行：`npm run test:unit -- phase-8-m0-b2-assistant-agent-center.dom.test.ts research-workflow.test.ts research-pages.dom.test.ts`

预期：B2 契约 PASS。若旧测试还期待 `知识智能体`、`useWorkflowStore`、`—` 耗时或模拟队列，只迁移这些旧断言到 B2 的固定五角色、真实 Store 与未知状态规则，不能删除覆盖或恢复伪数据。

### 任务 6：完整验证、范围门禁与最终提交

**文件：**
- 修改：仅任务 1–5 列出的 `desktop/**` 文件

- [ ] **步骤 1：运行完整验证**

```text
npm run test:unit
npx tsc --noEmit -p tsconfig.node.json
npx vue-tsc --noEmit -p tsconfig.web.json
npm run build
```

预期：每条命令退出码为 0；全量测试显示 0 failures，B2 契约实际数 `>= 150`。

- [ ] **步骤 2：提交前范围与格式审计**

```text
git diff --check -- desktop
git status --short
git diff --name-only -- desktop
```

预期：格式检查无输出；所有新增或修改文件位于 `desktop/**`；根目录既有未跟踪内容不暂存。

- [ ] **步骤 3：仅暂存 B2 的 desktop 文件并验证暂存区**

```text
git add -- desktop
git diff --cached --check
git diff --cached --name-only
```

预期：暂存清单仅包含 B2 实现、测试及本计划文件；不包含 `backend/`、`web/`、`app/` 或根目录临时目录。

- [ ] **步骤 4：创建最终实现提交**

```text
git commit -m "Phase 8-M0-B2 Scientific Research OS Assistant Agent Center Upgrade"
git log -1 --oneline
```

预期：最终提交信息精确为 `Phase 8-M0-B2 Scientific Research OS Assistant Agent Center Upgrade`。

## 计划自检

- 规格中的 Assistant 三栏、五个回应分区、四个共享组件、原生折叠、真实 Agent Store 限制、状态恢复、a11y 和响应式，分别由任务 4 覆盖。
- 五个固定角色、未知状态、真实事件/消息映射、指标、时间线、证据、工具历史和现有研究任务入口，由任务 5 覆盖。
- 两个新增 props-only 组件由任务 2–3 覆盖；`>=150` 契约和反伪造数据要求由任务 1 覆盖；全量门禁和精确提交由任务 6 覆盖。
- 计划未引用任何不存在的 Agent Store 字段，也未将没有 role、queue 或 duration 的字段推断为业务数据。
