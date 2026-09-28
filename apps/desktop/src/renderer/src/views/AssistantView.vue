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
  /* DL-5: 显式行约束。隐式 auto 行会被 .chat 内容撑高并溢出到 .shell-main 外滚
     （对话页整页滚动回归根因）；minmax(0,1fr) 钉住行高，侧栏与面板各自内滚。 */
  grid-template-rows: minmax(0, 1fr);
  min-height: 0;
}
</style>
