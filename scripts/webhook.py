#!/usr/bin/env python3
"""GitHub Webhook 监听服务 — 收到 push 事件后自动部署（端口 9001）"""

import hashlib
import hmac
import json
import logging
import os
import socket
import subprocess
import threading
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = 9001
SECRET = os.environ["WEBHOOK_SECRET"]
DEPLOY_SCRIPT = "/opt/microbubble-agent/scripts/deploy-auto.sh"
LOG_FILE = "/var/log/webhook-deploy.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("webhook")


def verify_signature(payload: bytes, signature: str) -> bool:
    """验证 GitHub Webhook 签名"""
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 2026-06-13 加固：socket timeout 防止 rfile.read 无限阻塞
        # 背景：GitHub 客户端偶发 10s 超时断开，Nginx 转 499 但 service 还在 rfile.read 等待
        # 设 15s timeout > GitHub 默认 10s 客户端超时，留 5s 余量给 service 读完 body
        self.connection.settimeout(15)

        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        # 防止 rfile.read 阻塞：socket.timeout 时返回 504 + 日志
        # 背景：阿里云到 GitHub 网络偶发抖动，客户端可能已断开但 rfile 还在等 body
        try:
            payload = self.rfile.read(content_length)
        except socket.timeout:
            logger.error(
                f"读取 body 超时 (15s)，客户端可能已断开 delivery={self.headers.get('X-GitHub-Delivery', 'no-id')} "
                f"ua={self.headers.get('User-Agent', 'none')}"
            )
            try:
                self.send_response(504)
                self.end_headers()
            except Exception:
                pass
            return

        # 记录详细诊断（2026-06-02 加固：解决 "redeliver 持续失败但无日志" 问题）
        delivery_id = self.headers.get("X-GitHub-Delivery", "no-id")
        event = self.headers.get("X-GitHub-Event", "")
        signature = self.headers.get("X-Hub-Signature-256", "")
        user_agent = self.headers.get("User-Agent", "")
        logger.info(
            f"POST /webhook delivery={delivery_id} event={event} "
            f"ua={user_agent} sig={signature[:20]}... size={content_length}"
        )

        # 验证签名
        if not verify_signature(payload, signature):
            # 2026-06-02 加固：记录更详细诊断信息（delivery_id / sig 前 20 字符）
            logger.warning(
                f"签名验证失败 delivery={delivery_id} "
                f"sig_present={'Y' if signature else 'N'} sig_head={signature[:20] if signature else 'none'} "
                f"secret_len={len(SECRET)} payload_head={payload[:50].decode('utf-8', 'replace')}"
            )
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        # 解析事件
        if event != "push":
            logger.info(f"忽略事件: {event}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # 先返回 200，避免 GitHub 10s 超时
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

        # 后台执行部署
        try:
            data = json.loads(payload)
            ref = data.get("ref", "")
            pusher = data.get("pusher", {}).get("name", "unknown")
            commits = len(data.get("commits", []))
            logger.info(f"收到 push: {pusher} 推送了 {commits} 个提交到 {ref} delivery={delivery_id}")

            if ref == "refs/heads/main":
                logger.info(f"开始自动部署 delivery={delivery_id}...")
                threading.Thread(target=self._run_deploy, daemon=True).start()
            else:
                logger.info(f"忽略非 main 分支: {ref}")
        except Exception as e:
            logger.error(f"处理失败: {e}", exc_info=True)

    def _run_deploy(self):
        """后台执行部署脚本（2026-06-02 加固：死亡任务清理 + 更详细日志）"""
        import os as _os
        try:
            logger.info(f"开始执行部署脚本 (pid={_os.getpid()})...")
            result = subprocess.run(
                ["bash", DEPLOY_SCRIPT],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                logger.info("部署成功 ✓")
                # 打印最后几行 stdout 帮助调试
                if result.stdout:
                    for line in result.stdout.strip().split('\n')[-5:]:
                        logger.info(f"  [script] {line}")
            else:
                logger.error(f"部署失败 (exit={result.returncode})")
                if result.stdout:
                    logger.error(f"  stdout: {result.stdout[-500:]}")
                if result.stderr:
                    logger.error(f"  stderr: {result.stderr[-500:]}")
        except subprocess.TimeoutExpired:
            logger.error("部署超时（300s）— 通常是 git pull 卡死（阿里云→GitHub TLS 偶发错误）")
        except Exception as e:
            logger.error(f"部署异常: {e}", exc_info=True)

    def do_GET(self):
        """健康检查"""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Webhook service is running")

    def log_message(self, format, *args):
        """静默 HTTP 日志，用自定义 logger"""
        pass


def main():
    # 2026-06-03 修复：HTTPServer 改 ThreadingHTTPServer
    # 单线程 HTTPServer 的问题：do_POST 触发的 _run_deploy 即使在 daemon 线程
    # 跑，HTTP 请求处理本身仍是顺序的——上一个请求的 send_response 没完全
    # flush 时新请求会排队。GitHub 10s 超时红线 + Python 单线程 = 部署期间
    # 后续所有 webhook 都失败（"delivery failed: time out"）。
    # ThreadingHTTPServer 每个请求独立线程，健康检查（do_GET）和 deploy
    # (do_POST) 互不阻塞，GitHub 立即收到 200。
    server = ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
    logger.info(f"Webhook 服务启动（多线程），监听端口 {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Webhook 服务停止")
        server.server_close()


if __name__ == "__main__":
    main()
