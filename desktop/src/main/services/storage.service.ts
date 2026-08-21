// Electron 持久化 storage 的统一抽象层（main 进程使用）。
//
// 设计原则：
// - 仅存密文（refresh_token）+ 非敏感 profile（username/avatar_url 等），
//   access_token 永不入库（每次启动通过 restore 重新获取）
// - 应用根目录 + userData 模式（不同 OS 不同路径）
// - 加密文件位于 OS 用户配置目录，Win 路径示例：
//   %APPDATA%/microbubble-desktop/config.json
//
// 详见 docs/desktop-conversion/security.md §Token 未来存储原则

import Store from 'electron-store'
import { APP_CONFIG } from '@shared/config'

type StoreSchema = {
  // safeStorage 加密后的 refresh_token（base64 字符串）
  refresh_token_cipher?: string
  // 后端返回的 user profile（明文即可，敏感信息已脱敏）
  profile?: import('@shared/auth-types').UserProfile
  // 后端 URL（开发阶段可能调整，记录最后一次连的后端）
  last_backend_url?: string
}

const store = new Store<StoreSchema>({
  name: 'microbubble-desktop-config',
  // 默认 schema；Store 类型推断会用上
  defaults: {},
  // 不加密整个 store，因为 refresh_token_cipher 已经是 safeStorage 输出
  encryptionKey: undefined
})

/** 存 refresh_token 密文（base64 字符串）。 */
export function setRefreshTokenCipher(cipher: string): void {
  store.set('refresh_token_cipher', cipher)
}

/** 取 refresh_token 密文；不存在时返回 undefined。 */
export function getRefreshTokenCipher(): string | undefined {
  return store.get('refresh_token_cipher')
}

/** 清所有 auth 相关 state（密文 + profile + last_backend_url）。幂等。 */
export function clearAuthState(): void {
  store.delete('refresh_token_cipher')
  store.delete('profile')
}

/** 存用户档案（非敏感信息）。 */
export function setProfile(profile: import('@shared/auth-types').UserProfile): void {
  store.set('profile', profile)
}

/** 取用户档案；不存在时返回 undefined。 */
export function getProfile(): import('@shared/auth-types').UserProfile | undefined {
  return store.get('profile')
}

/** 调试用：返回完整 store 路径。 */
export function getStorePath(): string {
  return store.path
}

export { APP_CONFIG }
