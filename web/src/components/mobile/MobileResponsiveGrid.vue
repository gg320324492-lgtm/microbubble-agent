<template>
  <div
    ref="gridRoot"
    class="mobile-responsive-grid"
    :class="['grid-' + currentColumns, { 'is-swiping': isSwiping }]"
    :style="gridStyle"
  >
    <div v-if="showColumnSwitcher" class="column-switcher">
      <button
        v-for="n in availableColumns"
        :key="n"
        type="button"
        class="col-btn"
        :class="{ active: currentColumns === n }"
        :aria-label="`切换到 ${n} 列布局`"
        @click="setColumns(n)"
      >
        <span class="col-btn-glyph" :data-cols="n">
          <span v-for="i in n" :key="i" class="col-cell" />
        </span>
        <span class="col-btn-label">{{ n }}列</span>
      </button>
    </div>

    <div class="grid-body" @touchstart="onTouchStart" @touchend="onTouchEnd">
      <div
        v-if="items.length === 0"
        class="grid-empty"
      >
        <slot name="empty">
          <div class="empty-icon">📭</div>
          <div class="empty-title">暂无数据</div>
        </slot>
      </div>

      <div
        v-else
        class="grid-items"
        :style="itemsStyle"
      >
        <div
          v-for="(item, idx) in items"
          :key="getKey(item, idx)"
          class="grid-item"
          :style="itemStyle"
        >
          <slot :item="item" :index="idx" />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// MobileResponsiveGrid.vue — 响应式 grid 容器 (移动端 1-4 列自适应)
// 2026-07-24  W68 第 1 批 路线 C Agent 5 派工
//
// 功能:
// - 1/2/3/4 列自适应 (基于 useResponsive 断点)
// - 触摸滑动切换 (swipe left/right 切列数)
// - 持久化列数选择 (localStorage)
// - 顶栏列数切换器 (可选)
//
// 用法:
//   <MobileResponsiveGrid :items="list" :gap="12">
//     <template #default="{ item }">
//       <KnowledgeCard :item="item" />
//     </template>
//   </MobileResponsiveGrid>

import { ref, computed, watch, onMounted } from 'vue'
import { useResponsive } from '@/composables/useResponsive'
import { useSwipeGesture } from '@/composables/useSwipeGesture'

const STORAGE_KEY = 'mobile-responsive-grid-cols'
const MIN_COLS = 1
const MAX_COLS = 4
const SWIPE_COL_STEP = 1  // 每次 swipe 切 1 列

function clampCols(n) {
  if (n < MIN_COLS) return MIN_COLS
  if (n > MAX_COLS) return MAX_COLS
  return n
}

function loadStoredColumns() {
  if (typeof window === 'undefined' || !window.localStorage) return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw == null) return null
    const n = parseInt(raw, 10)
    if (Number.isFinite(n) && n >= MIN_COLS && n <= MAX_COLS) return n
  } catch (_) {
    // localStorage 可能被禁用 (隐私模式), 静默降级
  }
  return null
}

function persistColumns(n) {
  if (typeof window === 'undefined' || !window.localStorage) return
  try {
    window.localStorage.setItem(STORAGE_KEY, String(n))
  } catch (_) {
    // 静默降级
  }
}

function columnsForBreakpoint(bp, max) {
  // 默认列数映射
  //   sm (xs/sm)  -> 1 列
  //   md          -> 2 列
  //   lg          -> 3 列
  //   xl          -> min(max, 4) 列
  switch (bp) {
    case 'sm': return 1
    case 'md': return 2
    case 'lg': return 3
    case 'xl': return Math.min(max, 4)
    default:   return 2
  }
}

export default {
  name: 'MobileResponsiveGrid',
  props: {
    items: { type: Array, default: () => [] },
    gap: { type: Number, default: 12 },
    // 初始列数 (未持久化时使用); null = 根据断点自动决定
    initialColumns: { type: Number, default: null },
    // 允许的最大列数 (用于缩窄列数范围)
    maxColumns: { type: Number, default: MAX_COLS },
    // 允许的最小列数
    minColumns: { type: Number, default: MIN_COLS },
    // 显示列数切换器
    showColumnSwitcher: { type: Boolean, default: true },
    // 启用 swipe 切换
    enableSwipe: { type: Boolean, default: true },
    // item key 提取函数 (或字段名)
    itemKey: { type: [String, Function], default: 'id' },
  },
  setup(props) {
    const gridRoot = ref(null)
    const { bp } = useResponsive()

    // 初始化列数: 持久化 > props.initialColumns > 断点默认
    const stored = loadStoredColumns()
    const fallback = columnsForBreakpoint(bp.value, props.maxColumns)
    const columns = ref(stored ?? props.initialColumns ?? fallback)

    const currentColumns = computed(() => clampCols(columns.value))

    // 监听断点变化, 自动收缩列数 (大屏 -> 多列, 小屏 -> 少列)
    // 但仅在用户没有显式选择时跟随 (如果已通过 swipe 切过, 不强制覆盖)
    const userTouched = ref(stored != null || props.initialColumns != null)
    watch(bp, (newBp) => {
      if (userTouched.value) return
      const suggested = columnsForBreakpoint(newBp, props.maxColumns)
      if (suggested !== columns.value) {
        columns.value = suggested
      }
    })

    function setColumns(n) {
      const next = clampCols(n)
      const clampedMax = Math.min(MAX_COLS, Math.max(props.minColumns, props.maxColumns))
      const final = next > clampedMax ? clampedMax : next < props.minColumns ? props.minColumns : next
      columns.value = final
      persistColumns(final)
      userTouched.value = true
    }

    function getKey(item, idx) {
      if (typeof props.itemKey === 'function') {
        const k = props.itemKey(item, idx)
        return k == null ? idx : k
      }
      if (item && typeof item === 'object' && props.itemKey in item) {
        return item[props.itemKey]
      }
      return idx
    }

    // Swipe 切换列数
    const isSwiping = ref(false)
    const { onSwipeLeft, onSwipeRight } = useSwipeGesture(gridRoot, {
      threshold: 60,
      timeout: 400,
    })
    if (props.enableSwipe) {
      onSwipeLeft(() => {
        if (currentColumns.value < MAX_COLS) {
          isSwiping.value = true
          setColumns(currentColumns.value + SWIPE_COL_STEP)
          setTimeout(() => { isSwiping.value = false }, 300)
        }
      })
      onSwipeRight(() => {
        if (currentColumns.value > MIN_COLS) {
          isSwiping.value = true
          setColumns(currentColumns.value - SWIPE_COL_STEP)
          setTimeout(() => { isSwiping.value = false }, 300)
        }
      })
    }

    // 触屏起点记录 (用于节流, 避免 touchstart/touchend 触发表情/滚动)
    function onTouchStart() { /* 标识符, 真实逻辑在 useSwipeGesture */ }
    function onTouchEnd() { /* 同上 */ }

    const availableColumns = computed(() => {
      const max = Math.min(MAX_COLS, props.maxColumns)
      const min = Math.max(MIN_COLS, props.minColumns)
      const arr = []
      for (let i = min; i <= max; i++) arr.push(i)
      return arr
    })

    const gridStyle = computed(() => ({
      '--grid-gap': `${props.gap}px`,
    }))

    const itemsStyle = computed(() => ({
      display: 'grid',
      gridTemplateColumns: `repeat(${currentColumns.value}, minmax(0, 1fr))`,
      gap: `${props.gap}px`,
    }))

    const itemStyle = computed(() => ({
      minWidth: 0,
    }))

    onMounted(() => {
      // 兜底: 如果 initialColumns 改变 (HMR) 重新同步
      if (props.initialColumns != null) {
        setColumns(props.initialColumns)
      }
    })

    return {
      gridRoot,
      currentColumns,
      isSwiping,
      availableColumns,
      setColumns,
      getKey,
      onTouchStart,
      onTouchEnd,
      gridStyle,
      itemsStyle,
      itemStyle,
    }
  },
}
</script>

<style scoped>
.mobile-responsive-grid {
  --grid-gap: 12px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.column-switcher {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: var(--color-bg-elevated, rgba(255, 255, 255, 0.6));
  border-radius: 10px;
  border: 1px solid var(--color-border, rgba(0, 0, 0, 0.06));
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.col-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-text-secondary, #666);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 150ms ease, color 150ms ease, transform 150ms ease;
  -webkit-tap-highlight-color: transparent;
  white-space: nowrap;
}

.col-btn:active {
  transform: scale(0.96);
}

.col-btn.active {
  background: var(--color-primary, #FF7A5C);
  color: #fff;
  border-color: var(--color-primary, #FF7A5C);
}

.col-btn-glyph {
  display: inline-grid;
  grid-template-columns: repeat(2, 6px);
  gap: 2px;
  align-items: center;
}

.col-btn-glyph[data-cols="1"] { grid-template-columns: 14px; }
.col-btn-glyph[data-cols="2"] { grid-template-columns: repeat(2, 7px); }
.col-btn-glyph[data-cols="3"] { grid-template-columns: repeat(3, 4px); }
.col-btn-glyph[data-cols="4"] { grid-template-columns: repeat(4, 4px); }

.col-cell {
  display: block;
  width: 100%;
  height: 10px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.7;
}

.col-btn.active .col-cell { opacity: 1; }

.col-btn-label { font-size: 12px; }

.grid-body {
  flex: 1;
  min-height: 0;
}

.grid-items {
  width: 100%;
}

.grid-item {
  min-width: 0;
}

.is-swiping .grid-items {
  transition: transform 200ms ease;
}

/* 空态 */
.grid-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  color: var(--color-text-secondary, #999);
}

.empty-icon { font-size: 40px; margin-bottom: 8px; }
.empty-title { font-size: 14px; }
</style>
