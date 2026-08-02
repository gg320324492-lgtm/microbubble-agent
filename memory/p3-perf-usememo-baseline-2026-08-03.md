# P3-PERF useMemo + baseline 沉淀（2026-08-03）

## 调研 grep

- `ChatViewSSE.vue`: `computed` 仅命中 isDark line 97、showThinking line 107、useDeepThinking line 110；均为低成本 store 派生，不包装。
- `ToolTraceItem.vue`: detailId / hasOutput / copyLabel / prettyJson / jumpTarget；选择昂贵 prettyJson。
- 测试目录已有 `ToolTraceItem.test.ts`，无 useMemo 或 chat 1000 消息压力测试。
- baseline build 初跑 PASS；baseline test:unit 暴露配置把 tests/e2e 一并收集、parse error 与 Node 低内存 OOM。

## 实施与 commits

- `fe5b187d2` — useMemo helper（W100 +40）。
- `2b94cdee0` — ToolTraceItem prettyJson + ChatViewSSE 消息索引缓存（W100 +41）。
- `d31976b1f` — useMemo、prettyJson 计数、1000 item 压力测试（W100 +42）。
- docs / memory commits 见本分支后续 log；据实提交，不凑 6 个。

## 测试与性能数字

- 专项：3 files / 16 tests PASS / 0 fail / 3.01s。
- 消息 x1000 mount：20.20ms。
- ToolTraceItem x1000 mount：734.89ms。
- prettyJson：同 output 下无关 prop 更新从潜在 2 次降至 1 次（节省 1/2，50%）；output 引用变化后正确执行第 2 次。
- Build：`npm run build` PASS，Vite 7.3.6，PWA disabled，manifest 自检 PASS。
- 全套基线据实：未达到全绿；首次全量在既有 e2e parse error 后 OOM，排除 e2e 串行仍 11 fail（含并行 2.3 未提交测试 2 fail + 既有 9 fail），不是本任务回归。

## 边界守恒

- `app/` 0 改动；alembic N/A。
- 本任务未改 `useChatStream.ts`、`SessionSidebar.vue`。
- `ChatViewSSE` 只改 script import/helper 与 regenerate 调用点，模板 0 改动。
- 无新依赖。

## 类 20

- Vue computed 本身已 memo；只有昂贵派生值/非响应式外部参数值得显式 useMemo。
- JSON 序列化 memo 必用重算计数测试覆盖 cache hit 和 invalidation 两条路径。
