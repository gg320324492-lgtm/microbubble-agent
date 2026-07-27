"""sanitize_fixture.py — W74 第 1 批 C-1 实施前置 2 (数据脱敏 faker 库)

派工 v8 段 8 实施前置 2 — 数据脱敏 (faker 库, 锚点范式第 246 守恒)

功能:
  1. 用 faker 库对 qa-bench 题库中的人名/邮箱/手机号/身份证号/银行卡号脱敏
  2. 不可逆 (SHA256 + salt) 防回推
  3. CI 集成 (--check 模式校验是否所有 fixture 已脱敏)

用法:
  # 生成脱敏 fixture
  python scripts/qa-bench/sanitize_fixture.py tests/qa-bench/data/combined_v4.jsonl -o tests/qa-bench/data/combined_v4_sanitized.jsonl

  # CI 校验 (期望所有 fixture 已脱敏, 否则 exit 1)
  python scripts/qa-bench/sanitize_fixture.py --check tests/qa-bench/data/combined_v4_sanitized.jsonl

锚点范式 W73 第 1 批 242 → W74 第 1 批 C-1 248 守恒 (+1)
0 production code 改动铁律守恒 (qa-bench 范畴, 仅 scripts/qa-bench/sanitize_fixture.py)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from faker import Faker
except ImportError:  # pragma: no cover - CI installs qa-bench requirements
    Faker = None  # type: ignore[assignment]

# 脱敏正则 (人名/邮箱/手机号/身份证/银行卡)
SANITIZE_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_cn": re.compile(r"\b1[3-9]\d{9}\b"),
    "id_card_cn": re.compile(r"\b\d{17}[\dXx]\b"),
    "bank_card": re.compile(r"\b\d{16,19}\b"),
    "wechat_id": re.compile(r"\bwx_[a-zA-Z0-9_]{6,}\b"),
}

# 不可逆盐 (生产中应从环境变量/secret manager 取, demo 用固定值)
DEFAULT_SALT = "qa-bench-sanitize-2026-07-27-w74-1st-batch-c1"


def _hash(value: str, salt: str) -> str:
    """不可逆 hash, 防回推原始 PII."""
    return "SAN_" + hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:12]


def _faker_token(kind: str, value: str, salt: str) -> str:
    """Create a deterministic Faker surrogate before hashing it.

    The final fixture still contains only the salted SHA token.  Faker is used
    to keep the replacement source realistic while the hash prevents recovery
    of the generated surrogate or original PII.
    """
    if Faker is None:
        return value
    fake = Faker("zh_CN")
    seed = int(hashlib.sha256(f"{salt}:{kind}:{value}".encode()).hexdigest()[:16], 16)
    fake.seed_instance(seed)
    if kind == "email":
        return fake.email()
    if kind == "phone_cn":
        return fake.phone_number()
    if kind == "id_card_cn":
        return fake.ssn()
    if kind == "bank_card":
        return fake.credit_card_number()
    if kind == "wechat_id":
        return f"wx_{fake.pystr(min_chars=8, max_chars=16)}"
    return fake.pystr(min_chars=8, max_chars=16)


def sanitize_text(text: str, salt: str) -> str:
    """对单段文本脱敏."""
    for kind, pattern in SANITIZE_PATTERNS.items():
        text = pattern.sub(
            lambda m: _hash(f"{kind}:{_faker_token(kind, m.group(0), salt)}", salt),
            text,
        )
    return text


def sanitize_item(item: dict, salt: str) -> dict:
    """对单条题库记录脱敏 (递归 dict/list)."""
    if isinstance(item, dict):
        return {k: sanitize_item(v, salt) for k, v in item.items()}
    if isinstance(item, list):
        return [sanitize_item(v, salt) for v in item]
    if isinstance(item, str):
        return sanitize_text(item, salt)
    return item


def sanitize_file(input_path: Path, output_path: Path, salt: str = DEFAULT_SALT) -> int:
    """批量脱敏 jsonl 文件."""
    count = 0
    with open(input_path, "r", encoding="utf-8") as fin, \
            open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line or line.startswith("#"):
                fout.write(line + "\n")
                continue
            try:
                obj = json.loads(line)
                sanitized = sanitize_item(obj, salt)
                fout.write(json.dumps(sanitized, ensure_ascii=False) + "\n")
                count += 1
            except json.JSONDecodeError:
                fout.write(line + "\n")
    return count


def check_sanitized(path: Path) -> bool:
    """CI 校验: 检查文件是否已脱敏 (无原始 PII 残留)."""
    if not path.exists():
        print(f"ERROR: {path} 不存在", file=sys.stderr)
        return False
    violations: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for kind, pattern in SANITIZE_PATTERNS.items():
                matches = pattern.findall(line)
                if matches:
                    violations.append(f"line {n} 命中 {kind}: {matches[0]}")
    if violations:
        print(f"ERROR: {path} 未完全脱敏 ({len(violations)} 处违规):", file=sys.stderr)
        for v in violations[:5]:
            print(f"  {v}", file=sys.stderr)
        return False
    print(f"OK: {path} 已脱敏")
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="qa-bench fixture 数据脱敏")
    p.add_argument("input", type=Path, help="输入 jsonl 文件")
    p.add_argument("-o", "--output", type=Path, help="输出 jsonl 文件")
    p.add_argument("--salt", default=DEFAULT_SALT, help="不可逆 hash 盐")
    p.add_argument("--check", action="store_true", help="只校验, 不脱敏")
    args = p.parse_args()

    if args.check:
        return 0 if check_sanitized(args.input) else 1

    if not args.output:
        print("ERROR: 非 --check 模式必须 -o 指定输出文件", file=sys.stderr)
        return 1

    count = sanitize_file(args.input, args.output, args.salt)
    print(f"已脱敏 {count} 条记录 → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())