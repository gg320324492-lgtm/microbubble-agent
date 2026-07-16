import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// fake-indexeddb: jsdom 默认不提供 IndexedDB, 引入 fake-indexeddb 启用持久化测试
import 'fake-indexeddb/auto'

// 2026-07-16 (#207): jsdom 缺 MediaRecorder / MediaStream / AudioContext, 注入 polyfill
import { FakeMediaRecorder, FakeMediaStream, FakeAudioContext } from './setup-media-recorder.js'

if (typeof globalThis.MediaRecorder === 'undefined') {
  globalThis.MediaRecorder = FakeMediaRecorder
}
if (typeof globalThis.MediaStream === 'undefined') {
  globalThis.MediaStream = FakeMediaStream
}
if (typeof globalThis.AudioContext === 'undefined') {
  globalThis.AudioContext = FakeAudioContext
}
if (typeof globalThis.navigator !== 'undefined' && !globalThis.navigator.mediaDevices) {
  Object.defineProperty(globalThis.navigator, 'mediaDevices', {
    value: { getUserMedia: () => Promise.resolve(new FakeMediaStream()) },
    writable: true,
    configurable: true,
  })
}

// 每个测试前重置 Pinia
beforeEach(() => {
  setActivePinia(createPinia())
})

// 全局 stub Element Plus 组件
config.global.stubs = {
  'el-button': { template: '<button><slot /></button>' },
  'el-input': { template: '<input />' },
  'el-dialog': { template: '<div><slot /></div>' },
  'el-table': { template: '<div><slot /></div>' },
  'el-pagination': { template: '<div />' },
  'el-select': { template: '<select />' },
  'el-option': { template: '<option />' },
  'el-form': { template: '<form><slot /></form>' },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-date-picker': { template: '<input />' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-card': { template: '<div><slot /></div>' },
  'el-empty': { template: '<div />' }
}
