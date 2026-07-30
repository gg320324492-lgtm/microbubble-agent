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
    // W89-X-21: Vitest 与 Playwright 测试收集边界隔离
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.{idea,git,cache,output,temp}/**',
      '**/tests/e2e/{mobile_push_notification,mobile_swipe_gesture,mobile_voice_input}.spec.{js,ts}',
      '**/tests/visual/{mobile,desktop,e2e,a11y,local-only,pwa}/**/*.spec.{js,ts,mjs}',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/composables/**', 'src/components/**']
    }
  }
})
