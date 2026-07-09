<!--
  FolderContextMenu.vue — Drive 文件夹/根项右键菜单 (v2.8 2026-07-10)
  用 el-dropdown trigger="contextmenu" 实现, 8 个节点共用 (5 根项 + 3 子项)

  Props:
  - items: Array<{label, command, icon?, divided?}>  菜单项
  - placement: String  菜单展开位置 (默认 bottom-start)

  Events:
  - @command(cmd)  菜单项被点击, 把 cmd 字符串往上抛
  - @click-outside  点击外部关闭 (可省, EP 自动处理)

  8 节点菜单配置 (按 type 区分):
  - root: [刷新, 新建子文件夹]
  - favorites: [刷新]
  - sub-folder: [打开, 新建子文件夹, 重命名, 复制 folder ID, 删除]
  - team: [刷新, 新建子文件夹]
  - requests: [刷新, 新建子文件夹]
  - trash: [刷新, 清空回收站, 恢复全部]
-->
<template>
  <el-dropdown
    ref="dropdownRef"
    trigger="contextmenu"
    :placement="placement"
    :teleported="true"
    @command="onCommand"
    @visible-change="onVisibleChange"
  >
    <span class="folder-menu-slot-wrap" @contextmenu.prevent="handleContextMenu">
      <slot />
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="item in items"
          :key="item.command"
          :command="item.command"
          :divided="item.divided || false"
          :disabled="item.disabled || false"
        >
          <el-icon v-if="item.icon" :size="14" style="margin-right: 6px; vertical-align: -2px;">
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.label }}</span>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
  placement: { type: String, default: 'bottom-start' },
})

const emit = defineEmits(['command', 'open', 'close'])

const dropdownRef = ref(null)

function handleContextMenu() {
  dropdownRef.value?.handleOpen()
}

function onCommand(cmd) {
  emit('command', cmd)
}

function onVisibleChange(visible) {
  emit(visible ? 'open' : 'close')
}

defineExpose({ open: () => dropdownRef.value?.handleOpen() })
</script>

<style scoped>
.folder-menu-slot-wrap {
  display: contents;  /* 不引入额外 DOM wrapper, 保留原 layout */
}
</style>
