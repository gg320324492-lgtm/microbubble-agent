/**
 * 成员身份称谓 — 2026-09-05 角色扁平化
 *
 * 与后端 app/core/member_identity.py 保持同一映射：
 * 课题组不再区分管理员/组长/成员等级，成员只带年级身份称谓
 * (导师 / 博士后 / 博士 / 硕士 / 本科生 / 校友)。
 *
 * 后端接口 (UserInfo / MemberResponse) 已直接返回派生的 `title` 字段；
 * 本工具用于仅有 grade 的本地数据 (旧缓存 / 群聊卡片降级展示)。
 */

const RULES = [
  { keywords: ['教授', '副教授', '讲师', '老师', '教师', '研究员', '副研究员', '辅导员', '导师'], status: '导师' },
  { keywords: ['博士后', '博后'], status: '博士后' },
  { keywords: ['博'], status: '博士' },
  { keywords: ['研', '硕'], status: '硕士' },
  { keywords: ['本', '大一', '大二', '大三', '大四'], status: '本科生' },
  { keywords: ['毕业', '校友'], status: '校友' },
]

export const DEFAULT_STATUS = '成员'

/** 由 grade 派统一身份称谓; 无法识别时返回 grade 原文, grade 缺失返回"成员" */
export function memberStatus(grade) {
  const g = (grade || '').trim()
  if (!g) return DEFAULT_STATUS
  for (const { keywords, status } of RULES) {
    if (keywords.some((k) => g.includes(k))) return status
  }
  return g
}

/** 从成员对象取展示称谓: 优先后端 title, 退化 grade 派生 */
export function memberTitleOf(member, fallback = DEFAULT_STATUS) {
  if (!member) return fallback
  return member.title || memberStatus(member.grade) || fallback
}

/** el-tag type 配色 (按身份称谓, 替代原 admin/leader/member 三色等级) */
export function memberTagType(member) {
  switch (memberTitleOf(member)) {
    case '导师':
    case '老师':
      return 'danger'
    case '博士后':
    case '博士':
      return 'warning'
    case '硕士':
      return 'primary'
    case '本科生':
      return 'success'
    default:
      return 'info'
  }
}
