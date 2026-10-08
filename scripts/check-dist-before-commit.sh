#!/bin/sh
# scripts/check-dist-before-commit.sh
#
# pre-commit dist 校验 — 2026-10-07 硬化 (收尾规划 §4.11 遗留③, 复检官拍板"逐项做")
#
# 背景: 本脚本旧版对漏 add web/dist 是「软性自动补 add」—— 会把磁盘上未提交的
# dist 强塞进当前 commit, 制造原子 src+dist; 且不校验 dist 与源的一致性 (stale
# dist 照样过)。这与 CLAUDE.md W100 R-5 两段式纪律 (先提交源 → npm run build →
# 再提交 dist) 相抵触: 原子提交会让 BUILD_TIMESTAMP 滞后一个源提交, 该提交上
# 重建 ≠ 入库 dist (e50631024 实战)。
#
# 现行两条硬规则 (与 web/scripts/build-id.mjs 单一真源配合):
#   规则 1 禁原子 src+dist: 同一 commit 同时暂存「构建源输入」(SOURCE_INPUTS,
#          由 build-id.mjs 给出) 与 web/dist 任何文件 → 拦截, 指引两段式。
#   规则 2 stale dist 硬校验: commit 含 web/dist 时, 按 SOURCE_INPUTS 算法从
#          **暂存区 (index)** 重算 BUILD_ID, 与 dist 内嵌 id=<12hex> 比对,
#          不一致 → 拦截 (报重算值 vs dist 值)。
# 自动补 add 收敛: 只有本次 commit **未暂存任何构建源输入** (dist-only 提交
#   漏 add 的场景) 才允许自动补齐; 源输入已暂存时绝不塞入 (那是原子提交制造机),
#   改为打印两段式指引后放行。
#
# 保留的既有语义 (未动):
#   - token-orphan 硬拦 (web/src 有暂存改动时, CLAUDE.md v73)
#   - staged index.html ↔ 磁盘资产配套硬拦 (2026-09-12 hard gate B)
#   - 拒绝非 production 压缩产物硬拦 (2026-09-30 S3.4, 行数判据)
#   - secrets / design-tokens drift 由 .git/hooks/pre-commit 链在前后执行, 不在本脚本
#
# 逃生口: git commit --no-verify (git 原生, 仅限复检官/主拍批准场景)
#
# 用法 (pre-commit hook 自动调用; 也可 sh scripts/check-dist-before-commit.sh 独立跑)
# 新成员 setup: bash scripts/setup-hooks.sh (串联 secrets → dist → drift)

# set +e: 不要 set -e, 否则内部 grep 无匹配返回 1 会短路整个 hook (W100 +75c 教训)
set +e

# 总耗时统计 (W100 +75c)
START_TIME=$(date +%s)

# 统一从仓库根执行 (独立调用时 CWD 不受控 — 借鉴 drift 脚本教训)
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
    echo "❌ [pre-commit] 不在 git 仓库里, dist 校验无法执行"
    exit 1
fi
cd "$REPO_ROOT" || exit 1

# ================================================================
# hard gate B: staged index.html 引用的资产必须存在 (2026-09-12
# index-Dm-g8UdN.js 404 事故沉淀, commit 9bf09f01b) — 既有语义原样保留
# ================================================================
hard_verify_dist_refs() {
    # 只在 web/dist/index.html 有 staged 改动时校验 (纯后端/docs 提交零开销)
    if ! git diff --cached --name-only -- 'web/dist/index.html' 2>/dev/null | grep -q .; then
        return 0
    fi
    MISSING=""
    for ref in $(git show :web/dist/index.html 2>/dev/null | grep -oE 'assets/[A-Za-z0-9_.-]+\.(js|css)' | sort -u); do
        [ -f "web/dist/$ref" ] || MISSING="$MISSING $ref"
    done
    if [ -n "$MISSING" ]; then
        echo ""
        echo "❌ [pre-commit] staged index.html 引用的资产在本地 web/dist 缺失:$MISSING"
        echo "   大概率: index.html 与 assets 来自不同次 build, 或漏 git add -f web/dist/"
        echo "   修复: cd web && npm run build && git add -f web/dist/ 重新 stage"
        echo "   (确要跳过: git commit --no-verify)"
        exit 1
    fi
}

# ================================================================
# 拒绝未压缩产物 (2026-09-30 S3.4 新增, 既有语义原样保留)
# 判据用行数: production 11 行 / NODE_ENV=test 构建 50 行 → 阈值 30 (2026-10-01 实测)
# ================================================================
verify_dist_is_minified() {
    entry=$(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' web/dist/index.html 2>/dev/null | head -1)
    if [ -z "$entry" ] || [ ! -f "web/dist/$entry" ]; then
        return 0   # 无入口 chunk, 交给既有校验处理
    fi
    lines=$(wc -l < "web/dist/$entry" | tr -d ' ')
    if [ "$lines" -gt 30 ]; then
        echo ""
        echo "❌ [pre-commit] web/dist/$entry 有 $lines 行 (> 30), 疑似非 production 构建"
        echo "   判据: production 11 行 / NODE_ENV=test 50 行 (2026-10-01 实测)。"
        echo "   行数判据与产物体量无关, 不会因应用增长误伤。"
        echo "   修复: rm -rf web/dist && cd web && npm run build && git add -f web/dist/"
        exit 1
    fi
}

# ================================================================
# 0. 暂存状态快照
# ================================================================
staged_dist=$(git diff --cached --name-only -- 'web/dist/')
staged_src=$(git diff --cached --name-only -- 'web/src/' ':(exclude)web/src/**/__tests__/**')
staged_web=$(git diff --cached --name-only -- 'web/')

# 构建源输入 (SOURCE_INPUTS 单一真源, 见 web/scripts/build-id.mjs)
# 只要 web/ 下有任何暂存改动就计算一次 (规则 1/2 与自动补 add 收敛都依赖它)
staged_build_inputs=""
BUILD_INPUTS_ERR=""
if [ -n "$staged_web" ]; then
    _bi=$(node web/scripts/build-id.mjs --staged-build-inputs 2>&1)
    _bi_rc=$?
    if [ "$_bi_rc" -eq 0 ]; then
        staged_build_inputs="$_bi"
    else
        BUILD_INPUTS_ERR="$_bi"
    fi
fi

# dist 待补内容 (未暂存的修改 + 未跟踪的 dist 文件), 自动补齐与第一段指引共用
dist_pending=$({ git diff --name-only -- web/dist/; git ls-files --others --exclude-standard -- web/dist/; } | grep -v '^$')

# ================================================================
# 规则 1: 禁原子 src+dist (暂存了 web/dist 才需要查)
# ================================================================
if [ -n "$staged_dist" ]; then
    if [ -n "$BUILD_INPUTS_ERR" ]; then
        echo ""
        echo "❌ [pre-commit] 拦截: web/dist 提交必须先通过「暂存源输入」计算, 但该计算失败:"
        echo "$BUILD_INPUTS_ERR" | sed 's/^/   /'
        echo "   fail-loud 不跳过 (类 20.133)。修复: 确认 PATH 里有 node / 上述错误已排除。"
        echo "   (紧急逃生: git commit --no-verify —— 仅限复检官/主拍批准场景)"
        echo "🛑 pre-commit 中止 (commit 失败)"
        exit 1
    fi
    if [ -n "$staged_build_inputs" ]; then
        input_count=$(printf '%s\n' "$staged_build_inputs" | grep -c .)
        dist_count=$(printf '%s\n' "$staged_dist" | grep -c .)
        echo ""
        echo "❌ [pre-commit] 拦截: 同一 commit 同时暂存了「构建源输入」与 web/dist —— 禁止原子 src+dist (R-5 两段式)"
        echo "   暂存的源输入 ($input_count 个):"
        printf '%s\n' "$staged_build_inputs" | head -10 | sed 's/^/     /'
        [ "$input_count" -gt 10 ] && echo "     ... (共 $input_count 个)"
        echo "   暂存的 dist 文件 ($dist_count 个, 已省略)"
        echo ""
        echo "   为什么拦: BUILD_TIMESTAMP = 源输入最后一次提交的 path-log 时间。"
        echo "   原子 src+dist 会让 dist 内嵌时间滞后一个源提交 → 在该提交上重建 ≠ 入库"
        echo "   dist (banner 时间差 → chunk 级联 rename)。e50631024 实战, CLAUDE.md W100 R-5。"
        echo ""
        echo "   正确操作 (两段式):"
        echo "     1) 第一段 (本次): 只提交源输入 —— git restore --staged web/dist 后再 commit"
        echo "     2) 构建:         cd web && npm run build"
        echo "     3) 第二段:       git add -f web/dist && git commit (单独一次 dist 提交)"
        echo ""
        echo "   (紧急逃生: git commit --no-verify —— 仅限复检官/主拍批准场景)"
        echo "🛑 pre-commit 中止 (commit 失败), 修复后重试"
        exit 1
    fi

    # ================================================================
    # 自动补齐 — 仅 dist-only 提交 (未暂存任何构建源输入) 漏 add 的场景
    #   必须在规则 2 **之前**: 只 stage 了 index.html 而新入口 chunk 还没 add 时,
    #   规则 2 会提取不到 id; 先补齐整个构建产物再做 stale 校验才自洽。
    #   (旧版对「源输入已暂存 + 磁盘 dist 脏」也自动补 → 制造原子提交, 已收敛到此)
    # ================================================================
    if [ -n "$dist_pending" ]; then
        pending_count=$(printf '%s\n' "$dist_pending" | grep -c .)
        echo ""
        echo "⚠️  [pre-commit] dist-only 提交进行中, 磁盘还有 $pending_count 个 web/dist 改动未暂存 (防漏 commit 触发 404, f6a2bc3d)"
        printf '%s\n' "$dist_pending" | head -10 | sed 's/^/   /'
        [ "$pending_count" -gt 10 ] && echo "   ... (共 $pending_count 个)"
        echo "🔧 自动执行: git add -f -A -- web/dist/ (本次未暂存任何构建源输入, 不构成原子提交)"
        # W100 +75c: 自动 add 加 timeout 30 防 git 卡死; 超时/失败 = 暂存集不完整,
        # 放行会 404 → fail-loud (旧版此处 exit 0 软放行, 已随硬化一并收紧)
        if ! timeout 30 git add -f -A -- web/dist/; then
            echo ""
            echo "❌ [pre-commit] git add 超时/失败 (30s), 暂存集不完整, 拒绝放行"
            echo "   手动执行: git add -f -A -- web/dist/ 后重新 commit"
            echo "   (紧急逃生: git commit --no-verify —— 仅限复检官/主拍批准场景)"
            exit 1
        fi
    fi

    # ================================================================
    # 规则 2: stale dist 硬校验 (commit 含 web/dist → 从暂存区重算 BUILD_ID 比对)
    #   重算与比对逻辑的单一真源 = web/scripts/build-id.mjs (vite 构建 import 同一份)
    # ================================================================
    _idx=$(node web/scripts/build-id.mjs --from-index 2>&1)
    _idx_rc=$?
    if [ "$_idx_rc" -ne 0 ] || ! printf '%s\n' "$_idx" | grep -qxE '[0-9a-f]{12}'; then
        echo ""
        echo "❌ [pre-commit] 拦截: 无法从暂存区重算 BUILD_ID (stale dist 校验无法执行):"
        echo "$_idx" | sed 's/^/   /'
        echo "   fail-loud 不跳过 (类 20.133)。修复: 排除上述错误后重试。"
        echo "   (紧急逃生: git commit --no-verify —— 仅限复检官/主拍批准场景)"
        echo "🛑 pre-commit 中止 (commit 失败)"
        exit 1
    fi
    idx_id=$_idx

    # dist 内嵌 id: staged index.html → 入口 chunk → id=<12hex> (main.js banner 注入)
    entry=$(git show :web/dist/index.html 2>/dev/null | grep -oE 'assets/index-[A-Za-z0-9_.-]+\.js' | head -1)
    dist_id=""
    if [ -n "$entry" ]; then
        dist_id=$(git show ":web/dist/$entry" 2>/dev/null | grep -oE 'id=[0-9a-f]{12}' | head -1 | sed 's/^id=//')
    fi
    if [ -z "$dist_id" ]; then
        echo ""
        echo "❌ [pre-commit] 拦截: 无法从暂存 dist 提取内嵌 id=<12hex> —— 无法证明它与已提交源一致"
        echo "   入口 chunk: ${entry:-<staged index.html 未找到>}"
        echo "   大概率: dist 不是 \`npm run build\` 产物, 或入口结构变更导致提取方式失效。"
        echo "   修复: cd web && npm run build && git add -f web/dist/ 重新提交"
        echo "   (紧急逃生: git commit --no-verify —— 仅限复检官/主拍批准场景)"
        echo "🛑 pre-commit 中止 (commit 失败)"
        exit 1
    fi
    if [ "$dist_id" != "$idx_id" ]; then
        echo ""
        echo "❌ [pre-commit] 拦截: stale dist —— 暂存的 web/dist 与已提交源不符"
        echo "   从暂存区 (index) 按 SOURCE_INPUTS 算法重算 BUILD_ID = $idx_id"
        echo "   dist 入口 $entry 内嵌 id=                = $dist_id"
        echo ""
        echo "   原因: 源改动入库后没有重新 npm run build 就提交了 dist (或 dist 构建自"
        echo "   未提交/滞后的源)。照此入库, 云端 pull 到的 dist 与源不配套。"
        echo ""
        echo "   正确操作 (两段式):"
        echo "     1) 确保源输入改动已全部提交 (git status 检查 web/ 下源输入)"
        echo "     2) cd web && npm run build"
        echo "     3) git add -f web/dist && git commit"
        echo ""
        echo "   (紧急逃生: git commit --no-verify —— 仅限复检官/主拍批准场景)"
        echo "🛑 pre-commit 中止 (commit 失败), 修复后重试"
        exit 1
    fi
fi

# ---- token orphan 检测 (v75, 既有硬拦语义原样保留; 触发条件 = web/src 有暂存改动) ----
if [ -n "$staged_src" ]; then
    # -f 而非 -x: 调用方式是 `bash <脚本>` 显式指定解释器, 不需要 exec 位。
    # 本仓 core.fileMode=false, 换机器/新克隆可能丢权限位, -x 会**静默跳过整项检查**
    # = 第二条假绿路径。文件不存在一律 fail-loud, 不当"没这项检查"处理。
    if [ ! -f "scripts/check-token-orphans.sh" ]; then
        echo ""
        echo "❌ [pre-commit] 找不到 scripts/check-token-orphans.sh (token-orphan 检查无法运行)"
        echo "   本次 web/src 有暂存改动, token-orphan 硬拦是必跑项, 不能静默跳过"
        echo "   (旧版用 [ -x ] 判存在 + 缺文件即跳过 → 换机器丢 exec 位时整项检查失效)"
        echo "   修复: git status 确认脚本未被误删/未 checkout, 恢复后重试"
        echo ""
        echo "🛑 pre-commit 中止 (commit 失败), 修复后重试"
        exit 1
    fi

    # W100 +75c: 加 timeout 30 防单步卡死 (Windows 10min timeout 误判场景)
    # 退出码契约 (scripts/check-token-orphans.sh:9-12):
    #   0 = 无 orphan | 1 = 有真 orphan | 2 = 配置错误
    # 另加 timeout 自身的 124 = 超时被 kill → 检查**未完成**, 不能当通过。
    # 2026-10-08 硬化: 旧版 `|| true` + 从 stdout 刮 "N 真 orphan" 会在超时时
    # 刮不到数字 → 条件为假 → 顺序落到脚本末尾 exit 0 假绿 (曾连续假绿 18 天)。
    ORPHAN_OUTPUT=$(timeout 30 bash scripts/check-token-orphans.sh 2>&1)
    ORPHAN_RC=$?
    case "$ORPHAN_RC" in
        0)
            # 无 orphan (白名单项已自动 skip) → 放行
            ;;
        1)
            # 有真 orphan → 原有报错 + 阻塞
            ORPHAN_COUNT=$(echo "$ORPHAN_OUTPUT" | grep -oE '[0-9]+ 真 orphan' | grep -oE '[0-9]+' | head -1)
            [ -z "$ORPHAN_COUNT" ] && ORPHAN_COUNT="未知数量"
            echo ""
            echo "❌ [pre-commit] 发现 $ORPHAN_COUNT 个 var(--token) orphan (CLAUDE.md v73 沉淀)"
            echo "   token 不在 variables.css / nutui-theme.scss / mobile-base.css 定义"
            echo "   修复选项:"
            echo "   1) 改对 token 名 (推荐, 项目已有 token)"
            echo "   2) 在 variables.css 补 token 定义"
            echo "   3) 加到 scripts/.token-orphan-allowlist (仅设计意图)"
            echo ""
            echo "📋 orphan 详情:"
            echo "$ORPHAN_OUTPUT" | grep "ORPHAN:" | sed 's/^/   /'
            echo ""
            echo "🛑 pre-commit 中止 (commit 失败), 修复后重试"
            exit 1
            ;;
        124)
            echo ""
            echo "❌ [pre-commit] token-orphan 检查超时 (timeout 30s 被 kill, 退出码 124)"
            echo "   本次 token-orphan 硬拦**未完成验证**, 不能当通过处理。"
            echo "   旧版 '|| true' 吞掉超时码 + summary 行压根没产生 → 静默 exit 0 假绿"
            echo "   手工跑定位慢在哪一步: bash scripts/check-token-orphans.sh"
            echo "   若脚本本身过慢, 修脚本让它 < 30s (不要靠放宽 timeout 掩盖)"
            echo "   紧急逃生: git commit --no-verify (仅限复检官/主拍批准场景)"
            echo ""
            echo "🛑 pre-commit 中止 (commit 失败), 修复后重试"
            exit 1
            ;;
        2)
            echo ""
            echo "❌ [pre-commit] token-orphan 检查配置错误 (退出码 2, 见 scripts/check-token-orphans.sh:12)"
            echo "   输出:"
            echo "$ORPHAN_OUTPUT" | sed 's/^/   /'
            echo ""
            echo "🛑 pre-commit 中止 (commit 失败), 修复后重试"
            exit 1
            ;;
        *)
            echo ""
            echo "❌ [pre-commit] token-orphan 检查返回未知退出码 $ORPHAN_RC — 不当作通过"
            echo "   输出:"
            echo "$ORPHAN_OUTPUT" | sed 's/^/   /'
            echo ""
            echo "🛑 pre-commit 中止 (commit 失败), 修复后重试"
            exit 1
            ;;
    esac
fi

# dist 待补内容 (dist_pending) 已在规则 1 之前计算, 此处直接复用

if [ -n "$staged_build_inputs" ]; then
    # ================================================================
    # 两段式第一段: 源输入已暂存, dist 必须留在下一次 commit
    #   (暂存了 dist 的情况已在上方规则 1 拦截, 走到这里 dist 必未暂存)
    #   —— 旧版在这里会 `git add -f web/dist/` 把磁盘 dist 强塞进来 (原子提交制造机),
    #   现改为指引后放行, 绝不自动补 (复检官拍板: 自动补 add 收敛)
    # ================================================================
    input_count=$(printf '%s\n' "$staged_build_inputs" | grep -c .)
    echo ""
    echo "ℹ️  [pre-commit] 两段式第一段: 本次只提交构建源输入 ($input_count 个), 未附带 web/dist — 正确 ✓"
    printf '%s\n' "$staged_build_inputs" | head -10 | sed 's/^/     /'
    [ "$input_count" -gt 10 ] && echo "     ... (共 $input_count 个)"
    if [ -n "$dist_pending" ]; then
        pending_count=$(printf '%s\n' "$dist_pending" | grep -c .)
        echo "   ⚠️  磁盘 web/dist/ 有 $pending_count 个未提交改动 — 本次**不会**自动补 add (那是原子提交制造机)。"
        echo "   ⚠️  若这批 dist 是在源提交之前构建的, 第二段前必须重新 npm run build:"
        echo "       BUILD_TIMESTAMP 取源输入 path-log, 提交源之前构建会滞后一个源提交"
        echo "       (e50631024 实战, CLAUDE.md W100 R-5 两段式)。"
    fi
    echo "   下一段 (本次 commit 完成后): cd web && npm run build && git add -f web/dist && git commit"
    echo "   (第二段会按暂存区源重算 BUILD_ID 与 dist 内嵌 id 比对, 不符即拦截)"
elif [ -n "$BUILD_INPUTS_ERR" ]; then
    # 源输入计算失败且没有 dist 暂存: 不阻断 (docs/测试类提交不受此影响), 但显眼警告
    echo ""
    echo "⚠️  [pre-commit] 暂存源输入计算失败 (本次未暂存 dist, 不阻断; 自动补 add 已禁用):"
    echo "$BUILD_INPUTS_ERR" | sed 's/^/   /'
fi
# (dist-only 自动补齐分支已上移到规则 1 之后、规则 2 之前 — 见上方说明)

# ---- 末段: dist 内容健全性 (既有语义: 压缩检查 + index.html↔资产配套) ----
final_staged_dist=$(git diff --cached --name-only -- 'web/dist/')
if [ -n "$final_staged_dist" ]; then
    verify_dist_is_minified
    final_dist_count=$(printf '%s\n' "$final_staged_dist" | grep -c .)
    echo ""
    echo "✅ [pre-commit] 已暂存 $final_dist_count 个 web/dist/ 文件, commit 继续"
fi
hard_verify_dist_refs

# W100 +75c: 总耗时输出 + 30s 警告
ELAPSED=$(($(date +%s) - START_TIME))
echo "⏱  [pre-commit] hook 总耗时: ${ELAPSED}s"
if [ "$ELAPSED" -gt 30 ]; then
    echo "⚠️  [pre-commit] 耗时 > 30s, 接近 harness timeout (默认 10min, 但 > 30s 体验差)"
    echo "   如果反复触发, 检查 web/dist/ 文件数 (200+ 文件可能触发 git add 慢)"
fi

exit 0
