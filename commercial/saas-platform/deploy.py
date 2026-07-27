"""
商业化 SaaS 平台部署脚本 (Phase 8 起步)

不替代 docker-compose, 是商业化部署专用, 配套 Dockerfile.commercial.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def build_image(tag: str = "microbubble-commercial:phase8") -> int:
    """构建商业化镜像."""
    dockerfile = REPO_ROOT / "docker" / "Dockerfile.commercial"
    if not dockerfile.exists():
        print(f"ERROR: {dockerfile} not found", file=sys.stderr)
        return 1
    print(f"[deploy] building {tag} from {dockerfile}")
    return subprocess.call([
        "docker", "build",
        "-f", str(dockerfile),
        "-t", tag,
        str(REPO_ROOT),
    ])


def start_container(tag: str = "microbubble-commercial:phase8", name: str = "mb-commercial") -> int:
    """启动商业化容器."""
    print(f"[deploy] starting container {name} from {tag}")
    return subprocess.call([
        "docker", "run", "-d",
        "--name", name,
        "--read-only",  # 安全加固 (read-only fs)
        "--security-opt", "seccomp=commercial-strict",  # 商业化 seccomp profile
        "-p", "8000:8000",
        "-v", "mb-commercial-data:/app/data",
        "-e", "MICROBUBBLE_LICENSE_KEY=demo-key-replace-me",
        tag,
    ])


def stop_container(name: str = "mb-commercial") -> int:
    """停止商业化容器."""
    print(f"[deploy] stopping container {name}")
    return subprocess.call(["docker", "stop", name])


def main() -> int:
    parser = argparse.ArgumentParser(description="MicroBubble Commercial deploy (Phase 8)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build", help="build commercial image")
    sp_start = sub.add_parser("start", help="start commercial container")
    sp_start.add_argument("--tag", default="microbubble-commercial:phase8")
    sp_start.add_argument("--name", default="mb-commercial")
    sp_stop = sub.add_parser("stop", help="stop commercial container")
    sp_stop.add_argument("--name", default="mb-commercial")

    args = parser.parse_args()
    if args.cmd == "build":
        return build_image()
    elif args.cmd == "start":
        return start_container(args.tag, args.name)
    elif args.cmd == "stop":
        return stop_container(args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
