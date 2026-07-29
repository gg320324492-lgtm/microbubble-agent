/**
 * k6 load test for Chat SSE long-connection
 * Endpoint: POST {BASE_URL}/api/v1/chat/stream (text/event-stream)
 * Target: app/api/v1/chat.py:250 chat_stream StreamingResponse
 * Usage: k6 run --vus 10 --duration 30s scripts/k6/chat_stream.js
 * W87-E-1 created 2026-07-29
 * Threshold: chat_stream_duration p(95) < 5000 ms (SSE 首字节 + 完整流)
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || 'test-token-placeholder';
const SSE_PATH = '/api/v1/chat/stream';

// 自定义指标: SSE first-byte (TTFB) + total duration
const sseFirstByte = new Trend('chat_sse_first_byte_ms');
const sseTotal = new Trend('chat_stream_duration_ms');
const sseEvents = new Counter('chat_sse_events_total');

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    // 主门禁: SSE 完整流 (post → done) p95 < 5000ms
    'chat_stream_duration_ms': ['p(95)<5000'],
    // 次门禁: first-byte (TTFB) p95 < 1500ms (LLM 冷启动场景)
    'chat_sse_first_byte_ms': ['p(95)<1500'],
    // 错误率门禁: 失败 < 1%
    'http_req_failed': ['rate<0.01'],
  },
};

export default function () {
  const url = `${BASE_URL}${SSE_PATH}`;
  const payload = JSON.stringify({
    message: '简要介绍一下微纳米气泡',
    session_id: `k6-loadtest-vu${__VU}-iter${__ITER}`,
    model: 'sonnet',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${AUTH_TOKEN}`,
    },
    // k6 0.49+ 流式响应: tags.streaming=true 自动分块
    tags: { streaming: 'true' },
  };

  const startTime = Date.now();
  const res = http.post(url, payload, params);

  // k6 处理 text/event-stream 时 res.timings.waiting ≈ first-byte
  sseFirstByte.add(res.timings.waiting);
  sseTotal.add(res.timings.duration);
  // SSE 计数: data: 行数 / 16 (近似 event 数, 每 event 至少 1 行 data: + 空行)
  const eventsCount = (res.body.match(/^data:/gm) || []).length;
  sseEvents.add(eventsCount);

  check(res, {
    'SSE status 200': (r) => r.status === 200,
    'SSE Content-Type event-stream': (r) => (r.headers['Content-Type'] || '').includes('event-stream'),
    'SSE 包含 [DONE] 哨兵': (r) => r.body.includes('[DONE]'),
    'SSE 含至少 3 个 data: 事件': (r) => eventsCount >= 3,
    '流式响应耗时 < 30s (熔断保护)': () => Date.now() - startTime < 30000,
  });
}
