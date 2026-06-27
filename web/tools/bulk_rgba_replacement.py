"""
v76.6 bulk rgba() -> rgba(var(--color-primary-rgb)) replacement.
仅替换文件中已有的硬编码 rgba 模式，不引入新 token。
"""
import re
import os

ROOT = r"e:\microbubble-agent\web\src"

# Files to scan (visible impact)
FILES = [
    "views/MeetingDetailView.vue",
    "views/chat/ChatViewSSE.vue",
    "components/chat/RichContent.vue",
    "components/paper/PaperHeader.vue",
    "components/paper/AbstractCard.vue",
    "components/paper/FigureCard.vue",
    "components/paper/RightImageRail.vue",
    "components/paper/RelatedKnowledgeList.vue",
    "components/paper/PaperBlockRenderer.vue",
    "components/mobile/VoiceTestFlow.vue",
    "components/mobile/VoiceprintEnrollFlow.vue",
    "components/mobile/TabBar.vue",
    "components/mobile/MemberAvatar.vue",
    "components/UploadStatusBadge.vue",
    "components/common/RouterFallbackSkeleton.vue",
    "views/LoginView.vue",
    "views/mobile/MobileLoginView.vue",
    "views/mobile/meeting/MobileMeetingDetailView.vue",
    "views/KnowledgeView.vue",
    "views/MeetingView.vue",
    "views/TaskView.vue",
    "views/mobile/MobileDashboard.vue",
    "views/mobile/MobileLoginView.vue",
    "views/MeetingRoomView.vue",
    "layouts/MainLayout.vue",
    "components/AudioPlayer.vue",
    "components/AudioRecorder.vue",
    "components/SessionSidebar.vue",
    "components/DashboardPet.vue",
    "components/ThemeToggleButton.vue",
    "components/chat/blocks/TaskListBlock.vue",
    "components/chat/blocks/MemberCardBlock.vue",
    "components/SpeakerStatsCard.vue",
    "components/mobile/CardList.vue",
    "components/voiceprint/VoiceprintCard.vue",
    "components/ParticipantAvatars.vue",
    "views/SettingsView.vue",
    "views/MeetingDetailView.vue",
    "components/chat/RichContent.vue",
]

# Patterns: (hex tuple, target variable)
PATTERNS = [
    (r"rgba\(\s*255,?\s*122,?\s*92\s*,", "rgba(var(--color-primary-rgb),"),
    (r"rgba\(\s*255,?\s*157,?\s*133\s*,", "rgba(var(--color-primary-light-rgb),"),
    (r"rgba\(\s*255,?\s*179,?\s*71\s*,", "rgba(var(--color-accent-rgb),"),
]

total_changes = 0
for rel in FILES:
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        print(f"  skip (not found): {rel}")
        continue
    with open(path, "r", encoding="utf-8") as f:
        s = f.read()
    new = s
    file_changes = 0
    for pat, rep in PATTERNS:
        n = len(re.findall(pat, new))
        if n:
            new = re.sub(pat, rep, new)
            file_changes += n
    if new != s:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        total_changes += file_changes
        print(f"  updated: {rel}  ({file_changes} replacements)")
    else:
        print(f"  no changes: {rel}")
print(f"\nTotal: {total_changes} replacements across {len(FILES)} files")
