#!/usr/bin/env python3
"""GitHub Webhook 监听服务 — 收到 push 事件后自动部署（端口 9001）"""

import hashlib
import hmac
import json
import logging
import os
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)

        # 验证签名
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(payload, signature):
            logger.warning("签名验证失败")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        # 解析事件
        event = self.headers.get("X-GitHub-Event", "")
        if event != "push":
            logger.info(f"忽略事件: {event}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        try:
            data = json.loads(payload)
            ref = data.get("ref", "")
            pusher = data.get("pusher", {}).get("name", "unknown")
            commits = len(data.get("commits", []))
            logger.info(f"收到 push: {pusher} 推送了 {commits} 个提交到 {ref}")

            # 只处理 main 分支
            if ref == "refs/heads/main":
                logger.info("开始自动部署...")
                result = subprocess.run(
                    ["bash", DEPLOY_SCRIPT],
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode == 0:
                    logger.info("部署成功")
                else:
                    logger.error(f"部署失败: {result.stderr}")
            else:
                logger.info(f"忽略非 main 分支: {ref}")

        except Exception as e:
            logger.error(f"处理失败: {e}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        """健康检查"""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Webhook service is running")

    def log_message(self, format, *args):
        """静默 HTTP 日志，用自定义 logger"""
        pass


def main():
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    logger.info(f"Webhook 服务启动，监听端口 {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Webhook 服务停止")
        server.server_close()


if __name__ == "__main__":
    main()
