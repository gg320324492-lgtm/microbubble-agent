// Token Vault：把 refresh_token 安全地存到本地。
//
// 设计原则（详见 docs/desktop-conversion/security.md §Token 未来存储原则）：
// - access_token 仅活内存（Pinia state / main 进程变量），从不出库
// - refresh_token 走 Electron safeStorage → OS 级加密后入 electron-store
//   - Win: DPAPI (current user / machine scope)
//   - macOS: Keychain
//   - Linux: libsecret / kwallet
// - 任何加密/解密失败都吞错返回 null（不允许阻塞启动；调用方负责清状态）
//
// 严禁存 localStorage / sessionStorage / IndexedDB 明文。

import { safeStorage } from 'electron'
import {
  getRefreshTokenCipher,
  setRefreshTokenCipher,
  clearAuthState
} from './storage.service'

/**
 * 把 refresh_token 加密后存盘。
 * - safeStorage.isEncryptionAvailable() === false 时拒绝（抛错让上层兜底）
 */
export function vaultStoreRefreshToken(refreshToken: string): void {
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error(
      'OS-level encryption (safeStorage) not available. ' +
        'Verify OS user has a protected keychain (Win DPAPI / macOS Keychain / Linux libsecret)'
    )
  }
  const cipher = safeStorage.encryptString(refreshToken)
  setRefreshTokenCipher(cipher.toString('base64'))
}

/**
 * 从盘里取回 refresh_token 明文。任何失败返回 null。
 * - 不存在: null
 * - 加密不可用: null
 * - 密文损坏: null
 * - 解密异常: null
 */
export function vaultLoadRefreshToken(): string | null {
  try {
    const cipherStr = getRefreshTokenCipher()
    if (!cipherStr) return null
    if (!safeStorage.isEncryptionAvailable()) {
      // 通常发生在用户清 OS keychain 或 GPU-only Linux。兜底强制清场，让用户重登。
      clearAuthState()
      return null
    }
    const buf = Buffer.from(cipherStr, 'base64')
    const plaintext = safeStorage.decryptString(buf)
    if (!plaintext || plaintext.length === 0) {
      clearAuthState()
      return null
    }
    return plaintext
  } catch (_err) {
    // decrypt 异常：密文损坏或 keychain 轮换后失效。强制清场让用户重登。
    clearAuthState()
    return null
  }
}

/** 清空 vault（登出时调）。幂等。 */
export function vaultClear(): void {
  clearAuthState()
}

/** 调试 / 设置页可见：safeStorage 在当前 OS 是否可用。 */
export function isVaultAvailable(): boolean {
  return safeStorage.isEncryptionAvailable()
}
