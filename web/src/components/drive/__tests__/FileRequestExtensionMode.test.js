// FileRequestExtensionMode.test.js — 创建文件请求的格式三档 (2026-11-10)
//
// 判据: 默认"不限格式"**不能**偷偷下发任何白名单/video_only；
// 只有显式选择"仅视频"或"自定义"才带限制。payload 是唯一可信证据
// (类 20.220: 界面写着不限, 不代表请求里真的没带限制)。
// 直接驱动 setup 状态而非模拟 el-dialog 的 slot/stub —— Element Plus 的
// dialog 是 Teleport, 用简化 stub 点按钮 fragile, 且测不到真正的契约 (payload)。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed } from 'vue'

const stubs = {
  'el-dialog': true, 'el-input': true, 'el-button': true, 'el-icon': true,
  'el-empty': true, 'el-switch': true, 'el-tag': true, 'el-form': true,
  'el-form-item': true, 'el-select': true, 'el-option': true,
  'el-input-number': true, 'QrCode': true,
}
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') },
}))
vi.mock('@element-plus/icons-vue', () => ({ Plus: { template: '<i />' } }))
vi.mock('@/views/drive/drive-view.css', () => ({}))

const created = vi.hoisted(() => ({ fn: vi.fn() }))
vi.mock('@/composables/useFileRequests', () => ({
  useFileRequests: () => ({
    requests: ref([]), loading: ref(false), error: ref(null),
    hasRequests: computed(() => false),
    fetchMy: vi.fn(), createRequest: created.fn, deactivate: vi.fn(),
  }),
}))

import FileRequestListPanel from '../FileRequestListPanel.vue'

async function createWith(mode, customText = '') {
  created.fn.mockResolvedValue({ token: 'abcdefghijklmnop' })
  const w = mount(FileRequestListPanel, { global: { stubs } })
  w.vm.createForm.title = '多件收件测试'
  w.vm.createForm.extensionMode = mode
  w.vm.createForm.extensionsText = customText
  await w.vm.onCreate()
  await flushPromises()
  return created.fn.mock.calls.at(-1)[0]
}

beforeEach(() => { vi.clearAllMocks() })

describe('创建面板: 格式三档与后端同源', () => {
  it('默认「不限格式」⇒ payload 既无 allowed_extensions 也无 video_only', async () => {
    const p = await createWith('any')
    expect(p.allowed_extensions).toBeUndefined()
    expect(p.video_only).toBeUndefined()
  })

  it('显式选「仅视频」⇒ 只带 video_only: true', async () => {
    const p = await createWith('video')
    expect(p.video_only).toBe(true)
    expect(p.allowed_extensions).toBeUndefined()
  })

  it('自定义留空 = 仍不限 (allowed_extensions: null), 不套视频白名单', async () => {
    const p = await createWith('custom', '')
    expect(p.allowed_extensions).toBeNull()
    expect(p.video_only).toBeUndefined()
  })

  it('自定义填了 pdf,docx ⇒ 只有这三项, 大小写/前导点/全角逗号已归一', async () => {
    const p = await createWith('custom', '.PDF, docx，xlsx')
    expect(p.allowed_extensions).toEqual(['pdf', 'docx', 'xlsx'])
  })
})
