"""成员身份称谓 — 2026-09-05 角色扁平化

课题组不再区分管理员/组长/成员等级 (role 字段退役, 仅作历史保留),
成员只带自己的年级身份称谓: 导师 / 博士后 / 博士 / 硕士 / 本科生 / 校友。

身份称谓从 Member.grade 派生 (grade 存"研二/博一/副教授"等细粒度年级,
本模块收敛为对外展示的统一称谓)。
"""

from typing import Optional

# 成员列表排序时的身份次序 (未知排最后)
STATUS_ORDER = ("导师", "博士后", "博士", "硕士", "本科生", "校友", "成员")

# 按序匹配: (grade 中的关键词元组) → 统一称谓
_RULES = (
    (("教授", "副教授", "讲师", "老师", "教师", "研究员", "副研究员", "辅导员", "导师"), "导师"),
    (("博士后", "博后"), "博士后"),
    (("博",), "博士"),          # 博士 / 博一 / 博二 / 直博
    (("研", "硕"), "硕士"),     # 研一 / 研二 / 研三 / 硕士
    (("本", "大一", "大二", "大三", "大四"), "本科生"),
    (("毕业", "校友"), "校友"),
)

DEFAULT_STATUS = "成员"


def member_status(grade: Optional[str]) -> str:
    """由年级 grade 派系统一身份称谓。

    grade 为空或无法识别时: 能识别的返回对应称谓, 否则返回 grade 原文
    (保留信息), grade 也缺失时返回 "成员"。
    """
    g = (grade or "").strip()
    if not g:
        return DEFAULT_STATUS
    for keywords, status in _RULES:
        if any(k in g for k in keywords):
            return status
    return g
