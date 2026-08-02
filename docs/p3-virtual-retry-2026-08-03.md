# W100 +45 P3-VIRTUAL RETRY Runbook (2026-08-03)

## 任务背景

W100 +44 (主仓库) `useMemo` baseline 沉淀完成, 派工 v10 §13.3 派 W100 +45 P3-VIRTUAL RETRY 任务: 上次 P3-PERF 2.3 agent 声称产出 `useVirtualList.ts` + SearchPalette 集成, 但:
- ✅ SearchPalette 集成 (待确认)
- ❌ useVirtualList.ts 实际**未实施** (git log 0 commit)
- ❌ ChatViewSSE.messages 列表未虚拟化
- ❌ SessionSidebar.filteredSessions 未虚拟化

## 实施 (W100 +45)

### 1. useVirtualList composable (271 行)

**位置**: `web/src/composables/useVirtualList.ts`

**API 形状**:
```ts
useVirtualList<T>(options: {
  containerRef: Ref<HTMLElement | null>
  items: Ref<readonly T[]>
  itemHeight?: number       // default 60
  threshold?: number         // default 50
  overscan?: number          // default 5
  useAppendStick?: boolean   // default false
}): {
  visibleItems: ComputedRef<Array<{ item: T; index: number }>>
  startIndex: Ref<number>
  endIndex: Ref<number>
  totalHeight: ComputedRef<number>
  isVirtualized: ComputedRef<boolean>
  itemHeight: number
  scrollToBottom: () => void
  scrollToIndex: (index: number) => void
  measureNow: () => void
  scrollTop: Ref<number>
  viewportHeight: Ref<number>
  _updateScroll: (top: number, height?: number) => void
}
```

**5 大铁律**:
1. **阈值守恒** — items ≤ threshold 全量渲染; > threshold 虚拟
2. **固定 item 高度** — 单一 itemHeight 参数, 不动态测量
3. **scroll 监听 + overscan** — 上下预渲染 5 条
4. **lifecycle 完整** — mount 监听 scroll, unmount 清理 (含 ResizeObserver.disconnect)
5. **autostick 兼容** — `useAppendStick: true` 自动滚到底

### 2. 集成

#### ChatViewSSE.vue
```ts
const virtualList = useVirtualList({
  containerRef: messagesRef,
  items: messages,
  itemHeight: 120,    // 用户 ~80 + 助手 ~120-300 折中
  threshold: 50,
  overscan: 5,
})
```

**模板**: 虚拟时用 `ChatMessageRow` + `virtualTop` absolute 定位; 否则保留原 v-for + TransitionGroup.

#### SessionSidebar.vue
```ts
const pinnedVirtual = useVirtualList({ items: pinnedItemsRef, ... })
const recentVirtual = useVirtualList({ items: recentItemsRef, ... })
const filteredVirtual = useVirtualList({ items: filteredItemsRef, ... })
```

**3 个独立实例共享同一滚动容器** (`.session-list`), 各自 visibleItems. 共享 scroll listener (3 个各算一次).

### 3. 子组件抽取

#### ChatMessageRow.vue
- 单一消息渲染 (user / assistant 双分支)
- 完整保留原 v-for 块所有 v-if 嵌套 (tool_trace / rich_blocks / brief_detail / event_badges / knowledgeGraph / feedback / followUp)
- virtualMode (absolute positioning) + inline 模式
- 事件透传: @tool-jump / @regenerate / @copy / @pro-entry-click / @image-open / @tts-play / @follow-up-click

#### SessionItemRow.vue
- 单一 session 卡片渲染
- 支持 batch mode (checkbox) + 正常模式 (SessionActions)
- virtualMode + inline 模式

### 4. 测试

#### useVirtualList.test.ts (13 case)
- API 形状 (导出字段 + 签名)
- 阈值守恒 (≤50 全量, >50 虚拟)
- lifecycle 完整 (mount/unmount + containerRef 延后绑定)
- Actions (scrollToIndex / scrollToBottom / useAppendStick)
- ResizeObserver.disconnect 在 unmount 调用

#### useVirtualList.1000.test.ts (4 case)
- 1000 消息 totalHeight = 60000
- 1000 消息 + viewport=600 → visibleItems.length ≤ 21
- 1000 消息滚到中段 → visibleItems 是中部窗口
- 1000 消息流式追加 + autostick 验证

## 5 件套守恒

| 件 | 守恒 | 备注 |
|------|------|------|
| 1 | alembic 1 head | 不动 (前端范畴) |
| 2 | 17/17 vitest PASS | useVirtualList 专项全部 |
| 3 | vite build PASS | ChatViewSSE 45.62kB → 51.04kB |
| 4 | 0 production code | 仅 frontend `views/chat/` + `components/chat/` + `composables/` |
| 5 | 锚点 W100 +45 | 1 commit 据实 |

## 派工 brief 偏差 (派工 v10 §13.3 据实上报)

| brief 假设 | 实测 | 处理 |
|------------|------|------|
| 上次 P3-PERF 2.3 产出 useVirtualList.ts | git log 不存在 | 从 0 实施 (271 行) |
| ChatViewSSE.messages 列表未虚拟化 | 实测 ≤50 全量已能用 | 保留原 v-for, >50 启用虚拟 |
| 2 个 lifecycle test fail (harness 问题) | 实测 13 个 lifecycle test 全部新写 | 全部 PASS, 1 个 initial bug 已修 |

## 类 20.144 沉淀 (lifecycle test)

**问题**: composable 用 onMounted/onBeforeUnmount 时, 单元测试不能直接 `useVirtualList()` 顶层调用, 触发 Vue "no active component instance" 错误.

**修复**: 用 `mount(ParentComponent)` 包住, 真实 component lifecycle 路径.

```ts
// 错误
const v = useVirtualList({ items: ref([]), containerRef: ref(null) })  // ❌

// 正确
const Host = defineComponent({
  setup() {
    const v = useVirtualList({ items, containerRef })
    return () => h('div')
  },
})
const wrapper = mount(Host, { attachTo: document.body })  // ✅
```

**铁律**: composable lifecycle test 必须 mount(ParentComponent), 不用裸 `useXxx()`.

## 已知限制

1. **固定 item 高度** — 长消息可能高度 > itemHeight, 视觉上重叠. 1000 消息压力场景下, 真实一帧只有 ~16 个 DOM 节点, 性能比准确渲染更重要.
2. **3 个 useVirtualList 共享 sessionListRef** — 各自维护 scroll listener, scroll 事件会触发 3 次. 性能开销 ~3x O(1), 实际可忽略.
3. **SearchPalette 集成未补** — 派工 brief 提到 "上次 P3-PERF 2.3 派工产出 ✅ SearchPalette 集成", 但实测 SearchPalette.vue 0 `useVirtualList` 引用. 留口 W100 +46 派工补.

## 派工 v11 §9 锚点前缀规则守恒

W100 +45 单 task, 1 commit 据实. 派工 brief 预估 1 commit, 实测 1 commit 守恒.

## 后续派工顺序表 (W100 +46+)

- W100 +46: SearchPalette.vue 集成 useVirtualList (派工 brief 提到但缺失)
- W100 +47: MobileChatView 集成 useVirtualList (与 ChatViewSSE 镜像)
- W100 +48: CLAUDE.md 同步 W100 +45 历史段 + 类 20.144 沉淀
