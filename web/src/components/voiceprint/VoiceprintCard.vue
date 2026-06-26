<template>
  <div class="voiceprint-card" @click="$emit('select', member.id)">
    <div class="fingerprint">
      <div
        v-for="(value, i) in member.embedding"
        :key="i"
        class="bar"
        :style="{ background: barColor(value) }"
      ></div>
    </div>
    <div class="meta">
      <el-avatar :src="member.avatar" :size="32" :alt="`${member.name}的头像`">{{ member.name?.[0] }}</el-avatar>
      <span class="name">{{ member.name }}</span>
      <span class="samples">{{ member.sample_count }} 次录入</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  member: { type: Object, required: true },
})
defineEmits(['select'])

function barColor(value) {
  // value 范围 [-1, 1]（embedding 归一化后）
  if (value > 0) {
    return `rgba(255, 122, 92, ${value})`
  } else {
    return `rgba(64, 158, 255, ${-value})`
  }
}
</script>

<style scoped>
.voiceprint-card {
  display: inline-block;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #eee;
}
.voiceprint-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.2);
  border-color: #ff7a5c;
}
.fingerprint {
  display: flex;
  gap: 0;
  height: 60px;
  width: 256px;
}
.bar {
  width: 1px;
  height: 100%;
  flex: 1;
}
.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
}
.name {
  font-weight: 500;
  flex: 1;
  color: #333;
}
.samples {
  color: #999;
  font-size: 11px;
}
</style>

<!-- v69 P1b fix: VoiceprintCard dark 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .voiceprint-card {
  background: var(--color-bg-card);
  border-color: var(--color-border-base);
  box-shadow: var(--shadow-sm);
}
[data-theme="dark"] .voiceprint-card:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
}
[data-theme="dark"] .name { color: var(--color-text-primary); }
[data-theme="dark"] .samples { color: var(--color-text-secondary); }
</style>
