import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'

import DesktopDriveView from '@/views/DesktopDriveView.vue'
import CreateFolderDialog from '@/components/drive/CreateFolderDialog.vue'
import { useFolderTree } from '@/composables/useFolderTree'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

const folder = {
  id: 7,
  name: '组会PPT',
  depth: 0,
  children: [],
}

describe('DesktopDriveView folder selection refs', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (url) => ({
      ok: true,
      json: async () => String(url).includes('/folders/tree')
        ? { tree: [folder], max_depth: 5 }
        : { items: [], total: 0 },
    })))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('初始 selectedFolder=null 时渲染不读取 null.value', () => {
    const store = useFolderTree()
    expect(store.selectedFolder).toBeNull()

    expect(() => shallowMount(DesktopDriveView)).not.toThrow()
  })

  it('selectedFolderId 与 selectedFolder 保持同一 Pinia ref 链路', async () => {
    const wrapper = shallowMount(DesktopDriveView)
    await flushPromises()

    const store = useFolderTree()
    store.selectedFolderId = folder.id
    await nextTick()

    const dialog = wrapper.findComponent(CreateFolderDialog)
    expect(dialog.props('parentId')).toBe(folder.id)
    expect(dialog.props('parentFolder')).toMatchObject({
      id: folder.id,
      name: folder.name,
    })

    wrapper.unmount()
  })
})
