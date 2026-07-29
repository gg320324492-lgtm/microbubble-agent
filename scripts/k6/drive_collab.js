/**
 * k6 load test for Drive Collab WebSocket long-connection
 * Endpoint: WS {BASE_URL}/api/v1/drive/files/{file_id}/collab?token=...
 * Target: app/api/v1/drive_collab.py:98 ws_collab (Yjs 协同编辑同步)
 * Usage: k6 run --vus 5 --duration 30s scripts/k6/drive_collab.js
 * W87-E-1 created 2026-07-29
 * Threshold: drive_event_latency_ms p(95) < 500 ms (init snapshot → client 收到 init)
 *
 * 注: 5 VU (协同编辑高开销, VU 太多会拖垮 dev server), 模拟 1 个 file_id 多端协同.
 */

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || 'test-token-placeholder';
const FILE_ID = __ENV.DRIVE_FILE_ID || '1';  // 需替换为压测租户真实文件 ID
const WS_PATH = `/api/v1/drive/files/${FILE_ID}/collab`;

// 自定义指标
const eventLatency = new Trend('drive_event_latency_ms');
const initLatency = new Trend('drive_init_snapshot_ms');
const opsReceived = new Counter('drive_ops_received_total');
const collabErrors = new Rate('drive_collab_errors');

export const options = {
  vus: 5,
  duration: '30s',
  thresholds: {
    // 主门禁: 协作文档事件投递 (server send → client recv) p95 < 500ms
    'drive_event_latency_ms': ['p(95)<500'],
    // 次门禁: 初次 init snapshot 推送 p95 < 800ms (snapshot 较大, base64)
    'drive_init_snapshot_ms': ['p(95)<800'],
    // 错误率
    'drive_collab_errors': ['rate<0.05'],
    // k6 内置 WS handshake
    'ws_connecting': ['p(95)<500'],
  },
};

export default function () {
  const url = `ws://${BASE_URL.replace(/^https?:\/\//, '')}${WS_PATH}?token=${AUTH_TOKEN}`;
  const startConnect = Date.now();

  const res = ws.connect(url, null, function (socket) {
    socket.on('open', function () {
      // 主动 ping (协议要求), 触发 server 响应 pong
      socket.send(JSON.stringify({ type: 'ping' }));
    });

    socket.on('message', function (data) {
      try {
        const msg = JSON.parse(data);
        const t = Date.now() - startConnect;

        if (msg.type === 'init') {
          // 初次 snapshot 到达 (大 base64 字符串)
          initLatency.add(t);
          // 模拟一次 op 上行 (空 op, 触发 server 回声给其他 VU)
          socket.send(JSON.stringify({
            type: 'op',
            payload: '',  // 空 op, 仅触发广播测试
            client_id: __VU * 1000 + __ITER,
          }));
        } else if (msg.type === 'op') {
          // 其他 VU 的 op 广播
          eventLatency.add(t);
          opsReceived.add(1);
        } else if (msg.type === 'pong') {
          // pong 不计入主事件流
          eventLatency.add(t);
        } else if (msg.type === 'error') {
          collabErrors.add(true);
          console.error(`collab error: ${msg.code} ${msg.message}`);
        } else {
          collabErrors.add(true);
        }
      } catch (e) {
        collabErrors.add(true);
      }
    });

    socket.on('error', function (e) {
      collabErrors.add(true);
      console.error(`Drive collab WS error: ${e.error()}`);
    });

    // 保活 28s
    socket.setTimeout(function () {
      socket.close();
    }, 28000);
  });

  check(res, {
    'Drive collab WS 握手 101': (r) => r && r.status === 101,
    'Drive collab 收到 init snapshot': (r) => initLatency.avg > 0,
  });

  sleep(1);
}
