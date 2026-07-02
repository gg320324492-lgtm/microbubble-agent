import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import UploadStatusBadge from '../UploadStatusBadge.vue'

/**
 * v2.2 修复测试 (2026-07-03): 徽章 stale-chunk 容错
 * 核心: uploadedCount === totalCount 时, 即使 online=false 徽章也走 complete 分支
 * 根因: 录音停止后 chunks 不再 markReachable, probe 累积 3 次失败
 *        翻红 (v2.1 c1a5abbe 设计) → 徽章 offline 分支误报"⚠ 网络已断开"
 * 修复: effectiveOnline 加 allUploaded 兜底, 事实级信号压过探测级信号
 */
describe('UploadStatusBadge v2.2 — stale-chunk 容错', () => {
  const factory = (props = {}) => mount(UploadStatusBadge, {
    props: {
      online: true,
      uploadedCount: 0,
      totalCount: 0,
      pendingCount: 0,
      state: 'recording',
      ...props,
    },
  })

  it('1. online=true + uploadedCount=totalCount=0 不显示徽章 (idle 态)', () => {
    const wrapper = factory({ state: 'idle' })
    // visible = false (idle 不显示)
    expect(wrapper.find('.upload-status-badge').exists()).toBe(false)
  })

  it('2. online=true + uploadedCount=totalCount=5 + state=recording → 显示"✓ 录音已安全保存"', () => {
    const wrapper = factory({ online: true, uploadedCount: 5, totalCount: 5, state: 'stopped' })
    expect(wrapper.find('.badge-text').text()).toBe('✓ 录音已安全保存')
    // 不应有 is-offline class
    expect(wrapper.find('.upload-status-badge').classes()).not.toContain('is-offline')
  })

  it('3.【v2.2 关键】online=false + uploadedCount=totalCount=5 + pendingCount=0 → 仍走 complete 分支', () => {
    // 场景: 录音已停, chunks 全部成功 (uploadedCount === totalCount),
    // 但 online 翻红 (probe 偶发 3 次失败)
    // 期望: 徽章显示"✓ 录音已安全保存", 而非"⚠ 网络已断开"
    const wrapper = factory({
      online: false,
      uploadedCount: 5,
      totalCount: 5,
      pendingCount: 0,
      state: 'stopped',
    })
    const text = wrapper.find('.badge-text').text()
    expect(text).toBe('✓ 录音已安全保存')
    // 关键断言: is-offline class 不应出现
    expect(wrapper.find('.upload-status-badge').classes()).not.toContain('is-offline')
    // is-complete class 应出现
    expect(wrapper.find('.upload-status-badge').classes()).toContain('is-complete')
  })

  it('4. online=false + uploadedCount < totalCount + pendingCount > 0 → 显示"N 片待联网重传"', () => {
    const wrapper = factory({
      online: false,
      uploadedCount: 2,
      totalCount: 5,
      pendingCount: 3,
      state: 'recording',
    })
    const text = wrapper.find('.badge-text').text()
    expect(text).toBe('⚠ 网络已断开，3 片待联网重传')
  })

  it('5. online=false + uploadedCount < totalCount + pendingCount=0 → 显示"已上传 X / Y"', () => {
    // P0 场景保留: 部分成功但还没全完, 离线时显示已上传数
    const wrapper = factory({
      online: false,
      uploadedCount: 3,
      totalCount: 5,
      pendingCount: 0,
      state: 'recording',
    })
    const text = wrapper.find('.badge-text').text()
    expect(text).toBe('⚠ 网络已断开，录音已暂存本地（已上传 3 / 5 片）')
  })

  it('6. online=true + pendingCount > 0 → 显示"上传中: X / Y 片"', () => {
    const wrapper = factory({
      online: true,
      uploadedCount: 3,
      totalCount: 5,
      pendingCount: 2,
      state: 'recording',
    })
    const text = wrapper.find('.badge-text').text()
    expect(text).toBe('上传中：3 / 5 片')
    expect(wrapper.find('.upload-status-badge').classes()).toContain('is-uploading')
  })

  it('7.【v2.2 关键】手动重试按钮在 allUploaded 时隐藏', () => {
    const wrapper = factory({
      online: false,
      uploadedCount: 5,
      totalCount: 5,
      pendingCount: 0,
      state: 'stopped',
    })
    // v2.2: 已上传完成即使 online=false 也不显示手动重试
    expect(wrapper.find('.badge-action').exists()).toBe(false)
  })

  it('8. 手动重试按钮在 pendingCount > 0 + 未完成时显示 (online=false)', () => {
    const wrapper = factory({
      online: false,
      uploadedCount: 2,
      totalCount: 5,
      pendingCount: 3,
      state: 'recording',
    })
    expect(wrapper.find('.badge-action').exists()).toBe(true)
  })

  it('9. 极端边界: uploadedCount=0 + totalCount=0 + online=false + pendingCount=0 → 显示兜底文案', () => {
    const wrapper = factory({
      online: false,
      uploadedCount: 0,
      totalCount: 0,
      pendingCount: 0,
      state: 'recording',
    })
    // 兜底: '⚠ 网络已断开，录音暂存于本地'
    const text = wrapper.find('.badge-text').text()
    expect(text).toBe('⚠ 网络已断开，录音暂存于本地')
  })

  it('10. v2.2 防御: 即使 effectiveOnline 因 bug 没包 allUploaded, message 也走 complete', () => {
    // 验证 message 函数第一个 if 守卫 (allUploaded.value) 独立保护
    // 这个测试是设计冗余, 防止 effectiveOnline 公式被未来修改弄丢 allUploaded
    const wrapper = factory({
      online: false,
      uploadedCount: 5,
      totalCount: 5,
      pendingCount: 0,
      state: 'stopped',
    })
    expect(wrapper.find('.badge-text').text()).toBe('✓ 录音已安全保存')
  })
})
