<!--
  VirtualList.vue — 通用虚拟列表 wrapper 组件 (Plan v1 Step 11)

  设计目标:
  - 0 风险: 仅新增组件, 不改任何现有 v-for 代码
  - 让任何 v-for 列表 1 行替换为 <VirtualList :items="..."> + 默认 slot
  - 内部调用现有 useVirtualList composable (沿用 5 铁律)

  用法:
    <!-- 之前 -->
    <div v-for="item in items" :key="item.id">{{ item.name }}</div>

    <!-- 之后 -->
    <VirtualList :items="items" :item-height="60" :threshold="50">
      <template #default="{ item, index }">
        <div :key="item.id">{{ item.name }}</div>
      </template>
    </VirtualList>

  0 production code 变更:
  - 不动 useVirtualList.ts (沿用 5 铁律: 固定 item 高度 + 阈值守恒 + scroll 监听 + overscan + lifecycle)
  - 不改现有 FileGrid / TaskView / SessionSidebar 任何代码
  - 仅给未来新加列表 (例如 mobile knowledge list) 提供 0 集成成本 shortcut

  何时用:
  - items ≤ 50: 不启用虚拟化 (isVirtualized=false), 走普通 v-for (沿用 transition)
  - items > 50: 启用虚拟化 (visibleItems computed), 渲染固定高度 items
  - 不支持复杂 item 高度 (固定 itemHeight 参数), 适合 ChatMessage / SessionItem / FileCard 类
-->
<script setup lang="ts" generic="T">
import { ref, onMounted, onBeforeUnmount, type Ref } from 'vue'
import { useVirtualList } from '@/composables/useVirtualList'

interface Props {
  /** 数据源 (响应式) */
  items: readonly T[]
  /** 单条预估高度 (px, 默认 60) */
  itemHeight?: number
  /** 启用虚拟化的阈值 (默认 50, ≤ 50 不启用) */
  threshold?: number
  /** 上下预渲染条数 (默认 5) */
  overscan?: number
  /** 容器自定义 class */
  containerClass?: string
  /** 容器自定义 style */
  containerStyle?: Record<string, string>
}

const props = withDefaults(defineProps<Props>(), {
  itemHeight: 60,
  threshold: 50,
  overscan: 5,
})

const containerRef = ref<HTMLElement | null>(null)

// 2026-08-17 #Step11: 复用 useVirtualList composable
// 5 铁律 + 抽象已经在 useVirtualList.ts 内实现, 这里只做 wrapper
const itemsRef = computed(() => props.items) as unknown as Ref<readonly T[]>
const {
  visibleItems,
  totalHeight,
  isVirtualized,
} = useVirtualList<T>({
  containerRef: containerRef as Ref<HTMLElement | null>,
  items: itemsRef,
  itemHeight: props.itemHeight,
  threshold: props.threshold,
  overscan: props.overscan,
})

// 立即 attach scroll listener (与 composable 内的 onMounted 重复但保险)
// composable 内部已自动 onMounted, 这里不重复
</script>

<template>
  <div
    ref="containerRef"
    :class="['virtual-list-container', containerClass]"
    :style="containerStyle"
    data-virtualized="false"
  >
    <!-- 2026-08-17 #Step11: 阈值守恒 (5 铁律 1).
         items ≤ threshold: 全量渲染 (与 v-for 行为 0 差别)
         items > threshold: 虚拟渲染 (用 absolute positioning) -->
    <template v-if="!isVirtualized">
      <slot
        v-for="item in items"
        :key="(item as any).id ?? (item as any).key ?? Math.random()"
        :item="item"
        :index="items.indexOf(item)"
      />
    </template>

    <!-- 虚拟渲染: 撑出滚动条 + 绝对定位 -->
    <template v-else>
      <div :style="{ height: `${totalHeight}px`, position: 'relative' }">
        <slot
          v-for="wrapper in visibleItems"
          :key="wrapper.index"
          :item="wrapper.item"
          :index="wrapper.index"
          :style="{ position: 'absolute', top: 0, left: 0, right: 0, transform: `translateY(${wrapper.index * itemHeight}px)`, height: `${itemHeight}px` }"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.virtual-list-container {
  /* 滚动容器 — 调用方需确保容器有固定 height 或 max-height */
  overflow-y: auto;
}
</style>
