#!/usr/bin/env python3
"""Prisma 1 表试点 mock 测试 — W-N-P3-A-POC 试点

派工 brief 严禁 pip install prisma, 本脚本纯 Python stdlib 解析 schema.prisma
字段并断言关键字段/索引/类型映射. 不依赖 prisma 真实安装.

用法:
    python scripts/prisma_poc_test.py

返回:
    PASS: 全部断言通过
    FAIL: 任一断言失败
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "prisma" / "schema.prisma"
MIRROR_PATH = Path(__file__).parent.parent / "app" / "models" / "prisma_dft_jobs.py"


def parse_schema() -> dict:
    """解析 schema.prisma 字段与索引"""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"schema.prisma not found: {SCHEMA_PATH}")
    text = SCHEMA_PATH.read_text(encoding="utf-8")

    # 抽取 model DftJob { ... } 块 (DOTALL 跨行, 用 @@map 行为锚避免 Json 默认 {"{}"} 干扰)
    model_match = re.search(r"model\s+\w+\s*\{(.*?)\n\}", text, re.DOTALL)
    if not model_match:
        raise ValueError("No model block found in schema.prisma")

    body = model_match.group(1)
    fields = {}
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        # 字段定义: name Type? @attr @attr (? 为可空)
        m = re.match(r"^(\w+)\s+(\w+)(\?)?\s*(.*)$", line)
        if m and not line.startswith("@@"):
            fields[m.group(1)] = {
                "type": m.group(2),
                "nullable": m.group(3) == "?",
                "attrs": m.group(4).strip(),
            }
    return fields


def parse_mirror_docstring() -> dict:
    """从 prisma_dft_jobs.py docstring 抽取 schema 镜像表"""
    if not MIRROR_PATH.exists():
        raise FileNotFoundError(f"prisma_dft_jobs.py not found: {MIRROR_PATH}")
    text = MIRROR_PATH.read_text(encoding="utf-8")

    # 找 model DftJob 块 (mirror 用 // 注释 + # end 边界, 不用 {})
    mirror_match = re.search(r"model\s+DftJob[^\n]*\n(.*?)#\s*end", text, re.DOTALL)
    if not mirror_match:
        raise ValueError("No DftJob model block in prisma_dft_jobs.py mirror")
    body = mirror_match.group(1)
    fields = {}
    for line in body.split("\n"):
        # mirror 用 # 注释嵌套, 去掉前导 # 注释符
        line = line.lstrip("#").strip()
        if not line or line.startswith("//"):
            continue
        m = re.match(r"^(\w+)\s+(\w+)(\?)?\s*(.*)$", line)
        if m and not line.startswith("@@"):
            fields[m.group(1)] = {
                "type": m.group(2),
                "nullable": m.group(3) == "?",
                "attrs": m.group(4).strip(),
            }
    return fields


def assert_field_type(fields: dict, name: str, expected_type: str, label: str) -> bool:
    """断言字段类型一致"""
    if name not in fields:
        print(f"  [FAIL] {label}: 字段 {name} 缺失")
        return False
    actual = fields[name]["type"]
    if actual != expected_type:
        print(f"  [FAIL] {label}: 字段 {name} 类型 {actual} != 期望 {expected_type}")
        return False
    print(f"  [PASS] {label}: 字段 {name} 类型 {actual}")
    return True


def assert_field_attrs(fields: dict, name: str, expected_substr: str, label: str) -> bool:
    """断言字段 attrs 包含期望子串"""
    if name not in fields:
        print(f"  [FAIL] {label}: 字段 {name} 缺失")
        return False
    attrs = fields[name]["attrs"]
    if expected_substr not in attrs:
        print(f"  [FAIL] {label}: 字段 {name} attrs {attrs} 不含 {expected_substr}")
        return False
    print(f"  [PASS] {label}: 字段 {name} attrs 含 {expected_substr}")
    return True


def assert_required_fields(fields: dict, required: list, label: str) -> bool:
    """断言必填字段全部存在"""
    ok = True
    for fname in required:
        if fname not in fields:
            print(f"  [FAIL] {label}: 必填字段 {fname} 缺失")
            ok = False
        else:
            print(f"  [PASS] {label}: 必填字段 {fname} 存在")
    return ok


def main() -> int:
    print("=" * 60)
    print("W-N-P3-A-POC +1 Prisma 1 表试点 mock 测试")
    print("=" * 60)

    all_ok = True

    # Step 1: 解析 schema.prisma
    print("\n[Step 1] 解析 prisma/schema.prisma")
    try:
        schema_fields = parse_schema()
        print(f"  字段: {list(schema_fields.keys())}")
    except Exception as e:
        print(f"  [FAIL] 解析失败: {e}")
        return 1

    # Step 2: 解析 mirror docstring
    print("\n[Step 2] 解析 app/models/prisma_dft_jobs.py mirror")
    try:
        mirror_fields = parse_mirror_docstring()
        print(f"  字段: {list(mirror_fields.keys())}")
    except Exception as e:
        print(f"  [FAIL] 解析失败: {e}")
        return 1

    # Step 3: 必填字段断言
    print("\n[Step 3] 必填字段断言 (schema.prisma)")
    required = ["id", "userId", "tool", "smiles", "params", "status",
                "result", "logPath", "errorMsg", "submitTime", "finishTime"]
    if not assert_required_fields(schema_fields, required, "schema.prisma"):
        all_ok = False

    # Step 4: 必填字段断言 (mirror)
    print("\n[Step 4] 必填字段断言 (mirror)")
    if not assert_required_fields(mirror_fields, required, "mirror"):
        all_ok = False

    # Step 5: 类型映射断言
    print("\n[Step 5] 字段类型映射断言")
    type_map = {
        "id": "String",
        "userId": "Int",
        "tool": "String",
        "smiles": "String",
        "params": "Json",
        "status": "String",
        "result": "Json",
        "logPath": "String",
        "errorMsg": "String",
        "submitTime": "DateTime",
        "finishTime": "DateTime",
    }
    for fname, ftype in type_map.items():
        if not assert_field_type(schema_fields, fname, ftype, "schema.prisma"):
            all_ok = False
        if not assert_field_type(mirror_fields, fname, ftype, "mirror"):
            all_ok = False

    # Step 6: 字段 attrs 断言 (schema.prisma 字段类型映射实战)
    print("\n[Step 6] 字段 attrs 断言")
    attrs_map = {
        "id": "@db.Uuid",
        "submitTime": "Timestamptz",
        "userId": "@map",  # @map("user_id") 标识 snake_case 映射
    }
    for fname, expected in attrs_map.items():
        if not assert_field_attrs(schema_fields, fname, expected, "schema.prisma"):
            all_ok = False
        if not assert_field_attrs(mirror_fields, fname, expected, "mirror"):
            all_ok = False
    # 特定字段: params 是 Json 类型 (Step 5 已断言), attrs 含 @default("{}")
    if not assert_field_attrs(schema_fields, "params", "@default", "schema.prisma"):
        all_ok = False
    if not assert_field_attrs(mirror_fields, "params", "@default", "mirror"):
        all_ok = False
    if not assert_field_type(schema_fields, "params", "Json", "schema.prisma"):
        all_ok = False
    if not assert_field_type(mirror_fields, "params", "Json", "mirror"):
        all_ok = False

    # Step 7: 字段数量守恒
    print("\n[Step 7] 字段数量守恒")
    if set(schema_fields.keys()) != set(mirror_fields.keys()):
        print(f"  [FAIL] schema 字段 {set(schema_fields.keys())} != mirror {set(mirror_fields.keys())}")
        all_ok = False
    else:
        print(f"  [PASS] schema 与 mirror 字段完全一致 ({len(schema_fields)} 字段)")

    # 总结
    print("\n" + "=" * 60)
    if all_ok:
        print("[RESULT] 全部断言 PASS")
        return 0
    else:
        print("[RESULT] 部分断言 FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
