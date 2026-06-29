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
import { computed } from 'vue'

const props = defineProps({
  member: { type: Object, required: true },
})
defineEmits(['select'])

// v77+2026-06-29 fix: per-card max 归一化声纹波形
// 根因: 老成员 embedding 是早期 pipeline 产出, 分量普遍接近 0 (sample_count 重置后没重算)
//       直接用 |value| 作 alpha 会让老成员波形几乎不可见 (~0.01 alpha)
//       新录入成员 embedding 值域 [-0.5, 0.5] 健康, 显示为半透明蓝
// 修复: per-card 计算 maxAbs, alpha = |value| / maxAbs 让每张卡用满 [0,1] 范围
//       + min floor 0.12 确保每条 bar 至少有一点颜色
//       + Number.isFinite 守卫 NaN/null/undefined
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

const MIN_ALPHA = 0.12  // floor: 保证最弱 bar 仍有颜色

function barColor(value) {
  // v76.6: 从 <html> 读 CSS 变量，让 bar 颜色跟随主题
  const primaryRgb = getComputedStyle(document.documentElement).getPropertyValue('--color-primary-rgb').trim() || '64, 158, 255'
  const infoRgb = '64, 158, 255'  // 信息蓝作为"负向"色 (距离近) 仍保留

  const numValue = Number(value)
  if (!Number.isFinite(numValue)) {
    // NaN / null / undefined 兜底: 用 floor 透明度
    return `rgba(${primaryRgb}, ${MIN_ALPHA})`
  }

  // per-card 归一化: alpha = |value| / maxAbs
  const max = maxAbs.value
  let alpha
  if (max > 0) {
    alpha = Math.max(MIN_ALPHA, Math.abs(numValue) / max)
  } else {
    // embedding 全为 0 / NaN 兜底: 全部用 floor
    alpha = MIN_ALPHA
  }

  return `rgba(${numValue >= 0 ? primaryRgb : infoRgb}, ${alpha})`
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
