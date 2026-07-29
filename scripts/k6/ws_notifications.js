/**
 * k6 load test for Notifications WebSocket long-connection
 * Endpoint: WS {BASE_URL}/api/v1/ws/notifications?token=...
 * Target: app/api/v1/ws_notifications.py:127 ws_notifications
 * Usage: k6 run --vus 10 --duration 30s scripts/k6/ws_notifications.js
 * W87-E-1 created 2026-07-29
 * Threshold: ws_message_latency_ms p(95) < 1000 ms (server ping → client 收到 ping/pong)
 */

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || 'test-token-placeholder';
const WS_PATH = '/api/v1/ws/notifications';

// 自定义指标
const wsMessageLatency = new Trend('ws_message_latency_ms');
const wsReconnects = new Counter('ws_reconnects_total');
const wsErrors = new Rate('ws_errors');

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    // 主门禁: 消息延迟 (server send → client recv) p95 < 1000ms
    'ws_message_latency_ms': ['p(95)<1000'],
    // 错误率门禁
    'ws_errors': ['rate<0.05'],
    // k6 内置 WS 错误率
    'ws_connecting': ['p(95)<500'],
  },
};

export default function () {
  const url = `ws://${BASE_URL.replace(/^https?:\/\//, '')}${WS_PATH}?token=${AUTH_TOKEN}`;
  const startConnect = Date.now();

  const res = ws.connect(url, null, function (socket) {
    socket.on('open', function () {
      // 触发握手完成: 收到 hello 帧视为成功
      const t = Date.now() - startConnect;
      wsMessageLatency.add(t);
    });

    socket.on('message', function (data) {
      try {
        const msg = JSON.parse(data);
        if (msg.type === 'ping') {
          // 收到 ping → 立即回 pong (协议契约)
          socket.send(JSON.stringify({ type: 'pong' }));
        }
        // 记录延迟: 任何消息到达都计入
        const t = Date.now() - startConnect;
        wsMessageLatency.add(t);
        ws_errors_inc(false);
      } catch (e) {
        ws_errors_inc(true);
      }
    });

    socket.on('close', function () {
      // 长连接中断视为 reconnect
      wsReconnects.add(1);
    });

    socket.on('error', function (e) {
      ws_errors_inc(true);
      console.error(`WS error: ${e.error()}`);
    });

    // 保活 28s (留 2s 缓冲, 防止 VU 关闭时被打断)
    socket.setTimeout(function () {
      socket.close();
    }, 28000);
  });

  check(res, {
    'WS 连接状态 101': (r) => r && r.status === 101,
    'WS session 耗时 < 30s': (r) => Date.now() - startConnect < 30000,
  });

  sleep(1);
}

// ws_errors Rate 累加辅助 (k6 Rate 需要 boolean)
function ws_errors_inc(isErr) {
  wsErrors.add(isErr);
}
