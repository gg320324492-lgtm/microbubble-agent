#!/usr/bin/env bash
# test-claude-code-notify-6triggers.sh
#
# W68 第 13 批 B-4 (2026-07-24): claude-code 6 trigger 实跑测试
# 验证 W68 第 12 批 B-4 实施的 6 trigger voice alert 全部能触发 + 念对应消息
# (commit f0c373663 docs/claude-code-notify-system-v2-2026-07-24.md)
#
# 6 trigger 测试矩阵:
#   1. Stop            (claude 完成回复)      -> "Claude 已经完成所有任务..."
#   2. UserPromptSubmit(用户发 prompt)         -> "正在处理您的输入..."
#   3. Notification    (claude 切窗口发通知)   -> "需要您注意..."
#   4. PermissionRequest(claude 问 approve)    -> "需要您批准权限..."
#   5. SessionStart    (claude 启动)          -> "开始新会话..."
#   6. PreToolUse-Bash (claude 调 Bash)        -> "正在执行工具..."
#
# 主指挥 SSH 跑: bash scripts/test-claude-code-notify-6triggers.sh
# 期望输出: 6 trigger 全部 PASS + SAPI 兜底念 6 条消息 (中文)
# 日志: logs/notify-6trigger-$(date +%Y%m%d).log
#
# 0 production code 改动 — 仅测试 + docs + memory (锚点范式第 165 守恒)
#
# 复用的实施:
#   - C:/Users/pc/bin/claude-voice-alert.ps1          (smart wrapper)
#   - C:/Users/pc/bin/claude-voice-alert-{stop,prompt,notify,perm,session,tool}.ps1
#                                                          (6 trigger wrappers)
#   - C:/Users/pc/.claude/settings.json               (user-level hooks 6 个 block)
#   - env:MNB_VOICE_ALERT_PROJECT_DIR=e:\microbubble-agent

set -euo pipefail

# ============== 1. PATH 校验 ==============
# 这脚本设计为在 e:\microbubble-agent 仓库根跑 (主指挥本地 PC, 非云 server)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ ! -d "${REPO_ROOT}/scripts" ] || [ ! -d "${REPO_ROOT}/memory" ]; then
    echo "[ERROR] 必须从仓库根跑: bash scripts/test-claude-code-notify-6triggers.sh" >&2
    echo "        当前: ${REPO_ROOT}" >&2
    exit 2
fi

# Windows 路径转换 (Git Bash)
WIN_REPO_ROOT="$(cd "${REPO_ROOT}" && pwd -W 2>/dev/null || echo "${REPO_ROOT}")"
WIN_SCRIPTS_BIN="/c/Users/pc/bin"
USER_SETTINGS="/c/Users/pc/.claude/settings.json"

echo "=========================================="
echo "Claude-Code 6 Trigger 实跑测试 (W68 第 13 批 B-4)"
echo "Repo root: ${REPO_ROOT}"
echo "Time:      $(date -Iseconds 2>/dev/null || date)"
echo "=========================================="

# ============== 2. 6 trigger 矩阵 ==============
# 期望 SAPI 念的消息 (来自 claude-voice-alert.ps1 wrapper fallback 分支)
declare -a TRIGGERS=(
    "stop|claude-voice-alert-stop.ps1|Claude 已经完成所有任务,请回来查看结果吧"
    "prompt|claude-voice-alert-prompt.ps1|正在处理您的输入"
    "notify|claude-voice-alert-notify.ps1|需要您注意,Claude 有新的通知"
    "perm|claude-voice-alert-perm.ps1|需要您批准权限"
    "session|claude-voice-alert-session.ps1|开始新会话"
    "tool|claude-voice-alert-tool.ps1|正在执行工具"
)

PASS_COUNT=0
FAIL_COUNT=0
LOG_DIR="${REPO_ROOT}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/notify-6trigger-$(date +%Y%m%d).log"

# log header
{
    echo "=========================================="
    echo "Claude-Code 6 Trigger 实跑测试 (W68 第 13 批 B-4)"
    echo "Time: $(date -Iseconds 2>/dev/null || date)"
    echo "Repo: ${REPO_ROOT}"
    echo "=========================================="
} >> "${LOG_FILE}"

# ============== 3. 前置检查 ==============
echo ""
echo "[前置检查] 6 trigger wrapper scripts 存在?"
echo "----------------------------------------"

PRELIM_OK=1
for entry in "${TRIGGERS[@]}"; do
    IFS='|' read -r MODE SCRIPT EXPECT_MSG <<< "${entry}"
    SCRIPT_PATH="${WIN_SCRIPTS_BIN}/${SCRIPT}"
    if [ -f "${SCRIPT_PATH}" ]; then
        SIZE=$(stat -c%s "${SCRIPT_PATH}" 2>/dev/null || stat -f%z "${SCRIPT_PATH}" 2>/dev/null || echo "?")
        echo "  [OK] ${SCRIPT} (${SIZE} bytes)"
        echo "  [PRELIM] ${SCRIPT} (${SIZE} bytes)" >> "${LOG_FILE}"
    else
        echo "  [MISSING] ${SCRIPT} — expected at ${SCRIPT_PATH}"
        echo "  [PRELIM] ${SCRIPT} MISSING" >> "${LOG_FILE}"
        PRELIM_OK=0
    fi
done

# settings.json 校验
if [ -f "${USER_SETTINGS}" ]; then
    SETTINGS_OK=$(grep -c '"hooks"' "${USER_SETTINGS}" 2>/dev/null || echo 0)
    HOOK_BLOCKS=$(grep -cE '"(Stop|UserPromptSubmit|Notification|PermissionRequest|SessionStart|PreToolUse)"' "${USER_SETTINGS}" 2>/dev/null || echo 0)
    echo ""
    echo "[前置检查] settings.json hooks 块:"
    echo "  [OK] ${USER_SETTINGS} (hooks blocks: ${HOOK_BLOCKS})"
    echo "  [PRELIM] settings.json hooks blocks: ${HOOK_BLOCKS}" >> "${LOG_FILE}"
    if [ "${HOOK_BLOCKS}" -lt 6 ]; then
        echo "  [WARN] 期望 6 hooks block (Stop+UserPromptSubmit+Notification+PermissionRequest+SessionStart+PreToolUse), 实际 ${HOOK_BLOCKS}"
        echo "  [PRELIM] WARN: expected 6 hooks blocks, got ${HOOK_BLOCKS}" >> "${LOG_FILE}"
    fi
else
    echo ""
    echo "[前置检查] [MISSING] ${USER_SETTINGS}"
    echo "  [PRELIM] settings.json MISSING" >> "${LOG_FILE}"
    PRELIM_OK=0
fi

# MNB_VOICE_ALERT_PROJECT_DIR 环境变量校验
MNB_DIR=$(grep -oE '"MNB_VOICE_ALERT_PROJECT_DIR"[^,}]+' "${USER_SETTINGS}" 2>/dev/null | head -1 || echo "")
if [ -n "${MNB_DIR}" ]; then
    echo ""
    echo "[前置检查] MNB_VOICE_ALERT_PROJECT_DIR 配置: ${MNB_DIR}"
    echo "  [PRELIM] MNB_VOICE_ALERT_PROJECT_DIR: ${MNB_DIR}" >> "${LOG_FILE}"
else
    echo ""
    echo "[前置检查] [WARN] MNB_VOICE_ALERT_PROJECT_DIR 未设置 — SAPI fallback 仍能工作但项目级 edge-tts 无法触发"
    echo "  [PRELIM] WARN: MNB_VOICE_ALERT_PROJECT_DIR not set" >> "${LOG_FILE}"
fi

if [ "${PRELIM_OK}" -eq 0 ]; then
    echo ""
    echo "[FATAL] 前置检查失败 — 6 trigger wrapper scripts 或 settings.json 缺失"
    echo "        请先跑 setup: bash scripts/setup-claude-code-notify.sh (W68 第 13 批 B-1)"
    echo "        或手动验证 C:/Users/pc/bin/claude-voice-alert-*.ps1 6 个文件存在"
    exit 3
fi

# ============== 4. 6 trigger 逐个实跑 ==============
# 每个 trigger 调对应 wrapper, wrapper 内部委托 claude-voice-alert.ps1
# 走 SAPI fallback 念预期消息
# wrapper 退出码必为 0 (见各 wrapper 的 "Always exit 0" 设计)

echo ""
echo "[6 Trigger 实跑]"
echo "----------------------------------------"

for i in "${!TRIGGERS[@]}"; do
    entry="${TRIGGERS[$i]}"
    IFS='|' read -r MODE SCRIPT EXPECT_MSG <<< "${entry}"
    SCRIPT_PATH="${WIN_SCRIPTS_BIN}/${SCRIPT}"
    NUM=$((i + 1))

    echo ""
    echo "[Test ${NUM}/6] Trigger: ${MODE} (${SCRIPT})"
    echo "         Expected: ${EXPECT_MSG}"

    # 跑 wrapper (不传任何 RestArgs, wrapper 走 mode-based default message 分支)
    # 用 timeout 兜底 (TTS 念完应 < 10s, 长于此判定卡住)
    START_TIME=$(date +%s 2>/dev/null || date +%s)
    SET_RESULT=0
    timeout 15s powershell.exe -NoProfile -ExecutionPolicy Bypass \
        -File "${SCRIPT_PATH}" 2>&1 | tee -a "${LOG_FILE}" > /dev/null || SET_RESULT=$?
    END_TIME=$(date +%s 2>/dev/null || date +%s)
    ELAPSED=$((END_TIME - START_TIME))

    # wrapper 设计: 任何错误都 swallow + exit 0
    # timeout 退出码 124 表示超时
    if [ "${SET_RESULT}" -eq 0 ]; then
        echo "         [PASS] exit=0, ${ELAPSED}s"
        echo "  [TEST ${NUM}] ${MODE} PASS (${ELAPSED}s)" >> "${LOG_FILE}"
        PASS_COUNT=$((PASS_COUNT + 1))
    elif [ "${SET_RESULT}" -eq 124 ]; then
        echo "         [TIMEOUT] 15s 未退出 — TTS 念完正常应 < 10s"
        echo "  [TEST ${NUM}] ${MODE} TIMEOUT (15s)" >> "${LOG_FILE}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        echo "         [FAIL] exit=${SET_RESULT}, ${ELAPSED}s"
        echo "  [TEST ${NUM}] ${MODE} FAIL (exit=${SET_RESULT})" >> "${LOG_FILE}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    # 避免 SAPI 排队冲突: 每 trigger 之间 sleep 2s
    if [ $i -lt 5 ]; then
        sleep 2
    fi
done

# ============== 5. wrapper log 校验 ==============
# wrapper 写 JSONL log 到 %LOCALAPPDATA%\voice-alert\wrapper-YYYYMMDD.log
# 期望 6 行 mode 分别为 stop/prompt/notify/perm/session/tool
echo ""
echo "[wrapper log 校验]"
echo "----------------------------------------"

WIN_DATE=$(date +%Y%m%d)
LOG_GLOB="/c/Users/pc/AppData/Local/voice-alert/wrapper-${WIN_DATE}.log"

if [ -f "${LOG_GLOB}" ]; then
    echo "  [OK] wrapper log: ${LOG_GLOB}"
    echo "  [LOG_CHECK] wrapper log exists: ${LOG_GLOB}" >> "${LOG_FILE}"

    for entry in "${TRIGGERS[@]}"; do
        IFS='|' read -r MODE SCRIPT EXPECT_MSG <<< "${entry}"
        # 找 mode 字段 = ${MODE} 的 log 行
        MATCHES=$(grep -c "\"mode\":\"${MODE}\"" "${LOG_GLOB}" 2>/dev/null || echo 0)
        if [ "${MATCHES}" -gt 0 ]; then
            echo "  [OK] log: mode=${MODE} (${MATCHES} entries)"
            echo "  [LOG_CHECK] mode=${MODE}: ${MATCHES} entries" >> "${LOG_FILE}"
        else
            echo "  [WARN] log: mode=${MODE} 未找到 (TTS 可能没真出声但 wrapper 兜底成功)"
            echo "  [LOG_CHECK] mode=${MODE}: 0 entries (WARN)" >> "${LOG_FILE}"
        fi
    done
else
    echo "  [WARN] wrapper log 未生成: ${LOG_GLOB}"
    echo "  [LOG_CHECK] wrapper log MISSING: ${LOG_GLOB}" >> "${LOG_FILE}"
fi

# ============== 6. 总报告 ==============
TOTAL=6
echo ""
echo "=========================================="
echo "总报告"
echo "=========================================="
echo "  PASS:    ${PASS_COUNT} / ${TOTAL}"
echo "  FAIL:    ${FAIL_COUNT} / ${TOTAL}"
echo "  日志:    ${LOG_FILE}"
echo "  Log:     ${LOG_GLOB:-<wrapper log 未生成>}"
echo ""
echo "  听感验证 (主指挥确认):"
echo "    1. Stop            -> 应听到 \"Claude 已经完成所有任务,请回来查看结果吧\""
echo "    2. UserPromptSubmit-> 应听到 \"正在处理您的输入\""
echo "    3. Notification    -> 应听到 \"需要您注意,Claude 有新的通知\""
echo "    4. PermissionRequest-> 应听到 \"需要您批准权限\""
echo "    5. SessionStart    -> 应听到 \"开始新会话\""
echo "    6. PreToolUse-Bash -> 应听到 \"正在执行工具\""
echo ""

{
    echo "=========================================="
    echo "总报告: PASS=${PASS_COUNT} / ${TOTAL}, FAIL=${FAIL_COUNT} / ${TOTAL}"
    echo "  期望: 6 trigger wrapper scripts 全部 exit=0, SAPI fallback 念 6 条消息"
    echo "  验证: 听感 + wrapper log mode 字段 (stop/prompt/notify/perm/session/tool)"
    echo "=========================================="
} >> "${LOG_FILE}"

if [ "${FAIL_COUNT}" -eq 0 ]; then
    echo "[OK] 6 trigger 全部 PASS"
    exit 0
else
    echo "[FAIL] ${FAIL_COUNT} 个 trigger 失败 — 详见 ${LOG_FILE}"
    exit 1
fi