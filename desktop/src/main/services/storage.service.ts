// Electron 持久化 storage 的统一抽象层（main 进程使用）。
//
// 设计原则：
// - 仅存密文（refresh_token）+ 非敏感 user，access_token 永不入库
// - 应用根目录 + userData 模式（不同 OS 不同路径）
// - 加密文件位于 OS 用户配置目录，Win 路径示例：
//   %APPDATA%/microbubble-desktop/config.json
//
// 详见 docs/desktop-conversion/security.md §Token 未来存储原则

import Store from 'electron-store'
import { APP_CONFIG } from '@shared/config'
import type { UserInfo } from '@shared/user-info'

type StoreSchema = {
  // safeStorage 加密后的 refresh_token（base64 字符串）
  refresh_token_cipher?: string
  // 后端返回的 user（非敏感信息；access_token + refresh_token 不在这里）
  user?: UserInfo
  // 后端 URL（开发阶段可能调整，记录最后一次连的后端）
  last_backend_url?: string
}

const store = new Store<StoreSchema>({
  name: 'microbubble-desktop-config',
  defaults: {},
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

/** 清所有 auth 相关 state（密文 + user + last_backend_url）。幂等。 */
export function clearAuthState(): void {
  store.delete('refresh_token_cipher')
  store.delete('user')
  store.delete('last_backend_url')
}

/** 存 user（非敏感信息）。 */
export function setUser(user: UserInfo): void {
  store.set('user', user)
}

/** 取 user；不存在时返回 undefined。 */
export function getUser(): UserInfo | undefined {
  return store.get('user')
}

/** 存最近一次连的后端 URL（仅供调试 / 设置页可见）。 */
export function setLastBackendUrl(url: string): void {
  store.set('last_backend_url', url)
}

/** 调试用：返回完整 store 路径。 */
export function getStorePath(): string {
  return store.path
}

export { APP_CONFIG }
