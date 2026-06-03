"""知识图谱构建器 — LLM 实体/关系提取 + Neo4j 写入

流程：
1. 接收知识条目（title + content）
2. LLM 提取实体（人名/机构/概念/方法/材料/设备/指标）
3. LLM 提取实体间关系
4. 实体消歧 + 去重
5. 写入 Neo4j

实体类型：Concept / Method / Material / Equipment / Metric / Person / Organization / Paper
关系类型：uses / produces / inhibits / measures / correlates / extends / contradicts / prerequisite
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("microbubble.kg_builder")

# 实体类型定义
ENTITY_TYPE_PROMPT = """你是一个微纳米气泡研究领域的知识图谱构建专家。
从以下文本中提取实体和关系。

## 实体类型
- Concept: 概念/理论/现象（如"微纳米气泡"、"空化效应"、"zeta电位"）
- Method: 方法/技术/工艺（如"超声法"、"电解法"、"溶气法"）
- Material: 材料/化学品（如"表面活性剂"、"聚合物"、"臭氧"）
- Equipment: 设备/仪器（如"粒度分析仪"、"高速相机"、"超声发生器"）
- Metric: 指标/参数（如"粒径分布"、"含气量"、"稳定性"、"溶解氧"）
- Person: 人名（如"杜同贺"、"赵航佳"）
- Organization: 机构（如"课题组"、"合作单位"）
- Paper: 文献/论文（如具体论文标题）

## 关系类型
- uses: 使用（A uses B）
- produces: 产生（A produces B）
- inhibits: 抑制（A inhibits B）
- measures: 测量（A measures B）
- correlates: 相关（A correlates B）
- extends: 扩展（A extends B）
- contradicts: 矛盾（A contradicts B）
- prerequisite: 前置（A prerequisite B）

## 输出格式
返回 JSON，包含 entities 和 relations 两个数组：
```json
{
  "entities": [
    {"name": "实体名", "type": "实体类型", "description": "简短描述", "aliases": ["别名1"]}
  ],
  "relations": [
    {"source": "源实体名", "target": "目标实体名", "type": "关系类型", "reason": "关系原因"}
  ]
}
```

注意：
- 实体名尽量用中文标准名称
- 别名包括英文缩写、同义词
- 每个实体必须有 type 和 description
- 关系必须有明确的 source、target、type
- 如果文本中没有明确的关系，不要强行提取
- 只提取与微纳米气泡研究相关的实体
"""


class KnowledgeGraphBuilder:
    """知识图谱构建器"""

    def __init__(self):
        pass

    async def extract_from_text(
        self, title: str, content: str
    ) -> Dict[str, List]:
        """从文本中提取实体和关系

        Args:
            title: 知识条目标题
            content: 知识条目内容

        Returns:
            {"entities": [...], "relations": [...]}
        """
        try:
            from app.services.llm_service import get_llm_response

            # 截取内容避免过长
            text = f"标题: {title}\n\n内容: {content[:3000]}"

            prompt = f"""{ENTITY_TYPE_PROMPT}

请从以下文本中提取实体和关系：

{text}"""

            response = await get_llm_response(prompt)
            result = self._parse_response(response)

            logger.info(
                f"图谱提取完成: {title[:30]}... → "
                f"{len(result['entities'])} 实体, {len(result['relations'])} 关系"
            )
            return result

        except Exception as e:
            logger.error(f"图谱提取失败: {title[:30]}...: {e}")
            return {"entities": [], "relations": []}

    def _parse_response(self, response: str) -> Dict[str, List]:
        """解析 LLM 返回的 JSON"""
        try:
            # 尝试提取 JSON 块
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()

            data = json.loads(json_str)

            entities = data.get("entities", [])
            relations = data.get("relations", [])

            # 验证实体格式
            valid_entities = []
            for e in entities:
                if isinstance(e, dict) and "name" in e and "type" in e:
                    if e["type"] in [
                        "Concept", "Method", "Material", "Equipment",
                        "Metric", "Person", "Organization", "Paper",
                    ]:
                        valid_entities.append({
                            "name": e["name"].strip(),
                            "type": e["type"],
                            "description": e.get("description", ""),
                            "aliases": e.get("aliases", []),
                        })

            # 验证关系格式
            valid_relations = []
            entity_names = {e["name"] for e in valid_entities}
            for r in relations:
                if isinstance(r, dict) and "source" in r and "target" in r and "type" in r:
                    if r["type"] in [
                        "uses", "produces", "inhibits", "measures",
                        "correlates", "extends", "contradicts", "prerequisite",
                    ]:
                        # 只保留源和目标都存在的关系
                        if r["source"] in entity_names and r["target"] in entity_names:
                            valid_relations.append({
                                "source": r["source"].strip(),
                                "target": r["target"].strip(),
                                "type": r["type"],
                                "reason": r.get("reason", ""),
                            })

            return {"entities": valid_entities, "relations": valid_relations}

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"解析 LLM 响应失败: {e}")
            return {"entities": [], "relations": []}

    async def build_graph_for_knowledge(
        self, knowledge_id: int, title: str, content: str
    ) -> Dict[str, int]:
        """为单条知识构建图谱

        Args:
            knowledge_id: 知识条目 ID
            title: 标题
            content: 内容

        Returns:
            {"entities_created": N, "relations_created": M}
        """
        # 1. LLM 提取
        extracted = await self.extract_from_text(title, content)

        if not extracted["entities"]:
            return {"entities_created": 0, "relations_created": 0}

        # 2. 写入 Neo4j
        from app.services.neo4j_service import get_neo4j_service
        neo4j = get_neo4j_service()

        entities_created = 0
        for entity in extracted["entities"]:
            node_id = neo4j.create_entity(
                name=entity["name"],
                entity_type=entity["type"],
                description=entity["description"],
                aliases=entity["aliases"],
                knowledge_ids=[knowledge_id],
            )
            if node_id:
                entities_created += 1

        relations_created = 0
        for rel in extracted["relations"]:
            success = neo4j.create_relation(
                source_name=rel["source"],
                target_name=rel["target"],
                relation_type=rel["type"],
                properties={"reason": rel["reason"], "knowledge_id": knowledge_id},
            )
            if success:
                relations_created += 1

        logger.info(
            f"图谱构建完成: knowledge_id={knowledge_id} → "
            f"{entities_created} 实体, {relations_created} 关系"
        )

        return {
            "entities_created": entities_created,
            "relations_created": relations_created,
        }


# 全局单例
_kg_builder: Optional[KnowledgeGraphBuilder] = None


def get_kg_builder() -> KnowledgeGraphBuilder:
    """获取图谱构建器单例"""
    global _kg_builder
    if _kg_builder is None:
        _kg_builder = KnowledgeGraphBuilder()
    return _kg_builder
