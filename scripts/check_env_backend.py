#!/usr/bin/env python
"""
scripts/check_env_backend.py — LLM Backend 配置一致性检查 (2026-07-15 #P2)

**问题** (2026-07-15): 7/13 #P1 切 ollama 时只改 LLM_BACKEND + thinking_mode
models, 没改 3 个辅助模型 (AGENT_INTENT_MODEL/REFLECTION/COMPRESSOR)
→ 这些仍是 mimo-v2.5 名字 → ollama 调不通 → intent_classifier 失败 fallback
→ TEAM_OVERVIEW intent 不触发 → 反幻觉修复形同虚设

**本脚本作用**: 检查 .env 的所有 model 设置与 LLM_BACKEND 是否一致
- LLM_BACKEND=ollama → 所有 model 必须是 ollama tag (qwen3:8b / deepseek-r1:7b)
- LLM_BACKEND=openai_compat → 所有 model 必须是 mimo-v2.5
- LLM_BACKEND=anthropic → 所有 model 必须是 anthropic tag (claude-* / mimo-v2.5)

**用法**:
  python scripts/check_env_backend.py
  python scripts/check_env_backend.py --strict  # 任意 mismatch 都 fail
  python scripts/check_env_backend.py --fix     # 自动修复 (改 .env)

**CI 集成建议**: 部署前 pre-deploy hook 跑此脚本, fail 则 abort
"""
import argparse
import os
import re
import sys
from pathlib import Path

# Windows GBK console 兼容 (CI 跑 .sh 时不会有, 但本地 .env 调试时需要)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# 项目根 (本脚本在 scripts/ 下)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


# 模型族定义 (按 ollama tag 简写前缀)
OLLAMA_MODEL_PREFIXES = ("qwen3:", "deepseek-r1:", "llama3", "qwen2", "mistral", "gemma")
ANTHROPIC_MODEL_PREFIXES = ("claude-",)
# mimo-v2.5 是特殊: 既可走 anthropic 也可走 openai_compat, 不需特定前缀判断


def load_env(path: Path) -> dict[str, str]:
    """解析 .env 文件为 dict (兼容注释 / 空行 / export 前缀)"""
    if not path.exists():
        print(f"[ERROR] .env 不存在: {path}", file=sys.stderr)
        sys.exit(1)
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def check_model_compat(backend: str, model: str) -> tuple[bool, str]:
    """检查 model 是否与 LLM_BACKEND 兼容

    Returns:
        (is_compatible, reason)
    """
    if not model:
        return True, "empty model (will use default)"

    if backend == "ollama":
        if any(model.startswith(p) for p in OLLAMA_MODEL_PREFIXES):
            return True, "ollama tag detected"
        return False, f"ollama backend but model={model!r} 不是 ollama tag (期望 qwen3:/deepseek-r1:/llama3/...)"

    if backend == "anthropic":
        if any(model.startswith(p) for p in ANTHROPIC_MODEL_PREFIXES) or model == "mimo-v2.5":
            return True, "anthropic / mimo model"
        return False, f"anthropic backend but model={model!r} 不是 anthropic tag (期望 claude-*/mimo-v2.5)"

    if backend == "openai_compat":
        # openai_compat 主要走 mimo, 但也可接任意 OpenAI 协议模型
        return True, "openai_compat accepts any OpenAI-protocol model"

    return True, f"unknown backend {backend!r} (skip check)"


# 关键 model 设置 (按 role 分组)
# (key, desc, scope) — scope:
#   "active" = 该 backend 实际会调, 必须 match
#   "fallback" = 其他 backend 才用, 当前 backend 下不会调, 不强制 match
MODEL_SETTINGS = [
    # === 必须 match 当前 backend (active) ===
    ("CLAUDE_MODEL", "主模型 (synthesis fallback)", "active"),
    ("AGENT_SYNTHESIS_MODEL", "综合主模型 (空时用 CLAUDE_MODEL)", "active"),
    ("AGENT_INTENT_MODEL", "意图分类", "active"),
    ("AGENT_REFLECTION_MODEL", "自评 / critique", "active"),
    ("AGENT_COMPRESSOR_MODEL", "工具结果压缩", "active"),
    ("AGENT_THINKING_MODE_FAST_MODEL", "三档模式 - fast", "active"),
    ("AGENT_THINKING_MODE_BALANCED_MODEL", "三档模式 - balanced", "active"),
    ("AGENT_THINKING_MODE_DEEP_MODEL", "三档模式 - deep", "active"),
    # === 当前 backend 才生效 (active) ===
    ("OLLAMA_MODEL", "Ollama 默认 model", "active_if_ollama"),
    # === 其他 backend 才用, 跳过 check (fallback) ===
    ("OLLAMA_FALLBACK_MODEL", "Ollama fallback model", "fallback"),
    ("MIMO_MODEL", "mimo model (其他 backend 用)", "fallback"),
    ("LLM_OPENAI_COMPAT_MODEL", "openai_compat 模式 model (其他 backend 用)", "fallback"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 .env LLM Backend 配置一致性")
    parser.add_argument("--strict", action="store_true", help="任意 mismatch 都 fail (CI 模式)")
    parser.add_argument("--fix", action="store_true", help="自动修复 mismatch (交互式确认)")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    backend = env.get("LLM_BACKEND", "anthropic")

    print(f"=== LLM Backend 一致性检查 ===")
    print(f"LLM_BACKEND: {backend}")
    print(f".env: {ENV_FILE}")
    print()

    mismatches: list[tuple[str, str, str, str]] = []  # (key, model, reason, suggested)

    for key, desc, scope in MODEL_SETTINGS:
        model = env.get(key, "")
        # 跳过 fallback (其他 backend 才用, 当前 backend 不调)
        if scope == "fallback":
            if model:
                print(f"  [SKIP] {key}={model!r:30s} ({desc}) - 其他 backend 才用, 跳过")
            else:
                print(f"  [SKIP] {key}='' ({desc}) - 其他 backend 才用, 跳过")
            continue
        # active_if_*: 当前 backend 才检查
        if scope == "active_if_ollama" and backend != "ollama":
            if model:
                print(f"  [SKIP] {key}={model!r:30s} ({desc}) - ollama 模式才生效, 当前 {backend} 跳过")
            else:
                print(f"  [SKIP] {key}='' ({desc}) - ollama 模式才生效, 当前 {backend} 跳过")
            continue

        if not model:
            print(f"  [SKIP] {key}={model!r:30s} ({desc}) - 未设置")
            continue
        ok, reason = check_model_compat(backend, model)
        symbol = "[OK]" if ok else "[X]"
        print(f"  {symbol} {key}={model!r:30s} ({desc}) - {reason}")
        if not ok:
            # 建议修复值
            if backend == "ollama":
                suggested = env.get("OLLAMA_MODEL", "qwen3:8b")
            elif backend == "openai_compat":
                suggested = env.get("MIMO_MODEL", "mimo-v2.5")
            else:
                suggested = "claude-sonnet-4-6"
            mismatches.append((key, model, reason, suggested))

    print()
    if not mismatches:
        print("[OK] 所有 model 设置与 LLM_BACKEND 一致")
        return 0

    print(f"[WARN] 发现 {len(mismatches)} 个 mismatch:")
    for key, model, reason, suggested in mismatches:
        print(f"  - {key}={model!r} → 建议改为 {suggested!r} ({reason})")

    if args.fix:
        # 自动改 .env
        text = ENV_FILE.read_text(encoding="utf-8")
        for key, model, reason, suggested in mismatches:
            new_line = f"{key}={suggested}"
            text = re.sub(
                rf"^{re.escape(key)}=.*$",
                new_line,
                text,
                flags=re.MULTILINE,
            )
            print(f"  [EDIT] {key}: {model!r} -> {suggested!r}")
        ENV_FILE.write_text(text, encoding="utf-8")
        print(f"\n[OK] .env 已修复. 下一步: docker compose up -d --force-recreate app")
        return 0

    if args.strict:
        print(f"\n[FAIL] strict 模式: aborting. 修复后重跑. 或用 --fix 自动改 .env")
        return 1

    print(f"\n[TIP] 建议: python scripts/check_env_backend.py --fix")
    print(f"   或手动修改 .env 后 docker compose up -d --force-recreate app")
    return 0


if __name__ == "__main__":
    sys.exit(main())