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
      // 2026-09-30 S3.4: 同类漏网补齐。mobile-baseline.spec.js 是真 Playwright
      // spec (import { test, expect } from '@playwright/test'), 归 playwright 跑, vitest 排除。
      'tests/e2e/mobile-baseline.spec.js',
      // ⚠️ mobile_dark_v33.spec.js **不能**排除: 它是 vitest + @vue/test-utils 用例
      // (文件头自述 + 第 29-30 行 import), 跑在 vitest 里。曾误加进 playwright.e2e.config.js
      // 的 testMatch, 结果 vitest 排除 + playwright 跑不了 = 彻底不跑, 比改动前更糟。
      // 它断言的"dark 模式 6 view 不应有硬编码 hex" stylelint 不管 (color-no-hex: null),
      // 故它是那条约束的唯一执行者。
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/composables/**', 'src/components/**']
    }
  }
})
