"""AI 内容排版服务 — 将 PDF 提取的混乱文本整理为结构化 Markdown"""

import logging
import re

from app.core.llm import get_anthropic_client, get_default_model, extract_text_from_response
from app.core.celery_db import create_celery_engine_and_session
from app.core.celery import celery_app

logger = logging.getLogger("microbubble.content_formatter")

FORMAT_PROMPT = """你是学术文档排版助手。请将以下从 PDF 提取的混乱文本整理为结构清晰的 Markdown 格式。

排版规则：
1. **去除干扰**：直接删除页眉、页脚、页码、目录碎片等非正文内容，不要用任何标记（如~~删除线~~）包裹
2. **合并段落**：将因换页而断开的句子和段落重新合并，保持语义完整
3. **识别层级**：按原文章节结构使用 # ## ### 标题层级
4. **化学式**：使用 HTML 标签格式化，如 MnO<sub>2</sub>、SO<sub>4</sub><sup>2−</sup>
5. **图片占位符**：文中以 [FIGURE:N] 标记的图片占位符必须原样保留，放在对应图表标题下方
    **重要（v28 step 21）**：不要在正文里展开图片的 caption 描述（如 "Fig. 2. Effects of..." 这种完整图注文本）。
    正文只放 [FIGURE:N] 占位符 + 必要的上下文引用（如 "Fig. 2"），图片详细 caption 由前端 figcard 自动展示。
    OCR 提取常把 caption 文本（如 "Fig. 2. Effects of oxidant supply on toluene conversion..."）当作正文段落输出，必须识别并**只保留**正文上下文，把图注整段删除。
6. **表格**：尽可能还原为 Markdown 表格格式
7. **完整保留**：不要删减或改写论文的实质性内容，只做排版整理
8. **参考文献**：保留完整，按原文格式
9. **禁止使用 ~~删除线~~ 语法**：要删除的内容直接移除，绝对不要用 ~~ 包裹

# v28 step 18 增强：清理 OCR 残留 + 字符乱
10. **作者署名页脚**（重要！）：删除所有 "X. Wang et al." / "T. Wang et al." / "X. Li et al."
    形式的页脚重复署名行（可能含大量空白 + 数字页码）。这种行每页 PDF 渲染都出现，
    必须全部删除。识别特征：行首大写字母+英文名+et al.+行尾孤立数字（页码）。
11. **OCR 错位的图片 alt 文本残留**：删除形如 "such ![ as radical generation..." / "orbital ![图（..."
    形式的不完整图片描述（OCR 把图片 alt 文本错位插入正文）。这些是 OCR 解析错误，
    不属于正文内容。
12. **中文图注污染**：删除 "图（P1，..." / "图（P3，..." / "图（P8，" 形式的中文图注残留。
    PDF 提取偶尔把多模态图说明以中文标记污染进正文。
13. **化学式必须用 Unicode 上下标字符**（强制要求）：O3 → O₃，H2O2 → H₂O₂，MnO2 → MnO₂，
    SO4^2- → SO₄²⁻，CO2 → CO₂，OH- → OH⁻，NH4+ → NH₄⁺。**绝对不要**用 <sub>/<sup> HTML 标签
    （这些标签会被前端二次转义显示为源码）。所有上下标用 Unicode 字符：₀₁₂₃₄₅₆₇₈₉
    + ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ + ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻。
14. **段落重排**：按原文逻辑语义重组段落。OCR 输出常把一个完整句子截断到下一行
    （软换行），重组时合并成正常段落。段落之间用空行分隔。
15. **正文为主，元信息为辅**：删除重复出现的 "Received ... Available online" / "© 2024 Elsevier"
    / "Journal of Hazardous Materials 513 (2026) 142456" 等元信息行。

标题: {title}
原始文本:
{content}

请直接输出整理后的 Markdown 文档，不要加任何解释说明。"""


class ContentFormatterService:
    """使用 LLM 将 PDF 提取文本整理为结构化 Markdown"""

    async def format_content(self, title: str, content: str) -> str:
        """整理内容排版，返回 Markdown 格式文本

        带 429 rate limit 重试（指数退避）：vision/Claude API rate limit 时等待更长时间
        """
        max_retries = 3
        wait_times = [3, 8, 15]
        last_error = None

        for attempt in range(max_retries):
            try:
                client = get_anthropic_client()
                # v28 step 18: 用 replace 不用 format —— 真实 content 里有 {} (JSON 残留、citation 等)
                #   str.format() 会把这些 {} 当占位符解析导致 "Replacement index N out of range"
                prompt = FORMAT_PROMPT.replace('{title}', str(title)).replace('{content}', str(content)[:50000])
                response = await client.messages.create(
                    model=get_default_model(),
                    max_tokens=16384,
                    timeout=300,
                    thinking={'type': 'disabled'},
                    messages=[{"role": "user", "content": prompt}]
                )
                formatted = extract_text_from_response(response)
                if formatted and len(formatted) > 50:
                    # 后处理：移除 LLM 可能产生的删除线标记
                    formatted = re.sub(r'~~.+?~~', '', formatted)
                    logger.info(f"内容排版成功: {title}, 输出 {len(formatted)} 字符")
                    return formatted
                else:
                    logger.warning(f"内容排版输出过短: {title}")
                    return ""
            except Exception as e:
                last_error = e
                error_str = str(e)
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower() or 'Too Many' in error_str
                if is_rate_limit and attempt < max_retries - 1:
                    wait_sec = wait_times[attempt] if attempt < len(wait_times) else 15
                    logger.warning(
                        f"内容排版 429 rate limit, 第 {attempt + 1}/{max_retries} 次重试, 等待 {wait_sec}s: {title[:40]}"
                    )
                    import asyncio
                    await asyncio.sleep(wait_sec)
                    continue
                logger.error(f"内容排版失败: {title}, 错误: {e}")
                return ""
        return ""


content_formatter_service = ContentFormatterService()


# ============================================================
# v28 step 18: Celery 异步重排 task
# 之前 _reformat_task 用 asyncio.create_task() 在 FastAPI 进程内 spawn，
# 进程重启任务丢失，formatted_content 永远不更新。
# 现在用 Celery，任务持久化到 Redis broker，worker 进程重启不丢。
# ============================================================

@celery_app.task(name="app.services.content_formatter_service.reformat_knowledge_task", bind=True, max_retries=2)
def reformat_knowledge_task(self, knowledge_id: int):
    """
    异步重排知识条目内容（Celery task）

    流程：
    1. 独立 AsyncSession 查 Knowledge
    2. 调 LLM 重排 content
    3. 解析 [FIGURE:N] 占位符 → 替换为 MinIO 实际 URL
    4. 写回 formatted_content

    抗重启（v28 step 18）：
    - 用独立 async_session（不共享 FastAPI app 的 session）
    - 任务持久化到 Redis，worker 进程重启仍能 resume
    - 失败自动重试 2 次（countdown=60s）
    """
    import asyncio
    from app.config import settings
    from app.models.knowledge import Knowledge
    from sqlalchemy import select

    async def _run():
        # v28 step 18: Celery worker 是新 event loop，不能复用 FastAPI app 的全局 async_session
        #   跨 event loop 复用连接池会报 "Future attached to a different loop"
        #   参考 reminder_service.py 模式：创建独立 NullPool 引擎 + 任务结束 dispose
        local_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with local_session_factory() as db:
                try:
                    result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
                    knowledge = result.scalar_one_or_none()
                    if not knowledge:
                        logger.error(f"reformat_knowledge_task: knowledge_id={knowledge_id} 不存在")
                        return

                    logger.info(f"[reformat] 开始: knowledge_id={knowledge_id}, content_len={len(knowledge.content or '')}")
                    formatted = await content_formatter_service.format_content(knowledge.title, knowledge.content or '')
                    if not formatted:
                        logger.warning(f"[reformat] LLM 输出空: knowledge_id={knowledge_id}")
                        return

                    # 解析 [FIGURE:N] → MinIO URL
                    formatted = await _resolve_figure_placeholders(knowledge_id, formatted)

                    # v28 step 20: 补全 References 段（LLM 经常截断 refs，从 content 原始数据补）
                    formatted = _restore_references_section(formatted, knowledge.content or '')

                    knowledge.formatted_content = formatted
                    await db.commit()
                    logger.info(f"[reformat] 完成: knowledge_id={knowledge_id}, formatted_len={len(formatted)}")
                except Exception as e:
                    logger.error(f"[reformat] 失败: knowledge_id={knowledge_id}, 错误: {e}", exc_info=True)
                    raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    except Exception as e:
        # Celery 自动重试
        raise self.retry(exc=e, countdown=60)


def _restore_references_section(formatted: str, original_content: str) -> str:
    """
    v28 step 20: 补全 References 段

    LLM 重排经常截断 References 段（如 p19 只写 3 条 [1] [2] [3] 就停了），
    但 original_content（PDF 提取原始数据）里有完整 refs。

    算法：
    1. 从 formatted 找 ## References 段（可能没截断也可能截断）
    2. 从 original_content 找 References 段（OCR 格式）
    3. 比较两者 ref 数量，original 多就补全
    4. 用 [N] 切分 original 的 refs，按序合并到 formatted 的 References 段

    重要：只补充 "原本在 original 里的 ref"，不增加新 ref
    """
    if not formatted or not original_content:
        return formatted

    # 1. 找 formatted 的 References 段
    f_ref_match = re.search(
        r'(##?\s*References\b[\s\S]*?)(?=\n##?\s|\Z)',
        formatted, re.IGNORECASE
    )

    # 2. 找 original_content 的 References 段（v28 step 20: 容忍前导任意非空字符）
    #    OCR 提取的 content 经常 References 段一直延续到末尾（没有终止词），
    #    所以兜底直接到 \Z（字符串末尾），但优先匹配终止词
    o_ref_match = re.search(
        r'References\s*\n([\s\S]*?)(?=\n\s*(?:Author\s+contributions|Declaration\s+of\s+competing|Graphical\s+abstract|Highlights|Acknowledgments?|Supplementary\s+material|Appendix|Notes\s+and|CRediT)\b|\Z)',
        original_content, re.IGNORECASE
    )

    if not o_ref_match:
        return formatted  # original 也没 References 段
    original_refs_text = o_ref_match.group(1).strip()
    # 从 original_refs_text 提取 [N] 开头的所有 ref（按 [N] 切分）
    # 注意：OCR 提取的 ref 可能跨多行（每行约 70 字符软换行）
    refs_raw = []
    for m in re.finditer(r'\[(\d+)\]\s*([\s\S]*?)(?=\[\d+\]|\Z)', original_refs_text):
        ref_text = re.sub(r'\s+', ' ', m.group(2)).strip()
        if ref_text and len(ref_text) > 10:
            refs_raw.append((int(m.group(1)), ref_text))

    if not refs_raw:
        return formatted

    if f_ref_match:
        # formatted 有 References 段：补充缺失的 [N]
        f_ref_section = f_ref_match.group(1)
        # 已有 [N] 集合
        existing_nums = set()
        for m in re.finditer(r'\[(\d+)\]', f_ref_section):
            existing_nums.add(int(m.group(1)))

        # 找缺失的 [N]
        missing = [(n, t) for n, t in refs_raw if n not in existing_nums]
        if not missing:
            return formatted  # formatted 已完整

        logger.info(f"[reformat] References 段缺 {len(missing)} 条（existing={sorted(existing_nums)} → adding={[n for n,_ in missing]}），从 content 补全")

        # 在 References 段末尾追加缺失 refs
        append_text = '\n\n' + '\n\n'.join(f"[{n}] {t}" for n, t in missing)
        # 找 References 段末尾插入（保留后续其他 section）
        return formatted[:f_ref_match.end()] + append_text + formatted[f_ref_match.end():]
    else:
        # formatted 完全没有 References 段：直接追加
        logger.info(f"[reformat] formatted 缺 References 段，从 content 补 {len(refs_raw)} 条")
        refs_text = '\n\n'.join(f"[{n}] {t}" for n, t in refs_raw)
        return formatted.rstrip() + f"\n\n## References\n\n{refs_text}\n"


async def _resolve_figure_placeholders(knowledge_id: int, text: str) -> str:
    """
    将 [FIGURE:N] 占位符替换为 MinIO 中的实际图片 URL

    抽出 _resolve_figure_placeholders 让 Celery task 和 FastAPI asyncio.create_task 都能复用
    """
    placeholders = re.findall(r'\[FIGURE:([\d.]+)\]', text)
    if not placeholders:
        return text

    from app.services.file_service import file_service
    prefix = f"knowledge/{knowledge_id}/"
    try:
        objects = await file_service.list_objects(prefix)
    except Exception as e:
        logger.warning(f"列出 MinIO 对象失败(knowledge_id={knowledge_id}): {e}")
        return text

    if not objects:
        return text

    # 按文件名中的数字排序
    def _idx(name: str) -> int:
        m = re.search(r'(\d+)', name)
        return int(m.group(1)) if m else 9999

    # v28 step 18: list_objects 返回 dict 或对象都支持
    def _name(obj):
        if isinstance(obj, dict):
            return obj.get('object_name', '') or obj.get('name', '')
        return getattr(obj, 'object_name', '') or getattr(obj, 'name', '')

    def _get_url(obj):
        if isinstance(obj, dict):
            return obj.get('url', '')
        return getattr(obj, 'url', '')

    sorted_objs = sorted(objects, key=lambda o: _idx(_name(o)))

    for idx, placeholder in enumerate(placeholders):
        if idx >= len(sorted_objs):
            break
        name = _name(sorted_objs[idx])
        url = _get_url(sorted_objs[idx])
        if not url:
            try:
                url = await file_service.get_object_url(name)
            except Exception:
                pass
        if url:
            text = text.replace(f"[FIGURE:{placeholder}]", url)
        else:
            text = text.replace(f"[FIGURE:{placeholder}]", "")

    return text
