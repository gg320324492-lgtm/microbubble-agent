// Provider Bootstrap — Phase 12 (2026-08-26 主拍决策)
// 首版默认云端模型 (MiMo Anthropic-compatible). 启动时若 user 未配 provider, 自动注入默认.
// 主拍决策 3: 云端模型 + 用户配置 API Key
// 主拍决策 6: API Key 用 Windows safeStorage 加密 (Phase 6-A2 已实现)
//
// 设计:
// 1. 启动时调用 ensureMimoDefaultProvider() (from index.ts after database bootstrap)
// 2. 若 user 已有 active provider 配置 → 不动 (用户优先)
// 3. 若无 → 注入 xiaomi-mimo provider + 设为 active
// 4. key 从 env 注入 (主拍可在 .env 设 MICROBUBBLE_MIMO_KEY) 或用 hardcoded (Phase 12 临时)

import { save as saveKey, exists as keyExists, get as getKey } from './model-secret-store'
import { saveConfig, getConfig } from './provider-config-store'
import { getActive, setActive } from './active-provider-store'
import { registerProvider } from './registry'
import { createOpenAiCompatibleProvider } from './providers/openai-compatible-provider'
import { createAnthropicCompatibleProvider } from './providers/anthropic-compatible-provider'
import { logger } from '../storage.service'

const MIMO_PROVIDER_ID = 'xiaomi-mimo'
const MIMO_BASE_URL = 'https://api.xiaomimimo.com/v1'
const MIMO_DEFAULT_MODEL = 'mimo-v2.5'
const MIMO_DISPLAY_NAME = '小米 MiMo (mimo-v2.5)'

// Phase 12 主拍决策 3: 1.0 支持两类通用 LLM 接口 (OpenAI-compatible + Anthropic-compatible).
// 同时支持 MiMo Anthropic 协议 (token-plan-cn.xiaomimimo.com/anthropic)
// 与 MiMo OpenAI 协议 (api.xiaomimimo.com/v1) — 用户按需选.
const MIMO_ANTHROPIC_PROVIDER_ID = 'xiaomi-mimo-anthropic'
const MIMO_ANTHROPIC_BASE_URL = 'https://token-plan-cn.xiaomimimo.com/anthropic'
const MIMO_ANTHROPIC_DISPLAY_NAME = '小米 MiMo (Anthropic 协议)'

/**
 * 启动时确保 MiMo provider 已配置.
 * 若用户已有 active provider → 不动 (用户优先).
 * 若无 → 注入 xiaomi-mimo 用 env 提供的 API key.
 */
export function ensureDefaultCloudProvider(): void {
  // 1. 注册 factory (重复 register 幂等). createOpenAiCompatibleProvider 接受 (apiKeyResolver, fetcher) → 返回 (cfg) => ModelProvider
  //   apiKeyResolver 从 secret-store 拉 key, 让 provider 每次用最新 key (主拍决策 3 6: key 可更新)
  const apiKeyResolver = (): string | null => {
    try {
      return getKey(MIMO_PROVIDER_ID)
    } catch {
      return null
    }
  }
  registerProvider(
    MIMO_PROVIDER_ID,
    createOpenAiCompatibleProvider(apiKeyResolver),
    {
      type: 'openai-compatible',
      capabilities: {
        streaming: true,
        tools: false,
        vision: false,
        functionCalling: false,
        jsonMode: true
      },
      displayName: MIMO_DISPLAY_NAME,
      defaultModel: MIMO_DEFAULT_MODEL
    }
  )

  // Phase 12 主拍决策 3: 注册 Anthropic-compatible provider (MiMo Anthropic 协议)
  const anthropicKeyResolver = (): string | null => {
    try {
      return getKey(MIMO_ANTHROPIC_PROVIDER_ID) || getKey(MIMO_PROVIDER_ID)
    } catch {
      return null
    }
  }
  registerProvider(
    MIMO_ANTHROPIC_PROVIDER_ID,
    createAnthropicCompatibleProvider(anthropicKeyResolver),
    {
      type: 'openai-compatible',
      capabilities: {
        streaming: true,
        tools: false,
        vision: false,
        functionCalling: false,
        jsonMode: true
      },
      displayName: MIMO_ANTHROPIC_DISPLAY_NAME,
      defaultModel: MIMO_DEFAULT_MODEL
    }
  )

  // 2. 若用户已配 active provider, 尊重用户选择
  const active = getActive()
  if (active) {
    logger.info('provider.bootstrap', '用户已配 active provider', { providerId: active.providerId })
    return
  }

  // 3. 注入 MiMo provider (用 env 或 hardcoded default)
  const apiKey = process.env['MIMO_API_KEY'] || 'tp-c2dh4lwgx2519tsuoffa8npxfcqofbiyaew94pwt4bc5yjlq'
  if (!apiKey) return

  // 4. 保存非敏感配置
  if (!getConfig(MIMO_PROVIDER_ID)) {
    saveConfig(MIMO_PROVIDER_ID, {
      type: 'openai-compatible',
      endpoint: MIMO_BASE_URL,
      defaultModel: MIMO_DEFAULT_MODEL,
      displayName: MIMO_DISPLAY_NAME,
      capabilities: ['streaming', 'json-mode']
    })
    logger.info('provider.bootstrap', '已注入 MiMo OpenAI provider', { providerId: MIMO_PROVIDER_ID, model: MIMO_DEFAULT_MODEL })
  }

  // Phase 12 主拍决策 3: 同样保存 Anthropic 协议 provider config (用户可选)
  if (!getConfig(MIMO_ANTHROPIC_PROVIDER_ID)) {
    saveConfig(MIMO_ANTHROPIC_PROVIDER_ID, {
      type: 'cloud',
      endpoint: MIMO_ANTHROPIC_BASE_URL,
      defaultModel: MIMO_DEFAULT_MODEL,
      displayName: MIMO_ANTHROPIC_DISPLAY_NAME,
      capabilities: ['streaming', 'json-mode']
    })
    logger.info('provider.bootstrap', '已注入 MiMo Anthropic provider', { providerId: MIMO_ANTHROPIC_PROVIDER_ID })
  }

  // 5. 保存 API key 到 safeStorage (OpenAI provider 用, Anthropic provider 共享此 key)
  if (!keyExists(MIMO_PROVIDER_ID)) {
    try {
      saveKey(MIMO_PROVIDER_ID, apiKey)
      logger.info('provider.bootstrap', '已保存 MiMo API key 到 safeStorage')
    } catch (e) {
      logger.warn('provider.bootstrap', '保存 MiMo key 失败, user 需手动配置', { error: e instanceof Error ? e.message : String(e) })
      return
    }
  }

  // 6. 设为 active
  setActive({
    providerId: MIMO_PROVIDER_ID,
    model: MIMO_DEFAULT_MODEL,
    enabled: true
  })
  logger.info('provider.bootstrap', 'MiMo 已设为 active provider')
}

/** 主拍决策 1: 1.0 不接正式设备. 模拟驱动仅 dev/演示模式. */
export function isDevOnlyFeature(featureName: string): boolean {
  return !import.meta.env.DEV && featureName === 'experiment-control'
}
