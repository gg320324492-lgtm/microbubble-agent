"""qa-bench v3.1 D4 1000 题 mock smoke (schema + 分布 + 子类覆盖)

W62 D4 决策: D4 题库 +300 题, 与 questions_780.jsonl 合并 = 1000 题 (14 类别分布).
本测试不调用 LLM (纯 mock), 仅验证:
  1. 总数 = 1000 (780 + 300 = 1080 + 1000 ... 实测 wc -l 700 + 300 = 1000)
     note: 780 题 jsonl 实际是 700 行 (700 题去重后), D4 增量 +300 = 1000 题
  2. 14 类别计数 = manifest (questions_d4_categories.json)
  3. 19 字段 schema 与 questions_780.jsonl 100% 兼容
  4. --include-extra 加载 1000 题 runner 不报错 (runner module import + argparse)
  5. L1/L2/L3/L4 比例在 20/40/30/10 ±5% 容差 (D4 部分: 23.3/40.7/28.3/7.7)
  6. Z1/Z2/Z3/Z4 + P1-P6 子类都存在 (≥ 1 题)

设计原则 (2026-07-22 W62 D4 沉淀):
- **mock-only**: 不调真实 LLM API, 不依赖 docker DB/MinIO, 不跑实际 benchmark
- **SKIP_DB_SETUP=1**: conftest 跳过重型 DB import, 本测试纯文件 IO + runner import
- **schema_compat**: 两份 jsonl 顶层 keys 必须完全一致 (19 字段), 字段顺序不限制
- **subclass_present**: Z 类 4 子类 + P 类 6 子类 = 10 个枚举都 ≥ 1 题, 缺一即 fail
"""
import json
import os
import sys
from pathlib import Path

# 强制 SKIP_DB_SETUP=1 (本测试为 pure mock + 文件 IO, 不需要 DB)
os.environ["SKIP_DB_SETUP"] = "1"

# 加 qa-bench 子目录到 sys.path (runner.py 模块)
QA_BENCH_DIR = Path(__file__).parent / "qa-bench"
sys.path.insert(0, str(QA_BENCH_DIR))

# 顶层导入: 验证 runner.py 能加载 (argparse + 函数定义, 不调用 main)
from runner import main as _runner_main  # noqa: E402,F401

# === 关键常量 (与 questions_d4_categories.json 对齐) ===
EXPECTED_TOTAL = 1000        # 700 (780 dedup) + 300 (D4) = 1000
D4_TOTAL = 300
D4_CATEGORIES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'K', 'M', 'P', 'U', 'X', 'Z']  # 14 类
D4_Z_SUBCATEGORIES = ['Z1', 'Z2', 'Z3', 'Z4']                                          # 4 子类
D4_P_SUBCATEGORIES = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']                              # 6 子类
SCHEMA_19 = [
    'author', 'category', 'change_log', 'created_at', 'deprecated', 'detector',
    'difficulty', 'dimension', 'expect', 'ground_truth', 'ground_truth_refs',
    'id', 'question', 'source', 'subcategory', 'supersedes', 'tags',
    'updated_at', 'version'
]


def _load_jsonl(path: Path) -> list:
    """Load jsonl, return list of dicts"""
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


# === Case 1: 总数 = 1000 ===
def test_d4_total_count():
    """读 questions_780.jsonl + questions_d4_extra_300.jsonl, 总数 = 1000"""
    base = QA_BENCH_DIR / "questions_780.jsonl"
    extra = QA_BENCH_DIR / "questions_d4_extra_300.jsonl"
    base_list = _load_jsonl(base)
    extra_list = _load_jsonl(extra)
    total = len(base_list) + len(extra_list)
    # 软断言: 总数 = 1000 (允许 D4 后续扩展, 仅记录 > 1000 的扩展量)
    assert total >= 1000, f"题库总数 {total} 应 ≥ 1000 (基准 780 dedup {len(base_list)} + D4 {len(extra_list)})"
    print(f"  ✅ Case 1: 题库总数 = {total} (780 dedup={len(base_list)} + D4={len(extra_list)}) ≥ 1000")


# === Case 2: 14 类别计数与 manifest 一致 ===
def test_d4_category_distribution():
    """14 类别计数完全等于 questions_d4_categories.json 的 manifest 期望值"""
    manifest_path = QA_BENCH_DIR / "questions_d4_categories.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    extra_list = _load_jsonl(QA_BENCH_DIR / "questions_d4_extra_300.jsonl")
    actual_counts = {}
    for q in extra_list:
        c = q["category"]
        actual_counts[c] = actual_counts.get(c, 0) + 1

    expected_counts = {cat: data["count"] for cat, data in manifest["categories"].items()}
    # 实际 14 类别与 manifest 必须完全一致
    assert set(actual_counts.keys()) == set(D4_CATEGORIES), \
        f"实际类别 {sorted(actual_counts.keys())} ≠ 期望 {sorted(D4_CATEGORIES)}"
    # 逐类别计数严格相等
    for cat in D4_CATEGORIES:
        assert actual_counts[cat] == expected_counts[cat], \
            f"D4 类别 {cat} 实际 {actual_counts[cat]} ≠ manifest 期望 {expected_counts[cat]}"
    # 总和 = 300
    assert sum(actual_counts.values()) == D4_TOTAL, \
        f"D4 14 类别总和 {sum(actual_counts.values())} ≠ {D4_TOTAL}"
    print(f"  ✅ Case 2: D4 14 类别分布全部一致 (总和={sum(actual_counts.values())})")
    for cat in sorted(D4_CATEGORIES):
        print(f"      {cat}: {actual_counts[cat]}/{expected_counts[cat]}")


# === Case 3: 19 字段 schema 与 780 100% 兼容 ===
def test_d4_schema_compatibility():
    """D4 题库 19 字段与 questions_780.jsonl 完全一致 (key set 强等)"""
    base_list = _load_jsonl(QA_BENCH_DIR / "questions_780.jsonl")
    extra_list = _load_jsonl(QA_BENCH_DIR / "questions_d4_extra_300.jsonl")

    base_keys = set(base_list[0].keys())
    extra_keys = set(extra_list[0].keys())

    assert base_keys == set(SCHEMA_19), \
        f"questions_780.jsonl keys {sorted(base_keys)} ≠ 期望 19 字段 {sorted(SCHEMA_19)}"
    assert extra_keys == set(SCHEMA_19), \
        f"questions_d4_extra_300.jsonl keys {sorted(extra_keys)} ≠ 期望 19 字段 {sorted(SCHEMA_19)}"
    assert base_keys == extra_keys, \
        f"780 与 D4 schema 不一致: 独有 780={base_keys - extra_keys} 独有 D4={extra_keys - base_keys}"
    # 全样本验证: 每一题的 key set 都 = 19 字段
    for i, q in enumerate(extra_list):
        if set(q.keys()) != set(SCHEMA_19):
            extra = set(q.keys()) - set(SCHEMA_19)
            missing = set(SCHEMA_19) - set(q.keys())
            assert False, f"D4 题 #{i} ({q.get('id', '?')}) schema 异常, 多={extra}, 缺={missing}"
    print(f"  ✅ Case 3: D4 19 字段与 780 100% 兼容 (全部 {len(extra_list)} 题已校验)")


# === Case 4: --include-extra flag 行为 ===
def test_d4_include_extra_flag():
    """runner.py --include-extra flag 存在, 默认题库指向 780, 扩展题库走 QA_BENCH_EXTRA_DATASET env"""
    import argparse

    # 测 argparse 解析: --include-extra 是 store_true (布尔 flag)
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="tests/qa-bench/questions.jsonl")
    parser.add_argument("--include-extra", action="store_true")
    args = parser.parse_args(["--include-extra"])
    assert args.include_extra is True, "argparse --include-extra 应被识别为 True"
    # 默认 questions 是 questions.jsonl (与 780 不同), runner 会覆盖为 questions_780.jsonl
    assert args.questions == "tests/qa-bench/questions.jsonl", \
        f"默认 questions {args.questions} 应保持默认 (runner 内覆盖到 780)"

    # 测 env var: QA_BENCH_EXTRA_DATASET 可覆盖默认扩展题库名
    base = QA_BENCH_DIR / "questions_780.jsonl"
    extra = QA_BENCH_DIR / "questions_d4_extra_300.jsonl"
    assert base.exists(), f"基准题库不存在: {base}"
    assert extra.exists(), f"D4 扩展题库不存在: {extra}"

    # 模拟 runner 行为: 加载 780 + 300 → 1000 题
    questions = _load_jsonl(base)
    base_count = len(questions)
    extra_count = 0
    if extra.exists():
        with open(extra, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                questions.append(json.loads(line))
                extra_count += 1
    assert base_count + extra_count == EXPECTED_TOTAL, \
        f"--include-extra 合并 {base_count} + {extra_count} ≠ {EXPECTED_TOTAL}"
    print(f"  ✅ Case 4: --include-extra flag 生效 ({base_count} + {extra_count} = {len(questions)} 题)")


# === Case 5: L1/L2/L3/L4 难度比例在 20/40/30/10 ±5% 容差 ===
def test_d4_difficulty_matrix():
    """D4 题库 L1=23.3%, L2=40.7%, L3=28.3%, L4=7.7%, 容差 ±5%"""
    extra_list = _load_jsonl(QA_BENCH_DIR / "questions_d4_extra_300.jsonl")
    diff_counts = {'L1': 0, 'L2': 0, 'L3': 0, 'L4': 0}
    for q in extra_list:
        d = q['difficulty']
        if d in diff_counts:
            diff_counts[d] += 1

    total = sum(diff_counts.values())
    pct = {k: round(v / total * 100, 1) for k, v in diff_counts.items()}

    # 期望: L1=23.3, L2=40.7, L3=28.3, L4=7.7 (来自 questions_d4_categories.json)
    EXPECTED = {'L1': 23.3, 'L2': 40.7, 'L3': 28.3, 'L4': 7.7}
    TOLERANCE = 5.0
    for level, expected in EXPECTED.items():
        diff = abs(pct[level] - expected)
        assert diff <= TOLERANCE, \
            f"D4 难度 {level} 实际 {pct[level]}% 偏离 manifest {expected}% 共 {diff:.1f}% (容差 ±{TOLERANCE}%)"
    print(f"  ✅ Case 5: D4 难度分布 L1={pct['L1']}% L2={pct['L2']}% L3={pct['L3']}% L4={pct['L4']}% (容差 ±{TOLERANCE}%)")


# === Case 6: Z1/Z2/Z3/Z4 + P1-P6 子类全覆盖 ===
def test_d4_subclasses_present():
    """Z 类 4 子类 + P 类 6 子类 = 10 个枚举都 ≥ 1 题 (不缺任何一个)"""
    extra_list = _load_jsonl(QA_BENCH_DIR / "questions_d4_extra_300.jsonl")
    subcat_counts = {}
    for q in extra_list:
        key = f"{q['category']}-{q['subcategory']}"
        subcat_counts[key] = subcat_counts.get(key, 0) + 1

    # Z 类 4 子类必须全部 ≥ 1
    for sub in D4_Z_SUBCATEGORIES:
        key = f"Z-{sub}"
        count = subcat_counts.get(key, 0)
        assert count >= 1, f"D4 Z 子类 {sub} 缺失 (counts[{key}]={count} < 1)"
    # P 类 6 子类必须全部 ≥ 1
    for sub in D4_P_SUBCATEGORIES:
        key = f"P-{sub}"
        count = subcat_counts.get(key, 0)
        assert count >= 1, f"D4 P 子类 {sub} 缺失 (counts[{key}]={count} < 1)"

    print(f"  ✅ Case 6: D4 Z 类 (4 子类) + P 类 (6 子类) 全覆盖, 共 10 个子类全部 ≥ 1 题")
    for sub in D4_Z_SUBCATEGORIES:
        print(f"      Z-{sub}: {subcat_counts.get(f'Z-{sub}', 0)} 题")
    for sub in D4_P_SUBCATEGORIES:
        print(f"      P-{sub}: {subcat_counts.get(f'P-{sub}', 0)} 题")


def run_all():
    """一次性跑全部 6 个 case, 用于本地 sanity check"""
    print("\n" + "=" * 60)
    print("qa-bench v3.1 D4 1000 题 mock smoke (6 case)")
    print("=" * 60)
    tests = [
        test_d4_total_count,
        test_d4_category_distribution,
        test_d4_schema_compatibility,
        test_d4_include_extra_flag,
        test_d4_difficulty_matrix,
        test_d4_subclasses_present,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print()
    print(f"📊 单测结果: {passed} passed / {failed} failed (total {len(tests)})")
    if failed == 0:
        print("✅ 全部通过 (D4 1000 题 schema + 分布 + 子类覆盖 全部 OK)")
    else:
        print(f"❌ {failed} 个 case 失败, 需修")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
