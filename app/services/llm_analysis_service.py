"""LLM 内容分析服务 — 动态分类、标签、核心概念提取"""

import json
import logging

from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

logger = logging.getLogger("microbubble.llm_analysis")

ANALYSIS_PROMPT = """你是微纳米气泡课题组的AI知识管理助手。分析以下文档，提取结构化信息。

返回严格的JSON格式（不要包含其他文字）：

{{"summary": "150字以内的中文摘要，抓住核心发现和方法",
  "category": "从以下预设分类中选择最匹配的一个：论文/方法/标准/综述/案例/FAQ/笔记/手册。如果都不匹配，根据内容自定一个具体的研究子方向分类。",
  "topic": "具体研究方向，例如：臭氧气泡消毒动力学、气泡生成与表征、NTA粒径分析、农业灌溉应用、黑臭水体治理等。",
  "tags": ["从内容中提取5-8个关键技术术语作为标签，如具体材料、方法、指标、应用场景"],
  "key_concepts": ["文档涉及的2-5个核心概念或关键发现，每个10字以内"],
  "related_topics": ["应该与此文档关联的2-4个研究主题，用于后续建立知识关联"],
  "knowledge_type": "文献阅读/实验方法/技术标准/研究综述/案例分析/数据报告/FAQ",
  "entities": [
    {{"subject": "主体(材料/方法/指标)", "predicate": "关系(影响/导致/抑制/促进/表征/检测)", "object": "客体(数值/效果/现象)", "condition": "条件(温度/浓度/pH/时间等)，无则null", "confidence": 0.9}}
  ],
  "formulas": [
    {{"name": "公式名称", "formula": "数学表达式(用*表示乘,/表示除,变量用字母)", "variables": {{"V0": {{"description": "空白滴定体积", "unit": "mL"}}}}, "result_unit": "结果单位", "conditions": "适用条件", "domain": "所属领域，从以下分类选择最匹配的一个: bubble_dynamics/mass_transfer/water_quality/chemical_kinetics/fluid_mechanics/statistical_analysis，或具体子领域如COD/BOD/DO/臭氧/消毒/吸附/传质/曝气/雷诺数/粒径"}}
  ]
}}

分类说明（category字段必须从以下选择）：
- 论文：学术论文、期刊文章、会议论文
- 方法：实验方法、操作流程、技术方案
- 标准：检测标准、行业规范、技术标准
- 综述：文献综述、研究综述、技术综述
- 案例：案例分析、应用实例、工程案例
- FAQ：常见问题、问答、疑难解答
- 笔记：学习笔记、会议记录、研究笔记
- 手册：操作手册、使用指南、技术手册

entities 字段要求：
- 从文档中提取 3-8 个结构化的知识三元组
- subject: 研究的主体对象（材料、方法、指标、设备等）
- predicate: 主体与客体之间的关系（导致、抑制、促进、表征、检测、影响、生成、去除等）
- object: 客体的具体内容（数值、效果、现象、结论等）
- condition: 该关系成立的条件（实验条件、环境参数等），如文中未明确则填null
- confidence: 基于文中证据强度的置信度 0-1
- 每个三元组应是一个独立的、可被引用的知识单元

formulas 字段要求：
- 从文档中提取数学公式和计算关系（0-3个，无则返回空数组）
- name: 公式的中文名称
- formula: 可执行的数学表达式（用*表示乘，/表示除，变量用字母）
- variables: 每个变量的描述和单位
- result_unit: 计算结果单位
- domain: 应用领域标签

标题: {title}
内容: {content}"""


class LLMAnalysisService:
    """基于 LLM 的内容分析：自动分类、标签、核心概念提取"""

    async def analyze_content(self, title: str, content: str) -> dict:
        """分析内容，返回 {summary, category, tags, key_concepts, related_topics, knowledge_type}

        v28 step 34 修复: 之前 JSON 解析失败（如数学公式 $$x$$ 含未转义字符）直接返空，
        整条 knowledge 卡 failed。改 fallback: 解析失败时用正则从 raw text 提取关键字段。
        """
        try:
            client = get_anthropic_client()
            prompt = ANALYSIS_PROMPT.format(
                title=title,
                content=content[:3000]
            )
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=1500,  # v28 step 34: 提到 1500 给数学公式留空间
                timeout=60,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}]
            )
            # 提取文本内容
            text = extract_text_from_response(response)
            # 解析 JSON
            try:
                result = parse_llm_json(text)
                if result.get("summary"):
                    return result
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"LLM JSON 解析失败: {type(e).__name__}: {str(e)[:120]}")
                # v28 step 34 fallback: 从 raw text 提取关键字段
                result = _fallback_extract_fields(text)
                if result.get('summary') or result.get('category'):
                    logger.info(f"Fallback 提取成功: summary={len(result.get('summary', ''))} chars")
                    return result
            # 解析成功但 summary 仍空（LLM 没生成）
            if not result.get("summary"):
                logger.warning("LLM 分析未返回 summary")
            return result
        except Exception as e:
            logger.error(f"LLM 内容分析失败: {e}")
            return {"summary": "", "category": "", "tags": [], "key_concepts": [], "related_topics": [], "knowledge_type": "文献阅读"}


def _fallback_extract_fields(text: str) -> dict:
    """v28 step 34 fallback: 当 LLM 返回 JSON 因数学公式等被破坏时，
    从 raw text 用正则提取关键字段（不完美但比返空好）"""
    import re
    result = {
        'summary': '', 'category': '', 'topic': '', 'tags': [],
        'key_concepts': [], 'related_topics': [], 'knowledge_type': '',
    }

    def extract_str(key: str) -> str:
        # 允许值中含 \" 转义
        m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        return m.group(1).replace('\\"', '"').replace('\\n', '\n') if m else ''

    def extract_array(key: str) -> list:
        m = re.search(rf'"{key}"\s*:\s*\[([^\]]+)\]', text)
        if not m:
            return []
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
        return [item.replace('\\"', '"') for item in items]

    for f in ['summary', 'category', 'topic', 'knowledge_type']:
        result[f] = extract_str(f)
    result['tags'] = extract_array('tags')
    result['key_concepts'] = extract_array('key_concepts')
    result['related_topics'] = extract_array('related_topics')
    return result


llm_analysis_service = LLMAnalysisService()
