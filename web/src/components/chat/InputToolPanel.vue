<!--
InputToolPanel.vue — ChatGPT 风格 "+" 触发的工具面板

5 项工具（按 ChatGPT 顺序，删除 GitHub / OpenAI Platform 两个无效按钮）:
- 添加照片和文件 (调 triggerImageUpload, 真有效)
- 从资料库添加 (跳 /drive, 真有效)
- 创建图片 (DALL-E 风格生成 - 占位, 点提示功能开发中)
- 网页搜索 (search_service - 占位)
- 深度研究 (deep_research - 占位)

实现:
- 由父组件 (ChatViewSSE) 控制 visible (v-model)
- 父组件接收 emit 事件触发对应操作
- 不在本组件内 import router / ElMessage, 保持纯展示逻辑
-->
<script setup lang="ts">
/**
 * InputToolPanel.vue — ChatGPT 风格 "+" 工具面板
 *
 * 父组件用法:
 *   <InputToolPanel
 *     v-model:visible="toolPanelOpen"
 *     @pick-image="triggerImageUpload"
 *     @pick-file="triggerFileUpload"
 *     @pick-from-drive="() => router.push('/drive')"
 *     @feature-not-ready="(name) => ElMessage.info(`${name} 功能开发中`)"
 *   />
 */
import { computed, onBeforeUnmount, onMounted } from 'vue'

interface ToolItem {
  id: string
  icon: string          // emoji 占位, 后续可换 SVG
  label: string         // 主标题
  subtitle: string      // 副标题
  status: 'available' | 'pending'  // available 触发事件, pending 显示 "功能开发中"
  action?: string       // emit 事件名
}

const props = defineProps<{
  visible: boolean
  webSearchOn: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'pick-image'): void
  (e: 'pick-file'): void
  (e: 'pick-from-drive'): void
  (e: 'toggle-web-search'): void
  (e: 'set-deep-research'): void
}>()

const TOOLS: ToolItem[] = [
  {
    id: 'photo',
    icon: '📎',
    label: '添加照片和文件',
    subtitle: '从电脑上上传图片、PDF、文档',
    status: 'available',
    action: 'pick-file',
  },
  {
    id: 'library',
    icon: '📚',
    label: '从资料库添加',
    subtitle: '浏览和选择项目内的知识库文档',
    status: 'available',
    action: 'pick-from-drive',
  },
  {
    id: 'web-search',
    icon: '🌐',
    label: '网页搜索',
    subtitle: '开启后回答会先联网查询实时信息',
    status: 'available',
    action: 'toggle-web-search',
  },
  {
    id: 'deep-research',
    icon: '🔭',
    label: '深度研究',
    subtitle: '切换到深度模式，获取更详尽的报告',
    status: 'available',
    action: 'set-deep-research',
  },
]

const isOpen = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

function handleToolClick(tool: ToolItem) {
  if (tool.action === 'pick-image') {
    emit('pick-image')
  } else if (tool.action === 'pick-file') {
    emit('pick-file')
  } else if (tool.action === 'pick-from-drive') {
    emit('pick-from-drive')
  } else if (tool.action === 'toggle-web-search') {
    emit('toggle-web-search')
    emit('update:visible', false)  // 开关型: 关面板让用户看到状态徽标
    return
  } else if (tool.action === 'set-deep-research') {
    emit('set-deep-research')
    emit('update:visible', false)
    return
  }
  emit('update:visible', false)
}

function closePanel() {
  emit('update:visible', false)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isOpen.value) {
    closePanel()
  }
}

function onClickOutside(e: MouseEvent) {
  if (!isOpen.value) return
  const target = e.target as HTMLElement
  if (target.closest('.input-tool-panel') || target.closest('.plus-trigger')) return
  closePanel()
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  // 用 mousedown 提前拦截, 避免 toggle 按钮的 click 又被 outside 关闭
  document.addEventListener('mousedown', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('mousedown', onClickOutside)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="tool-panel">
      <div v-if="isOpen" class="input-tool-panel" role="menu" aria-label="工具面板">
        <div class="itp-header">
          <span class="itp-hint">输入以搜索插件、文件和技能</span>
        </div>
        <ul class="itp-list">
          <li
            v-for="tool in TOOLS"
            :key="tool.id"
            class="itp-item"
            role="menuitem"
            :aria-disabled="tool.status === 'pending'"
            @click="handleToolClick(tool)"
          >
            <span class="itp-icon" :aria-hidden="true">{{ tool.icon }}</span>
            <div class="itp-text">
              <div class="itp-label">{{ tool.label }}</div>
              <div class="itp-subtitle">{{ tool.subtitle }}</div>
            </div>
            <span v-if="tool.id === 'web-search' && webSearchOn" class="itp-action itp-on">开启中</span>
          </li>
        </ul>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.input-tool-panel {
  position: fixed;
  bottom: 96px;
  left: 50%;
  transform: translateX(-50%);
  width: min(560px, calc(100vw - 32px));
  max-height: 60vh;
  overflow-y: auto;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-base);
  border-radius: 18px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18), 0 2px 6px rgba(0, 0, 0, 0.08);
  z-index: 1000;
  padding: 8px;
  font-size: 14px;
  color: var(--color-text-primary);
}

.itp-header {
  padding: 10px 14px 6px;
  border-bottom: 1px solid var(--color-border-light);
  margin-bottom: 4px;
}
.itp-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.itp-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.itp-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.12s ease, transform 0.12s ease;
  user-select: none;
}
.itp-item:hover {
  background: var(--color-bg-hover);
  transform: translateX(2px);
}
.itp-item:active {
  background: var(--color-bg-warm);
  transform: translateX(0);
}

.itp-icon {
  font-size: 22px;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 8px;
  background: var(--color-bg-warm);
}

.itp-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.itp-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.3;
}
.itp-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
}

.itp-action {
  font-size: 12px;
  color: #0e766e;
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid rgba(14, 118, 110, 0.35);
  font-family: Consolas, 'SFMono-Regular', monospace;
  letter-spacing: 0.08em;
}
[data-theme="dark"] .itp-action {
  color: #35c2a4;
  border-color: rgba(53, 194, 164, 0.4);
}

/* dark mode 适配 */
[data-theme="dark"] .input-tool-panel {
  background: var(--color-bg-card);
  border-color: var(--color-border-base);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 2px 6px rgba(0, 0, 0, 0.3);
}
[data-theme="dark"] .itp-icon {
  background: var(--color-bg-warm);
}

/* 弹起 / 收起动画 */
.tool-panel-enter-active,
.tool-panel-leave-active {
  transition: opacity 0.18s ease, transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.tool-panel-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(8px) scale(0.96);
}
.tool-panel-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(4px) scale(0.98);
}

/* 移动端: 全宽 + 底部更紧凑 */
@media (max-width: 768px) {
  .input-tool-panel {
    width: calc(100vw - 16px);
    bottom: 80px;
    max-height: 70vh;
  }
}
</style>