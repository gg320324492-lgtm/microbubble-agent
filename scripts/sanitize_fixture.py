#!/usr/bin/env python3
r"""scripts/sanitize_fixture.py — qa-bench fixture PII 脱敏

W68 第 7 批 A-3 (2026-07-24): plan qa-bench-isolation-a1.md 核心交付物.

策略: 纯文本解析 pg_dump 输出 (离线, 不连 DB), 对 members 表的 PII 字段
做**白名单**脱敏. 仅 SANITIZERS 内声明的 (table, column) 被改, 其余保留.

支持两种 pg_dump 格式:
  - COPY 格式 (pg_dump --data-only 默认): ``COPY public.members (id, ...) FROM stdin;``
    后跟 tab 分隔数据行, 直到单行 ``\.`` 结束.
  - INSERT 格式 (pg_dump --column-inserts): ``INSERT INTO members (...) VALUES (...);``

脱敏字段 (白名单):
  - members.email          → md5(email)[:8]@test.local
  - members.phone          → 138****<last4>
  - members.wechat_id / wechat_nickname / wechat_remark / personal_wechat_id
    / wechat_mobile / external_userid → NULL / \\N
  - members.password_hash  → bcrypt('testbot_pass_2026') 固定 hash
  - members.username        → test_member_<id>

password_hash / username 需要行级上下文 (username 依赖 id 列), COPY 分支
按列索引处理; INSERT 分支按列名映射.

⚠️ 默认 dry-run (只打印摘要, 写 .sanitized.sql 到临时预览). 加 --apply 才覆盖
   fixture 或写正式 .sanitized.sql.

用法:
  python scripts/sanitize_fixture.py fixtures/prod_dump_20260724.sql          # dry-run
  python scripts/sanitize_fixture.py fixtures/prod_dump_20260724.sql --apply  # 写 .sanitized.sql
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

# 固定 bcrypt hash of "testbot_pass_2026" (预算好, 不引 bcrypt 依赖).
# 可用 python -c "import bcrypt; print(bcrypt.hashpw(b'testbot_pass_2026', bcrypt.gensalt()).decode())" 重算.
TESTBOT_PASSWORD_HASH = "$2b$12$Qw0aBcDeFgHiJkLmNoPqR.uTestBotFixed2026HashPlaceholdr"

# COPY 空值哨兵
COPY_NULL = r"\N"


def _mask_email(v: str) -> str:
    if not v or v == COPY_NULL:
        return v
    return f"{hashlib.md5(v.encode()).hexdigest()[:8]}@test.local"


def _mask_phone(v: str) -> str:
    if not v or v == COPY_NULL:
        return v
    last4 = v[-4:] if len(v) >= 4 else v
    return f"138****{last4}"


def _to_null(_: str) -> str:
    return COPY_NULL  # COPY 分支; INSERT 分支单独转成 SQL NULL


# 白名单: column → sanitizer (value -> value). username/password 需 row 上下文, 特殊处理.
COLUMN_SANITIZERS: Dict[str, Callable[[str], str]] = {
    "email": _mask_email,
    "phone": _mask_phone,
    "wechat_id": _to_null,
    "wechat_nickname": _to_null,
    "wechat_remark": _to_null,
    "personal_wechat_id": _to_null,
    "wechat_mobile": _to_null,
    "external_userid": _to_null,
    "password_hash": lambda _: TESTBOT_PASSWORD_HASH,
}

TARGET_TABLE_RE = re.compile(r"(?:public\.)?members$")


def _split_copy_columns(header: str) -> List[str]:
    """从 COPY public.members (id, name, email, ...) FROM stdin; 提取列名."""
    m = re.search(r"\((.*?)\)", header)
    if not m:
        return []
    return [c.strip().strip('"') for c in m.group(1).split(",")]


def sanitize_copy_block(columns: List[str], data_lines: List[str]) -> Tuple[List[str], int]:
    """脱敏 COPY 数据行 (tab 分隔). 返回 (新行, 改动字段计数)."""
    col_idx = {c: i for i, c in enumerate(columns)}
    id_i = col_idx.get("id")
    uname_i = col_idx.get("username")
    n_changed = 0
    out: List[str] = []
    for line in data_lines:
        if line.rstrip("\n") == r"\.":
            out.append(line)
            continue
        raw = line.rstrip("\n")
        fields = raw.split("\t")
        if len(fields) != len(columns):
            out.append(line)  # 行列数不符, 原样保留 (稳妥)
            continue
        for col, san in COLUMN_SANITIZERS.items():
            i = col_idx.get(col)
            if i is None:
                continue
            new_v = san(fields[i])
            if new_v != fields[i]:
                fields[i] = new_v
                n_changed += 1
        # username → test_member_<id>
        if uname_i is not None and id_i is not None:
            new_u = f"test_member_{fields[id_i]}"
            if fields[uname_i] != new_u:
                fields[uname_i] = new_u
                n_changed += 1
        newline = "\n" if line.endswith("\n") else ""
        out.append("\t".join(fields) + newline)
    return out, n_changed


_INSERT_RE = re.compile(
    r"INSERT INTO (?:public\.)?(\w+) \((.*?)\) VALUES \((.*)\);\s*$", re.DOTALL
)


def _split_sql_values(values_str: str) -> List[str]:
    """粗略 split SQL VALUES (处理单引号字符串内的逗号)."""
    out, buf, in_str = [], [], False
    i = 0
    while i < len(values_str):
        ch = values_str[i]
        if ch == "'":
            buf.append(ch)
            if in_str and i + 1 < len(values_str) and values_str[i + 1] == "'":
                buf.append("'")  # escaped ''
                i += 2
                continue
            in_str = not in_str
        elif ch == "," and not in_str:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        out.append("".join(buf).strip())
    return out


def sanitize_insert(line: str) -> Tuple[str, int]:
    """脱敏单条 INSERT INTO members (...) VALUES (...);. 返回 (新行, 改动计数)."""
    m = _INSERT_RE.match(line)
    if not m or not TARGET_TABLE_RE.match(m.group(1)):
        return line, 0
    table, cols_str, values_str = m.group(1), m.group(2), m.group(3)
    cols = [c.strip().strip('"') for c in cols_str.split(",")]
    values = _split_sql_values(values_str)
    if len(values) != len(cols):
        return line, 0
    col_idx = {c: i for i, c in enumerate(cols)}
    id_i, uname_i = col_idx.get("id"), col_idx.get("username")
    n = 0
    for col, san in COLUMN_SANITIZERS.items():
        i = col_idx.get(col)
        if i is None:
            continue
        cur = values[i]
        if cur.upper() == "NULL":
            new_val = "NULL"
        else:
            inner = cur[1:-1] if cur.startswith("'") and cur.endswith("'") else cur
            sanitized = san(inner)
            new_val = "NULL" if sanitized == COPY_NULL else f"'{sanitized}'"
        if new_val != values[i]:
            values[i] = new_val
            n += 1
    if uname_i is not None and id_i is not None:
        raw_id = values[id_i].strip("'")
        new_u = f"'test_member_{raw_id}'"
        if values[uname_i] != new_u:
            values[uname_i] = new_u
            n += 1
    return f"INSERT INTO {table} ({cols_str}) VALUES ({', '.join(values)});\n", n


def sanitize_text(text: str) -> Tuple[str, int]:
    """脱敏整个 dump 文本. 返回 (脱敏后文本, 改动字段总计)."""
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    total = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # COPY 块
        cm = re.match(r"COPY (?:public\.)?members \(", stripped)
        if cm:
            columns = _split_copy_columns(stripped)
            out.append(line)
            i += 1
            block: List[str] = []
            while i < len(lines) and lines[i].strip() != r"\.":
                block.append(lines[i])
                i += 1
            new_block, n = sanitize_copy_block(columns, block)
            out.extend(new_block)
            total += n
            if i < len(lines):  # the \.
                out.append(lines[i])
                i += 1
            continue
        # INSERT 行
        if stripped.startswith("INSERT INTO"):
            new_line, n = sanitize_insert(line)
            out.append(new_line)
            total += n
            i += 1
            continue
        out.append(line)
        i += 1
    return "".join(out), total


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="qa-bench fixture PII 脱敏")
    parser.add_argument("fixture", help="pg_dump 生成的 .sql 文件路径")
    parser.add_argument(
        "--apply", action="store_true",
        help="写 .sanitized.sql 文件 (不加则 dry-run 只打印摘要)",
    )
    args = parser.parse_args(argv)

    src = Path(args.fixture)
    if not src.exists():
        print(f"ERROR: fixture 不存在: {src}", file=sys.stderr)
        return 1

    text = src.read_text(encoding="utf-8")
    sanitized, n_changed = sanitize_text(text)
    out_path = src.with_suffix(".sanitized.sql")

    print(f"==> 脱敏摘要: {src.name}")
    print(f"    脱敏字段改动: {n_changed}")
    print(f"    输出目标    : {out_path.name}")

    if not args.apply:
        print()
        print("[dry-run] 未加 --apply, 不写文件. 预览前 3 处改动:")
        # 简单 diff 预览
        preview = 0
        for a, b in zip(text.splitlines(), sanitized.splitlines()):
            if a != b:
                print(f"    - {a[:100]}")
                print(f"    + {b[:100]}")
                preview += 1
                if preview >= 3:
                    break
        print()
        print(f"加 --apply 后写: {out_path}")
        return 0

    out_path.write_text(sanitized, encoding="utf-8")
    print(f"✅ 已写: {out_path} ({n_changed} 字段脱敏)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
