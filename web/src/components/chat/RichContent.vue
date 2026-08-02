<script setup>
/**
 * RichContent.vue — 结构化富文本块分发器（含折叠 wrapper，方案 C Stage 4）
 *
 * 用法：
 *   <RichContent :block="richBlock" />
 *
 * 展示行为：
 * - 默认展开，让用户第一眼看到真实任务数据
 * - LLM 主动传 collapsed_by_default=true 时隐藏长列表，保留协议兼容
 * - 不提供手动折叠按钮，避免真实内容被 wrapper 长期遮挡
 */
import { computed } from 'vue'
import { resolveBlock } from './blocks/registry'

const props = defineProps({ block: { type: Object, required: true } })

const shouldBeExpanded = computed(() => props.block.collapsed_by_default !== true)

</script>

<template>
  <div class="rich-content-wrapper" :class="`type-${block.type}`">
    <!-- 真实 block 组件始终挂载；仅兼容 LLM 显式 collapsed_by_default=true。 -->
    <!-- W100-BUGFIX (类 20.123 据实上报): 转发 block.data.citations 给 KnowledgeRefBlock,
         否则 KnowledgeRefBlock 的 citation 高亮逻辑收到空数组. block.data 已含 citations (search_knowledge 工具写入). -->
    <div class="rich-expanded" v-show="shouldBeExpanded">
      <component
        :is="resolveBlock(block.type)"
        :block="block"
        :citations="block.data?.citations || []"
      />
    </div>
  </div>
</template>

<style scoped>
.rich-content-wrapper {
  margin: 8px 0;
  border-radius: 8px;
  overflow: hidden;
}

.rich-expanded {
  position: relative;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: 8px;
  padding: 8px;
}
</style>
