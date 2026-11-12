// quotaDisplayRemoved.test.js — 网盘配额显示已下线 (2026-11-12)
//
// 主指挥拍板「去掉配额显示」: 侧栏徽章「全组已用 20.8 GB / 10.0 GB」与
// 首页网盘卡片的「/ 10 GB」都不再出现; 也不再为徽章发 GET /storage-quota。
//
// 这两条读的是工作区真实源码 (不是容器镜像里的旧副本) ⇒ 必须放在前端 vitest。
import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const read = (rel) => fs.readFileSync(path.resolve(__dirname, rel), 'utf-8')

describe('网盘配额显示下线', () => {
  it('Dashboard 只显示真实已用, 不再渲染 / 上限', () => {
    const src = read('../../../views/Dashboard.vue')
    expect(src).not.toContain('driveQuotaGB')
    expect(src).not.toContain('/ {{ driveQuotaGB }}')
    expect(src).toContain('GB 已用')
  })

  it('DesktopDriveView 不再渲染配额徽章 / 不再请求 storage-quota', () => {
    const src = read('../../../views/DesktopDriveView.vue')
    expect(src).not.toContain('StorageQuotaBadge')
    expect(src).not.toContain('quotaInfo')
    expect(src).not.toContain("axios.get('/api/v1/drive/storage-quota')")
    expect(src).not.toContain('全组已用')
  })
})
