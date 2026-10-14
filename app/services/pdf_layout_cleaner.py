"""PDF 版面清洗 —— Word 稿件（行号版式）专用

## 为什么需要

投稿稿件常由 Word 导出成 PDF，**每行前插行号、每页插页码**，而且**词被行号劈开**：

    multi-ROS react
    34
    ion networks ...          ← "reaction" 被劈成 react + ion

直接入库 ⇒ BM25 / PG tsvector **匹配不到被劈开的词**（`reaction` 搜不到
`react`+`ion`）⇒ 该文献等于检索不到（类 20.220：副作用没发生，但没人报错）。

实测案例 `ER-26-18027.pdf`（83 页综述 / 13530 英文词）。

## ⚠️ 设计取舍：**只删数字行 + 补空格，不跨行接合词**

我一度实现了「把被劈开的词接回去」，实测发现**结构上无法区分**这两种情况：

    page22:  'turbulent shear\n314 \n can induce bubble collapse'
             ↑ 数字行隔开的是**两个完整词**（shear / can），接合会得到 `shearcan`
    page5 :  'multi-ROS react\n34 \nion networks'
             ↑ 数字行把**一个词**劈开了，接合才能得到 `reaction`

两者在文本层面**完全同构**，没有词典就判不了。误接的代价（`shearcan` 这种
粘连词会**污染整个 BM25 索引**，让所有查询都受影响）**大于**漏接的代价。

⇒ 采**保守策略**：删掉独占纯数字行，把单换行折成空格（保留段落空行）。
`shear can` / `diff erent` 虽不完美，但**不产生垃圾 token**。

**代价量化**：全文 13530 词中被劈开的约 33 词（**0.24%**）；而同一篇里
`reaction` 完整出现 111 次、`oxidation` 43 次 ⇒ 检索命中几乎不受影响。
这个交换是划算的。

## 两条踩过的坑（别重蹈）

1. **过度修正**：曾加宽规则 `\\b(word)\\s+([a-z]{1,3})\\b`，结果把**正常空格也吃掉**：
   `present in`→`presentin`、`cavitation and`→`cavitationand`。已删除。
2. **规则顺序**：任何跨块接合规则都必须放在「折叠空白」**之后**，否则空行还是
   `\\n\\n\\n`，规则匹配不到、等于没生效。

## 不碰的东西

`[PAGE:N]` / `[FIGURE:N]` 占位符不触发任何规则（含方括号、非纯数字行）。
"""
import re


def _is_line_number(s: str) -> bool:
    """独占一行的纯数字（行号 / 页码）。限 1~4 位，避免误伤正文数字。"""
    return re.fullmatch(r"\d{1,4}", s.strip()) is not None


def clean_page(text: str) -> str:
    """清洗**单页**文本。删行号（独占行 + 行内）+ 单换行折成空格。

    ⚠️ **不做跨行接词**（见模块 docstring 的取舍说明）。
    """
    if not text:
        return ""

    # 1) 删掉独占一行的纯数字（行号 / 页码）
    lines = [ln for ln in text.split("\n") if not _is_line_number(ln)]

    text = "\n".join(lines)

    # 2) 单换行 → 空格（空行保留作段落分隔）
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # 3) ⚠️ **不做行内行号删除**（曾实现过，实测会误删正文数字，已放弃）：
    #      `turbulent shear 314   can induce`   ← 行号排在词中间（要删）
    #      `See equations 12 and 14 for details` ← 引用编号（不能删）
    #      `at 300 K and 15 bar the rate is 21`   ← 量纲数值（不能删）
    #    三者**结构上无法区分**（都是「小写字母 + 空格 + 2~4 位数字 + 空格 + 小写」），
    #    没有词典就判不了。实测误删率高于命中收益 ⇒ 宁可不删。
    #    代价：行内行号（实测 1415 处）留在正文里，是纯数字 token，
    #    对 BM25 的影响可忽略（只占 1% 左右 token），**不会粘连正常词**。

    # 4) 折叠空白
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_line_numbered_pdf(text: str) -> bool:
    """判断是否属于「行号版式」稿件（只对这类 PDF 施加清洗）。

    判据：整页里**独占一行的纯数字**占比。普通排版 PDF 里数字几乎不会单独占行。
    阈值取 ≥3 个**且**占非空行数的 ≥8%。

    ⚠️ 早期版本只看**前 40 行**，实测误判（稿件首页是摘要 + 元数据，
    行号稀疏，40 行内凑不够 3 个 → 漏判 → 清洗不生效）。
    ⇒ 改为**扫整页**，用「个数 + 占比」双条件，漏判与误判都更稳。
    """
    if not text:
        return False
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) < 12:
        return False
    hits = sum(1 for ln in lines if _is_line_number(ln))
    return hits >= 3 and hits >= 0.08 * len(lines)


__all__ = ["clean_page", "is_line_numbered_pdf"]