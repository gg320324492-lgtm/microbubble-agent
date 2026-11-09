/**
 * fileRequestFailure.js — 匿名收件页失败态的「可读化 + 可行动判定」(2026-11-09)
 *
 * 背景: 匿名分片上传新增 5 个端点后，失败原因从「一个 422」变成 7 种语义
 *   (404 链接不存在 / 409 已收满 或 片未齐 / 410 链接关闭或过期、会话中止或过期 /
 *    413 超上限 / 415 扩展名不允许 / 422 该片校验失败 / 500 合并校验失败)。
 * 直接把 `axios` 的 "Request failed with status code 413" 甩给外部人员
 * ⇒ 对方既看不懂也不知道该做什么 (与本仓 meetingFailure.js 修的是同一类问题)。
 *
 * 本模块是「HTTP 状态码 + 后端中文 detail → 用户能据此行动的话」的**唯一切换点**:
 * 桌面/移动共用同一个 /r/:token 页面，但小文件通路与分片通路都会失败，
 * 两处各写一份文案必然漂移 (类 20.220)。
 *
 * 契约:
 * - describeFileRequestFailure(err) **永远返回对象**，不抛异常、不返回 null
 *   ⇒ 调用方无需做空值防御
 * - `technical` 保留后端原始 detail 与状态码，供折叠展示与事后排查，不当主文案
 * - `action` 是给 UI 的**动作枚举**，不是文案 —— 免得 UI 再去 match 中文串
 */

/** 失败类型编码 —— 前端自己的语义分类，与后端文案无关 */
export const FR_FAILURE_CODE = {
  /** token 不存在 (链接输错 / 已删除) */
  LINK_NOT_FOUND: 'link_not_found',
  /** 收件已收满 (份数或活跃会话数达上限) */
  QUOTA_FULL: 'quota_full',
  /** 分片还没传齐就请求合并 */
  CHUNKS_INCOMPLETE: 'chunks_incomplete',
  /** 链接已关闭或过期 */
  LINK_CLOSED: 'link_closed',
  /** 上传会话已中止或过期 */
  SESSION_GONE: 'session_gone',
  /** 单文件超上限 */
  FILE_TOO_BIG: 'file_too_big',
  /** 累计总量超上限 */
  TOTAL_TOO_BIG: 'total_too_big',
  /** 扩展名不在白名单 */
  EXT_NOT_ALLOWED: 'ext_not_allowed',
  /** 某一片字节校验失败 (传输损坏) */
  CHUNK_CORRUPT: 'chunk_corrupt',
  /** 服务端合并/落地失败 */
  MERGE_FAILED: 'merge_failed',
  /** 请求过于频繁 (429) */
  RATE_LIMITED: 'rate_limited',
  /** 网络断了 (拿不到 status) */
  NETWORK: 'network',
  /** 其他/未知 */
  UNKNOWN: 'unknown',
}

/** UI 可采取的动作 —— 决定失败卡片上那颗按钮是什么 */
export const FR_FAILURE_ACTION = {
  /** 可以直接重试 (分片通路会从断点继续) */
  RETRY: 'retry',
  /** 只能稍后再试 (服务端限流/临时故障) */
  WAIT: 'wait',
  /** 换一个文件/重新选择 */
  RESELECT: 'reselect',
  /** 联系发起人 */
  CONTACT: 'contact',
  /** 没救，只能告知 */
  NONE: 'none',
}

/** 从 axios 错误里取状态码；拿不到 (网络层失败/请求未发出) ⇒ 0 */
export function statusOf(err) {
  const s = err?.response?.status
  const n = typeof s === 'number' ? s : Number(s)
  return Number.isFinite(n) ? n : 0
}

/**
 * 后端 detail 一律走 HTTPException(detail=str)，所以中文串在这里取；
 * 另外兼容统一异常格式 `{error: {message}}` (app/core/exceptions.py)。
 */
export function detailOf(err) {
  const data = err?.response?.data
  if (typeof data === 'string' && data.trim()) return data.trim()
  if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail.trim()
  if (typeof data?.error?.message === 'string' && data.error.message.trim()) {
    return data.error.message.trim()
  }
  const raw = typeof err?.message === 'string' ? err.message.trim() : ''
  return raw === 'Network Error' ? '' : raw
}

/**
 * 规则表 —— **顺序敏感: 先具体后通用**。
 * 409/410/413/422 都是「一码多义」，必须靠后端中文串把语义分开:
 *   409 既可能是"已收满"也可能是"片没传齐" —— 前者要联系发起人，后者点重试就行。
 * ⚠️ 这里 match 的是**后端 detail 的关键词**，所以文案与代码注释里都写清了依赖;
 *    后端改中文措辞时本表要跟着改 (改判据必须同时改两侧)。
 */
const RULES = [
  {
    code: FR_FAILURE_CODE.CHUNKS_INCOMPLETE,
    match: (st, d) => st === 409 && /片未上传|未传齐/.test(d),
    title: '还有分片没传完',
    detail: '这份文件有几个分片还没到达服务器，所以暂时不能合并。' +
      '点「继续上传」会接着没传完的部分传，不用从头再来。',
    action: FR_FAILURE_ACTION.RETRY,
  },
  {
    // ⚠️ 这条也是 409，但语义与"收满"不同: 是**同时进行的会话数**到顶
    //    (本仓后端用 max_submissions 兼作活跃会话闸, 堵反复 init 灌 staging)。
    //    所以是"等一会儿再传"，不是"没份了" —— 排在 QUOTA_FULL 之前。
    code: FR_FAILURE_CODE.RATE_LIMITED,
    match: (st, d) => st === 409 && /进行中上传数/.test(d),
    title: '这个链接正在收别的文件',
    detail: '同一个收件链接同时只能有几个大文件在传，现在已经排满了。' +
      '等当前那个传完（或它的断点过期）之后再点「继续上传」就行。',
    action: FR_FAILURE_ACTION.WAIT,
  },
  {
    code: FR_FAILURE_CODE.QUOTA_FULL,
    match: (st, d) => st === 409 && /收满|已达上限/.test(d),
    title: '这个收件链接已经收满了',
    detail: '发起人设定的收件份数已经用完，链接不再接收新文件。' +
      '请联系发起人，让他重新生成一个收件链接。',
    action: FR_FAILURE_ACTION.CONTACT,
  },
  {
    code: FR_FAILURE_CODE.LINK_CLOSED,
    match: (st, d) => st === 410 && /链接/.test(d),
    title: '收件链接已关闭或已过期',
    detail: '这个链接已经被发起人关闭，或者超过了有效期。' +
      '已经传完的文件不受影响；要继续收文件请联系发起人重新生成链接。',
    action: FR_FAILURE_ACTION.CONTACT,
  },
  {
    // ⚠️ 404 有两种: 「文件请求不存在」(token 错) 与「上传会话不存在」(断点过期)。
    //    前者要联系发起人重发链接，后者只要重选文件即可 —— 必须分开。
    code: FR_FAILURE_CODE.SESSION_GONE,
    match: (st, d) => (st === 410 && !/链接/.test(d)) || (st === 404 && /会话/.test(d)),
    title: '这次上传会话已经失效',
    detail: '大文件上传的断点记录超过 24 小时没接着传，服务端已经把它清掉了。' +
      '请重新选择同一个文件，从头再传一次。',
    action: FR_FAILURE_ACTION.RESELECT,
  },
  {
    // ⚠️ 这个 404 **不是** "链接不存在", 而是"这个服务上根本没有这条路由" ——
    //    FastAPI 对未注册路径回的默认体就是字面量 {"detail":"Not Found"}，
    //    与业务层 404 的中文 detail ("文件请求不存在") 完全不同。
    //    真实场景: 前端已发布但后端还没重建容器 ⇒ 若把它翻成"链接不存在",
    //    对方会去找发起人重发链接, 而真正该做的是部署后端 (2026-11-09 实测撞到的)。
    code: FR_FAILURE_CODE.UNKNOWN,
    match: (st, d) => st === 404 && /^(not found|method not allowed)$/i.test(d),
    title: '大文件上传服务当前不可用',
    detail: '这台服务器上没有找到大文件上传接口，通常是服务端刚更新还没发布完。' +
      '稍等几分钟后点「重试」；持续如此请把这段技术详情发给发起人。',
    action: FR_FAILURE_ACTION.RETRY,
  },
  {
    code: FR_FAILURE_CODE.LINK_NOT_FOUND,
    match: (st) => st === 404,
    title: '收件链接不存在',
    detail: '这个链接地址在本系统里查不到，通常是链接被删除了或者复制时缺了字符。' +
      '请让发起人重新发一次收件链接。',
    action: FR_FAILURE_ACTION.CONTACT,
  },
  {
    code: FR_FAILURE_CODE.TOTAL_TOO_BIG,
    match: (st, d) => st === 413 && /总量|累计/.test(d),
    title: '这个链接的总容量已经用满',
    detail: '所有已收文件的总大小加起来到了发起人设的上限，这份文件放不下了。' +
      '请联系发起人提高总容量上限，或者让他重新生成一个收件链接。',
    action: FR_FAILURE_ACTION.CONTACT,
  },
  {
    code: FR_FAILURE_CODE.FILE_TOO_BIG,
    match: (st, d) => st === 413,
    title: '文件太大了，超过单个文件的上限',
    detail: '服务器已经告诉你这份文件超过单文件限制，这个链接收不下它。' +
      '请联系发起人确认单文件上限，或者改用其他方式（如移动硬盘/其它网盘）交付。',
    action: FR_FAILURE_ACTION.CONTACT,
  },
  {
    code: FR_FAILURE_CODE.EXT_NOT_ALLOWED,
    match: (st, d) => st === 415,
    title: '这种文件类型不在收件范围内',
    detail: '发起人限定了能收的文件类型，这个文件的扩展名不在名单里。' +
      '请换一个符合要求的文件，或联系发起人确认可收类型。',
    action: FR_FAILURE_ACTION.RESELECT,
  },
  {
    code: FR_FAILURE_CODE.UNKNOWN,
    match: (st, d) => st === 422 && /姓名/.test(d),
    title: '请先填写你的姓名',
    detail: '这个收件链接要求实名提交，姓名没填或被清空了。' +
      '填上姓名后再点上传即可。',
    action: FR_FAILURE_ACTION.NONE,
  },
  {
    code: FR_FAILURE_CODE.CHUNK_CORRUPT,
    match: (st, d) => st === 422 && /校验失败|损坏/.test(d),
    title: '有分片在传输中损坏了',
    detail: '服务器逐片算了校验值，发现某一片和你本地的字节不一致，已经拒绝收下它。' +
      '点「继续上传」会重传这些片；若反复出现，请检查网络或换一条网络再传。',
    action: FR_FAILURE_ACTION.RETRY,
  },
  {
    code: FR_FAILURE_CODE.MERGE_FAILED,
    match: (st, d) => st >= 500,
    title: '服务器合并文件时失败了',
    detail: '分片都传到了，但服务器把它们拼成完整文件并核对时没成功，' +
      '残缺的临时对象已经被服务器自动丢弃，不会留下半个文件。' +
      '请稍等片刻后点「继续上传」重试；若仍然失败请联系发起人。',
    action: FR_FAILURE_ACTION.RETRY,
  },
  {
    code: FR_FAILURE_CODE.RATE_LIMITED,
    match: (st) => st === 429,
    title: '传得太快被服务器限流了',
    detail: '同一网络短时间内请求太多，服务器让先等一会儿。' +
      '上传没有失败，稍等十几秒点「继续上传」会接着传。',
    action: FR_FAILURE_ACTION.WAIT,
  },
  {
    code: FR_FAILURE_CODE.NETWORK,
    match: (st) => st === 0,
    title: '网络断了，上传已暂停',
    detail: '这一片没能发出去（或没能收到回应）。' +
      '已传到的部分服务器都记着，等网络恢复后点「继续上传」会从断点接着传。',
    action: FR_FAILURE_ACTION.RETRY,
  },
]

const FALLBACK = {
  code: FR_FAILURE_CODE.UNKNOWN,
  title: '上传没有成功',
  detail: '服务器返回了一个未预期的结果。可以重试一次；' +
    '若仍然失败，请把下方「技术详情」发给发起人。',
  action: FR_FAILURE_ACTION.RETRY,
}

/**
 * 把一次失败翻译成 `{ code, title, detail, action, technical, status }`
 *
 * @param {Error|{}} err axios 错误对象 (或任何带 response.status / message 的东西)
 * @returns {object} 永远非 null
 */
export function describeFileRequestFailure(err) {
  const status = statusOf(err)
  const detail = detailOf(err)
  const rule = RULES.find((r) => r.match(status, detail)) || FALLBACK

  return {
    code: rule.code,
    title: rule.title,
    detail: rule.detail,
    /** 该给按钮挂哪个动作 (FR_FAILURE_ACTION.*) */
    action: rule.action,
    /** 后端原始中文 + 状态码 —— 折叠展示用，不当主文案 */
    technical: detail ? `${detail} (HTTP ${status || '无响应'})` : `HTTP ${status || '无响应'}`,
    status,
  }
}
