/**
 * Desktop Drive version diff UI — route-level component tests.
 *
 * Scenarios:
 * 1. Open the comparison dialog from /drive/file/:id/versions.
 * 2. Choose a from/to pair and request the exact diff URL.
 * 3. Render unified diff additions and deletions.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import DesktopFileVersionsView from '@/views/desktop/DesktopFileVersionsView.vue'
import DesktopVersionDiffDialog from '@/components/desktop/DesktopVersionDiffDialog.vue'

vi.mock('axios', () => {
  const get = vi.fn()
  globalThis.__desktopVersionDiffAxios = { get }
  return { default: { get } }
})

const versionsFixture = {
  file_id: 99,
  file_name: 'experiment-notes.md',
  count: 3,
  items: [
    {
      id: 303,
      file_id: 99,
      version_number: 3,
      size: 156,
      uploader_id: 2,
      uploader_name: '王天志',
      comment: '更新实验结论',
      is_current: true,
      created_at: '2026-07-24T11:00:00',
      minio_object_key: 'drive/99/v3.md',
    },
    {
      id: 302,
      file_id: 99,
      version_number: 2,
      size: 142,
      uploader_id: 1,
      uploader_name: '管理员',
      comment: '补充压力参数',
      is_current: false,
      created_at: '2026-07-23T10:00:00',
      minio_object_key: 'drive/99/v2.md',
    },
    {
      id: 301,
      file_id: 99,
      version_number: 1,
      size: 128,
      uploader_id: 1,
      uploader_name: '管理员',
      comment: '初稿',
      is_current: false,
      created_at: '2026-07-22T09:00:00',
      minio_object_key: 'drive/99/v1.md',
    },
  ],
}

function diffFixture(from = 2, to = 3) {
  const fromItem = versionsFixture.items.find(item => item.version_number === from)
  const toItem = versionsFixture.items.find(item => item.version_number === to)
  return {
    file_id: 99,
    file_name: versionsFixture.file_name,
    from_version_number: from,
    from_version_id: fromItem.id,
    to_version_number: to,
    to_version_id: toItem.id,
    is_text: true,
    unified_diff: `--- v${from}+++ v${to}@@ -1,2 +1,2 @@-旧实验结论\n+新实验结论\n 压力参数 0.3 MPa\n`,
    changed_lines: [1],
    additions: 5,
    deletions: 5,
    size_delta: toItem.size - fromItem.size,
    uploader_delta: fromItem.uploader_id !== toItem.uploader_id,
    from_meta: {
      version_id: fromItem.id,
      version_number: from,
      size: fromItem.size,
      uploader_id: fromItem.uploader_id,
      comment: fromItem.comment,
      is_current: fromItem.is_current,
      created_at: fromItem.created_at,
    },
    to_meta: {
      version_id: toItem.id,
      version_number: to,
      size: toItem.size,
      uploader_id: toItem.uploader_id,
      comment: toItem.comment,
      is_current: toItem.is_current,
      created_at: toItem.created_at,
    },
  }
}

async function mountVersionsView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/drive', component: { template: '<div />' } },
      { path: '/drive/file/:id/versions', component: DesktopFileVersionsView },
    ],
  })
  await router.push('/drive/file/99/versions')
  await router.isReady()

  const wrapper = mount(DesktopFileVersionsView, {
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

function axiosMock() {
  return globalThis.__desktopVersionDiffAxios
}

describe('desktop_drive_version_diff', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'desktop-test-token')
    axiosMock().get.mockReset()
    axiosMock().get.mockImplementation((url) => {
      if (url === '/api/v1/drive/files/99/versions') {
        return Promise.resolve({ data: versionsFixture })
      }
      if (url.includes('/api/v1/drive/versions/files/99/diff?')) {
        const query = new URL(url, 'http://localhost').searchParams
        return Promise.resolve({ data: diffFixture(Number(query.get('from')), Number(query.get('to'))) })
      }
      return Promise.reject(new Error(`unmocked GET: ${url}`))
    })
  })

  it('场景1: 顶部“版本对比”按钮打开桌面弹窗', async () => {
    const wrapper = await mountVersionsView()
    const openButton = wrapper.find('[data-testid="open-version-diff"]')

    expect(openButton.exists()).toBe(true)
    expect(wrapper.vm.diffDialogVisible).toBe(false)
    await openButton.trigger('click')
    await flushPromises()

    expect(wrapper.vm.diffDialogVisible).toBe(true)
    expect(wrapper.findComponent(DesktopVersionDiffDialog).exists()).toBe(true)
    expect(wrapper.html()).toContain('起始版本')
    expect(wrapper.html()).toContain('目标版本')
  })

  it('场景2: 选择 from v1 / to v3 后请求对应 query', async () => {
    const wrapper = await mountVersionsView()
    await wrapper.find('[data-testid="open-version-diff"]').trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent(DesktopVersionDiffDialog)
    dialog.vm.fromVersion = 1
    dialog.vm.toVersion = 3
    dialog.vm.onSelectionChange()
    await flushPromises()

    expect(axiosMock().get).toHaveBeenCalledWith(
      '/api/v1/drive/versions/files/99/diff?from=1&to=3',
      expect.objectContaining({
        headers: { Authorization: 'Bearer desktop-test-token' },
      }),
    )
    expect(dialog.vm.diffResult.from_version_number).toBe(1)
    expect(dialog.vm.diffResult.to_version_number).toBe(3)
  })

  it('场景3: unified diff 显示 from/to 轨道并高亮增删行', async () => {
    const wrapper = await mountVersionsView()
    await wrapper.find('[data-testid="open-version-diff"]').trigger('click')
    await flushPromises()

    const viewer = wrapper.find('[data-testid="unified-diff"]')
    expect(viewer.exists()).toBe(true)
    expect(viewer.text()).toContain('FROM · v2')
    expect(viewer.text()).toContain('TO · v3')
    expect(wrapper.find('.dvd-diff-cell.is-delete').text()).toContain('旧实验结论')
    expect(wrapper.find('.dvd-diff-cell.is-add').text()).toContain('新实验结论')
  })
})
