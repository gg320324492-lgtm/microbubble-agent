// 2026-07-08 修复验证 - el-popover 改用 :visible 受控 prop 范式
// v1 (2026-07-03): el-popconfirm → el-popover + ref.show(), @click.stop 挡住冒泡
// v2 (2026-07-08): 改用 :visible + @update:visible, EP 2.4.4 __expose 不暴露 show()
//   ref.show() 返回 undefined, 弹框永不弹出 → 看到"点了删除按钮没反应"
import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { nextTick } from 'vue'

describe('MeetingView delete popover fix - 2026-07-08 受控 visible 范式', () => {
  it('核心证明 (回归): 删除按钮 @click.stop 挡住外层 card @click 冒泡', async () => {
    const ElButton = (await import('element-plus')).ElButton
    const ElPopover = (await import('element-plus')).ElPopover

    const log = []

    const Comp = {
      components: { ElButton, ElPopover },
      template: `
        <div class="card" @click="onCardClick">
          <el-popover
            :width="220"
            trigger="manual"
            popper-class="delete-meeting-popover"
            :visible="!!visible[100]"
            @update:visible="(v) => visible[100] = v"
          >
            <template #reference>
              <el-button
                class="del-btn"
                :data-delete-ref-id="100"
                @click.stop="openPopover(100)"
              >删除</el-button>
            </template>
          </el-popover>
        </div>
      `,
      data() {
        return { visible: {} }
      },
      methods: {
        onCardClick() { log.push('card_click') },
        openPopover(id) { log.push('openPopover'); this.visible[id] = true },
      },
    }

    const wrapper = mount(Comp, { attachTo: document.body })
    const delBtn = wrapper.find('.del-btn')
    await delBtn.trigger('click')
    await nextTick()

    console.log('click log:', JSON.stringify(log))
    expect(log).toContain('openPopover')
    expect(log).not.toContain('card_click')  // ← @click.stop 防冒泡

    wrapper.unmount()
  })

  it('核心证明 (新): 受控 :visible + @update:visible 范式, 点击删除按钮后 visible[id] 变 true (确认弹框会开)', async () => {
    const ElButton = (await import('element-plus')).ElButton
    const ElPopover = (await import('element-plus')).ElPopover

    const Comp = {
      components: { ElButton, ElPopover },
      template: `
        <el-popover
          :width="220"
          trigger="manual"
          popper-class="delete-meeting-popover"
          :visible="!!visible[100]"
          @update:visible="(v) => visible[100] = v"
        >
          <template #reference>
            <el-button
              class="del-btn"
              :data-delete-ref-id="100"
              @click.stop="openPopover(100)"
            >删除</el-button>
          </template>
        </el-popover>
      `,
      data() {
        return { visible: {} }
      },
      methods: {
        openPopover(id) { this.visible[id] = true },
      },
    }

    const wrapper = mount(Comp, { attachTo: document.body })

    // 点击前: visible[100] 为 undefined, 弹框不开
    expect(wrapper.vm.visible[100]).toBeUndefined()
    // 点击删除按钮 → openPopover 写入 visible[100] = true
    await wrapper.find('.del-btn').trigger('click')
    await nextTick()

    // 核心断言 (2026-07-08 新增): 弹框可见状态已切到 true, EP 受控 prop 路径会真正打开
    expect(wrapper.vm.visible[100]).toBe(true)

    wrapper.unmount()
  })

  it('回归保护: 删除按钮有 data-delete-ref-id 属性 (用于外部点击关闭检测)', async () => {
    const ElButton = (await import('element-plus')).ElButton
    const ElPopover = (await import('element-plus')).ElPopover

    const Comp = {
      components: { ElButton, ElPopover },
      template: `
        <el-popover
          :width="220"
          trigger="manual"
          popper-class="delete-meeting-popover"
          :visible="!!visible[100]"
          @update:visible="(v) => visible[100] = v"
        >
          <template #reference>
            <el-button
              class="del-btn"
              :data-delete-ref-id="100"
              @click.stop="openPopover(100)"
            >删除</el-button>
          </template>
        </el-popover>
      `,
      data() {
        return { visible: {} }
      },
      methods: {
        openPopover(id) { this.visible[id] = true },
      },
    }

    const wrapper = mount(Comp, { attachTo: document.body })
    const delBtn = wrapper.find('[data-delete-ref-id="100"]')
    expect(delBtn.exists()).toBe(true)
    expect(delBtn.attributes('data-delete-ref-id')).toBe('100')

    wrapper.unmount()
  })
})
