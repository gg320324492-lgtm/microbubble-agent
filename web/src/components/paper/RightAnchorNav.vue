<template>
  <aside v-if="anchors.length" class="right-anchor-nav" :class="{ 'is-collapsed': collapsed }">
    <div class="anchor-nav-header">
      <span class="anchor-nav-title">📑 文章导航</span>
      <button class="anchor-nav-toggle" @click="collapsed = !collapsed" :title="collapsed ? '展开导航' : '收起导航'">
        <el-icon><ArrowRight v-if="collapsed" /><ArrowLeft v-else /></el-icon>
      </button>
    </div>

    <div v-show="!collapsed" class="anchor-nav-body">
      <ul class="anchor-list">
        <li
          v-for="anchor in anchors"
          :key="anchor.id"
          :class="[
            'anchor-item',
            `anchor-level-${anchor.level}`,
            { 'is-active': activeId === anchor.id }
          ]"
          @click="scrollToAnchor(anchor)"
        >
          <span class="anchor-indicator"></span>
          <span class="anchor-text">{{ anchor.title }}</span>
        </li>
      </ul>

      <!-- 模块入口 -->
      <div v-if="hasModules" class="anchor-modules">
        <div class="anchor-modules-divider"></div>
        <div v-if="moduleCounts.figures" class="anchor-module-item" @click="emitScrollTo('#paper-figures')">
          <el-icon><Picture /></el-icon>
          <span>图表 ({{ moduleCounts.figures }})</span>
        </div>
        <div v-if="moduleCounts.extractions" class="anchor-module-item" @click="emitScrollTo('#paper-extractions')">
          <el-icon><DataAnalysis /></el-icon>
          <span>提取物 ({{ moduleCounts.extractions }})</span>
        </div>
        <div v-if="moduleCounts.related" class="anchor-module-item" @click="emitScrollTo('#paper-related')">
          <el-icon><Connection /></el-icon>
          <span>相关知识 ({{ moduleCounts.related }})</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ArrowRight, ArrowLeft, Picture, DataAnalysis, Connection } from '@element-plus/icons-vue'

const props = defineProps({
  anchors: { type: Array, default: () => [] },
  moduleCounts: { type: Object, default: () => ({ figures: 0, extractions: 0, related: 0 }) },
})

const emit = defineEmits(['scroll-to'])

const collapsed = ref(false)
const activeId = ref(null)
let observer = null
let scrollThrottle = null

const hasModules = computed(() => {
  return Object.values(props.moduleCounts).some(v => v > 0)
})

function scrollToAnchor(anchor) {
  const el = document.getElementById(`section-${anchor.id}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function emitScrollTo(selector) {
  const el = document.querySelector(selector)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function setupObserver() {
  if (typeof IntersectionObserver === 'undefined') return
  if (observer) observer.disconnect()
  const visibilityMap = new Map()
  observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      visibilityMap.set(entry.target.id, entry.intersectionRatio)
    }
    // 找到当前可见度最高且 > 0 的 section
    let bestId = null
    let bestRatio = 0
    for (const [id, ratio] of visibilityMap.entries()) {
      if (ratio > bestRatio) {
        bestRatio = ratio
        bestId = id
      }
    }
    if (bestId) {
      const id = bestId.replace('section-', '')
      if (activeId.value !== id) {
        activeId.value = id
        // 滚动时把当前激活项也滚到导航视口里
        nextTick(() => {
          const activeEl = document.querySelector('.anchor-item.is-active')
          if (activeEl) {
            const navBody = activeEl.closest('.anchor-nav-body')
            if (navBody) {
              const navRect = navBody.getBoundingClientRect()
              const itemRect = activeEl.getBoundingClientRect()
              if (itemRect.top < navRect.top || itemRect.bottom > navRect.bottom) {
                activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
              }
            }
          }
        })
      }
    }
  }, {
    rootMargin: '-80px 0px -60% 0px',
    threshold: [0, 0.1, 0.5, 1],
  })

  // 注册所有 section 锚点
  for (const anchor of props.anchors) {
    const el = document.getElementById(`section-${anchor.id}`)
    if (el) observer.observe(el)
  }
}

watch(() => props.anchors, () => {
  nextTick(() => setupObserver())
}, { deep: true })

onMounted(() => {
  nextTick(() => setupObserver())
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.right-anchor-nav {
  position: sticky;
  top: 88px;
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 12px 0;
  max-height: calc(100vh - 110px);
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  transition: width 0.2s;
}

.right-anchor-nav.is-collapsed {
  width: 44px;
}

.anchor-nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 14px 8px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.anchor-nav-title {
  font-size: 13px;
  font-weight: 600;
  color: #1F2937;
  white-space: nowrap;
}

.is-collapsed .anchor-nav-title {
  display: none;
}

.anchor-nav-toggle {
  background: none;
  border: none;
  cursor: pointer;
  color: #6B7280;
  font-size: 14px;
  padding: 4px;
  border-radius: 4px;
}

.anchor-nav-toggle:hover {
  background: #F3F4F6;
  color: var(--color-primary);
}

.anchor-nav-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 6px 0;
  scrollbar-width: thin;
}

.anchor-nav-body::-webkit-scrollbar {
  width: 4px;
}

.anchor-nav-body::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}

.anchor-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.anchor-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1.5;
  color: #4B5563;
  transition: all 0.15s;
  margin-bottom: 2px;
  position: relative;
}

.anchor-item:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.anchor-item.is-active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-weight: 500;
}

.anchor-indicator {
  width: 3px;
  height: 12px;
  background: transparent;
  border-radius: 2px;
  flex-shrink: 0;
  transition: background 0.15s;
}

.anchor-item.is-active .anchor-indicator {
  background: var(--color-primary);
}

.anchor-item:hover .anchor-indicator {
  background: var(--color-primary-light);
}

.anchor-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

.anchor-level-2 {
  padding-left: 22px;
  font-size: 12.5px;
}

.anchor-level-3 {
  padding-left: 34px;
  font-size: 12px;
}

.anchor-level-4 {
  padding-left: 46px;
  font-size: 12px;
  color: #6B7280;
}

.anchor-modules {
  margin-top: 8px;
  padding: 0 8px;
}

.anchor-modules-divider {
  height: 1px;
  background: var(--color-border-light);
  margin: 8px 0;
}

.anchor-module-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12.5px;
  color: #4B5563;
  cursor: pointer;
  transition: all 0.15s;
}

.anchor-module-item:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

@media (max-width: 1280px) {
  .right-anchor-nav {
    position: static;
    max-height: none;
  }
}
</style>
