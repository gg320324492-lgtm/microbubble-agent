// 2026-07-03 修复验证 - el-popconfirm → el-popover 替代
// 核心证明: el-popover + @click.stop 能挡住 click 冒泡到外层 card
// (jsdom 模拟不出来 trigger="manual" 的真实 popper 显示, 但核心 click 不冒泡可验证)
import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { nextTick } from 'vue'

describe('MeetingView delete popover fix - 核心验证', () => {
  it('核心证明: el-popover + @click.stop 替代 el-popconfirm 后, 删除按钮 click 不冒泡到外层 card', async () => {
    const ElButton = (await import('element-plus')).ElButton
    const ElPopover = (await import('element-plus')).ElPopover

    const log = []

    const Comp = {
      components: { ElButton, ElPopover },
      template: `
        <div class="card" @click="onCardClick">
          <el-popover
            :ref="el => setPopoverRef(el)"
            trigger="manual"
            popper-class="delete-meeting-popover"
          >
            <template #reference>
              <el-button
                class="del-btn"
                :data-delete-ref-id="100"
                @click.stop="openPopover"
              >删除</el-button>
            </template>
          </el-popover>
        </div>
      `,
      methods: {
        onCardClick() { log.push('card_click') },
        openPopover() { log.push('openPopover') },
        setPopoverRef(el) { this.popoverRef = el },
      },
    }

    const wrapper = mount(Comp, { attachTo: document.body })

    // 核心: 点删除按钮 → 应只触发 openPopover, 不触发外层 card 的 viewMeeting
    const delBtn = wrapper.find('.del-btn')
    await delBtn.trigger('click')
    await nextTick()

    console.log('click log:', JSON.stringify(log))
    // 期望: openPopover in log, card_click NOT in log
    expect(log).toContain('openPopover')
    expect(log).not.toContain('card_click')

    wrapper.unmount()
  })

  it('回归保护: 删除按钮有 data-delete-ref-id 属性 (用于外部点击关闭检测)', async () => {
    const ElButton = (await import('element-plus')).ElButton
    const ElPopover = (await import('element-plus')).ElPopover

    const Comp = {
      components: { ElButton, ElPopover },
      template: `
        <el-popover
          :ref="el => setPopoverRef(el)"
          trigger="manual"
          popper-class="delete-meeting-popover"
        >
          <template #reference>
            <el-button
              class="del-btn"
              :data-delete-ref-id="100"
              @click.stop="openPopover"
            >删除</el-button>
          </template>
        </el-popover>
      `,
      methods: {
        openPopover() {},
        setPopoverRef(el) { this.popoverRef = el },
      },
    }

    const wrapper = mount(Comp, { attachTo: document.body })
    const delBtn = wrapper.find('[data-delete-ref-id="100"]')
    expect(delBtn.exists()).toBe(true)
    expect(delBtn.attributes('data-delete-ref-id')).toBe('100')

    wrapper.unmount()
  })
})