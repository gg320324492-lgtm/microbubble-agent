"""ci_secret_check.py — W74 第 1 批 C-1 实施前置 4 (CI secret 检查)

派工 v8 段 8 实施前置 4 — qa-bench CI secret 守门 (锚点范式第 247 守恒)

校验规则:
  1. 必填 secrets: MIMO_API_KEY (mimo cloud) + POSTGRES_PASSWORD (test DB)
  2. 禁止 hardcoded secret: 扫描 .github/workflows/ + scripts/qa-bench/ 是否有明文 key
  3. secret 长度校验: MIMO_API_KEY >= 20 chars
  4. .env 不入 git: 检查 .gitignore 含 .env + .env.qa-bench

用法 (CI 步骤):
  python scripts/qa-bench/ci_secret_check.py

退出码: 0 = 通过, 1 = 失败 (CI 红)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# 必填 secrets (CI env 必须有)
REQUIRED_SECRETS: dict[str, dict[str, object]] = {
    "MIMO_API_KEY": {"min_length": 20, "reason": "mimo cloud 推理必需"},
    "POSTGRES_PASSWORD": {"min_length": 8, "reason": "test DB stack 启动必需"},
}

# 扫描 hardcoded secret 模式 (前 8 位 prefix 即视作泄漏)
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "mimo_api_key": re.compile(r'mimo[-_]?(?:api[-_]?)?key[\s:=]+[a-zA-Z0-9_-]{16,}'),
    "openai_api_key": re.compile(r"sk-[a-zA-Z0-9]{32,}"),
    "anthropic_api_key": re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),
    "postgres_password": re.compile(r"(?:postgres|pg)[-_]?password[\s:=]+\S{8,}", re.IGNORECASE),
}

# 扫描路径 (不扫 secrets/ / .git/)
SCAN_PATHS: list[str] = [
    ".github/workflows/",
    "scripts/qa-bench/",
]

# 例外 (本文件自身, 含模式字符串)
SCAN_EXCEPTIONS: list[str] = [
    "scripts/qa-bench/ci_secret_check.py",
]


def check_required_secrets() -> list[str]:
    """CI env 必填 secret 守门."""
    violations: list[str] = []
    for name, rule in REQUIRED_SECRETS.items():
        val = os.environ.get(name, "")
        if not val:
            violations.append(f"{name} 未设置 (reason: {rule.get('reason', '')})")
        elif len(val) < rule.get("min_length", 1):
            violations.append(f"{name} 长度 < {rule.get('min_length')} (实际 {len(val)})")
    return violations


def check_hardcoded_secrets() -> list[str]:
    """扫描代码 hardcoded secret 泄漏."""
    violations: list[str] = []
    repo_root = Path(__file__).resolve().parent.parent.parent
    for scan_path in SCAN_PATHS:
        full_path = repo_root / scan_path
        if not full_path.exists():
            continue
        for f in full_path.rglob("*"):
            if not f.is_file():
                continue
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            if rel in SCAN_EXCEPTIONS:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for kind, pattern in SECRET_PATTERNS.items():
                if pattern.search(content):
                    violations.append(f"{rel} 命中 hardcoded {kind} (regex 匹配)")
    return violations


def check_gitignore() -> list[str]:
    """检查 .gitignore 含 .env + .env.qa-bench."""
    violations: list[str] = []
    repo_root = Path(__file__).resolve().parent.parent.parent
    gi = repo_root / ".gitignore"
    if not gi.exists():
        return [".gitignore 不存在"]
    content = gi.read_text(encoding="utf-8", errors="ignore")
    for required in (".env", ".env.qa-bench", ".env.*"):
        # 检查 .env.qa-bench 命中 .env.* 模式即可
        if required == ".env.qa-bench":
            if not re.search(r"\.env\.\*", content) and ".env.qa-bench" not in content:
                violations.append(f".gitignore 未排除 {required}")
        elif required not in content:
            violations.append(f".gitignore 未排除 {required}")
    return violations


def main() -> int:
    all_violations: list[str] = []
    all_violations.extend(check_required_secrets())
    all_violations.extend(check_hardcoded_secrets())
    all_violations.extend(check_gitignore())
    if all_violations:
        print("ERROR: qa-bench CI secret 检查违规:", file=sys.stderr)
        for v in all_violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("OK: qa-bench CI secret 检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())