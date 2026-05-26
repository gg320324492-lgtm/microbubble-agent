"""LLM 内容分析服务 — 动态分类、标签、核心概念提取"""

import json
import logging

from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

logger = logging.getLogger("microbubble.llm_analysis")

ANALYSIS_PROMPT = """你是微纳米气泡课题组的AI知识管理助手。分析以下文档，提取结构化信息。

返回严格的JSON格式（不要包含其他文字）：

{{"summary": "150字以内的中文摘要，抓住核心发现和方法",
  "category": "根据文档内容自定分类，要具体到研究子方向，例如：臭氧气泡消毒动力学、气泡生成与表征、NTA粒径分析、农业灌溉应用、黑臭水体治理等。不要使用宽泛的'基础/方法/文献'，要具体。",
  "tags": ["从内容中提取5-8个关键技术术语作为标签，如具体材料、方法、指标、应用场景"],
  "key_concepts": ["文档涉及的2-5个核心概念或关键发现，每个10字以内"],
  "related_topics": ["应该与此文档关联的2-4个研究主题，用于后续建立知识关联"],
  "knowledge_type": "文献阅读/实验方法/技术标准/研究综述/案例分析/数据报告/FAQ",
  "entities": [
    {{"subject": "主体(材料/方法/指标)", "predicate": "关系(影响/导致/抑制/促进/表征/检测)", "object": "客体(数值/效果/现象)", "condition": "条件(温度/浓度/pH/时间等)，无则null", "confidence": 0.9}}
  ]
}}

entities 字段要求：
- 从文档中提取 3-8 个结构化的知识三元组
- subject: 研究的主体对象（材料、方法、指标、设备等）
- predicate: 主体与客体之间的关系（导致、抑制、促进、表征、检测、影响、生成、去除等）
- object: 客体的具体内容（数值、效果、现象、结论等）
- condition: 该关系成立的条件（实验条件、环境参数等），如文中未明确则填null
- confidence: 基于文中证据强度的置信度 0-1
- 每个三元组应是一个独立的、可被引用的知识单元

标题: {title}
内容: {content}"""


class LLMAnalysisService:
    """基于 LLM 的内容分析：自动分类、标签、核心概念提取"""

    async def analyze_content(self, title: str, content: str) -> dict:
        """分析内容，返回 {summary, category, tags, key_concepts, related_topics, knowledge_type}"""
        try:
            client = get_anthropic_client()
            prompt = ANALYSIS_PROMPT.format(
                title=title,
                content=content[:3000]
            )
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=800,
                timeout=30,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}]
            )
            # 提取文本内容
            text = extract_text_from_response(response)
            # 解析 JSON
            result = parse_llm_json(text)
            # 验证必要字段
            if not result.get("summary"):
                logger.warning("LLM 分析未返回 summary")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"LLM 分析返回非 JSON 格式: {e}")
            # 尝试从原始响应中提取关键信息
            return {"summary": "", "category": "", "tags": [], "key_concepts": [], "related_topics": [], "knowledge_type": "文献阅读"}
        except Exception as e:
            logger.error(f"LLM 内容分析失败: {e}")
            return {"summary": "", "category": "", "tags": [], "key_concepts": [], "related_topics": [], "knowledge_type": "文献阅读"}


llm_analysis_service = LLMAnalysisService()
