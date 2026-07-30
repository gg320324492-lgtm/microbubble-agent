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
    // W90-X-4: 排除非 vitest 范畴测试
    // - tests/visual/** (Playwright 视觉回归, 单独跑)
    // - tests/e2e/mobile_push_notification.spec.js + mobile_swipe_gesture.spec.js + mobile_voice_input.spec.js
    //   ↑ 这些是 @playwright/test 格式 (含 test.use()), 不应被 vitest 收集, 否则报
    //     "Playwright Test did not expect test.use() to be called here" (jsdom 不可重定义)
    exclude: [
      '**/node_modules/**',
      'tests/visual/**',
      'tests/e2e/mobile_push_notification.spec.js',
      'tests/e2e/mobile_swipe_gesture.spec.js',
      'tests/e2e/mobile_voice_input.spec.js',
      // W90-X-4: build regression gate (单跑, 跑 npm run build, 不入 npm run test:unit 全量)
      'tests/e2e/mobile_build_validation.spec.js',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/composables/**', 'src/components/**']
    }
  }
})
