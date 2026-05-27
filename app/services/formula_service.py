"""公式服务 — 公式提取、存储、安全计算"""

import math
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_

from app.models.knowledge_formula import KnowledgeFormula
from app.models.formula_category import FormulaCategory

logger = logging.getLogger("microbubble.formula")

SAFE_MATH = {
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "pow": pow, "abs": abs, "min": min, "max": max,
    "pi": math.pi, "e": math.e,
}


class FormulaService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_formulas(self, domain: Optional[str] = None,
                            knowledge_id: Optional[int] = None,
                            keyword: Optional[str] = None,
                            category_id: Optional[int] = None,
                            source_type: Optional[str] = None,
                            page: int = 1, page_size: int = 20) -> dict:
        filters = [KnowledgeFormula.is_active == True]
        if domain:
            filters.append(KnowledgeFormula.domain == domain)
        if knowledge_id:
            filters.append(KnowledgeFormula.knowledge_id == knowledge_id)
        if category_id:
            # 包含子分类
            cat_ids = await self._get_category_ids(category_id)
            filters.append(KnowledgeFormula.category_id.in_(cat_ids))
        if source_type:
            filters.append(KnowledgeFormula.source_type == source_type)
        if keyword:
            filters.append(
                KnowledgeFormula.name.ilike(f"%{keyword}%") |
                KnowledgeFormula.formula_latex.ilike(f"%{keyword}%")
            )

        base = select(KnowledgeFormula)
        count_base = select(func.count()).select_from(KnowledgeFormula)
        if filters:
            base = base.where(*filters)
            count_base = count_base.where(*filters)

        total = (await self.db.execute(count_base)).scalar() or 0
        query = base.order_by(desc(KnowledgeFormula.confidence))
        query = query.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        return {
            "items": [self._formula_to_dict(f) for f in rows],
            "total": total, "page": page, "page_size": page_size,
        }

    async def calculate(self, formula_id: int, variables: dict) -> dict:
        result = await self.db.execute(
            select(KnowledgeFormula).where(KnowledgeFormula.id == formula_id)
        )
        formula = result.scalar_one_or_none()
        if not formula:
            return {"error": "公式不存在"}

        expected_vars = formula.variables or {}
        missing = [k for k in expected_vars
                   if k not in variables and expected_vars[k].get("required", True)]
        if missing:
            return {
                "error": f"缺少必要变量: {', '.join(missing)}",
                "expected_variables": expected_vars,
            }

        try:
            expr = formula.formula_python
            for var_name, var_val in variables.items():
                expr = expr.replace(var_name, str(var_val))

            result_value = self._safe_eval(expr)

            steps = []
            for var_name, var_val in variables.items():
                meta = expected_vars.get(var_name, {})
                steps.append({
                    "variable": var_name, "value": var_val,
                    "unit": meta.get("unit", ""),
                    "description": meta.get("description", ""),
                })
            steps.append({
                "variable": "result", "value": result_value,
                "unit": formula.result_unit or "",
                "description": formula.name,
            })

            return {
                "value": round(result_value, 6),
                "unit": formula.result_unit or "",
                "steps": steps,
                "formula_name": formula.name,
                "formula_latex": formula.formula_latex,
            }
        except Exception as e:
            logger.warning(f"公式计算失败(formula_id={formula_id}): {e}")
            return {"error": f"计算失败: {str(e)}"}

    def _safe_eval(self, expression: str) -> float:
        allowed = {"__builtins__": {}}
        allowed.update(SAFE_MATH)
        return float(eval(expression, allowed, {}))

    async def get_domains(self) -> List[dict]:
        result = await self.db.execute(
            select(
                KnowledgeFormula.domain,
                func.count(KnowledgeFormula.id).label("cnt"),
            ).where(
                KnowledgeFormula.domain.isnot(None),
                KnowledgeFormula.domain != "",
            ).group_by(KnowledgeFormula.domain).order_by(desc("cnt"))
        )
        return [{"name": row.domain, "count": row.cnt} for row in result.all()]

    # ── Category tree ──

    async def get_categories(self) -> list:
        """返回分类树（含公式计数）"""
        # 获取所有分类
        result = await self.db.execute(
            select(FormulaCategory).order_by(FormulaCategory.sort_order)
        )
        all_cats = result.scalars().all()

        if not all_cats:
            return []

        # 批量查询公式计数
        cat_ids = [c.id for c in all_cats]
        count_result = await self.db.execute(
            select(
                KnowledgeFormula.category_id,
                func.count(KnowledgeFormula.id).label("cnt"),
            ).where(
                KnowledgeFormula.category_id.in_(cat_ids),
                KnowledgeFormula.is_active == True,
            ).group_by(KnowledgeFormula.category_id)
        )
        count_map = {row.category_id: row.cnt for row in count_result.all()}

        # 构建树
        cat_map = {}
        for c in all_cats:
            cat_map[c.id] = {
                "id": c.id,
                "name": c.name,
                "display_name": c.display_name,
                "description": c.description,
                "icon": c.icon,
                "parent_id": c.parent_id,
                "sort_order": c.sort_order,
                "children": [],
                "formula_count": count_map.get(c.id, 0),
            }

        tree = []
        for item in cat_map.values():
            if item["parent_id"] is None:
                tree.append(item)
            else:
                parent = cat_map.get(item["parent_id"])
                if parent:
                    parent["children"].append(item)

        # 递归累加公式计数到父分类
        def _accumulate(node):
            for child in node["children"]:
                _accumulate(child)
                node["formula_count"] += child["formula_count"]

        for root in tree:
            _accumulate(root)

        return tree

    async def _get_category_ids(self, category_id: int) -> List[int]:
        """获取分类及其所有子分类的 ID 列表"""
        result = await self.db.execute(
            select(FormulaCategory.id).where(
                or_(
                    FormulaCategory.id == category_id,
                    FormulaCategory.parent_id == category_id,
                )
            )
        )
        return [row[0] for row in result.all()]

    # ── Domain-to-category mapping for LLM extraction ──

    # domain 字符串 -> category name 的映射表
    DOMAIN_MAP = {
        "cod": "cod", "化学需氧量": "cod",
        "bod": "bod", "生化需氧量": "bod",
        "do": "do", "溶解氧": "do",
        "去除率": "treatment", "吸附": "treatment", "langmuir": "treatment",
        "臭氧": "ozonation", "ct值": "ozonation",
        "消毒": "disinfection",
        "一级反应": "reaction_rate", "二级反应": "reaction_rate",
        "动力学": "reaction_rate",
        "arrhenius": "temperature_effect",
        "雷诺数": "flow_regime", "re": "flow_regime",
        "韦伯数": "flow_regime", "we": "flow_regime",
        "空化": "pressure_loss", "水头损失": "pressure_loss", "darcy": "pressure_loss",
        "young-laplace": "bubble_generation", "laplace": "bubble_generation",
        "表面张力": "bubble_generation",
        "epstein": "bubble_stability", "溶解": "bubble_stability",
        "sauter": "bubble_size", "粒径": "bubble_size",
        "stokes": "bubble_rise", "上升速度": "bubble_rise",
        "亨利": "gas_dissolution", "传质": "gas_dissolution",
        "sotr": "oxygen_transfer", "sae": "oxygen_transfer",
        "曝气": "oxygen_transfer", "kla": "oxygen_transfer",
        "标准差": "descriptive_stats", "rsd": "descriptive_stats",
        "检出限": "calibration", "lod": "calibration",
        "定量限": "calibration", "loq": "calibration",
        "标准曲线": "calibration",
        "bubble": "bubble_dynamics", "气泡": "bubble_dynamics",
        "传质过程": "mass_transfer",
        "水处理": "water_quality", "水质": "water_quality",
        "化学动力学": "chemical_kinetics",
        "流体": "fluid_mechanics",
        "统计": "statistical_analysis",
    }

    # 缓存分类 name -> id 的映射（惰性加载）
    _category_name_cache: dict = None

    async def _ensure_category_cache(self):
        if self._category_name_cache is not None:
            return
        result = await self.db.execute(
            select(FormulaCategory.id, FormulaCategory.name)
        )
        self._category_name_cache = {row.name: row.id for row in result.all()}

    async def _resolve_category_name(self, domain: str) -> Optional[int]:
        """模糊匹配 domain 字符串到分类 ID"""
        if not domain:
            return None
        domain_lower = domain.lower()
        for key, cat_name in self.DOMAIN_MAP.items():
            if key in domain_lower:
                await self._ensure_category_cache()
                return self._category_name_cache.get(cat_name)
        return None

    # ── Save from LLM extraction ──

    async def save_formulas_from_analysis(self, knowledge_id: int, formulas: List[dict]):
        """保存 LLM 分析提取的公式"""
        for f in formulas:
            domain = f.get("domain", "")
            category_id = await self._resolve_category_name(domain)

            formula = KnowledgeFormula(
                knowledge_id=knowledge_id,
                name=f.get("name", ""),
                formula_latex=f.get("formula", ""),
                formula_python=self._latex_to_python(f.get("formula", "")),
                variables=f.get("variables", {}),
                result_unit=f.get("result_unit", ""),
                conditions=f.get("conditions", ""),
                domain=domain,
                confidence=f.get("confidence", 0.5),
                source_type="extracted",
                category_id=category_id,
                is_active=True,
            )
            self.db.add(formula)
        await self.db.commit()
        logger.info(f"文档 {knowledge_id}: 保存 {len(formulas)} 条公式")

    def _latex_to_python(self, latex: str) -> str:
        if not latex:
            return "0"
        s = latex.replace("×", "*").replace("÷", "/").replace("−", "-")
        s = s.replace("π", "pi").replace("α", "alpha").replace("η", "eta").replace("ρ", "rho")
        s = s.replace("·", "*")
        # Superscript digits
        s = s.replace("²", "**2").replace("³", "**3")
        # Greek letters commonly used in formulas
        s = s.replace("σ", "sigma").replace("Σ", "sum").replace("μ", "mu")
        s = s.replace("θ", "theta").replace("δ", "delta").replace("λ", "lambda")
        if "=" in s:
            s = s.split("=", 1)[1].strip()
        return s

    @staticmethod
    def _formula_to_dict(f: KnowledgeFormula) -> dict:
        return {
            "id": f.id, "knowledge_id": f.knowledge_id,
            "name": f.name, "formula_latex": f.formula_latex,
            "variables": f.variables or {},
            "result_unit": f.result_unit,
            "conditions": f.conditions, "domain": f.domain,
            "confidence": f.confidence,
            "source_type": f.source_type,
            "category_id": f.category_id,
            "category_name": f.category.display_name if f.category else None,
            "is_active": f.is_active,
            "created_at": str(f.created_at) if f.created_at else None,
        }
