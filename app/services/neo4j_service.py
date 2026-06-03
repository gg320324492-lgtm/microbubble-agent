"""Neo4j 图数据库服务

提供知识图谱的 CRUD 和 Cypher 查询能力。
实体节点：Concept / Method / Material / Equipment / Metric / Person / Organization / Paper
关系边：uses / produces / inhibits / measures / correlates / extends / contradicts / prerequisite

连接配置从环境变量读取，失败时优雅降级（图谱功能不可用但不影响其他功能）。
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("microbubble.neo4j")

# Neo4j 连接配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "microbubble2024"

# 实体类型
ENTITY_TYPES = [
    "Concept", "Method", "Material", "Equipment",
    "Metric", "Person", "Organization", "Paper",
]

# 关系类型
RELATION_TYPES = [
    "uses", "produces", "inhibits", "measures",
    "correlates", "extends", "contradicts", "prerequisite",
]


class Neo4jService:
    """Neo4j 图数据库服务"""

    def __init__(self):
        self._driver = None

    def _get_driver(self):
        """惰性获取 Neo4j driver"""
        if self._driver is not None:
            return self._driver
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            # 验证连接
            self._driver.verify_connectivity()
            logger.info("Neo4j 连接成功")
            return self._driver
        except Exception as e:
            logger.warning(f"Neo4j 连接失败: {e}（图谱功能不可用）")
            self._driver = None
            return None

    def close(self):
        """关闭连接"""
        if self._driver:
            self._driver.close()
            self._driver = None

    # ===== 实体 CRUD =====

    def create_entity(
        self,
        name: str,
        entity_type: str,
        description: str = "",
        aliases: List[str] = None,
        properties: Dict[str, Any] = None,
        knowledge_ids: List[int] = None,
    ) -> Optional[str]:
        """创建实体节点

        Args:
            name: 实体名称
            entity_type: 实体类型（Concept/Method/Material/...）
            description: 描述
            aliases: 别名列表
            properties: 类型特有属性
            knowledge_ids: 关联的知识条目 ID

        Returns:
            Neo4j 节点 ID，失败返回 None
        """
        driver = self._get_driver()
        if driver is None:
            return None

        query = """
        MERGE (e:%s {name: $name})
        ON CREATE SET
            e.description = $description,
            e.aliases = $aliases,
            e.properties = $properties,
            e.knowledge_ids = $knowledge_ids,
            e.created_at = datetime()
        ON MATCH SET
            e.description = CASE WHEN $description <> '' THEN $description ELSE e.description END,
            e.aliases = CASE WHEN size($aliases) > 0 THEN $aliases ELSE e.aliases END,
            e.knowledge_ids = CASE WHEN size($knowledge_ids) > 0 THEN $knowledge_ids ELSE e.knowledge_ids END,
            e.updated_at = datetime()
        RETURN elementId(e) AS id
        """ % entity_type

        try:
            with driver.session() as session:
                result = session.run(
                    query,
                    name=name,
                    description=description or "",
                    aliases=aliases or [],
                    properties=properties or {},
                    knowledge_ids=knowledge_ids or [],
                )
                record = result.single()
                if record:
                    node_id = record["id"]
                    logger.debug(f"实体创建/更新: {name} ({entity_type}) -> {node_id}")
                    return node_id
        except Exception as e:
            logger.error(f"创建实体失败: {name} ({entity_type}): {e}")
        return None

    def create_relation(
        self,
        source_name: str,
        target_name: str,
        relation_type: str,
        properties: Dict[str, Any] = None,
    ) -> bool:
        """创建关系

        Args:
            source_name: 源实体名称
            target_name: 目标实体名称
            relation_type: 关系类型
            properties: 关系属性

        Returns:
            是否成功
        """
        driver = self._get_driver()
        if driver is None:
            return False

        if relation_type not in RELATION_TYPES:
            logger.warning(f"未知关系类型: {relation_type}")
            return False

        query = """
        MATCH (a {name: $source}), (b {name: $target})
        MERGE (a)-[r:%s]->(b)
        ON CREATE SET r.properties = $properties, r.created_at = datetime()
        ON MATCH SET r.properties = CASE WHEN $properties <> {} THEN $properties ELSE r.properties END
        RETURN type(r) AS rel_type
        """ % relation_type

        try:
            with driver.session() as session:
                result = session.run(
                    query,
                    source=source_name,
                    target=target_name,
                    properties=properties or {},
                )
                record = result.single()
                if record:
                    logger.debug(f"关系创建: {source_name} -[{relation_type}]-> {target_name}")
                    return True
        except Exception as e:
            logger.error(f"创建关系失败: {source_name} -[{relation_type}]-> {target_name}: {e}")
        return False

    def get_entity(self, name: str) -> Optional[Dict]:
        """获取实体及其关系"""
        driver = self._get_driver()
        if driver is None:
            return None

        query = """
        MATCH (e {name: $name})
        OPTIONAL MATCH (e)-[r]->(target)
        RETURN e, collect({
            relation: type(r),
            target: target.name,
            target_type: labels(target)[0],
            properties: r.properties
        }) AS relations
        """

        try:
            with driver.session() as session:
                result = session.run(query, name=name)
                record = result.single()
                if record and record["e"]:
                    node = record["e"]
                    return {
                        "name": node.get("name"),
                        "type": list(node.labels)[0] if node.labels else "Unknown",
                        "description": node.get("description", ""),
                        "aliases": node.get("aliases", []),
                        "properties": node.get("properties", {}),
                        "knowledge_ids": node.get("knowledge_ids", []),
                        "relations": [r for r in record["relations"] if r.get("relation")],
                    }
        except Exception as e:
            logger.error(f"获取实体失败: {name}: {e}")
        return None

    def search_entities(self, query: str, limit: int = 10) -> List[Dict]:
        """模糊搜索实体"""
        driver = self._get_driver()
        if driver is None:
            return []

        cypher = """
        MATCH (e)
        WHERE e.name CONTAINS $query OR any(alias IN e.aliases WHERE alias CONTAINS $query)
        RETURN e.name AS name, labels(e)[0] AS type, e.description AS description,
               e.knowledge_ids AS knowledge_ids
        LIMIT $limit
        """

        try:
            with driver.session() as session:
                result = session.run(cypher, query=query, limit=limit)
                return [
                    {
                        "name": r["name"],
                        "type": r["type"],
                        "description": r["description"] or "",
                        "knowledge_ids": r["knowledge_ids"] or [],
                    }
                    for r in result
                ]
        except Exception as e:
            logger.error(f"搜索实体失败: {query}: {e}")
        return []

    # ===== 图谱查询 =====

    def get_neighbors(
        self, name: str, hops: int = 1, limit: int = 20
    ) -> Dict:
        """获取实体的邻居（多跳遍历）"""
        driver = self._get_driver()
        if driver is None:
            return {"center": name, "nodes": [], "edges": []}

        cypher = """
        MATCH path = (center {name: $name})-[*1..%d]-(neighbor)
        WITH center, relationships(path) AS rels, nodes(path) AS ns
        UNWIND rels AS r
        WITH DISTINCT startNode(r) AS src, endNode(r) AS tgt, type(r) AS rtype
        LIMIT $limit
        RETURN collect(DISTINCT {
            source: src.name, source_type: labels(src)[0],
            target: tgt.name, target_type: labels(tgt)[0],
            relation: rtype
        }) AS edges,
        collect(DISTINCT {name: src.name, type: labels(src)[0]}) +
        collect(DISTINCT {name: tgt.name, type: labels(tgt)[0]}) AS nodes
        """ % hops

        try:
            with driver.session() as session:
                result = session.run(cypher, name=name, limit=limit)
                record = result.single()
                if record:
                    # 去重节点
                    seen = set()
                    unique_nodes = []
                    for n in record["nodes"]:
                        if n["name"] not in seen:
                            seen.add(n["name"])
                            unique_nodes.append(n)
                    return {
                        "center": name,
                        "nodes": unique_nodes,
                        "edges": record["edges"],
                    }
        except Exception as e:
            logger.error(f"获取邻居失败: {name}: {e}")
        return {"center": name, "nodes": [], "edges": []}

    def get_community_summary(self, limit: int = 5) -> List[Dict]:
        """获取图谱社区摘要（按实体类型聚类）"""
        driver = self._get_driver()
        if driver is None:
            return []

        cypher = """
        MATCH (e)
        WITH labels(e)[0] AS entity_type, collect(e.name) AS names, count(e) AS cnt
        ORDER BY cnt DESC
        LIMIT $limit
        RETURN entity_type, names, cnt
        """

        try:
            with driver.session() as session:
                result = session.run(cypher, limit=limit)
                return [
                    {
                        "type": r["entity_type"],
                        "names": r["names"][:10],  # 最多显示 10 个
                        "count": r["cnt"],
                    }
                    for r in result
                ]
        except Exception as e:
            logger.error(f"获取社区摘要失败: {e}")
        return []

    def get_graph_stats(self) -> Dict:
        """获取图谱统计"""
        driver = self._get_driver()
        if driver is None:
            return {"nodes": 0, "edges": 0, "types": {}}

        try:
            with driver.session() as session:
                nodes = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
                edges = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
                types = {}
                for record in session.run(
                    "MATCH (n) RETURN labels(n)[0] AS type, count(n) AS cnt"
                ):
                    types[record["type"]] = record["cnt"]
                return {"nodes": nodes, "edges": edges, "types": types}
        except Exception as e:
            logger.error(f"获取图谱统计失败: {e}")
        return {"nodes": 0, "edges": 0, "types": {}}

    def find_paths(
        self, source: str, target: str, max_hops: int = 3
    ) -> List[List[Dict]]:
        """查找两个实体之间的路径"""
        driver = self._get_driver()
        if driver is None:
            return []

        cypher = """
        MATCH path = shortestPath(
            (a {name: $source})-[*1..%d]-(b {name: $target})
        )
        RETURN [n IN nodes(path) | {name: n.name, type: labels(n)[0]}] AS path_nodes,
               [r IN relationships(path) | type(r)] AS path_rels
        LIMIT 5
        """ % max_hops

        try:
            with driver.session() as session:
                result = session.run(cypher, source=source, target=target)
                paths = []
                for record in result:
                    nodes = record["path_nodes"]
                    rels = record["path_rels"]
                    path = []
                    for i, node in enumerate(nodes):
                        path.append(node)
                        if i < len(rels):
                            path.append({"relation": rels[i]})
                    paths.append(path)
                return paths
        except Exception as e:
            logger.error(f"查找路径失败: {source} -> {target}: {e}")
        return []

    def delete_entity(self, name: str) -> bool:
        """删除实体及其关系"""
        driver = self._get_driver()
        if driver is None:
            return False

        try:
            with driver.session() as session:
                session.run("MATCH (e {name: $name}) DETACH DELETE e", name=name)
                logger.debug(f"实体删除: {name}")
                return True
        except Exception as e:
            logger.error(f"删除实体失败: {name}: {e}")
        return False


# 全局单例
_neo4j_service: Optional[Neo4jService] = None


def get_neo4j_service() -> Neo4jService:
    """获取 Neo4j 服务单例"""
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService()
    return _neo4j_service
