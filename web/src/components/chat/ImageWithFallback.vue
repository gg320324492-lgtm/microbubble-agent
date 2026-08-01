<script setup lang="ts">
/**
 * ImageWithFallback.vue — 通用图片兜底组件（W99 +20 派工 v10）
 *
 * 用途：替代裸 <img>，加载失败时显示占位符"🖼️ 图片加载失败"
 *
 * 设计要点：
 * 1. 默认懒加载（loading="lazy"），首屏不抢带宽
 * 2. 失败一次后保持占位态（failed.value = true），避免重试风暴
 * 3. 占位符走 design token（--color-bg-warm + --color-text-secondary），dark mode 自动适配
 * 4. 走 prefers-reduced-motion：无动画/transition
 * 5. 类 20.130 实战：iOS Safari img onerror 在 v-html 内不可靠，组件级 onerror 才是兜底
 *
 * 限制：
 * - v-html 注入的 <img> 不会经过本组件，需走 renderMarkdown 注入 inline onerror
 * - 跨域 404 vs 鉴权 403 在 onerror 阶段不可区分，统一显示"图片加载失败"
 */
import { ref } from 'vue'

const props = withDefaults(defineProps<{
  src: string
  alt?: string
  /** 自定义 class，传到 <img> 或占位符 */
  imgClass?: string
  /** 自定义占位文本 */
  fallbackText?: string
  /** 失败时回调（埋点/上报用） */
  onFailed?: (src: string) => void
}>(), {
  alt: '',
  imgClass: '',
  fallbackText: '图片加载失败',
  onFailed: undefined,
})

const failed = ref(false)
const loaded = ref(false)

function onError(e: Event) {
  if (failed.value) return  // 避免重复触发
  failed.value = true
  loaded.value = false
  // 防止浏览器显示碎图图标
  const target = e.target as HTMLImageElement | null
  if (target) {
    target.removeAttribute('src')
  }
  // 上报（埋点，不抛错）
  if (props.onFailed) {
    try { props.onFailed(props.src) } catch { /* swallow */ }
  }
}

function onLoad() {
  loaded.value = true
  failed.value = false
}
</script>

<template>
  <span class="image-with-fallback" :class="{ 'is-loaded': loaded, 'is-failed': failed }">
    <img
      v-if="!failed"
      :src="src"
      :alt="alt"
      :class="imgClass"
      loading="lazy"
      decoding="async"
      @error="onError"
      @load="onLoad"
    />
    <span v-else class="image-fallback" role="img" :aria-label="`${alt || fallbackText}`">
      <span class="fallback-icon" aria-hidden="true">🖼️</span>
      <span class="fallback-text">{{ fallbackText }}</span>
    </span>
  </span>
</template>

<style scoped>
.image-with-fallback {
  display: inline-block;
  max-width: 100%;
}

.image-with-fallback img {
  max-width: 100%;
  height: auto;
  display: block;
}

.image-fallback {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--color-bg-warm, #f5f5f5);
  border: 1px dashed var(--color-border-base, #dcdfe6);
  border-radius: 4px;
  color: var(--color-text-secondary, #909399);
  font-size: 12px;
  line-height: 1;
}

.fallback-icon {
  font-size: 14px;
}

.fallback-text {
  white-space: nowrap;
}

@media (prefers-reduced-motion: reduce) {
  .image-with-fallback,
  .image-fallback {
    transition: none !important;
    animation: none !important;
  }
}
</style>
