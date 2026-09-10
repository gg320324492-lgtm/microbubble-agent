/**
 * resolveAvatarUrl 单测 (2026-09-10 头像 404 修复)
 * 跑法: npx vitest run src/utils/__tests__/resolveAvatarUrl.test.js
 */
import { describe, it, expect } from 'vitest'
import { resolveAvatarUrl } from '@/utils/memberIdentity'

describe('resolveAvatarUrl', () => {
  it('裸 object key 补 minio 反代前缀 (相对路径, 双部署形态同源)', () => {
    expect(resolveAvatarUrl('avatars/9772d5ed.jpg')).toBe('/minio/microbubble/avatars/9772d5ed.jpg')
    expect(resolveAvatarUrl('/avatars/x.jpg')).toBe('/minio/microbubble/avatars/x.jpg')
  })
  it('已是完整 URL 原样返回', () => {
    const u = 'https://agent.mnb-lab.cn/minio/microbubble/avatars/x.jpg'
    expect(resolveAvatarUrl(u)).toBe(u)
  })
  it('已是 /minio/ 相对形态不重复加前缀', () => {
    expect(resolveAvatarUrl('/minio/microbubble/avatars/x.jpg')).toBe('/minio/microbubble/avatars/x.jpg')
  })
  it('空值/非字符串安全透传 (统一 undefined 让 el-avatar 走 fallback slot)', () => {
    expect(resolveAvatarUrl(null)).toBeUndefined()
    expect(resolveAvatarUrl('')).toBeUndefined()
    expect(resolveAvatarUrl(undefined)).toBeUndefined()
  })
})
