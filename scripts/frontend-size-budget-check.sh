set +e
FAILED=0
TOTAL_NOW=0
TOTAL_BUDGET=0

# BUDGET_FILE 可用环境变量覆盖 (仅供沙箱自测指向临时基线; CI 用默认相对路径)
BUDGET_FILE="${BUDGET_FILE:-scripts/frontend-size-budget.txt}"
EXACT=""
GLOBS=""

# 解析 kind|path|limit[|note]。note 可选, 当前仅取字面量 provisional。
# 存回时一律补成三段 (path|limit|note), 便于 split_entry 统一拆。
# kind 三种: file (单文件, 计入合计) / glob (目录递归, 计入合计) /
#           cap  (单文件**只判不累加**, 见下)。cap 是 2026-10-02 复检新增。
CAPS=""
while IFS='|' read -r kind path limit note; do
  case "$kind" in ''|\#*) continue ;; esac
  case "$kind" in
    file) EXACT="$EXACT$path|$limit|$note
" ;;
    glob) GLOBS="$GLOBS$path|$limit|$note
" ;;
    cap)  CAPS="$CAPS$path|$limit|$note
" ;;
    *) echo "::error file=$BUDGET_FILE,title=未知 kind::无法识别的条目类型 '$kind'（本脚本支持 file/glob/cap），该条可能未按预期生效。"
       FAILED=1 ;;
  esac
done < "$BUDGET_FILE"

# 拆 entry 为 ENTRY_PATH / ENTRY_LIMIT / ENTRY_NOTE。
# 注意: note 可为空, 故不能用 ${entry##*|} 取 limit (会把空 note 当成 limit)。
split_entry() {
  ENTRY_PATH="${1%%|*}"
  _rest="${1#*|}"
  ENTRY_LIMIT="${_rest%%|*}"
  case "$_rest" in
    *'|'*) ENTRY_NOTE="${_rest#*|}" ;;
    *)     ENTRY_NOTE="" ;;
  esac
}

report() {
  name="$1"; now="$2"; limit="$3"
  TOTAL_NOW=$((TOTAL_NOW + now))
  TOTAL_BUDGET=$((TOTAL_BUDGET + limit))
  if [ "$now" -gt "$limit" ]; then
    echo "::error file=$name,title=前端热点体量新增::$now > 基线 $limit（+$((now - limit))）。真拆见 S3.6-3b；新增一律 fail。"
    FAILED=1
  elif [ "$now" -lt "$limit" ]; then
    echo "::notice title=前端热点体量改善::$name 较基线少 $((limit - now)) 行，请把基线数字调低以固化成果。"
  fi
}

# cap 条目: 单文件天花板, **只判不累加**。
# 为什么需要它: S3.8 拆分后 web/src/utils/paper/normalize.js 有 2136 行, 单看
# glob 合计 5774 毫无约束 —— 只要同目录别的文件缩了, 这个文件可以无限长。
# 但若改用 file 条目, 它会被 file 与 glob **各算一遍**, 合计凭空 +2136,
# 正是 E2 决策(不留 barrel)明令拒绝的"同一批代码算两遍"。
# 故新增 cap: 判它有没有超天花板, 但不碰合计。
cap_report() {
  name="$1"; now="$2"; limit="$3"
  if [ "$now" -gt "$limit" ]; then
    echo "::error file=$name,title=单文件天花板突破::$now > cap $limit（+$((now - limit))）。该文件已在其所属 glob 合计内计过, 此条只判不累加；请真拆, 别再加行。"
    FAILED=1
  else
    echo "::notice title=单文件余量::$name $now / cap $limit（余 $((limit - now)) 行）"
  fi
}

# 暂定基线提醒 —— 占位值要变成会提醒的标记, 而不是会炸的雷。
# 命中与跳过两条路径都发: 跳过态恰恰是提醒价值最高的时刻 (人正要建这个目录,
# 此刻不提醒, 等目录建好、基线已随手提交, 就再没人知道这数字是猜的)。
provisional_notice() {
  echo "::notice title=暂定基线待实测替换::$1 的基线 $2 仍标注 provisional —— 该数字含估算余量, 拆分落地前无从实测。首次拆分 PR 完成后请用 \`wc -l\` 实测合计替换本条数字，并把 note 段清空。"
}

for entry in $EXACT; do
  split_entry "$entry"
  f="$ENTRY_PATH"; limit="$ENTRY_LIMIT"
  if [ ! -f "$f" ]; then
    echo "::error file=$f,title=体量门禁失效::被监控文件不存在，本棘轮已失去意义，请更新 BUDGET"
    FAILED=1
    continue
  fi
  report "$f" "$(wc -l < "$f" | tr -d ' ')" "$limit"
done

for entry in $GLOBS; do
  split_entry "$entry"
  dir="$ENTRY_PATH"; limit="$ENTRY_LIMIT"
  [ "$ENTRY_NOTE" = "provisional" ] && provisional_notice "$dir" "$limit"
  # 未知 note 不得静默忽略: 否则下一个人写了 provisional2 之类会以为生效了。
  if [ -n "$ENTRY_NOTE" ] && [ "$ENTRY_NOTE" != "provisional" ]; then
    echo "::error file=$dir,title=未知 note::无法识别的 note '$ENTRY_NOTE'（本脚本只支持 provisional），该条可能未按预期生效。"
    FAILED=1
  fi
  # 递归 (不用 -maxdepth 1): 拆分时若某个文件再分子目录, 那部分体量不得静默脱管。
  # 这与 S3.7 8 "新文件失明" 是同一型错误, 只是发生在新层级。
  files=$(find "$dir" -name '*.js' -type f 2>/dev/null | sort)
  if [ -z "$files" ]; then
    echo "::notice title=glob 目录暂无文件::$dir 下无 .js（递归查找），跳过（尚未拆分）"
    continue
  fi
  sum=0; n=0
  for f in $files; do sum=$((sum + $(wc -l < "$f" | tr -d ' '))); n=$((n+1)); done
  report "$dir 下 *.js 递归合计（$n 个文件）" "$sum" "$limit"
done

for entry in $CAPS; do
  split_entry "$entry"
  f="$ENTRY_PATH"; limit="$ENTRY_LIMIT"
  if [ ! -f "$f" ]; then
    echo "::error file=$f,title=单文件天花板失效::cap 指向的文件不存在（可能已被进一步拆分或改名），请更新 BUDGET 的 cap 条目"
    FAILED=1
    continue
  fi
  cap_report "$f" "$(wc -l < "$f" | tr -d ' ')" "$limit"
done

echo "合计: $TOTAL_NOW / 基线 $TOTAL_BUDGET"
exit $FAILED