// 退出自动备份密码的落盘形态（M6-2 清账③）— 纯函数，cipher 注入，离线可测。
//
// 历史遗留：M5-2 把退出备份密码以明文写进 settings（backup.exitPassword）。
// 现在改为 safeStorage 加密存储（backup.exitPasswordEnc），并保留一次性迁移：
//   读旧明文 → 加密 → 写入加密键 → 清明文键；无旧值时不做任何写入。
// 渲染进程永远拿不到明文或密文：GET 一律返回掩码（加密值不回显）。

export const EXIT_PASSWORD_KEY = 'backup.exitPassword'
export const EXIT_PASSWORD_ENC_KEY = 'backup.exitPasswordEnc'
/** 回显掩码 — 与 ModelServiceSection 的 apiKeyMasked 保持同一观感 */
export const SECRET_MASK = '••••••••'

export interface SecretCipher {
  encrypt(plaintext: string): string
  decrypt(ciphertext: string): string | null
}

export interface SecretWritePlan {
  /** 需要写入加密键的值；null = 无有效密码（调用方应清空两个键） */
  encrypted: string | null
  /** 是否需要清除旧的明文键 */
  clearPlaintext: boolean
}

function asNonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

/**
 * 迁移计划：把旧明文升级为加密存储。
 * - 已有可用加密值 → 保持不动（幂等），仅在有明文残留时清明文
 * - 有旧明文 → 加密并写加密键 + 清明文
 * - 无旧值（含空串/非字符串）→ 不写入任何东西（兼容全新安装）
 */
export function planExitPasswordMigration(input: {
  legacyPlaintext: unknown
  encrypted: unknown
  cipher: Pick<SecretCipher, 'encrypt'>
}): SecretWritePlan {
  const legacy = asNonEmptyString(input.legacyPlaintext)
  const existingEnc = asNonEmptyString(input.encrypted)

  if (existingEnc) return { encrypted: existingEnc, clearPlaintext: legacy !== null }
  if (!legacy) return { encrypted: null, clearPlaintext: false }
  return { encrypted: input.cipher.encrypt(legacy), clearPlaintext: true }
}

/**
 * 写入计划：用户在设置页提交新密码时走这里（明文即刻转加密）。
 * 空串 = 清除密码（两个键都清）。
 */
export function planExitPasswordWrite(value: unknown, cipher: Pick<SecretCipher, 'encrypt'>): SecretWritePlan {
  const plain = asNonEmptyString(value)
  if (!plain) return { encrypted: null, clearPlaintext: true }
  return { encrypted: cipher.encrypt(plain), clearPlaintext: true }
}

/** 读取计划：优先解密加密键；失败/缺失时回退旧明文（并提示需要迁移） */
export function resolveExitPassword(input: {
  legacyPlaintext: unknown
  encrypted: unknown
  cipher: Pick<SecretCipher, 'decrypt'>
}): { password: string | null; needsMigration: boolean } {
  const existingEnc = asNonEmptyString(input.encrypted)
  if (existingEnc) {
    const dec = input.cipher.decrypt(existingEnc)
    if (dec) return { password: dec, needsMigration: false }
    // 加密值无法解密（换机/DPAPI 失效）：若有旧明文则用它，否则视为无密码
  }
  const legacy = asNonEmptyString(input.legacyPlaintext)
  if (legacy) return { password: legacy, needsMigration: true }
  return { password: null, needsMigration: false }
}

/** 对渲染进程的回显：有密码只给掩码，没有给 null（明文与密文都不外泄） */
export function maskSecret(hasSecret: boolean): string | null {
  return hasSecret ? SECRET_MASK : null
}
