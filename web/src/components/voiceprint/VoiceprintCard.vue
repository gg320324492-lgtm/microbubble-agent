<template>
  <div class="voiceprint-card" @click="$emit('select', member.id)">
    <div class="fingerprint">
      <div
        v-for="(value, i) in member.embedding"
        :key="i"
        class="bar"
        :class="getBarClass(value)"
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
import { computed } from 'vue'

const props = defineProps({
  member: { type: Object, required: true },
})
defineEmits(['select'])

// v77 P2.6-G.2: 收敛 bar 颜色到 .bar--low/mid/high 枚举 class
// 根因: 老版本 barColor() runtime :style + 硬编码 '64, 158, 255' 蓝 + rgba alpha 计算
//       不感知 6 主题, dark/ocean/forest 全部用 primary 单一色调
// 修复: per-card max 归一化 (避免老成员 embedding 全 0 不可见) + 0.33/0.66 阈值切 3 档 class
//       class 由 _runtime-style-tokens.scss 提供 (--color-warning-bg / --color-warning → --color-success 渐变)
//       6 主题自动跟随 token, dark mode 由 token 自身 dark 覆盖
//       + Number.isFinite 守卫 NaN/null/undefined 兜底为 .bar--low
const maxAbs = computed(() => {
  const emb = props.member?.embedding
  if (!Array.isArray(emb) || emb.length === 0) return 0
  let max = 0
  for (const v of emb) {
    const abs = Math.abs(Number(v))
    if (Number.isFinite(abs) && abs > max) max = abs
  }
  return max
})

// per-card 归一化: |value| / maxAbs 比值切 3 档
// 0.33 / 0.66 阈值保证同一张卡内 3 档都有合理分布
// maxAbs=0 兜底: 全部 .bar--low
function getBarClass(value) {
  const numValue = Number(value)
  if (!Number.isFinite(numValue) || maxAbs.value === 0) {
    return 'bar--low'
  }
  const ratio = Math.abs(numValue) / maxAbs.value
  if (ratio >= 0.66) return 'bar--high'
  if (ratio >= 0.33) return 'bar--mid'
  return 'bar--low'
}
</script>

<style scoped>
.voiceprint-card {
  display: inline-block;
  padding: 12px;
  background: var(--color-bg-card);
  border-radius: 8px;
  cursor: pointer;
  transition: var(--transition-all-normal);
  border: 1px solid var(--color-border-light);
}
.voiceprint-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(var(--color-primary-rgb), 0.2);
  border-color: var(--color-primary);
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
  color: var(--color-text-primary);
}
.samples {
  color: var(--color-text-secondary);
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
