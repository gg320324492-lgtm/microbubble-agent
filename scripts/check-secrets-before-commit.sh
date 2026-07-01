#!/bin/sh
# scripts/check-secrets-before-commit.sh
#
# 防止 commit 时意外入库 admin JWT / refresh token 等敏感凭据
# 教训: 2026-07-01 commit 6573f2b3 删 tests/qa-bench/_login.json + _token.txt 后沉淀
#
# 两层检测:
#   1. 文件名: staged 文件名匹配敏感模式 (_login.json / _token.txt / _token.json)
#   2. 文件内容: staged 文本文件含 JWT 关键字 "access_token": "eyJ..." (admin 登录 token 特征)
#
# Hard block (不像 dist hook 软自动修):
#   凭据泄露是不可逆风险, 一旦 push 到 GitHub 即使 force-rewrite 也有 reflog 残留
#   必须 hard block 让人显式处理
#
# 不依赖 .gitignore:
#   .gitignore 只护未 tracked 文件, 一旦 `git add -f` 就会被 bypass
#   pre-commit 是最后一道防线, 必须在 add 之后检查
#
# 用法 (pre-commit hook 自动调用, 独立调用也行):
#   sh scripts/check-secrets-before-commit.sh
#
# 新成员 setup (CLAUDE.md 纪律):
#   .git/hooks/pre-commit 已串联调用本脚本 (wrapper 在 .git/hooks/pre-commit)
#   独立调用也行

# ---- 1. 文件名检测 ----
# 检查 staged 文件名是否匹配敏感模式
filename_violations=$(git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null | \
    grep -E '(_login\.(json|txt)|_token\.(txt|json))$' || true)

if [ -n "$filename_violations" ]; then
    echo ""
    echo "❌ [pre-commit] 检测到凭据文件名, 拒绝 commit"
    echo "   这些文件通常含 admin JWT / refresh token, 绝不能入库"
    echo ""
    echo "🚨 违规文件:"
    echo "$filename_violations" | sed 's/^/   /'
    echo ""
    echo "🔧 修复选项:"
    echo "   1) 把凭据移到 git ignored 路径 (scripts/.* 或 .local/)"
    echo "   2) 把真 token 替换成占位符 (\"eyJ...<REDACTED>\")"
    echo "   3) 如果是合法测试 fixture (如 _seed.json 不是凭据),"
    echo "      重命名为不带 _login/_token 前缀的名字"
    echo ""
    echo "🛑 pre-commit 中止, 修复后重试"
    exit 1
fi

# ---- 2. 文件内容检测 ----
# 只对 staged 文本文件扫描 JWT 关键字 (避免误伤大二进制)
# JWT 特征: "access_token": "eyJ..." (eyJ 开头是 JWT base64 标准)
# 跳过 docs/ + CLAUDE.md/CHANGELOG.md/README.md (含 JWT 解释字面量, 不是真凭据)
staged_files=$(git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null | \
    grep -E '\.(json|txt|env|yaml|yml|sh|py|js|ts|md)$' || true)

content_violations=""
if [ -n "$staged_files" ]; then
    for f in $staged_files; do
        # 跳过 docs/ + 顶级 md (含 JWT 字面量解释, 不是真凭据)
        # 注意: 只跳顶级 md, 不跳 *.md (避免 docs/test.md 含真 JWT 被漏检)
        case "$f" in
            docs/*|README.md|CHANGELOG.md|CLAUDE.md) continue ;;
        esac
        # 读取 staged 版本
        content=$(git show ":$f" 2>/dev/null || true)
        [ -z "$content" ] && continue
        # 检测两类 JWT 模式:
        #   1. JSON 风格:    "access_token": "eyJ..." (CLAUDE.md / 配置文件常见)
        #   2. 赋值风格:     access_token = "eyJ..." (Python / Shell 常见)
        # eyJ 开头 + 长 base64 是 JWT 标准签名
        if echo "$content" | grep -qE '("(access_token|refresh_token)"[[:space:]]*:[[:space:]]*"|(access_token|refresh_token)[[:space:]]*[=:][[:space:]]*["'\''])eyJ[A-Za-z0-9_-]{20,}'; then
            content_violations="${content_violations}\n   ${f}"
        fi
    done
fi

if [ -n "$content_violations" ]; then
    echo ""
    echo "❌ [pre-commit] 检测到文件内容含 admin JWT 关键字, 拒绝 commit"
    echo "   \"access_token\": \"eyJ...\" 或 \"refresh_token\": \"eyJ...\" 是 admin 登录 token"
    echo ""
    echo "🚨 违规文件:"
    printf '%b\n' "$content_violations"
    echo ""
    echo "🔧 修复选项:"
    echo "   1) 凭据移到 git ignored 路径"
    echo "   2) 把真 token 替换成占位符"
    echo "   3) 如果是文档字符串 (非真实凭据), 改写 escape"
    echo ""
    echo "🛑 pre-commit 中止, 修复后重试"
    exit 1
fi

exit 0