#!/usr/bin/env python3
"""
scripts/trivy/check_pinned_images.py
W86 第 1 批 D-1 (锚点范式 320 → 321 预期) — pre-commit Hook 2: Dockerfile pinning

目的:
    防止 base image 用 `:latest` 或无 tag 的浮动版本号.
    标准: 任何 image 引用必须含具体次版本号 (e.g. `python:3.11-slim-bookworm`,
          而非 `python:latest` 或 `python:slim`).

违反场景:
    - `FROM python:latest`          → build 时浮到最新, 不可重现
    - `FROM python:slim`           → 同 major 系列浮动 (3.10 / 3.11 / 3.12 随机)
    - `image: nginx:alpine`        → alpine major 系列浮动 (1.25 / 1.26 随机)
    - `image: minio/minio`         → 完全无 tag, 默认是 :latest

合法形式:
    - `FROM python:3.11-slim-bookworm` (含具体次版本 3.11)
    - `FROM postgres:16-alpine`     (含具体次版本 16)
    - `FROM nvidia/cuda:12.1-runtime-ubuntu22.04` (含具体次版本 12.1)
    - `image: neo4j:5-community`    (含具体 major 5)
    - `image: redis:7-alpine`       (含具体 major 7)
    - `image: pgvector/pgvector:0.5.1-pg16` (含具体次版本 0.5.1 + pg16)

退出码:
    0 = 全部 image 钉死
    1 = 发现浮动 image, 列出文件:行号

用法:
    python scripts/trivy/check_pinned_images.py

集成:
    .pre-commit-config.yaml → hook: dockerfile-pinning
    files: 匹配模式参见配置 YAML
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 强制 stdout/stderr 用 UTF-8 (Windows GBK 默认会失败, 注释含中文 + emoji)
# 详: tests/precommit/test_hooks_executable.py + CLAUDE.md 2026-07-29 W86-D-1 沉淀
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 已知合法短 tag 白名单 (用例: postfix 1 个 stable tag, 不随时间漂移)
# 原则: 白名单只接收根镜像官方发布策略里**承诺**某个具体版本的 tag (不漂移).
# 例如:
#   - `nginxinc/nginx-unprivileged:stable-alpine` ❌ 不接受 (stable 每次发布号会变)
#   - `nginxinc/nginx-unprivileged:1.25-alpine` ✅ 接受 (1.25 是固定次版本)
# 所以白名单保守为空, 用规则 1: 必须含 :x.y 或 :x 数字段.
_KNOWN_PINNED_TAGS: set[str] = set()


def _has_numeric_pin(tag: str) -> bool:
    """检查 tag 是否含具体数字版本 (e.g. '3.11', '16', '12.1').

    合法的"具体数字版本"模式:
      - '3.11'        — major.minor
      - '16-alpine'   — major-suffix (含 16)
      - '3.11-slim'   — major.minor-suffix
      - '0.5.1-pg16'  — 含 0.5.1 (具体 triple-digit)
      - '1.0.0-jdk21' — 含 1.0.0

    浮动的 (违规) 模式:
      - 'latest'      — 无数字
      - 'slim'        — 无数字
      - 'alpine'      — 无数字
      - 'stable'      — 无数字
      - 'stable-alpine' — 无数字
      - '' (空)       — 完全无 tag
    """
    if not tag:
        return False
    # tag 必须含至少一段数字 (major 或 major.minor 或 major.minor.patch)
    # 用简单正则: 至少一个 \d 或 \d+\.\d+ 段
    if re.search(r"\d", tag):
        return True
    # 白名单检查 (保守: 当前空)
    return tag in _KNOWN_PINNED_TAGS


def _check_file(path: Path, root: Path) -> list[str]:
    """扫描一个文件的所有 image 引用, 返回违规列表 (file:line:tag)."""
    violations: list[str] = []
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return violations

    lines = content.splitlines()
    rel_path = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)

    # 模式 1: Dockerfile `FROM image:tag`
    # 例: `FROM python:3.11-slim-bookworm`
    # 例: `FROM nvidia/cuda:12.1-runtime-ubuntu22.04 AS builder`
    from_re = re.compile(r"^\s*FROM\s+([^\s]+)(?:\s+AS\s+\w+)?\s*$", re.IGNORECASE)

    # 模式 2: docker-compose `image: name:tag`
    # 例: `image: postgres:16-alpine`
    # 例: `    image: nginx:alpine` ❌
    # 例: `    image: minio/minio`  ❌ (默认 :latest)
    image_re = re.compile(r"^\s*image\s*:\s*([^\s#]+)\s*$", re.IGNORECASE)

    for line_no, line in enumerate(lines, 1):
        # Dockerfile FROM 行
        m = from_re.match(line)
        if m:
            ref = m.group(1).strip()
            # 跳过 ARG 变量 (含 ${} 或 $VAR)
            if "${" in ref or "${" in ref or ref.startswith("$"):
                continue
            # 跳过 scratch / 阶段别名
            if ref.lower() in ("scratch",):
                continue
            # 提取 :tag 部分
            if ":" in ref:
                # 处理 digests: python:3.11@sha256:... → tag = 3.11
                # 处理 registry:port: registry.example.com:5000/repo:tag
                # 简化: 取最后一个 : 之后的部分作为 tag (假设无 @digest)
                # 若含 @, 先剥 digest
                tag_part = ref.rsplit("@", 1)[0]
                # 用最后一个 : 分隔 (registry:port 也用 :, 这里假设 docker-compose 不会用 port)
                # Dockerfile FROM 不会带 registry port, 所以最右 : 后是 tag
                tag = tag_part.rsplit(":", 1)[-1]
            else:
                tag = ""  # 完全无 tag → :latest

            if not _has_numeric_pin(tag):
                violations.append(f"{rel_path}:{line_no}: FLOATING `FROM {ref}` (tag={tag!r})")

        # docker-compose image 行
        m = image_re.match(line)
        if m:
            ref = m.group(1).strip().strip('"').strip("'")
            # 跳过变量 (e.g. ${APP_IMAGE})
            if "${" in ref or ref.startswith("$"):
                continue
            if ":" in ref:
                tag_part = ref.rsplit("@", 1)[0]
                # registry.example.com:5000/repo:tag → 最后一个 : 后是 tag
                # 但 registry:port 也含 :
                # 启发: 形如 X:Y:Z 的合法情况是 registry:port/repo:tag, 即 port 段是数字
                # 这里保守处理: 取最右 : 后作为 tag (port 一般 < 65536)
                # 简化: 若 ref 形如 'host:port/path', 跳过
                if re.match(r"^[a-z0-9.-]+:\d+(/|$)", ref):
                    # registry with port
                    # tag 在 / 后: host:port/repo:tag
                    after_slash = ref.split("/", 1)[-1]
                    tag = after_slash.rsplit(":", 1)[-1] if ":" in after_slash else ""
                else:
                    tag = tag_part.rsplit(":", 1)[-1]
            else:
                tag = ""  # 无 tag → :latest

            if not _has_numeric_pin(tag):
                violations.append(f"{rel_path}:{line_no}: FLOATING `image: {ref}` (tag={tag!r})")

    return violations


def main() -> int:
    root = Path.cwd()
    # 扫描所有 Dockerfile + docker-compose.yml/yaml
    patterns = [
        "Dockerfile",
        "Dockerfile.*",
        "docker/Dockerfile",
        "docker/Dockerfile.*",
        "docker-compose.yml",
        "docker-compose.yaml",
        "docker-compose.*.yml",
        "docker-compose.*.yaml",
    ]

    candidate_files: set[Path] = set()
    for pattern in patterns:
        # 用 glob 模式匹配
        for path in root.glob(pattern):
            if path.is_file():
                candidate_files.add(path)

    if not candidate_files:
        print("INFO: 未发现 Dockerfile / docker-compose 文件, 跳过")
        return 0

    all_violations: list[str] = []
    for f in sorted(candidate_files):
        all_violations.extend(_check_file(f, root))

    if all_violations:
        print("❌ [pre-commit] Dockerfile base image 未钉死 (CLAUDE.md 永久纪律)")
        print("")
        print("📋 违规清单 (file:line: description):")
        for v in all_violations:
            print(f"   {v}")
        print("")
        print(f"🚨 共 {len(all_violations)} 处违规")
        print("")
        print("🔧 修复选项:")
        print("   1) 把 :latest 改成具体次版本 (e.g. python:3.11-slim-bookworm)")
        print("   2) 把 :alpine 改成具体 major (e.g. nginx:1.25-alpine)")
        print("   3) 完全无 tag 的 image 必须加 tag (e.g. minio/minio:latest → minio/minio:RELEASE.2024-01-01)")
        print("")
        print("🛑 pre-commit 中止, 修复后重试")
        return 1

    print(f"✅ [pre-commit] {len(candidate_files)} 个 image 文件全部钉死")
    return 0


if __name__ == "__main__":
    sys.exit(main())
