<!--
  VirtualList.vue — 通用虚拟列表 wrapper 组件 (Plan v1 Step 11)

  设计目标:
  - 0 风险: 仅新增组件, 不改任何现有 v-for 代码
  - 让任何 v-for 列表 1 行替换为 VirtualList 组件 + 默认 slot
  - 内部调用现有 useVirtualList composable (沿用 5 铁律)

  用法示意 (Vue SFC 头部注释内严禁出现注释终止符序列与真实尖括号标签,
  否则注释被提前终止导致编译报错 — 本组件注释改写为纯文本描述):

    之前: v-for 遍历 items 渲染每个 item
    之后: 用本组件包一层, items / item-height / threshold 传参,
          default slot 接收 item 与 index 渲染行

  何时用:
  - items 小于等于 threshold (默认 50): 不启用虚拟化, 走普通 v-for
  - items 大于 threshold: 启用虚拟化 (absolute 定位固定行高)
  - 不支持复杂 item 高度 (固定 itemHeight 参数), 适合 ChatMessage / SessionItem / FileCard 类
-->
<script setup lang="ts" generic="T">
import { ref, computed, onMounted, onBeforeUnmount, type Ref } from 'vue'
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
