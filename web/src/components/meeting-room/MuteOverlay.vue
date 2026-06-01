<template>
  <transition name="fade">
    <div v-if="visible" class="mute-overlay">
      <el-icon :size="80" color="white"><Mute /></el-icon>
      <div class="mute-text">已静音</div>
      <div class="mute-hint">点击麦克风按钮取消</div>
    </div>
  </transition>
</template>

<script setup>
import { Mute } from '@element-plus/icons-vue'
defineProps({ visible: { type: Boolean, default: false } })
</script>

<style scoped>
.mute-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 50;
  color: white;
  pointer-events: none;
}
.mute-text { font-size: 24px; font-weight: 500; margin-top: 20px; }
.mute-hint { font-size: 14px; opacity: 0.6; margin-top: 8px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
