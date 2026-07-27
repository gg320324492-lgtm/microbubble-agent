#!/bin/bash
# scripts/lib/webhook_payload.sh
# W75 第 1 批 B-3 共用 webhook 库 — 6 件套监控共用 (W73 B-2 4 类 + W74 D-1 多租户 + W75 B-1 声纹)
# 依据: W74 第 1 批 E-1 报告 P2 实战 — webhook payload 缺右花括号 + || true 静默吞报警
#
# 用法 (在监控脚本中 source):
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/webhook_payload.sh"
#   notify_alert "alembic-monitor" "critical" "alembic 双头 detected" "heads=[080,085]"
#
# 必含字段: severity, source, message, timestamp, details
# 纪律: 失败时主动告警 exit 1, 不再用 || true 静默吞

# 防止多次 source 重复定义
if [ -n "${__WEBHOOK_PAYLOAD_LIB_LOADED:-}" ]; then
    return 0
fi
__WEBHOOK_PAYLOAD_LIB_LOADED=1

# 默认 retry 策略 (W75 B-3 派工 v6 段 5 反馈 #6 实战)
WEBHOOK_RETRY_COUNT="${WEBHOOK_RETRY_COUNT:-3}"
WEBHOOK_RETRY_INTERVAL="${WEBHOOK_RETRY_INTERVAL:-5}"

# validate_payload_json <source> <severity> <message> <details>
# 验证 payload 5 字段完整 + JSON 格式正确 (服务端可解析)
validate_payload_json() {
    local source="$1"
    local severity="$2"
    local message="$3"
    local details="$4"

    if [ -z "$source" ] || [ -z "$severity" ] || [ -z "$message" ]; then
        echo "validate_payload_json: source/severity/message 不能为空" >&2
        return 1
    fi

    case "$severity" in
        critical|error|warn|info) ;;
        *) echo "validate_payload_json: severity=$severity 不在 [critical|error|warn|info]" >&2; return 1 ;;
    esac

    # details 必须是合法 JSON (用 python -c 验证, 失败非零返回)
    echo "$details" | python -c "import sys, json; json.loads(sys.stdin.read())" 2>/dev/null
}

# send_webhook_with_retry <url> <payload>
# 重试 3 次, 间隔 5s; 任一失败主动告警 exit 1, 不用 || true
send_webhook_with_retry() {
    local url="$1"
    local payload="$2"

    local attempt=1
    while [ "$attempt" -le "$WEBHOOK_RETRY_COUNT" ]; do
        HTTP_CODE=$(curl -sS -X POST -H 'Content-Type: application/json' \
            --max-time 10 \
            -d "$payload" \
            -w "%{http_code}" -o /dev/null \
            "$url" 2>&1)
        CURL_EXIT=$?

        if [ "$CURL_EXIT" -eq 0 ] && [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
            return 0
        fi

        if [ "$attempt" -lt "$WEBHOOK_RETRY_COUNT" ]; then
            sleep "$WEBHOOK_RETRY_INTERVAL"
        fi
        attempt=$((attempt + 1))
    done

    # 全部 retry 失败: 主动告警, 写到 stderr + exit 1 (W75 B-3 派工 v6 段 5 反馈 #6 实战)
    echo "ERROR: webhook send failed after $WEBHOOK_RETRY_COUNT retries (url=$url, last_http=$HTTP_CODE)" >&2
    return 1
}

# format_alert_payload <source> <severity> <message> <details_json>
# 输出完整 5 字段 JSON: severity/source/message/timestamp/details
format_alert_payload() {
    local source="$1"
    local severity="$2"
    local message="$3"
    local details="$4"

    local timestamp
    timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

    python -c "
import json, sys
payload = {
    'severity': sys.argv[1],
    'source': sys.argv[2],
    'message': sys.argv[3],
    'timestamp': sys.argv[4],
    'details': json.loads(sys.argv[5])
}
print(json.dumps(payload, ensure_ascii=False))
" "$severity" "$source" "$message" "$timestamp" "$details"
}

# log_alert <message>
# 写本地 log 文件 (用于离线排查)
log_alert() {
    local message="$1"
    local log_file="${ALERT_LOG_FILE:-/var/log/microbubble-agent/alert.log}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" | tee -a "$log_file" >&2
}

# notify_alert <source> <severity> <message> <details_json>
# 顶层调用: 验证 → 格式化 → 发送 (retry) → 失败 exit 1
notify_alert() {
    local source="$1"
    local severity="$2"
    local message="$3"
    local details="$4"
    local webhook_url="${WEBHOOK_URL:-}"

    # 1. 验证 payload
    if ! validate_payload_json "$source" "$severity" "$message" "$details"; then
        log_alert "INVALID payload: source=$source severity=$severity"
        return 1
    fi

    # 2. 格式化 payload (含完整 5 字段)
    local payload
    payload=$(format_alert_payload "$source" "$severity" "$message" "$details")

    # 3. log 本地
    log_alert "[$severity][$source] $message"

    # 4. 发 webhook (若配置)
    if [ -z "$webhook_url" ]; then
        # 没配 webhook 也不静默 — log warning 然后 graceful 退出 (test 环境常见)
        log_alert "WARN: WEBHOOK_URL 未配置, 仅本地 log"
        return 0
    fi

    # 5. send + retry, 失败 exit 1 (W75 B-3 派工 v6 段 5 反馈 #6 实战 — 删 || true)
    if ! send_webhook_with_retry "$webhook_url" "$payload"; then
        log_alert "FAIL: webhook 发送失败 (3 次 retry 已耗尽)"
        return 1
    fi

    return 0
}