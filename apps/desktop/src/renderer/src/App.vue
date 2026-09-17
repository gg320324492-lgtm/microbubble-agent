<script setup lang="ts">
// 根组件 — 全部页面经 router 挂载（setup/login → ShellLayout 六项）。
// M4：命令面板（Ctrl+K 唤起，全键盘操作）+ 命令注册表（导航/新建/退出）。
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { CommandRegistry, type Command } from '@shared/command-registry'
import CommandPalette from './components/CommandPalette.vue'

const router = useRouter()
const showPalette = ref(false)
const registry = new CommandRegistry()

function registerCommands(): void {
  const nav = (path: string) => () => void router.push(path)
  const cmds: Command[] = [
    { id: 'nav-assistant', title: 'AI 助手', keywords: 'ai zhushou 助手 assistant', action: nav('/app/assistant') },
    { id: 'nav-eln', title: '实验 ELN', keywords: 'sy shiyan eln 实验 experiment', action: nav('/app/eln') },
    { id: 'nav-manuscripts', title: '稿件', keywords: 'gj gaojian 稿件 manuscript', action: nav('/app/manuscripts') },
    { id: 'nav-knowledge', title: '知识库', keywords: 'zsk zhishi 知识 knowledge', action: nav('/app/knowledge') },
    { id: 'nav-meetings', title: '会议', keywords: 'hy huiyi 会议 meeting', action: nav('/app/meetings') },
    { id: 'nav-settings', title: '设置', keywords: 'sz shezhi 设置 settings', action: nav('/app/settings') },
    { id: 'new-experiment', title: '新建实验（实验 ELN）', keywords: 'xj sy xinjian 新建实验', action: nav('/app/eln') },
    { id: 'new-manuscript', title: '新建稿件（稿件）', keywords: 'xj gj xinjian 新建稿件', action: nav('/app/manuscripts') },
    { id: 'new-meeting', title: '新建会议（会议）', keywords: 'xj hy xinjian 新建会议', action: nav('/app/meetings') },
    { id: 'app-quit', title: '退出应用', keywords: 'tc tuichu 退出 quit exit', action: () => void window.api.app.quit() }
  ]
  for (const c of cmds) registry.register(c)
}

function onGlobalKeydown(e: KeyboardEvent): void {
  if (e.ctrlKey && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    showPalette.value = !showPalette.value
  }
}

let keyHandler: ((e: KeyboardEvent) => void) | null = null

onMounted(() => {
  registerCommands()
  keyHandler = onGlobalKeydown
  window.addEventListener('keydown', keyHandler)
})
onUnmounted(() => {
  if (keyHandler) window.removeEventListener('keydown', keyHandler)
})
</script>

<template>
  <router-view />
  <CommandPalette :registry="registry" :visible="showPalette" @close="showPalette = false" />
</template>
