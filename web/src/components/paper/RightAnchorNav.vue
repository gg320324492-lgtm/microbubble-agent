<template>
  <aside v-if="sections.length || modules.length" class="right-anchor-nav" :class="{ 'is-collapsed': collapsed }">
    <div class="anchor-nav-header">
      <span class="anchor-nav-title">📑 文章导航</span>
      <button class="anchor-nav-toggle" @click="collapsed = !collapsed" :title="collapsed ? '展开导航' : '收起导航'">
        <el-icon><ArrowRight v-if="collapsed" /><ArrowLeft v-else /></el-icon>
      </button>
    </div>

    <div v-show="!collapsed" class="anchor-nav-body">
      <!-- 论文章节（按 type 显示友好图标） -->
      <ul v-if="sections.length" class="anchor-list">
        <li
          v-for="anchor in sections"
          :key="anchor.id"
          :class="[
            'anchor-item',
            `anchor-level-${anchor.level}`,
            { 'is-active': activeId === anchor.id }
          ]"
          :data-type="anchor.type"
          @click="scrollToAnchor(anchor)"
        >
          <span class="anchor-indicator"></span>
          <el-icon v-if="sectionIcon(anchor.type)" class="anchor-icon">
            <component :is="sectionIcon(anchor.type)" />
          </el-icon>
          <span class="anchor-text">{{ sectionLabel(anchor) }}</span>
        </li>
      </ul>

      <!-- 模块入口：图表 / 提取物 / 相关知识 -->
      <div v-if="modules.length" class="anchor-modules">
        <div class="anchor-modules-divider"></div>
        <div
          v-for="mod in modules"
          :key="mod.id"
          class="anchor-module-item"
          @click="emitScrollTo('#' + mod.anchor)"
        >
          <el-icon><DataAnalysis v-if="mod.id === 'm-figures'" /><Connection v-else /></el-icon>
          <span>{{ mod.title }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import {
  ArrowRight, ArrowLeft, Picture, DataAnalysis, Connection,
  Document, Reading, DataLine, Files, EditPen, List, ChatLineRound, Promotion, Coin,
} from '@element-plus/icons-vue'

const props = defineProps({
  sections: { type: Array, default: () => [] },
  modules: { type: Array, default: () => [] },
})

const emit = defineEmits(['scroll-to'])

const collapsed = ref(false)
const activeId = ref(null)
let observer = null

// 章节 type → 图标
const sectionIcon = (type) => {
  const map = {
    abstract: Reading,
    keywords: Coin,
    highlights: Coin,
    graphical_abstract: Picture,
    article_info: Document,
    introduction: Reading,
    background: Reading,
    methods: Files,
    results: DataLine,
    discussion: ChatLineRound,
    conclusion: Promotion,
    acknowledgments: EditPen,
    references: List,
    supplementary: Document,
    appendix: Document,
    preamble: Document,
    normal: null,
  }
  return map[type] || null
}

// 章节 type → 显示标签（中文）
// v28 step 19: 用户要求导航保留数字编号 (3 / 3.1 / 3.1.1)
// 之前 stripNumberPrefix() 主动剥掉编号，现在改用 "中文章节名 + 数字编号 + 标题" 三段式
const sectionLabel = (anchor) => {
  const typeLabelMap = {
    abstract: '摘要',
    keywords: '关键词',
    highlights: '亮点',
    graphical_abstract: '图形摘要',
    article_info: '文章信息',
    introduction: '引言',
    background: '研究背景',
    methods: '材料与方法',
    results: '结果与讨论',
    discussion: '讨论',
    conclusion: '结论',
    acknowledgments: '致谢',
    references: '参考文献',
    supplementary: '补充材料',
    appendix: '附录',
    preamble: '前言',
  }
  const title = anchor.title || ''
  // 提取编号 "1." / "3.1." / "3.1.1"
  const numMatch = title.match(/^(\d+(?:\.\d+)*)\.?\s*/)
  const num = numMatch ? numMatch[1] : ''
  // 提取去掉编号后的标题
  const titleNoNum = numMatch ? title.slice(numMatch[0].length).trim() : title

  // v28 step 97: 只 level=1 显示中文 type prefix
  //   level>=2 子章节只显示 "2.3. Experimental"，不重复显示 "材料与方法 · "
  //   （父章节 2. Materials and methods 已经显示了 "材料与方法 · 2. Materials and methods"）
  const isTopLevel = (anchor.level || 1) === 1

  if (isTopLevel && anchor.type && typeLabelMap[anchor.type]) {
    // 顶层章节：中文 type + 编号 + 标题
    // 例: "材料与方法 · 2. Materials and methods"
    return num
      ? `${typeLabelMap[anchor.type]} · ${num}. ${titleNoNum}`
      : `${typeLabelMap[anchor.type]} · ${titleNoNum}`
  }
  // 子章节或无 type 的顶层：只显示编号 + 标题
  // 例: "2.3. Experimental" 或 "Discussion"
  return num ? `${num}. ${titleNoNum}` : titleNoNum
}

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

  for (const anchor of props.sections) {
    const el = document.getElementById(`section-${anchor.id}`)
    if (el) observer.observe(el)
  }
}

watch(() => props.sections, () => {
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
  color: var(--color-text-primary);
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
