<template>
  <Teleport to="body">
    <Transition name="mobile-push-dialog-fade">
      <div
        v-if="modelValue"
        class="mobile-push-dialog-mask"
        role="dialog"
        aria-modal="true"
        aria-labelledby="push-dialog-title"
        @click.self="onMaskClick"
      >
        <div class="mobile-push-dialog-card" :style="cardStyle">
          <div class="icon-wrap" aria-hidden="true">
            <span class="icon-bell">🔔</span>
          </div>
          <h2 id="push-dialog-title" class="dialog-title">启用推送通知？</h2>
          <p class="dialog-desc">
            开启后，{{ shortAppName }} 会在以下情况第一时间通知您：
          </p>
          <ul class="benefit-list">
            <li>
              <span class="benefit-icon" aria-hidden="true">💬</span>
              <span>有人 @ 提到您</span>
            </li>
            <li>
              <span class="benefit-icon" aria-hidden="true">📁</span>
              <span>网盘文件被分享 / 评论</span>
            </li>
            <li>
              <span class="benefit-icon" aria-hidden="true">⏰</span>
              <span>每日 {{ digestTime }} 任务提醒</span>
            </li>
          </ul>
          <div class="compat-hint" v-if="!canPush">
            <p v-if="isIOS && !isStandalone" class="warn-text">
              📱 iOS Safari 必须先将本应用<strong>添加到主屏</strong>才能启用推送。
            </p>
            <p v-else class="warn-text">
              ⚠️ 当前浏览器不支持 Web Push API, 可后续在 Chrome / Edge 桌面体验完整功能。
            </p>
          </div>
          <div class="action-row">
            <button
              type="button"
              class="btn btn-secondary"
              @click="onDismiss"
              :disabled="loading"
            >
              {{ isDismissed ? '不再提醒' : '暂不开启' }}
            </button>
            <button
              type="button"
              class="btn btn-primary"
              @click="onAllow"
              :disabled="loading || !canPush"
            >
              {{ loading ? '请求中…' : '允许通知' }}
            </button>
          </div>
          <p class="footer-hint">
            可在「设置 → 推送通知」中随时修改
          </p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * MobilePushPermissionDialog.vue — 移动端推送权限申请弹窗 (W68 路线 5 第 3 批)
 *
 * 设计目标:
 * 1. 首次访问 / 启用通知时弹出 (类 iOS Safari 原生体验)
 * 2. 拒绝 / 关闭后 7 天不再弹 (composable 内部维护 dismissed TTL)
 * 3. iOS Safari 兼容: 检测 standalone PWA + 给出"添加到主屏"引导
 * 4. v-model 控制显示 / 隐藏 (父组件控制)
 * 5. emit('allow') / emit('dismiss') / emit('error') 父组件可监听
 *
 * 复用:
 * - useMobilePushNotification (本批新建 composable)
 * - useMobileSafeArea (W68 路线 C Agent 2) — 避开 iPhone 刘海
 * - useHaptic (已有)
 *
 * 6 大铁律:
 * 1. iOS 16.4+ 必须 standalone (添加到主屏) 才能 push — 给出明确文案引导
 * 2. 7 天 TTL 拒绝冷却 — 避免用户被骚扰
 * 3. v-model + emit 双工 — 父组件既控制显示也能监听结果
 * 4. requestPermission 必须在用户手势内 (本组件内 click 触发满足)
 * 5. showLocal 调试入口保留 — 允许后可手动测试本地通知
 * 6. 视觉与 nut-action-sheet 对齐 — 圆角 + 阴影 + fade 动画 (复用 W68 路线 C 风格)
 */

import { ref, computed, watch } from 'vue'
import { useMobilePushNotification } from '@/composables/useMobilePushNotification'
import { useMobileSafeArea } from '@/composables/useMobileSafeArea'
import { useHaptic } from '@/composables/chat/useHaptic'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  appName: { type: String, default: '小气助手' },
  digestTime: { type: String, default: '11:00' },
  dismissOnMaskClick: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'allow', 'dismiss', 'error'])

const push = useMobilePushNotification()
const safeArea = useMobileSafeArea()
const haptic = useHaptic()

const loading = ref(false)

// 计算属性
const canPush = computed(() => push.canPush.value)
const isIOS = computed(() => push.isIOS.value)
const isStandalone = computed(() => push.isStandalone.value)
const isDismissed = computed(() => push.isDismissed.value)
const shortAppName = computed(() => props.appName)

// 底部安全区 padding
const cardStyle = computed(() => ({
  paddingBottom: `calc(20px + ${safeArea.bottom.value})`,
}))

// 监听 modelValue, 显示时 haptic
watch(() => props.modelValue, (val) => {
  if (val) {
    haptic.tap()
  }
})

function onAllow() {
  loading.value = true
  haptic.tap()
  ;(async () => {
    try {
      const result = await push.requestPermission()
      if (result === 'granted') {
        // 进一步订阅 (走降级路径, 项目目前无 VAPID)
        await push.subscribe()
        emit('allow', { permission: result })
        emit('update:modelValue', false)
        // 成功后给一个本地通知提示用户已开启
        setTimeout(() => {
          push.showLocal({
            title: `${props.appName} 推送已开启`,
            body: '您将在收到重要通知时看到横幅提醒',
            tag: 'push-enabled-confirm',
          })
        }, 300)
      } else {
        // denied / default
        emit('dismiss', { permission: result })
        emit('update:modelValue', false)
      }
    } catch (e) {
      emit('error', e)
      emit('update:modelValue', false)
    } finally {
      loading.value = false
    }
  })()
}

function onDismiss() {
  loading.value = true
  push.markDismissed()
  haptic.warning()
  emit('dismiss', { permission: push.permission.value })
  emit('update:modelValue', false)
  loading.value = false
}

function onMaskClick() {
  if (props.dismissOnMaskClick) {
    onDismiss()
  }
}
</script>

<style scoped>
.mobile-push-dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  /* 让 dialog 跟 iOS Safari 一样有毛玻璃背景 (支持 backdrop-filter 时) */
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
}

.mobile-push-dialog-card {
  background: var(--color-bg-card, #fff);
  border-radius: var(--radius-xl, 16px);
  padding: 24px 22px 20px;
  width: 100%;
  max-width: 360px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
  text-align: center;
}

.icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, var(--color-primary, #FF7A5C), var(--color-accent, #FFB347));
  border-radius: 50%;
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.25);
}

.icon-bell {
  font-size: 32px;
  line-height: 1;
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.1));
}

.dialog-title {
  margin: 0 0 10px;
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary, #303133);
}

.dialog-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--color-text-secondary, #606266);
  line-height: 1.5;
}

.benefit-list {
  list-style: none;
  margin: 0 0 16px;
  padding: 14px 16px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: var(--radius-md, 8px);
  text-align: left;
}

.benefit-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--color-text-primary, #303133);
  line-height: 1.8;
}

.benefit-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.compat-hint {
  margin-bottom: 16px;
  padding: 10px 12px;
  background: var(--color-warning-bg, #fdf6ec);
  border-radius: var(--radius-sm, 4px);
  border-left: 3px solid var(--color-warning, #E6A23C);
}

.warn-text {
  margin: 0;
  font-size: 12px;
  color: var(--color-warning, #E6A23C);
  line-height: 1.5;
  text-align: left;
}

.action-row {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
}

.btn {
  flex: 1;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  border: none;
  border-radius: var(--radius-md, 8px);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: opacity 0.15s ease, transform 0.1s ease;
}

.btn:active {
  transform: scale(0.97);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-regular, #606266);
}

.btn-primary {
  background: linear-gradient(135deg, var(--color-primary, #FF7A5C), var(--color-accent, #FFB347));
  color: #fff;
  box-shadow: 0 2px 8px rgba(255, 122, 92, 0.3);
}

.footer-hint {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--color-text-placeholder, #909399);
  line-height: 1.4;
}

/* 过渡动画 */
.mobile-push-dialog-fade-enter-active,
.mobile-push-dialog-fade-leave-active {
  transition: opacity 0.2s ease;
}

.mobile-push-dialog-fade-enter-from,
.mobile-push-dialog-fade-leave-to {
  opacity: 0;
}

.mobile-push-dialog-fade-enter-active .mobile-push-dialog-card,
.mobile-push-dialog-fade-leave-active .mobile-push-dialog-card {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.mobile-push-dialog-fade-enter-from .mobile-push-dialog-card {
  transform: translateY(20px) scale(0.95);
}

.mobile-push-dialog-fade-leave-to .mobile-push-dialog-card {
  transform: translateY(10px) scale(0.98);
}

/* Dark mode 适配 (CLAUDE.md v60-v67 教训 — 必须非 scoped, 但此组件 scoped 也行因为 :deep) */
@media (prefers-color-scheme: dark) {
  .mobile-push-dialog-card {
    background: #1f1f1f;
    color: #e5e5e5;
  }
  .dialog-title { color: #e5e5e5; }
  .dialog-desc { color: #b0b0b0; }
  .benefit-list { background: #2a2a2a; }
  .benefit-list li { color: #e5e5e5; }
}
</style>