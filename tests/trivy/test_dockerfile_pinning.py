"""W86-C-1: Dockerfile / docker-compose base image 钉死 e2e 硬门禁.

确保 9 个 Dockerfile (10 个 FROM) + docker-compose.yml 5 个 image 行
**0 个**使用浮动 tag (裸 latest / 无 patch 号的 major-only tag).

浮动 tag 的危害: CVE 无法追踪 (今天扫过的镜像明天可能已换基底),
构建不可复现. 见 scripts/install-trivy.md + memory/w86-1st-batch-c1-trivy-2026-07-29.md
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

DOCKERFILES = [
    "Dockerfile",
    "Dockerfile.db",
    "Dockerfile.funasr",
    "Dockerfile.mcp",
    "Dockerfile.voice-pipeline",
    "Dockerfile.whisper",
    "web/Dockerfile",
    "docker/Dockerfile.commercial",
]

COMPOSE_FILE = "docker-compose.yml"

# FROM <image>[:tag] [AS name]  — 忽略 FROM <stage-name> 的多阶段引用
FROM_RE = re.compile(r"^\s*FROM\s+(?P<ref>\S+)", re.IGNORECASE)
IMAGE_RE = re.compile(r"^\s*image:\s*(?P<ref>\S+)")

# 已知的多阶段内部 stage 名 (FROM builder 之类), 不是真镜像
INTERNAL_STAGES = {"builder", "runtime"}


# 上游用 major.minor 即表示完整 patch 版本的镜像 (postgres 无第三段).
# 其余镜像一律要求 3 段数字 — 否则 'python:3.11-slim' 这种 major.minor
# 会被误判为已钉死 (它其实每次 rebuild 都可能换 patch).
TWO_SEGMENT_COMPLETE = {"postgres"}


def _tag_of(ref: str) -> str | None:
    """取镜像引用的 tag. 无 tag 返回 None (= 隐式 latest)."""
    # 去掉 digest
    ref = ref.split("@", 1)[0]
    # registry host 里的 ':' 是端口, 用最后一个 '/' 之后的部分判断
    last = ref.rsplit("/", 1)[-1]
    if ":" not in last:
        return None
    return last.rsplit(":", 1)[1]


def _name_of(ref: str) -> str:
    """取镜像名 (去 registry / namespace / tag), 例如 minio/minio:X → minio."""
    ref = ref.split("@", 1)[0]
    last = ref.rsplit("/", 1)[-1]
    return last.rsplit(":", 1)[0] if ":" in last else last


def _is_pinned(ref: str) -> bool:
    """镜像引用是否算钉死.

    钉死 =
      - MinIO 式 RELEASE.<日期戳>, 或
      - tag 以 3 段数字开头 (3.11.15-slim / 20.19.6-alpine / 12.1.1-runtime-*), 或
      - 上游只有 2 段版本方案的镜像 (postgres:16.14-alpine)
    不钉死 = 无 tag (隐式 latest) / 'latest' / 'alpine' / '16-alpine' / '3.11-slim' 这类浮动.
    """
    tag = _tag_of(ref)
    if tag is None or tag == "latest":
        return False
    # MinIO: RELEASE.2025-09-07T16-13-09Z
    if tag.startswith("RELEASE."):
        return True
    # 3 段数字开头 = 真 patch 级钉死
    if re.match(r"^v?\d+\.\d+\.\d+", tag):
        return True
    # postgres:16.14-alpine — 上游 major.minor 就是完整版本
    if _name_of(ref) in TWO_SEGMENT_COMPLETE and re.match(r"^\d+\.\d+(?:\D|$)", tag):
        return True
    return False


def _collect_refs() -> list[tuple[str, int, str]]:
    """收集所有 (file, lineno, ref) 待检查镜像引用."""
    refs: list[tuple[str, int, str]] = []

    for rel in DOCKERFILES:
        path = REPO_ROOT / rel
        assert path.is_file(), f"缺失 Dockerfile: {rel}"
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = FROM_RE.match(line)
            if not m:
                continue
            ref = m.group("ref")
            if ref.lower() in INTERNAL_STAGES:
                continue
            refs.append((rel, i, ref))

    compose = REPO_ROOT / COMPOSE_FILE
    assert compose.is_file(), f"缺失 {COMPOSE_FILE}"
    for i, line in enumerate(compose.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue  # 注释掉的 service (whisper 退役段)
        m = IMAGE_RE.match(line)
        if m:
            refs.append((COMPOSE_FILE, i, m.group("ref")))

    return refs


def test_all_dockerfiles_present():
    """9 个目标文件 (8 Dockerfile + compose) 全部存在."""
    for rel in [*DOCKERFILES, COMPOSE_FILE]:
        assert (REPO_ROOT / rel).is_file(), f"缺失: {rel}"


def test_refs_discovered():
    """真验证: 确实扫到了预期数量的镜像引用 (10 FROM + 5 compose image).

    派工范式 v6 §1.2 — 防止正则失配导致 '0 个引用 → 空集合永远 PASS' 的假绿。
    """
    refs = _collect_refs()
    from_refs = [r for r in refs if r[0] != COMPOSE_FILE]
    image_refs = [r for r in refs if r[0] == COMPOSE_FILE]
    assert len(from_refs) == 10, f"期望 10 个 FROM, 实际 {len(from_refs)}: {from_refs}"
    assert len(image_refs) == 6, f"期望 6 个 compose image, 实际 {len(image_refs)}: {image_refs}"


@pytest.mark.parametrize("rel,lineno,ref", _collect_refs(), ids=lambda v: str(v))
def test_no_floating_tag(rel, lineno, ref):
    """0 个浮动 tag: 每个镜像引用必须钉死到 patch/日期戳版本."""
    assert _is_pinned(ref), (
        f"{rel}:{lineno} 使用浮动 tag: {ref!r} (tag={_tag_of(ref)!r}). "
        f"必须钉死到 x.y.z 或 RELEASE.<日期戳> — W86-C-1 CVE 追踪要求"
    )


def test_no_bare_latest_anywhere():
    """整体断言: 所有引用中 0 个 'latest' / 无 tag."""
    offenders = [
        f"{rel}:{lineno} {ref}"
        for rel, lineno, ref in _collect_refs()
        if _tag_of(ref) in (None, "latest")
    ]
    assert not offenders, "发现裸 latest / 无 tag 引用:\n" + "\n".join(offenders)


@pytest.mark.parametrize(
    "ref",
    [
        "python:3.11-slim",             # major.minor 不算钉死 (patch 仍浮动)
        "python:3.11-slim-bookworm",
        "postgres:16-alpine",           # major-only
        "redis:7-alpine",
        "nginx:alpine",                 # 纯变体名, 无版本
        "nginx",                        # 无 tag = 隐式 latest
        "minio/minio",
        "ollama/ollama:latest",
        "neo4j:5-community",
        "node:20-alpine",
        "nvidia/cuda:12.1-runtime-ubuntu22.04",
    ],
)
def test_is_pinned_rejects_floating(ref):
    """负向自检: 门禁必须能识别浮动 tag.

    防止判定逻辑写松 (例如 `3.11-slim` 里的 '3.11' 被当成已钉死) 导致假绿。
    """
    assert not _is_pinned(ref), f"{ref!r} 应判定为浮动 tag, 但门禁放过了"


@pytest.mark.parametrize(
    "ref",
    [
        "python:3.11.15-slim",
        "python:3.11.15-slim-bookworm",
        "postgres:16.14-alpine",        # 上游 major.minor 即完整版本
        "redis:7.4.9-alpine",
        "nginx:1.31.2-alpine",
        "node:20.19.6-alpine",
        "neo4j:5.26.27-community",
        "nvidia/cuda:12.1.1-runtime-ubuntu22.04",
        "ollama/ollama:0.31.1",
        "minio/minio:RELEASE.2025-09-07T16-13-09Z",
    ],
)
def test_is_pinned_accepts_real_pins(ref):
    """正向自检: 本次实际钉死的 tag 全部判定为已钉死."""
    assert _is_pinned(ref), f"{ref!r} 应判定为已钉死, 但门禁拒绝了"


def test_pin_comment_present():
    """每个被钉死的 Dockerfile 顶部含 CVE 追踪注释 (可追溯钉死日期)."""
    marker = "pinned on 2026-07-29 for CVE tracking (W86-C-1 Trivy)"
    missing = [
        rel
        for rel in DOCKERFILES
        if marker not in (REPO_ROOT / rel).read_text(encoding="utf-8")
    ]
    assert not missing, f"以下 Dockerfile 缺钉死注释: {missing}"
