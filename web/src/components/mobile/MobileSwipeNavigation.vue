<!--
  MobileSwipeNavigation.vue — 移动端左右滑切换页面包装组件 (W68 G-2 新增)
  2026-07-24  W68 路线 G-2 Mobile 手势导航

  功能:
  - 包装任意子内容, 在 wrapper 上接管水平 swipe 事件
  - 滑动过程中显示左右边缘阴影 (CSS class .swiping-left / .swiping-right)
  - 触发后: 触觉反馈 navigator.vibrate(10) + 调 leftAction/rightAction
  - iOS Safari 兼容: overscroll-behavior-x: contain 防边缘回弹手势误触发
  - touch-action: pan-y 阻止默认水平滚动

  用法:
    <MobileSwipeNavigation
      :left-action="onSwipeLeft"
      :right-action="onSwipeRight"
    >
      <PageContent />
    </MobileSwipeNavigation>
-->
<template>
  <div
    ref="rootRef"
    class="mobile-swipe-navigation"
    :class="[`swipe-${currentSwipe || 'idle'}`]"
    :aria-label="ariaLabel"
  >
    <div v-if="currentSwipe === 'left'" class="swipe-edge-shadow swipe-edge-shadow-right" aria-hidden="true" />
    <div v-if="currentSwipe === 'right'" class="swipe-edge-shadow swipe-edge-shadow-left" aria-hidden="true" />

    <slot />

    <!-- 调试 / 测试 hook: data-swipe-current 给 e2e 测试读取当前状态 -->
    <span class="swipe-debug" :data-swipe-current="currentSwipe || 'idle'" hidden />
  </div>
</template>

<script>
import { ref } from 'vue'
import { useSwipeGesture } from '@/composables/useSwipeGesture'

export default {
  name: 'MobileSwipeNavigation',
  props: {
    leftAction: { type: Function, default: null },
    rightAction: { type: Function, default: null },
    enableVibrate: { type: Boolean, default: true },
    threshold: { type: Number, default: 50 },
    ariaLabel: { type: String, default: '滑动切换页面区域' },
  },
  setup(props) {
    const rootRef = ref(null)
    const { onSwipeLeft, onSwipeRight, currentSwipe } = useSwipeGesture(rootRef, {
      threshold: props.threshold,
      timeout: 300,
      velocity: 0.3,
      preventScrollConflict: true,
    })

    function vibrate() {
      if (!props.enableVibrate) return
      if (typeof navigator === 'undefined' || !navigator.vibrate) return
      try {
        navigator.vibrate(10)  // 10ms 短促触觉, 不打扰
      } catch (err) {
        // 用户拒绝权限 / 老浏览器 / 静默降级
      }
    }

    onSwipeLeft(() => {
      vibrate()
      if (typeof props.leftAction === 'function') {
        try { props.leftAction() } catch (err) { console.error('[MobileSwipeNavigation] leftAction error:', err) }
      }
    })

    onSwipeRight(() => {
      vibrate()
      if (typeof props.rightAction === 'function') {
        try { props.rightAction() } catch (err) { console.error('[MobileSwipeNavigation] rightAction error:', err) }
      }
    })

    return {
      rootRef,
      currentSwipe,
      ariaLabel: props.ariaLabel,
    }
  },
}
</script>

<style scoped>
.mobile-swipe-navigation {
  position: relative;
  width: 100%;
  height: 100%;
  /* iOS Safari 边缘手势兼容: 阻止 overscroll 触发系统返回手势 */
  overscroll-behavior-x: contain;
  /* touch-action: pan-y 允许垂直滚动, 禁止水平滚动 (浏览器自己处理水平 swipe) */
  touch-action: pan-y;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
}

.swipe-edge-shadow {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 18px;
  pointer-events: none;
  z-index: 5;
  /* 渐变阴影提示用户: 这一侧有可触发动作 */
  background: linear-gradient(to var(--shadow-direction, right), rgba(0, 0, 0, 0.18), transparent);
  transition: opacity 150ms ease;
}

.swipe-edge-shadow-right {
  right: 0;
  --shadow-direction: right;
}

.swipe-edge-shadow-left {
  left: 0;
  --shadow-direction: left;
}

.swipe-debug {
  display: none;
}

/* 暗色模式适配 (继承 design tokens) */
:global(html[data-theme='dark']) .mobile-swipe-navigation .swipe-edge-shadow {
  background: linear-gradient(to var(--shadow-direction, right), rgba(255, 255, 255, 0.10), transparent);
}
</style>