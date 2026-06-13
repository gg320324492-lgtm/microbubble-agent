#!/usr/bin/env bash
# check_typing_imports.sh — 扫描 Python 文件中缺失的 typing import
#
# 背景：CLAUDE.md 519/527 行铁律 — Python 模块加载时类型注解会执行，
# 缺 typing import（如用了 Dict 但没 `from typing import Dict`）会让整个模块
# 加载失败 → 工具/服务一调就报。Docker 模块缓存会掩盖该 bug 数天。
#
# 用法：
#   bash scripts/check_typing_imports.sh                  # 扫描默认目录
#   bash scripts/check_typing_imports.sh app/agent        # 指定目录
#
# 退出码：0 = 全部 OK；1 = 发现缺失（输出文件名）
#
# 集成：pre-commit hook、CI、deploy-auto.sh 部署前

set -uo pipefail

DIRS="${@:-app/agent app/services app/api}"
TYPES="Dict List Tuple Optional Union Set FrozenSet Type Callable Iterator AsyncIterator Awaitable Coroutine Mapping Sequence Iterable Generator AsyncGenerator"

found_missing=0
total_scanned=0

for dir in $DIRS; do
    if [ ! -d "$dir" ]; then
        echo "WARN: 目录不存在: $dir" >&2
        continue
    fi
    while IFS= read -r -d '' file; do
        total_scanned=$((total_scanned + 1))
        # 跳过空文件
        if [ ! -s "$file" ]; then
            continue
        fi
        for type_name in $TYPES; do
            # 只匹配作为类型注解的用法（: TypeName 或 -> TypeName 或 [TypeName...]）
            # 避免误报：忽略字符串字面量、变量名等
            if grep -qE "(:\s*${type_name}\b|->\s*${type_name}\b|\[${type_name}\b|,\s*${type_name}\b)" "$file" 2>/dev/null; then
                # 该文件使用了 type_name，检查是否 import
                # 模式1: from typing import ... TypeName ... (多行括号也覆盖)
                # 模式2: import typing 后用 typing.TypeName
                if ! grep -qE "from typing import .*\b${type_name}\b|import typing|from typing import \(" "$file" 2>/dev/null; then
                    # 进一步排除：可能是字符串注解 "TypeName"
                    actual_uses=$(grep -cE "(:\s*${type_name}\b|->\s*${type_name}\b|\[${type_name}\b)" "$file" 2>/dev/null || echo 0)
                    if [ "$actual_uses" -gt 0 ]; then
                        echo "MISSING typing.${type_name} in: $file"
                        found_missing=$((found_missing + 1))
                    fi
                fi
            fi
        done
    done < <(find "$dir" -type f -name "*.py" -not -path "*/__pycache__/*" -not -path "*/migrations/*" -print0)
done

echo ""
echo "扫描了 $total_scanned 个文件"
if [ "$found_missing" -gt 0 ]; then
    echo "❌ 发现 $found_missing 处缺失的 typing import"
    echo ""
    echo "修复方法：在文件顶部添加缺失的 import，例如："
    echo "  from typing import Dict, List, Optional, Tuple"
    exit 1
fi
echo "✅ 所有 typing 注解的 import 都齐全"
exit 0
