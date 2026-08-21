# MicroBubble Chat Performance (Phase 3-B0 评估)

> **目的**: Phase 2-Impl-3B + Phase 3-A Chat 流式 Markdown 渲染性能评估,
> Phase 3-B0 frozen. 为 Phase 3+ 接 RAG / 富 markdown 时的性能 baseline。
>
> **说明**: 本 doc 是**定性 + 简单 benchmark 描述**, 不依赖第三方压测
> 框架. 实测数字 Phase 4+ 加 micro-bench 库时再补充。
>
> **范围**:
> - MarkdownViewer 解析 + 渲染 (Phase 2-Impl-2B)
> - chat store 100ms debounce 流式累加 (Phase 3-A)
> - SSE chunk → renderer → DOM 更新整链路
> - 1000 token / 5000 token 行为预估
>
> **不在范围**:
> - 后端 v2_agent LLM 推理时延 (backend 范畴)
> - 网络 RTT (环境依赖)
> - SSE 帧解析 (Phase 3-A 已实现 + 优化空间小)

---

## 1. 性能数据通路

```
SSE upstream
  │  (网络 → main process)
  ↓
chat-stream.service.ts runStream()
  │  TextDecoder + parseLine + JSON.parse
  ↓
webContents.send('chat:stream-chunk', ctx, event)
  │  (主进程 → renderer 进程间 IPC, structured clone)
  ↓
preload/index.ts: chunkListeners fanout
  │  直接回调
  ↓
chatStore.handleStreamChunk(ctx, event)
  │  - 校验 ctx.sessionId (streamStaleCheck)
  │  - 累加 streamingMessage.content (Phase 3-A)
  │  - 触发 scheduleStreamingContentRender (100ms debounce)
  ↓
chatStore.streamingContentRender ref.value 更新
  ↓
Vue reactive: ChatView re-render
  ↓
MarkdownViewer (Phase 2-Impl-2B) 解析 content 为 AST, v-for 渲染
  ↓
DOM commit (Chromium rendering pipeline)
```

**主热点**:
1. JSON.parse (每 chunk 一次) — 70 bytes/SSE frame ≈ 5µs/frame (Phase 3-A 测过)
2. Vue reactive trigger (每 chunk 累加触发) — but **流式 content 不在 streamingContentRender 上**
3. MarkdownViewer 解析 — AST build O(content.length), 仅 **每 100ms 一次**
4. DOM diff — Vue key 复用, 增量

---

## 2. 100ms Debounce 策略 (Phase 3-A)

### 2.1 行为

```
[ms 0]    SSE chunk -> content = "你好"
[ms 100]  scheduleStreamingContentRender: 触发 (clearTimeout)
[ms 100]  streamingContentRender = "你好"
[ms 100]  Vue 触发 MarkdownViewer 重新 parse
[ms 110]  [ms 110 SSE chunk] -> content = "你好，"
[ms 110]  scheduleStreamingContentRender: 不触发 (刚被 schedule)
[ms 200]  streamingContentRender = "你好，"
[ms 200]  Vue 触发 MarkdownViewer 重新 parse
```

**结论**: 100ms window 内所有 chunk 合并成 1 次 MarkdownViewer 解析。

### 2.2 调优空间

| 场景 | 当前 | 优化方向 |
|------|------|----------|
| 普通流 (5-20 token/sec) | 100ms 1 次 parse | OK |
| 快流 (50-200 token/sec) | 100ms 1 次 parse | OK (10-20 Hz parse) |
| 突发流 (200+ token/sec) | 100ms 1 次 parse | 偏慢 → 16-30Hz → 33-62ms debounce |
| 极慢流 (< 1 token/sec) | 100ms 后才更新 | 体感 OK (typing 风) |

**Phase 3+ 计划**: 自适应 debounce — 流速越快, debounce 越短 (16ms 起步)。

---

## 3. 1000 token 行为预估

> **假设**: SSE 流速 30 tokens/sec (典型), 中文 Markdown (含 headings + code + list)。

| 阶段 | 时间 | 累计 |
|------|------|------|
| SSE 接收完成 | ~33 sec | 0 → 1000 tokens |
| DOM commit 总次数 | ~330 次 | (每 100ms debounce) |
| MarkdownViewer parse 总次数 | ~330 次 | 每次 ≤5ms (10K char 文档) |
| Vue reactive trigger | ~1000 次 | content += 触发 reactive |
| 主观流畅度 | 流畅 | 100ms 内补上 3 tokens |

**预估占用**:
- CPU: 主线程 MarkdownViewer ~3% (parse) + Vue ~2% (render) — 双核足够
- Memory: content 字符串 1000 token ≈ 3-5 KB, AST ≈ 8-15 KB, 总 < 30 KB
- 帧率: 60fps 目标, MarkdownViewer 重 parse 期间可能短暂掉到 30-45 fps (parse 5ms), 仍流畅

---

## 4. 5000 token 行为预估

> **假设**: 同上, 30 tokens/sec → 总流时间 ~167 sec ≈ 2.8 min。

| 阶段 | 时间 | 累计 |
|------|------|------|
| SSE 接收完成 | ~167 sec | 0 → 5000 tokens |
| DOM commit 总次数 | ~1670 次 | (100ms debounce) |
| MarkdownViewer parse 总次数 | ~1670 次 | 每次 ≤15ms (40K char 文档) |
| Memory 峰值 | ~150 KB | content (15KB) + AST (50KB) + DOM (~80KB) |

**预估占用**:
- CPU: 主线程偶尔 spike 到 8-12% (parse 长 content)
- 帧率: 极偶尔 30 fps spikes (parse > 16ms), 整体仍 60 fps
- 内存: content 反复累加, 老 V8 string 优化 + GC 回收; AST 重建占主要

**风险点**:
- MarkdownViewer.parse 是 O(content.length) — 5000 char ≈ 1ms parse, 50000 char ≈ 30ms (j/long content)
- 长代码块 (` ```...``` `) 行数多 → 解析慢
- Phase 3+ 接 RAG citation 后 content 翻倍 (citation block 嵌入) → 需 30Hz debounce

---

## 5. 优化 Phase 4+ 路线图

| 优先级 | 优化 | 预期收益 |
|--------|------|----------|
| P0 | 自适应 debounce (流速检测) | 高并发流时 60 fps 锁定 |
| P1 | MarkdownViewer 增量 parse (按行缓存) | 长文档 O(content) 降到 O(delta) |
| P1 | AST 复用 (上次 parse result + diff apply) | 重复 parse 取消 |
| P2 | virtual list (超出可视区 chunk 不渲染) | 万 token 内存降到 30% |
| P2 | WebWorker parse (off main thread) | 主线程释放 5-10% CPU |
| P3 | 流结束 完整重 parse + 富 markdown (表格 / 高亮) | Phase 3+ 接 RAG rich_block |

---

## 6. Benchmark 计划 (Phase 4+)

```ts
// 计划: tests/perf/chat-stream.bench.ts
//
//   stream_1k_tokens_zh_cn: benchmark SSE chunk dispatch + Vue render
//   stream_5k_tokens_code_block: benchmark long code block parse
//   stream_10k_tokens_mixed: stress test (RAG + tool + plain text)
//
//   指标:
//     - MarkdownViewer.parse.duration (ms per call)
//     - Vue rerender.duration (ms per commit)
//     - Memory.delta (RSS before / after 5k tokens)
//     - Dropped frames (60 fps target → % drops)
//
//   工具: vitest bench + playwright-trace (Phase 4+ 加)
```

**当前不实施**: Phase 3-B0 不引第三方 (vitest bench OK 但 Phase 4+ 项目批)。
Phase 4 起步: 实测 1000 / 5000 token 行为, 补 §3 §4 数字。

---

## 7. 关键不变量 (Phase 3-B0 frozen)

1. ✅ **0 v-html**: MarkdownViewer 全文 escape + AST v-for 渲染
2. ✅ **Token 不漂移 renderer**: main 唯一持 Bearer, refresh 全在 main
3. ✅ **Cancel 干净**: AbortController + activeStreams Map + UI 同步
4. ✅ **Session 隔离**: StreamContext.sessionId 校验 stale chunks
5. ✅ **Retry 无重**: client_msg_id 内部生成, Phase 3+ backend 启用去重
6. ✅ **Markdown 渐进增强**: 流中纯文本渲染, 完成切 MarkdownViewer
7. ✅ **debounce 不甩字**: 100ms 合并但 content 持续累加, 不丢 token

---

## Status (2026-08-21 Phase 3-B0 frozen)

- ✅ 性能通路定性分析
- ✅ 100ms debounce 行为
- ✅ 1000 / 5000 token 预估 (不含实测)
- ⏳ Phase 4+ 实测 benchmark
- ⏳ Phase 4+ 优化路线图实施

---

📌 **维护规则**:
- 实测数字必须 commit 时同时补 §3 §4
- 重大优化必须先量后改, 量纲见 §6 benchmark 计划
- MarkdownViewer 内部算法改动 → 重跑 §3 §4 预估, 标口径变化
