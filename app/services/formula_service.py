"""公式服务 — 公式提取、存储、安全计算"""

import math
import logging
import asyncio
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.knowledge_formula import KnowledgeFormula

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
                            page: int = 1, page_size: int = 20) -> dict:
        filters = []
        if domain:
            filters.append(KnowledgeFormula.domain == domain)
        if knowledge_id:
            filters.append(KnowledgeFormula.knowledge_id == knowledge_id)
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

    async def save_formulas_from_analysis(self, knowledge_id: int, formulas: List[dict]):
        """保存 LLM 分析提取的公式"""
        for f in formulas:
            formula = KnowledgeFormula(
                knowledge_id=knowledge_id,
                name=f.get("name", ""),
                formula_latex=f.get("formula", ""),
                formula_python=self._latex_to_python(f.get("formula", "")),
                variables=f.get("variables", {}),
                result_unit=f.get("result_unit", ""),
                conditions=f.get("conditions", ""),
                domain=f.get("domain"),
                confidence=f.get("confidence", 0.5),
            )
            self.db.add(formula)
        await self.db.commit()
        logger.info(f"文档 {knowledge_id}: 保存 {len(formulas)} 条公式")

    def _latex_to_python(self, latex: str) -> str:
        s = latex.replace("×", "*").replace("÷", "/").replace("−", "-")
        s = s.replace("π", "pi").replace("α", "alpha").replace("η", "eta").replace("ρ", "rho")
        s = s.replace("·", "*")
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
            "created_at": str(f.created_at) if f.created_at else None,
        }
