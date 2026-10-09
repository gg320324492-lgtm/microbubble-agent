/**
 * 知识详情页「多模态提取」图片 OCR 统计口径（2026-10-09 agent33）
 *
 * ## 为什么需要这个文件
 *
 * 后端 `c9dc3f484`（agent31）把 `ocr_status='done'` 拆成两个枚举：
 *   - `done`         —— OCR 跑完**且抽到了文本**（写入 `ocr_text`）
 *   - `done_no_text` —— OCR 跑完但**返回空**（`ocr_text` 为空）
 *
 * 拆分前 `KnowledgeDetailView.fetchMultimodalData` 用三个 `filter` 手写统计，
 * 两个新枚举里只有 `done` 被认领，`done_no_text`（以及同样漏网的 `partial`）
 * 在任何桶里都匹配不到 —— **从 UI 上直接蒸发**。
 *
 * 实测全库 5446 张图：`done`=2050（全有字）/ `done_no_text`=3317（全空）/
 * `failed`=79。旧口径下详情页只显示「完成 2050 / 失败 79」，
 * 3317 张图（61%）无归属，而「总数」又没显示，三个数字加起来对不上
 * `imgs.length` —— 这正是类 20.220「状态字段会撒谎」的同类问题：
 * 展示层只认自己认识的那几个值，其余静默丢弃。
 *
 * ## 口径决策：`done_no_text` **单列一桶**，不并入 `done`
 *
 * 理由（语义 + 数字两侧都站得住）：
 *
 * 1. **两者语义相反**。`done` 的行 100% 带 `ocr_text`，`done_no_text` 的行
 *    100% 为空 —— 这不是程度差异，是「产出了可检索内容」与「没产出」的
 *    分界。而 `ocr_text` 非空正是第 5 路多模态召回的硬过滤条件
 *    （`app/services/multimodal_retriever.py:180`），并入后「OCR 完成 5367」
 *    会被读成「5367 张图有可检索文字」，是句假话。
 * 2. **并进去等于把昨天的修复在展示层撤销**。`done_no_text` 拆出来的唯一目的
 *    就是让「跑完但没字」不再和「跑完且有字」共用一个值；前端再合并回去，
 *    等于白拆。
 * 3. **它是最大的一桶，不是边角**。3317/5446 = 61%，藏进 `done` 里会让
 *    「完成」这个数字虚高 2.6 倍，恰好掩盖掉本轮多模态治理要回答的问题
 *    ——「多少张图真的产出了文本」。
 *
 * ⚠️ **标签文案不许断言「图里没字」**：按 `multimodal_extraction_service.py`
 * 的注释，`done_no_text` 只描述**这一次 OCR 调用**跑完返回空，不是对图片内容
 * 的断言（实测 id=6368 图上明确有中文标注，换 prompt 重跑即拿到文字）。
 * 所以标签写「无文本」并在 title 里写明「不等于图里确实没字」。
 *
 * ## 不变量：`done + doneNoText + failed + pending + skipped + other === total`
 *
 * 用 `other` 兜住一切未知枚举（如 `partial`、以及将来新增的状态）。
 * 这是本文件存在的核心目的：**任何一张图都不许从统计里消失**。
 * 下次后端再加枚举，详情页会显示「其他 N」提醒人补口径，而不是静默少一块。
 */

export const OCR_STATUS = {
  DONE: 'done',
  DONE_NO_TEXT: 'done_no_text',
  FAILED: 'failed',
  PENDING: 'pending',
  SKIPPED: 'skipped',
}

/**
 * 按 OCR 状态给图片列表分桶。
 *
 * 纯函数、无副作用 —— 便于直接单测（不挂组件也能验口径）。
 *
 * @param {Array<{ocr_status?: string|null}>} images 图片列表
 * @returns {{total:number, done:number, doneNoText:number, failed:number,
 *            pending:number, skipped:number, other:number}}
 *   六个桶之和恒等于 `total`。
 */
export function computeImageOcrStats(images) {
  const stats = {
    total: 0,
    done: 0,
    doneNoText: 0,
    failed: 0,
    pending: 0,
    skipped: 0,
    other: 0,
  }

  if (!Array.isArray(images)) return stats

  for (const img of images) {
    stats.total += 1
    switch (img?.ocr_status) {
      case OCR_STATUS.DONE:
        stats.done += 1
        break
      case OCR_STATUS.DONE_NO_TEXT:
        stats.doneNoText += 1
        break
      case OCR_STATUS.FAILED:
        stats.failed += 1
        break
      case OCR_STATUS.PENDING:
        stats.pending += 1
        break
      // `skipped` 是终态不是「处理中」：写入侧
      // `_skip_banner_images` 给母版装饰横幅落的标记，OCR 永远不会再跑，
      // 混进 `pending` 会让用户以为它在排队。两者拆开显示。
      case OCR_STATUS.SKIPPED:
        stats.skipped += 1
        break
      // `partial`（OCR 失败但视觉结构化字段拿到了）等一切未列举状态。
      default:
        stats.other += 1
    }
  }

  return stats
}

export default computeImageOcrStats