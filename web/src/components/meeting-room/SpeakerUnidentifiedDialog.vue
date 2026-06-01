<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="未识别发言人"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="unidentified-content">
      <p class="transcript-preview">{{ transcript }}</p>
      <p class="hint">请选择刚才说话的人：</p>
      <div class="candidates">
        <div
          v-for="c in candidates"
          :key="c.id"
          class="candidate-card"
          @click="$emit('claim', c.id)"
        >
          <el-avatar :src="c.avatar" :size="50">
            {{ c.name?.charAt(0) }}
          </el-avatar>
          <div class="name">{{ c.name }}</div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  candidates: { type: Array, default: () => [] },
  transcript: { type: String, default: '' },
})
defineEmits(['update:visible', 'claim'])
</script>

<style scoped>
.unidentified-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.transcript-preview {
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
  color: #666;
  font-size: 14px;
}
.hint {
  font-size: 14px;
  color: #999;
  margin: 0;
}
.candidates {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.candidate-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #fff;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.candidate-card:hover {
  border-color: #ff7a5c;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.2);
}
.name {
  font-size: 14px;
  font-weight: 500;
}
</style>
