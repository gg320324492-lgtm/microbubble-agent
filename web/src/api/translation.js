/**
 * translation API 客户端 — 2026-07-20 论文段落/全文翻译实装
 *
 * 镜像 web/src/api/chatHistory.js 模式（直接 axios 调用）
 * 1 个端点（来自 app/api/v1/translation.py）：
 *   - POST /translation/translate  翻译 (body: {text, target_lang})
 *
 * 关键纪律：
 * - 失败抛异常 → 调用方 try/except 决定兜底 (默认返原文, 不显示空白)
 * - 422 (text 空/超长/lang 不支持) 抛带 detail 的 Error, 前端 toast 显式提示
 */

import axios from 'axios'

const BASE = '/api/v1'

/**
 * 翻译文本到目标语言
 * @param {Object} params
 * @param {string} params.text - 待翻译文本 (1-8000 字符)
 * @param {string} params.target_lang - 目标语言代码 (en/zh/ja/ko/fr/de/es/ru/zh-TW)
 * @returns {Promise<{translated_text: string, target_lang: string, source_length: number}>}
 * @throws {Error} 422 输入校验失败 / 500 服务异常
 */
export async function translateText({ text, target_lang }) {
  if (!text || !text.trim()) {
    throw new Error('待翻译文本不能为空')
  }
  if (text.length > 8000) {
    throw new Error(`文本超过最大长度 8000 字符 (实际 ${text.length})，请分段翻译`)
  }
  const response = await axios.post(`${BASE}/translation/translate`, {
    text: text.trim(),
    target_lang: target_lang.trim().toLowerCase(),
  })
  return response.data
}
