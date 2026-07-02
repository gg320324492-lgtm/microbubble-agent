// useDriveSubSidebarCollapsed.js — DriveLayout 4 个 view 共享的折叠状态
//
// v2 PR7 修复: 抽离折叠状态 + localStorage 同步逻辑, 避免 4 个 view 复制粘贴
// 关键设计:
// - 模块级 module-singleton ref (across 4 view mounts/composables 调用, ref 仍是同一份)
// - localStorage 变更即时同步, 但初始值仅在模块加载时读一次 (4 view mount 时复用同一份状态)
// - toggle() 暴露给组件, view 切换时不重置
//
// 使用:
//   import { useDriveSubSidebarCollapsed } from '@/composables/useDriveSubSidebarCollapsed'
//   const { collapsed, toggle } = useDriveSubSidebarCollapsed()

import { ref, watch } from 'vue'

const STORAGE_KEY = 'mnb:ui:drive:subSidebarCollapsed'

function readInitial() {
  if (typeof localStorage === 'undefined') return false
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

// 模块级 singleton: 4 view 引用同一个 ref, 切换 view 不重置状态
const collapsed = ref(readInitial())

// watch in flush: 'post' 让 DOM 更新完毕后再写 localStorage
watch(collapsed, (v) => {
  try {
    localStorage.setItem(STORAGE_KEY, v ? '1' : '0')
  } catch {
    /* localStorage 写入失败容错 (隐私模式/QuotaExceeded) */
  }
}, { flush: 'post' })

export function useDriveSubSidebarCollapsed() {
  function toggle() {
    collapsed.value = !collapsed.value
  }
  return { collapsed, toggle }
}
