import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.js'],
    // PR #10: 排除 Playwright 视觉回归（单独运行）
    // 2026-08-31: 另排除 3 个放错位置的 Playwright spec —— 它们 import '@playwright/test'
    // 却躺在 tests/e2e/*.spec.js 里; Playwright testMatch 只认 tests/visual/**/*.spec.mjs
    // (即它们从没被任何 runner 跑过), 而 vitest 收集到就整体崩 ("test.use() did not
    // expect to be called here")。同目录其余 .spec.js 均为真 vitest 测试, 故按文件排除。
    exclude: [
      '**/node_modules/**',
      'tests/visual/**',
      'tests/e2e/mobile_swipe_gesture.spec.js',
      'tests/e2e/mobile_voice_input.spec.js',
      'tests/e2e/mobile_push_notification.spec.js',
      // 2026-09-30 S3.4: 第 4 个同类漏网。Playwright testMatch 只认 tests/visual/**,
      // 故这些 spec 从未被任何 runner 跑过, 在 vitest 里只会整体崩。
      'tests/e2e/mobile-baseline.spec.js',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/composables/**', 'src/components/**']
    }
  }
})
