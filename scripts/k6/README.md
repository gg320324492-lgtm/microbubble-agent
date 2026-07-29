# k6 长连接压测 (W87-E-1)

> **目的**: 给 SSE / WebSocket 长连接端点提供 k6 压测脚本 + 阈值门禁.
> **来源**: 派工 v6 §5 反馈 #类 20.26 — "压测脚本必含阈值门禁 + baseline 留口".
> **历史背景**: W87 派工前评估 (6/10 SSE/WS 长连接完全裸奔), k6 单 binary 装机成本低, JS 与项目技术栈一致, ROI 高.

## 装机

参考 [`scripts/install-k6.md`](../install-k6.md) (macOS / Linux / Windows / Docker).

**本任务 (W87-E-1) 不真装 k6 binary**, 装机步骤仅做文档. 真装机留 W87+ 后续或主指挥按需.

## 跑法

### 1. 本地 dev server (默认 http://localhost:3000)

```bash
# 1) 启 dev server (Docker 8 services + npm run dev)
docker compose up -d
npm --prefix web run dev   # 另一 terminal

# 2) 跑压测
npm --prefix web run load:chat    # SSE
npm --prefix web run load:ws      # WS notifications
npm --prefix web run load:drive   # WS drive collab
```

### 2. 生产 / 预发环境

```bash
K6_BASE_URL=https://staging.example.com \
K6_AUTH_TOKEN=<test-user-jwt> \
npm --prefix web run load:chat
```

### 3. 直接调 k6 (不走 npm)

```bash
k6 run --vus 10 --duration 30s scripts/k6/chat_stream.js
k6 run --vus 10 --duration 30s scripts/k6/ws_notifications.js
k6 run --vus 5  --duration 30s scripts/k6/drive_collab.js
```

### 4. Docker 跑 (CI 推荐)

```bash
docker run --rm -i grafana/k6 run - <scripts/k6/chat_stream.js
```

## 脚本清单与阈值

| 脚本 | 端点 | VU | 阈值 | 真实业务 |
|------|------|----|------|----------|
| `chat_stream.js` | `POST /api/v1/chat/stream` (SSE) | 10 | `chat_stream_duration p95 < 5000ms` | LLM 流式对话主路径 |
| `ws_notifications.js` | `WS /api/v1/ws/notifications` | 10 | `ws_message_latency p95 < 1000ms` | 实时通知推送 (ping/pong + activity + mention) |
| `drive_collab.js` | `WS /api/v1/drive/files/{id}/collab` | 5 | `drive_event_latency p95 < 500ms` | Yjs 网盘协同编辑 (PR10) |

## 阈值设计依据

- **chat_stream_duration p95 < 5000ms**:
  - LLM 流式响应基线 (生产 Sonnet): p95 ≈ 3.2s (W72 第 2 批 D-1 真实施沉淀).
  - 阈值 5000ms 留 1.5x 安全余量 (LLM 冷启动 + 工具调用 overhead).
- **chat_sse_first_byte p95 < 1500ms**:
  - SSE TTFB 应接近 HTTP TTFB (< 500ms 正常, 1500ms 视为 LLM 冷启动).
- **ws_message_latency p95 < 1000ms**:
  - WS 通知本质是 server push, 无 LLM overhead. 1s 阈值覆盖网络抖动 + Redis pub/sub 延迟.
- **drive_event_latency p95 < 500ms**:
  - 协同编辑用户体验敏感: 500ms 以上开始感知延迟 (Google Docs 同类指标).

## 与现有 `tests/perf/` 关系

**现状 (CLAUDE.md 文档与代码脱节已发现, W87 C-2 据实上报)**:

- `tests/perf/test_synthesis_latency.py` — 单请求 Python 性能测试 (pytest 内部计时).
- `tests/perf/test_tool_round_trip.py` — tool 路由性能 (无 HTTP 层).
- **0 长连接 SSE/WS 压测** — 6/10 缺口.

**本任务定位**: **不替代** `tests/perf/`, 而**补充**长连接层. pytest 跑单请求快速反馈, k6 跑长连接 + 多 VU + 阈值门禁. 两者互补.

**CLAUDE.md 文档与代码脱节据实上报**:
- CLAUDE.md 标注 "tests/perf/: 6 测试: brief<3s / SSE<1s / tool<5ms" — 实际目录只有 2 个文件 (test_synthesis_latency.py + test_tool_round_trip.py), 不存在 6 测试.
- 真实情况待 W87+ 派工调研整改 (派工 v6 §5 反馈: 不在本批范围).

## Baseline 留口

压测跑出的 baseline 数据应存档到 `scripts/k6/baselines/<endpoint>_<YYYYMMDD>.json`. 真跑留 W87+ 后续.

## 待办 (主指挥后续)

- [ ] 真跑一次生成 baselines (W87 后续派工或主指挥 on-demand)
- [ ] CI 集成 (W88+) — GitHub Actions `actions/upload-artifact` 上传 json
- [ ] 与 baseline 历史曲线对比告警 (阈值破坏 → fail PR)
- [ ] k6 binary 装机 (主指挥按需)
- [ ] CLAUDE.md 文档与代码脱节整改 (派工 v6 §5 据实上报, 留 W87+)
