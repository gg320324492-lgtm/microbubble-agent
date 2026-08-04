#!/bin/bash
# MicroBubble Replay Meeting (W2 +N 2026-08-04)
# 端到端 API 流程: 本地音频文件 → 完整重跑会议 (start → upload → stop → 后处理)
#
# 用法:
#   bash scripts/replay_meeting.sh <audio-file> <created_by_username>
#   bash scripts/replay_meeting.sh "/c/Users/pc/Desktop/天津大学环境科学与工程学院 4.m4a" zhanghongkui
#
# 流程:
#   1. Login → JWT token
#   2. POST /meetings/start-recording → 会议 ID (status=recording)
#   3. POST /meetings/{id}/upload-audio → 上传音频到 MinIO recordings bucket
#   4. POST /meetings/{id}/stop-recording → 触发 Celery post_meeting_process
#   5. 轮询 GET /meetings/{id} → 等待 status=completed
#   6. 输出最终状态 (含 AI 自动生成的标题)
#
# 关联铁律: 类 20.146 (W2 +N) - "重跑会议" 端到端流程沉淀

set -uo pipefail

AUDIO_FILE="${1:-}"
USERNAME="${2:-zhanghongkui}"
SERVER="${SERVER:-https://agent.mnb-lab.cn}"
PASSWORD="${PASSWORD:-123456}"  # W2 +N 重置后默认密码
MAX_WAIT_SEC=600
POLL_INTERVAL=30

if [ -z "$AUDIO_FILE" ] || [ ! -f "$AUDIO_FILE" ]; then
    echo "ERROR: audio file not found: $AUDIO_FILE"
    echo "Usage: bash scripts/replay_meeting.sh <audio-file> <created_by_username>"
    echo "Example: bash scripts/replay_meeting.sh '/c/Users/pc/Desktop/audio.m4a' zhanghongkui"
    exit 1
fi

FILE_SIZE=$(stat -c%s "$AUDIO_FILE" 2>/dev/null || stat -f%z "$AUDIO_FILE" 2>/dev/null || echo 0)

echo "============================================================"
echo " Replay Meeting (W2 +N 2026-08-04)"
echo "============================================================"
echo "  Audio file: $AUDIO_FILE"
echo "  File size:  $FILE_SIZE bytes"
echo "  Created by: $USERNAME"
echo "  Server:     $SERVER"
echo "  Timeout:    ${MAX_WAIT_SEC}s (poll ${POLL_INTERVAL}s)"
echo ""

# 1. Login
echo "[1/6] Login..."
LOGIN_RESP=$(curl -sk -X POST "$SERVER/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" 2>&1)
TOKEN=$(echo "$LOGIN_RESP" | python -c "import sys, json; d=json.load(sys.stdin); print(d.get('access_token', ''))" 2>/dev/null || echo "")
if [ -z "$TOKEN" ]; then
    echo "ERROR: Login failed: $LOGIN_RESP"
    exit 1
fi
echo "      Token: ${TOKEN:0:30}..."

# 2. Start recording
echo ""
echo "[2/6] Start recording..."
START_RESP=$(curl -sk -X POST "$SERVER/api/v1/meetings/start-recording" \
    -H "Authorization: Bearer $TOKEN" 2>&1)
MEETING_ID=$(echo "$START_RESP" | python -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
if [ -z "$MEETING_ID" ]; then
    echo "ERROR: Start recording failed: $START_RESP"
    exit 1
fi
echo "      Meeting ID: $MEETING_ID"

# 3. Upload audio
echo ""
echo "[3/6] Upload audio (multipart/form-data, $FILE_SIZE bytes)..."
UPLOAD_RESP=$(curl -sk -X POST "$SERVER/api/v1/meetings/$MEETING_ID/upload-audio" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@${AUDIO_FILE};type=audio/mp4" 2>&1)
UPLOAD_CODE=$?
echo "      $UPLOAD_RESP"
if [ "$UPLOAD_CODE" -ne 0 ] || ! echo "$UPLOAD_RESP" | grep -q "audio_url"; then
    echo "ERROR: Upload failed"
    exit 1
fi

# 4. Stop recording (trigger Celery)
echo ""
echo "[4/6] Stop recording (trigger Celery post_meeting_process)..."
STOP_RESP=$(curl -sk -X POST "$SERVER/api/v1/meetings/$MEETING_ID/stop-recording" \
    -H "Authorization: Bearer $TOKEN" 2>&1)
echo "      $STOP_RESP"

# 5. Poll until completed (or timeout)
echo ""
echo "[5/6] Polling status (max ${MAX_WAIT_SEC}s)..."
START_TS=$(date +%s)
LAST_STATUS=""
while true; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - START_TS))
    if [ "$ELAPSED" -gt "$MAX_WAIT_SEC" ]; then
        echo "      [TIMEOUT ${MAX_WAIT_SEC}s] last_status=$LAST_STATUS"
        break
    fi

    STATUS_JSON=$(curl -sk -H "Authorization: Bearer $TOKEN" "$SERVER/api/v1/meetings/$MEETING_ID" 2>&1)
    STATUS=$(echo "$STATUS_JSON" | python -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    UPLOAD=$(echo "$STATUS_JSON" | python -c "import sys, json; print(json.load(sys.stdin).get('upload_status', ''))" 2>/dev/null || echo "")
    TITLE=$(echo "$STATUS_JSON" | python -c "import sys, json; print(json.load(sys.stdin).get('title', ''))" 2>/dev/null || echo "")
    TR_LEN=$(echo "$STATUS_JSON" | python -c "import sys, json; d=json.load(sys.stdin); t=d.get('transcript','') or ''; print(len(t))" 2>/dev/null || echo "0")
    POL_LEN=$(echo "$STATUS_JSON" | python -c "import sys, json; d=json.load(sys.stdin); t=d.get('transcript_polished','') or []; print(len(t) if isinstance(t, list) else len(str(t)))" 2>/dev/null || echo "0")

    if [ "$STATUS" != "$LAST_STATUS" ] || [ "$((ELAPSED % 60))" -lt 5 ]; then
        echo "      [${ELAPSED}s] status=$STATUS upload=$UPLOAD title=\"$TITLE\" transcript_len=$TR_LEN polished_segments=$POL_LEN"
        LAST_STATUS="$STATUS"
    fi

    if [ "$STATUS" = "completed" ]; then
        echo "      ✓ completed"
        break
    fi
    if [ "$STATUS" = "failed" ]; then
        echo "      ✗ failed"
        break
    fi

    sleep "$POLL_INTERVAL"
done

# 6. Final state
echo ""
echo "[6/6] Final meeting state:"
echo "============================================================"
curl -sk -H "Authorization: Bearer $TOKEN" "$SERVER/api/v1/meetings/$MEETING_ID" 2>&1 | python -m json.tool 2>&1 | head -40
echo ""
echo "============================================================"
echo " Meeting ID:   $MEETING_ID"
echo " Frontend URL: $SERVER/meetings/$MEETING_ID"
echo "============================================================"