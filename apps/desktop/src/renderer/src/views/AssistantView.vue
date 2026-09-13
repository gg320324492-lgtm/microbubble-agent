<script setup lang="ts">
// AI 助手工作台 — 会话列表 + 对话面板（agent 主战场）
import SessionList from '../components/chat/SessionList.vue'
import ChatPanel from '../components/chat/ChatPanel.vue'
</script>

<template>
  <div class="workbench">
    <SessionList />
    <ChatPanel />
  </div>
</template>

<style scoped>
.workbench {
  flex: 1;
  display: grid;
  grid-template-columns: 248px 1fr;
  min-height: 0;
}
</style>
