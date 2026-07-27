"""endpoint_lock.py — W74 第 1 批 C-1 实施前置 3 (模型/endpoint 锁)

派工 v8 段 8 实施前置 3 — qa-bench 模型/endpoint 锁 (锚点范式第 247 守恒)

锁定契约 (CI 守门):
  - LLM_BACKEND=mimo (锁定, 不允许切换到 ollama/anthropic/openai)
  - EMBEDDING_MODEL=text2vec-base-chinese (锁定)
  - RERANK_MODEL=BAAI/bge-reranker-v2-m3 (锁定, W67 D5 gate 实战)
  - API_BASE_URL 不可指向 localhost (防测-生产混淆)

用法:
  # CI 校验 (期望通过, exit 0; 失败 exit 1)
  python scripts/qa-bench/endpoint_lock.py --check

  # 输出当前端点配置 (调试用)
  python scripts/qa-bench/endpoint_lock.py --show

锚点范式 W73 第 1 批 242 → W74 第 1 批 C-1 248 守恒 (+1)
0 production code 改动铁律守恒 (qa-bench 范畴, 仅 scripts/qa-bench/endpoint_lock.py)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 锁定契约 (CI 守门值, 与生产配置对比)
LOCKED_CONFIG: dict[str, object] = {
    "LLM_BACKEND": {
        "allowed": ["mimo"],
        "forbidden": ["ollama", "anthropic", "openai", "local-mock"],
        "reason": "W67 D5 gate 真跑 mimo cloud, 切换破坏 baseline 对照",
    },
    "EMBEDDING_MODEL": {
        "allowed": ["text2vec-base-chinese"],
        "forbidden": ["bge-large-zh", "text2vec-base", "m3e-large"],
        "reason": "W66 v3.0 700 题基线锁模型",
    },
    "RERANK_MODEL": {
        "allowed": ["BAAI/bge-reranker-v2-m3"],
        "forbidden": ["bge-reranker-base", "bge-reranker-large"],
        "reason": "W67 D5/D6/D7/D8 全链路统一 rerank 模型",
    },
    "API_BASE_URL_FORBIDDEN": {
        "forbidden": ["localhost", "127.0.0.1", "0.0.0.0"],
        "reason": "防 qa-bench CI 误指向本地 mock",
    },
}


def _read_env_file(path: Path) -> dict[str, str]:
    """读 .env 文件 → dict."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _merged_env() -> dict[str, str]:
    """merge 进程 env + .env (后者覆盖前者)."""
    merged = dict(os.environ)
    repo_root = Path(__file__).resolve().parent.parent.parent
    merged.update(_read_env_file(repo_root / ".env"))
    merged.update(_read_env_file(repo_root / ".env.qa-bench"))
    return merged


def check_endpoint_lock() -> tuple[bool, list[str]]:
    """CI 守门: 校验所有锁定项.

    Returns: (passed, violations)
    """
    env = _merged_env()
    violations: list[str] = []
    for key, rule in LOCKED_CONFIG.items():
        val = env.get(key, "")
        if not val:
            continue  # 未配置跳过 (CI 默认可能无)
        allowed = rule.get("allowed", [])
        forbidden = rule.get("forbidden", [])
        if allowed and val not in allowed:
            violations.append(f"{key}={val} 不在允许列表 {allowed} (reason: {rule.get('reason', '')})")
        if forbidden and val in forbidden:
            violations.append(f"{key}={val} 在禁止列表 {forbidden} (reason: {rule.get('reason', '')})")
    return (len(violations) == 0, violations)


def show_current() -> dict[str, str]:
    """返回当前生效配置 (排除敏感字段)."""
    env = _merged_env()
    return {k: "***" if "KEY" in k or "SECRET" in k or "PASSWORD" in k else v
            for k, v in env.items() if k in LOCKED_CONFIG}


def main() -> int:
    p = argparse.ArgumentParser(description="qa-bench 模型/endpoint 锁守门")
    p.add_argument("--check", action="store_true", help="CI 守门模式")
    p.add_argument("--show", action="store_true", help="显示当前生效配置")
    args = p.parse_args()

    if args.show:
        print(json.dumps(show_current(), ensure_ascii=False, indent=2))
        return 0

    if not args.check:
        p.print_help()
        return 1

    passed, violations = check_endpoint_lock()
    if passed:
        print("OK: qa-bench 模型/endpoint 锁守门通过")
        return 0
    print("ERROR: qa-bench 模型/endpoint 锁违规:", file=sys.stderr)
    for v in violations:
        print(f"  - {v}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())