// vitest — node 环境跑主进程服务测试（用 node:sqlite 适配器，避开 Electron ABI），
// *.dom.test.ts 走 jsdom 跑组件契约测试（happy-dom 18 事件构造器与 VTU 不兼容，故用 jsdom）
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [vue()],
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    environmentMatchGlobs: [['tests/unit/**/*.dom.test.ts', 'jsdom']]
  },
  resolve: {
    alias: {
      '@shared': resolve(__dirname, 'src/shared'),
      '@main': resolve(__dirname, 'src/main'),
      '@renderer': resolve(__dirname, 'src/renderer/src')
    }
  }
})
