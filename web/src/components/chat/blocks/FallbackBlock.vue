<script setup>
/**
 * FallbackBlock.vue — 兜底 block，未识别 type 渲染为 markdown
 */
import { marked } from 'marked'
import { computed } from 'vue'
const props = defineProps({ block: { type: Object, required: true } })
marked.setOptions({ breaks: true, gfm: true })

const html = computed(() => {
  const data = props.block?.data || {}
  // 优先 data.content 字段，其次整个 JSON
  const text = data.content || data.text || JSON.stringify(data, null, 2)
  return marked.parse(text)
})
</script>

<template>
  <div class="fallback-block">
    <div v-if="block.title" class="fb-title">{{ block.title }}</div>
    <div class="fb-content" v-html="html" />
  </div>
</template>

<style scoped>
.fallback-block {
  background: var(--color-bg-warm);
  border-left: 3px solid var(--color-primary);
  padding: 8px 12px;
  margin: 8px 0;
  border-radius: 4px;
  font-size: 13px;
}
.fb-title { font-weight: 600; margin-bottom: 4px; }
.fb-content :deep(pre) { background: var(--color-bg-card); padding: 6px; border-radius: 4px; overflow-x: auto; font-size: 12px; }
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .fallback-block {
  background: var(--color-bg-warm);
  color: var(--color-text-regular);
}
[data-theme="dark"] .fb-title {
  color: var(--color-text-primary);
}
[data-theme="dark"] .fb-content {
  color: var(--color-text-regular);
}
/* W100 死规则修复: scoped 深层穿透伪类在本块(非 scoped)不编译, 原样留在产物 CSS 里永不生效 (实测 dist 含字面量伪类). .fb-content 与 pre/code/a 之间无中间节点, 该伪类本就无穿透对象, 直接退化为纯后代.
   纯后代安全(含移动端): FallbackBlock 经 MobileRichCard→RichContent→registry 也会在移动端渲染, 但其内容恒在本组件**不透明**的 .fallback-block(--color-bg-warm, dark 下 #2a2d35)内, 够不到移动端气泡的紫粉渐变, 故不必像 ChatViewSSE 的 .msg-content a 那样限定桌面作用域.
   dark 首次生效后: pre/code 底色此前=容器同色(#2a2d35, 代码块隐形) → #1a1d23, 文字 #e8eaed = 14.01; 链接 #FF9D85 on #2a2d35 = 6.83. 均过 AA(4.50). 移动端 tie-break 若由 .mobile-rich-card pre 胜出亦过 (9.84).
   注: 上面 border 的 --color-border-light 在 dark 下与容器同色(1.00) 故不可见, 属装饰性边框, WCAG 1.4.11 的 3:1 只约束识别控件所必需的边界, 不适用 —— 仅记录, 本次不改. */
[data-theme="dark"] .fb-content pre {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-light);
}
[data-theme="dark"] .fb-content code {
  color: var(--color-text-primary);
  background: var(--color-bg-page);
}
[data-theme="dark"] .fb-content a {
  color: var(--color-primary);
}
</style>
