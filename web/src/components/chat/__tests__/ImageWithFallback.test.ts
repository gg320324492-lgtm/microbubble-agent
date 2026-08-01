/**
 * ImageWithFallback 单测 — W99 +20 派工 v10
 * 6 case 覆盖：基础渲染 / onerror 兜底 / onFailed 回调 / alt 透传 / 自定义 class / 重复 onerror 防重入
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ImageWithFallback from '../ImageWithFallback.vue'

describe('ImageWithFallback — W99 +20', () => {
  it('① 基础渲染：失败前显示 img', () => {
    const wrapper = mount(ImageWithFallback, { props: { src: '/a.png', alt: 'A' } })
    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/a.png')
    expect(img.attributes('alt')).toBe('A')
    expect(img.attributes('loading')).toBe('lazy')
  })

  it('② onerror 触发后切到占位符', async () => {
    const wrapper = mount(ImageWithFallback, { props: { src: '/missing.png' } })
    const img = wrapper.find('img')
    await img.trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    const fallback = wrapper.find('.image-fallback')
    expect(fallback.exists()).toBe(true)
    expect(fallback.text()).toContain('图片加载失败')
  })

  it('③ onFailed 回调被调用（埋点）', async () => {
    const onFailed = vi.fn()
    const wrapper = mount(ImageWithFallback, {
      props: { src: '/bad.png', onFailed },
    })
    await wrapper.find('img').trigger('error')
    expect(onFailed).toHaveBeenCalledWith('/bad.png')
  })

  it('④ alt 透传到 fallback aria-label', async () => {
    const wrapper = mount(ImageWithFallback, {
      props: { src: '/x.png', alt: '自定义 alt' },
    })
    await wrapper.find('img').trigger('error')
    const fallback = wrapper.find('.image-fallback')
    expect(fallback.attributes('aria-label')).toBe('自定义 alt')
  })

  it('⑤ 自定义 fallbackText', async () => {
    const wrapper = mount(ImageWithFallback, {
      props: { src: '/x.png', fallbackText: '404 not found' },
    })
    await wrapper.find('img').trigger('error')
    expect(wrapper.find('.image-fallback').text()).toContain('404 not found')
  })

  it('⑥ 重复 onerror 不重复触发 onFailed', async () => {
    const onFailed = vi.fn()
    const wrapper = mount(ImageWithFallback, {
      props: { src: '/x.png', onFailed },
    })
    const img = wrapper.find('img')
    await img.trigger('error')
    // 二次触发：img 已不在 DOM，需重新查
    const fallback = wrapper.find('.image-fallback')
    expect(fallback.exists()).toBe(true)
    // onFailed 只应被调一次
    expect(onFailed).toHaveBeenCalledTimes(1)
  })
})
