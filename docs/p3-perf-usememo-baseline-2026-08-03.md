# P3-PERF useMemo 与性能基线（2026-08-03）

## 范围

- 新增 Vue `computed` 驱动的 `useMemo<T>` helper。
- `ToolTraceItem` 缓存 `prettyJson`，只在 `trace.tool_output` 引用变化时重新序列化。
- `ChatViewSSE` 缓存消息 ID → 索引映射，加速重新生成定位；模板 1282 行未修改。
- 新增 1000 条消息和 1000 个 `ToolTraceItem` 的 jsdom 压力基线。
- 未修改 `app/`、`useChatStream.ts`、`SessionSidebar.vue`，未新增依赖。

## 调研结论

- `ChatViewSSE` 原有 `isDark`、`showThinking`、`useDeepThinking` 已是 `computed`，Vue 自动缓存，不重复包装。
- `ToolTraceItem` 的 `prettyJson` 调用 `JSON.stringify(..., null, 2)`，是最明确的昂贵派生值。
- 原有 `ToolTraceItem.test.ts` 存在；新测试在原套件补充 JSON 重算计数。

## 验证结果

- 专项 Vitest：3 files / 16 tests PASS，0 fail，3.01s。
- 重算计数：首次展开 1 次；仅变更 `duration_ms` 后仍 1 次，节省 1 次；替换 `tool_output` 后增至 2 次且输出更新。
- 压力基线（同机第二次实测）：1000 条轻量消息 mount 20.20ms；1000 个 `ToolTraceItem` mount 734.89ms。
- `npm run build`：PASS；Vite 7.3.6，PWA disabled，postbuild manifest 自检 PASS。
- 全量 `npm run test:unit` 基线非全绿：运行包含 `tests/e2e`、既有 parse error，并在低内存下 OOM。排除 e2e 串行复跑仍有 11 个失败，其中 2 个来自并行 2.3 虚拟滚动未提交变更，9 个是既有 ThinkingCapsule/assistantPhase/mobile-fab/PWA 测试；本任务专项 16/16 PASS。

## 类 20 派生

1. Vue 3.5 `computed` 自带依赖追踪和惰性缓存；简单 store 派生值重复套 `useMemo` 不会增加收益，helper 应留给昂贵计算或显式外部依赖。
2. `JSON.stringify` 等昂贵派生值适合按输入对象引用 memo；必须同时用计数测试证明无关 prop 更新不重算、输入变更会失效。
