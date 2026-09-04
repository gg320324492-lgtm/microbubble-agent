/**
 * useDriveDragMove.test.js — 盘内拖拽 MIME 契约 (批次③)
 * 拖源与落点共享的序列化/解析: 防 MIME 打错字静默失效 + 外部拖拽互斥。
 */
import { describe, it, expect } from 'vitest'
import {
  DRIVE_MOVE_MIME,
  readDriveMovePayload,
  isDriveMoveDragging,
} from '@/composables/useDriveDragMove'

function fakeDT(map) {
  const types = Object.keys(map)
  return { types, getData: (k) => map[k] ?? '' }
}

describe('useDriveDragMove', () => {
  it('往返: serialize(ids) → readDriveMovePayload 还原', () => {
    const dt = fakeDT({ [DRIVE_MOVE_MIME]: JSON.stringify([3, 7, 12]) })
    expect(readDriveMovePayload(dt)).toEqual([3, 7, 12])
    expect(isDriveMoveDragging({ dataTransfer: dt })).toBe(true)
  })

  it('外部文件拖拽 (仅 Files type) 不识别为盘内移动', () => {
    const dt = fakeDT({ Files: '' })
    expect(readDriveMovePayload(dt)).toBeNull()
    expect(isDriveMoveDragging({ dataTransfer: dt })).toBe(false)
  })

  it('脏 payload 防御: 非 JSON / 非整数数组 / 空数组 → null', () => {
    expect(readDriveMovePayload(fakeDT({ [DRIVE_MOVE_MIME]: 'not-json' }))).toBeNull()
    expect(readDriveMovePayload(fakeDT({ [DRIVE_MOVE_MIME]: '[1,"2"]' }))).toBeNull()
    expect(readDriveMovePayload(fakeDT({ [DRIVE_MOVE_MIME]: '[]' }))).toBeNull()
  })

  it('dataTransfer 缺失不炸', () => {
    expect(readDriveMovePayload(null)).toBeNull()
    expect(isDriveMoveDragging(undefined)).toBe(false)
  })
})
