/**
 * useMobileBiometric.ts — 移动端生物识别认证 (WebAuthn / Touch ID / Face ID / Android 指纹)
 *
 * W68 第 8 批 B-3: Mobile UX v3.2 生物识别集成
 *
 * 设计要点:
 * 1. 探测链:
 *    PublicKeyCredential + window.isSecureContext (HTTPS) → WebAuthn 可用
 *    ↓ 否则
 *    fallback: 6 位数字 PIN 码 (localStorage 加密存)
 * 2. 流程:
 *    register(): 生成 challenge + 创建 credential → localStorage 存 credentialId
 *    authenticate(): 拿到 storedCredentialId → navigator.credentials.get() → 签名 challenge
 *       验证: 本项目目前**无后端 WebAuthn verify 端点**, 仅前端模拟流程
 *       降级: 失败 5 次后强制 PIN 码
 * 3. iOS Safari 限制:
 *    - 必须 HTTPS (or localhost)
 *    - 用户手势内调用 (click/tap event handler)
 *    - iOS 14.5+ 才有 built-in authenticator (在此之前需外部 authenticator)
 *    - navigator.credentials.get 在用户手势内触发
 * 4. Android Chrome 限制:
 *    - 84+ 支持 WebAuthn
 *    - 必须 HTTPS (or localhost)
 * 5. fallback PIN 码:
 *    - 6 位数字
 *    - localStorage 存 hash (SHA-256, 防止明文)
 *    - 5 次失败 → 锁定 5 分钟
 * 6. 安全考虑:
 *    - challenge 每次随机 (crypto.getRandomValues)
 *    - credentialId 不暴露给用户 (Base64URL 编码)
 *    - 本项目目前无后端 verify, 所以是"前端可信任的快速解锁"流程;
 *      真正敏感操作仍需密码
 *
 * 用法:
 *   const bio = useMobileBiometric()
 *   const support = await bio.detectSupport()           // { hasWebAuthn, hasFaceID, hasTouchID, hasFingerprint, hasPIN, ... }
 *   await bio.registerPIN('123456')                     // 设置 PIN 码
 *   const pinOk = await bio.verifyPIN('123456')         // 校验 PIN
 *   const webAuthnOk = await bio.authenticate()         // 生物识别 (返回 true/false)
 *   bio.setBiometricEnabled(true/false)                 // 用户偏好开关
 *   const enabled = bio.isBiometricEnabled()             // 是否启用
 */

import { ref, computed, readonly } from 'vue'
import { ElMessage } from 'element-plus'

// localStorage 键
const LS_KEY_PIN_HASH = 'mobile_biometric_pin_hash'
const LS_KEY_PIN_SET_AT = 'mobile_biometric_pin_set_at'
const LS_KEY_BIO_ENABLED = 'mobile_biometric_enabled'
const LS_KEY_FAILED_ATTEMPTS = 'mobile_biometric_failed_attempts'
const LS_KEY_LOCKED_UNTIL = 'mobile_biometric_locked_until'
const LS_KEY_CREDENTIAL_ID = 'mobile_biometric_credential_id' // Base64URL
const LS_KEY_USER_HANDLE = 'mobile_biometric_user_handle' // 内部标识 (非 userId, 防泄露)

// PIN 码参数
const PIN_LENGTH = 6
const MAX_FAILED_ATTEMPTS = 5
const LOCKOUT_MINUTES = 5

// WebAuthn Relying Party
const RP_NAME = '小气助手'
const RP_ID = typeof window !== 'undefined' ? window.location.hostname : 'localhost'

/**
 * 探测浏览器生物识别能力
 */
async function detectSupportRaw() {
  if (typeof window === 'undefined') {
    return {
      hasWebAuthn: false,
      hasPublicKeyCredential: false,
      hasIsSecureContext: false,
      isIOS: false,
      isAndroid: false,
      userAgent: '',
      authenticatorType: 'none' as const,
    }
  }
  const ua = navigator.userAgent || ''
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (ua.includes('Mac') && 'ontouchend' in document)
  const isAndroid = /Android/.test(ua)

  const hasPublicKeyCredential =
    typeof window.PublicKeyCredential === 'function'
  const hasIsSecureContext = window.isSecureContext || false
  // 进一步探测: navigator.credentials + PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable
  let hasPlatformAuthenticator = false
  let hasConditionalUI = false
  if (hasPublicKeyCredential && typeof PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable === 'function') {
    try {
      hasPlatformAuthenticator = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
    } catch {
      hasPlatformAuthenticator = false
    }
  }
  if (
    hasPublicKeyCredential &&
    typeof (PublicKeyCredential as any).isConditionalMediationAvailable === 'function'
  ) {
    try {
      hasConditionalUI = await (PublicKeyCredential as any).isConditionalMediationAvailable()
    } catch {
      hasConditionalUI = false
    }
  }
  const hasWebAuthn = hasPublicKeyCredential && hasIsSecureContext && hasPlatformAuthenticator

  let authenticatorType: 'face' | 'touch' | 'fingerprint' | 'none' = 'none'
  if (hasWebAuthn) {
    if (isIOS) {
      // iOS 14.5+ 自带 Face ID / Touch ID — 我们无法精确区分 (系统不暴露)
      // 启发式: iPhone X+ (无 home 键) → Face ID, 否则 Touch ID
      const isModerniPhone = /iPhone1[2-9]|iPhone2[0-9]/.test(ua) || ua.includes('iPhone15')
      authenticatorType = isModerniPhone ? 'face' : 'touch'
    } else if (isAndroid) {
      authenticatorType = 'fingerprint'
    }
  }

  return {
    hasWebAuthn,
    hasPublicKeyCredential,
    hasIsSecureContext,
    hasPlatformAuthenticator,
    hasConditionalUI,
    isIOS,
    isAndroid,
    userAgent: ua,
    authenticatorType,
  }
}

// SHA-256 + Base64URL (Web Crypto / fallback)
async function sha256(input: string): Promise<string> {
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    try {
      const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input))
      return bufferToBase64URL(buf)
    } catch {
      // continue to fallback
    }
  }
  // fallback: 简单 hash (web crypto 不可用时, 仅做弱校验)
  let hash = 0
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) - hash + input.charCodeAt(i)) | 0
  }
  return Math.abs(hash).toString(16).padStart(16, '0')
}

function bufferToBase64URL(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]!)
  // btoa 在 node 环境没有 — 用 base64 替换
  if (typeof btoa !== 'undefined') {
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  }
  // 浏览器无 btoa 基本不可能, 兜底
  return Buffer.from(binary, 'binary').toString('base64url')
}

function randomBytes(len: number): Uint8Array {
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const arr = new Uint8Array(len)
    crypto.getRandomValues(arr)
    return arr
  }
  // 兜底: Math.random (弱随机, 仅测试用)
  const arr = new Uint8Array(len)
  for (let i = 0; i < len; i++) arr[i] = Math.floor(Math.random() * 256)
  return arr
}

function bufferToBase64URLBytes(arr: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < arr.length; i++) binary += String.fromCharCode(arr[i]!)
  if (typeof btoa !== 'undefined') {
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  }
  return ''
}

function base64URLToBuffer(s: string): Uint8Array {
  let base64 = s.replace(/-/g, '+').replace(/_/g, '/')
  while (base64.length % 4) base64 += '='
  if (typeof atob !== 'undefined') {
    const binary = atob(base64)
    const arr = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i)
    return arr
  }
  return new Uint8Array(0)
}

export interface BiometricSupport {
  hasWebAuthn: boolean
  hasPublicKeyCredential: boolean
  hasIsSecureContext: boolean
  hasPlatformAuthenticator: boolean
  hasConditionalUI: boolean
  isIOS: boolean
  isAndroid: boolean
  userAgent: string
  /** 'face' = Face ID, 'touch' = Touch ID, 'fingerprint' = Android 指纹, 'none' = 无 */
  authenticatorType: 'face' | 'touch' | 'fingerprint' | 'none'
  /** 是否有可用生物识别 */
  available: boolean
  /** 中文显示名 */
  displayName: string
}

export interface BiometricAuthResult {
  ok: boolean
  method: 'webauthn' | 'pin' | 'none'
  error?: string
  /** 用户取消 (AbortError) — 不是错误, 是 explicit dismiss */
  dismissed?: boolean
}

export function useMobileBiometric() {
  // 探测结果 (异步初始化, 组件 onMounted 时调 await bio.detectSupport())
  const support = ref<BiometricSupport | null>(null)
  const enabled = ref(loadEnabled())
  const loading = ref(false)
  const lastError = ref<string | null>(null)
  const failedAttempts = ref(loadFailedAttempts())

  function loadEnabled(): boolean {
    if (typeof localStorage === 'undefined') return false
    return localStorage.getItem(LS_KEY_BIO_ENABLED) === 'true'
  }

  function loadFailedAttempts(): number {
    if (typeof localStorage === 'undefined') return 0
    const v = parseInt(localStorage.getItem(LS_KEY_FAILED_ATTEMPTS) || '0', 10)
    return Number.isFinite(v) ? v : 0
  }

  const isLocked = computed(() => {
    if (typeof localStorage === 'undefined') return false
    const until = localStorage.getItem(LS_KEY_LOCKED_UNTIL)
    if (!until) return false
    const lockUntil = parseInt(until, 10)
    if (!Number.isFinite(lockUntil)) return false
    if (Date.now() > lockUntil) {
      // 已过期, 清掉状态
      localStorage.removeItem(LS_KEY_LOCKED_UNTIL)
      localStorage.removeItem(LS_KEY_FAILED_ATTEMPTS)
      failedAttempts.value = 0
      return false
    }
    return true
  })

  /**
   * 探测支持 — 组件挂载时建议调一次, 缓存到 support ref
   */
  async function detectSupport(): Promise<BiometricSupport> {
    const raw = await detectSupportRaw()
    const result: BiometricSupport = {
      ...raw,
      available: raw.hasWebAuthn,
      displayName:
        raw.authenticatorType === 'face'
          ? 'Face ID'
          : raw.authenticatorType === 'touch'
            ? 'Touch ID'
            : raw.authenticatorType === 'fingerprint'
              ? '指纹'
              : '生物识别',
    }
    support.value = result
    return result
  }

  /**
   * 启用 / 禁用生物识别开关 (用户偏好)
   */
  function setBiometricEnabled(value: boolean) {
    enabled.value = value
    if (typeof localStorage !== 'undefined') {
      if (value) {
        localStorage.setItem(LS_KEY_BIO_ENABLED, 'true')
      } else {
        localStorage.removeItem(LS_KEY_BIO_ENABLED)
      }
    }
  }

  function isBiometricEnabled(): boolean {
    return enabled.value && (support.value?.available ?? false)
  }

  /**
   * 注册 WebAuthn credential
   * - 仅第一次需要, 之后 navigator.credentials.get 直接用存储的 credentialId
   * - 本项目无后端 verify, 所以注册仅生成挑战 + 存 credentialId
   */
  async function registerWebAuthn(): Promise<boolean> {
    if (!support.value?.hasWebAuthn) {
      lastError.value = '设备不支持 WebAuthn'
      return false
    }
    loading.value = true
    try {
      const userId = getOrCreateUserHandle()
      const userIdBytes = base64URLToBuffer(userId)
      const challenge = randomBytes(32)

      const publicKeyOptions: PublicKeyCredentialCreationOptions = {
        challenge,
        rp: { name: RP_NAME, id: RP_ID },
        user: {
          id: userIdBytes,
          name: 'microbubble-user',
          displayName: '小气助手用户',
        },
        pubKeyCredParams: [
          { type: 'public-key', alg: -7 }, // ES256 (首选)
          { type: 'public-key', alg: -257 }, // RS256
        ],
        authenticatorSelection: {
          authenticatorAttachment: 'platform', // 内置 (Touch/Face/指纹)
          userVerification: 'required',
          residentKey: 'preferred',
        },
        timeout: 60_000,
        attestation: 'none', // 本项目不需要 server 验证 attestation
      }

      const cred = (await navigator.credentials.create({ publicKey: publicKeyOptions })) as PublicKeyCredential | null
      if (!cred) {
        lastError.value = '注册失败'
        return false
      }
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(LS_KEY_CREDENTIAL_ID, bufferToBase64URLBytes(new Uint8Array(cred.rawId)))
      }
      return true
    } catch (err: any) {
      console.warn('[useMobileBiometric] register failed:', err)
      lastError.value = err?.message || '注册失败'
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 生物识别认证 (主流程) — 用户必须从 click/tap 事件内调用
   */
  async function authenticate(): Promise<BiometricAuthResult> {
    // 锁定检查
    if (isLocked.value) {
      return {
        ok: false,
        method: 'none',
        error: '太多失败, 已锁定',
      }
    }
    if (!support.value?.hasWebAuthn) {
      return { ok: false, method: 'none', error: '设备不支持生物识别' }
    }
    const credentialId = typeof localStorage !== 'undefined' ? localStorage.getItem(LS_KEY_CREDENTIAL_ID) : null
    if (!credentialId) {
      // 没有已注册的 credential — 试一次 register (但 register 也必须在用户手势内)
      const ok = await registerWebAuthn()
      if (!ok) {
        return { ok: false, method: 'none', error: '未注册生物识别' }
      }
      return await authenticate()
    }

    loading.value = true
    try {
      const challenge = randomBytes(32)
      const credentialIdBytes = base64URLToBuffer(credentialId)

      const publicKeyOptions: PublicKeyCredentialRequestOptions = {
        challenge,
        allowCredentials: [
          {
            id: credentialIdBytes,
            type: 'public-key',
            transports: ['internal'],
          },
        ],
        userVerification: 'required',
        timeout: 60_000,
      }

      const cred = (await navigator.credentials.get({ publicKey: publicKeyOptions })) as PublicKeyCredential | null
      if (!cred) {
        recordFailure()
        return { ok: false, method: 'webauthn', error: '认证失败' }
      }
      // 成功 — 清失败计数
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(LS_KEY_FAILED_ATTEMPTS)
        localStorage.removeItem(LS_KEY_LOCKED_UNTIL)
      }
      failedAttempts.value = 0
      lastError.value = null
      return { ok: true, method: 'webauthn' }
    } catch (err: any) {
      if (err?.name === 'AbortError' || err?.name === 'NotAllowedError') {
        // 用户取消 — 不计入失败
        return { ok: false, method: 'webauthn', dismissed: true, error: '用户取消' }
      }
      console.warn('[useMobileBiometric] auth failed:', err)
      recordFailure()
      lastError.value = err?.message || '认证失败'
      return { ok: false, method: 'webauthn', error: lastError.value ?? '认证失败' }
    } finally {
      loading.value = false
    }
  }

  /**
   * 注册 6 位 PIN 码 (用于 fallback 或纯 PIN 模式)
   */
  async function registerPIN(pin: string): Promise<boolean> {
    if (!/^\d{6}$/.test(pin)) {
      ElMessage?.error?.('PIN 码必须是 6 位数字')
      return false
    }
    const hash = await sha256(pin + RP_ID) // 加盐
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(LS_KEY_PIN_HASH, hash)
      localStorage.setItem(LS_KEY_PIN_SET_AT, Date.now().toString())
    }
    return true
  }

  /**
   * 校验 PIN 码
   */
  async function verifyPIN(pin: string): Promise<BiometricAuthResult> {
    if (isLocked.value) {
      return { ok: false, method: 'pin', error: '已锁定, 请稍后再试' }
    }
    if (!/^\d{6}$/.test(pin)) {
      recordFailure()
      return { ok: false, method: 'pin', error: 'PIN 必须是 6 位数字' }
    }
    const stored = typeof localStorage !== 'undefined' ? localStorage.getItem(LS_KEY_PIN_HASH) : null
    if (!stored) {
      return { ok: false, method: 'pin', error: '未设置 PIN' }
    }
    const hash = await sha256(pin + RP_ID)
    if (hash === stored) {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(LS_KEY_FAILED_ATTEMPTS)
        localStorage.removeItem(LS_KEY_LOCKED_UNTIL)
      }
      failedAttempts.value = 0
      return { ok: true, method: 'pin' }
    }
    recordFailure()
    return { ok: false, method: 'pin', error: 'PIN 错误' }
  }

  function recordFailure() {
    failedAttempts.value += 1
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(LS_KEY_FAILED_ATTEMPTS, failedAttempts.value.toString())
      if (failedAttempts.value >= MAX_FAILED_ATTEMPTS) {
        const lockedUntil = Date.now() + LOCKOUT_MINUTES * 60 * 1000
        localStorage.setItem(LS_KEY_LOCKED_UNTIL, lockedUntil.toString())
        ElMessage?.error?.(`失败次数过多, 已锁定 ${LOCKOUT_MINUTES} 分钟`)
      }
    }
  }

  function getOrCreateUserHandle(): string {
    if (typeof localStorage === 'undefined') return ''
    let handle = localStorage.getItem(LS_KEY_USER_HANDLE)
    if (!handle) {
      handle = bufferToBase64URLBytes(randomBytes(16))
      localStorage.setItem(LS_KEY_USER_HANDLE, handle)
    }
    return handle
  }

  /**
   * 重置所有生物识别 + PIN 数据 (用户主动注销设备时)
   */
  function reset() {
    if (typeof localStorage === 'undefined') return
    ;[
      LS_KEY_PIN_HASH,
      LS_KEY_PIN_SET_AT,
      LS_KEY_BIO_ENABLED,
      LS_KEY_FAILED_ATTEMPTS,
      LS_KEY_LOCKED_UNTIL,
      LS_KEY_CREDENTIAL_ID,
      LS_KEY_USER_HANDLE,
    ].forEach((k) => localStorage.removeItem(k))
    enabled.value = false
    failedAttempts.value = 0
  }

  /**
   * 是否已设置 PIN 码
   */
  function hasPIN(): boolean {
    if (typeof localStorage === 'undefined') return false
    return !!localStorage.getItem(LS_KEY_PIN_HASH)
  }

  return {
    // 状态
    support: readonly(support),
    enabled: readonly(enabled),
    loading: readonly(loading),
    lastError: readonly(lastError),
    failedAttempts: readonly(failedAttempts),
    isLocked,

    // 探测
    detectSupport,

    // WebAuthn
    registerWebAuthn,
    authenticate,

    // PIN fallback
    registerPIN,
    verifyPIN,
    hasPIN,

    // 偏好
    setBiometricEnabled,
    isBiometricEnabled,

    // 重置
    reset,
  }
}

export default useMobileBiometric
