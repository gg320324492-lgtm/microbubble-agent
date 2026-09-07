/**
 * FolderTreeNode.test.js — 团队共享盘一级文件夹禁用展开 (2026-09-08)
 *
 * 背景: 团队共享盘下的一级文件夹 (is_team_default 根节点, 如 组会PPT) 展开
 * 后子文件夹列表与右侧文件列表完全重复, 用户要求一级文件夹不再有下拉框。
 *
 * 覆盖 (4 case):
 * - 默认 expandable=true: 有 children + 已展开 → 渲染 toggle 箭头 + 子节点
 * - expandable=false: 有 children 也渲染 spacer 占位, 不渲染 toggle
 * - expandable=false: 即使 id 在 expandedFolderIds 中也不渲染子节点
 * - expandable=false: 子项计数徽章仍然显示 (信息保留, 不重复列表)
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ userInfo: { id: 1 }, isAdmin: false }),
}))

vi.mock('@/composables/useDriveDragMove', () => ({
  isDriveMoveDragging: () => false,
  readDriveMovePayload: () => null,
}))

vi.mock('../FolderContextMenu.vue', () => ({
  default: { template: '<div class="ctx-menu-stub"><slot /></div>' },
}))

import FolderTreeNode from '../FolderTreeNode.vue'

const makeFolder = (overrides = {}) => ({
  id: 336,
  name: '组会PPT',
  owner_id: 1,
  children: [
    { id: 339, name: '冯懿鑫', owner_id: 1, children: [] },
    { id: 356, name: '陈天祥', owner_id: 1, children: [] },
  ],
  ...overrides,
})

function mountNode(folder, { expanded = new Set(), expandable } = {}) {
  return mount(FolderTreeNode, {
    props: {
      folder,
      selectedFolderId: null,
      expandedFolderIds: expanded,
      ...(expandable === undefined ? {} : { expandable }),
    },
  })
}

describe('FolderTreeNode expandable', () => {
  it('默认 expandable=true: 有 children 且已展开 → 渲染 toggle + 子节点 (行为不变)', () => {
    const wrapper = mountNode(makeFolder(), { expanded: new Set([336]) })
    expect(wrapper.find('.folder-tree-node-toggle').exists()).toBe(true)
    expect(wrapper.findAll('.folder-tree-node').length).toBeGreaterThan(1)
  })

  it('expandable=false: 渲染 spacer 占位, 不渲染 toggle 箭头', () => {
    const wrapper = mountNode(makeFolder(), { expandable: false })
    expect(wrapper.find('.folder-tree-node-toggle').exists()).toBe(false)
    expect(wrapper.find('.folder-tree-node-toggle-spacer').exists()).toBe(true)
  })

  it('expandable=false: 即使在 expandedFolderIds 中也不渲染子节点', () => {
    const wrapper = mountNode(makeFolder(), {
      expanded: new Set([336]),
      expandable: false,
    })
    expect(wrapper.find('.folder-tree-node-toggle').exists()).toBe(false)
    expect(wrapper.findAll('.folder-tree-node').length).toBe(1)
  })

  it('expandable=false: 子项计数徽章仍显示', () => {
    const wrapper = mountNode(makeFolder(), { expandable: false })
    expect(wrapper.find('.folder-tree-node-count').text()).toBe('2')
  })
})
