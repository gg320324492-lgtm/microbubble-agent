"""A/B test: text2vec 768d vs Qwen3 1024d 检索对比"""
import os, asyncio, logging
logging.getLogger('sqlalchemy.engine').disabled = True
import sys
sys.path.insert(0, '/app')

from app.core.database import async_session
from app.services.embedding_service import _get_model, _is_qwen3
from sqlalchemy import text


async def search_knowledge(query, use_v2=False, top_k=5):
    model = _get_model()
    if _is_qwen3(model):
        arr = model.encode([query], for_query=True)
        qvec = arr[0].tolist()
    else:
        qvec = model.encode(query, normalize_embeddings=True).tolist()
    col = 'embedding_v2' if use_v2 else 'embedding'
    qvec_str = '[' + ','.join(f'{x:.6f}' for x in qvec) + ']'
    sql = f"SELECT id, title, 1 - ({col} <=> '{qvec_str}'::vector) AS sim FROM knowledge WHERE {col} IS NOT NULL ORDER BY {col} <=> '{qvec_str}'::vector LIMIT {top_k}"
    async with async_session() as db:
        result = await db.execute(text(sql))
        return [(row[0], (row[1] or '')[:40], float(row[2])) for row in result.fetchall()]


async def main():
    queries = [
        '微纳米气泡在水处理',
        'zeta 电位影响',
        'PMS 活化降解甲苯',
        '羟基自由基氧化',
        '气泡尺寸测量',
    ]
    print(f'模型: {_get_model().__class__.__name__}', flush=True)
    print(flush=True)
    for q in queries:
        r_old = await search_knowledge(q, use_v2=False)
        r_new = await search_knowledge(q, use_v2=True)
        old_ids = [r[0] for r in r_old]
        new_ids = [r[0] for r in r_new]
        overlap = len(set(old_ids) & set(new_ids))
        top1_old = f'id={old_ids[0]} sim={round(r_old[0][2],3)}' if old_ids else 'empty'
        top1_new = f'id={new_ids[0]} sim={round(r_new[0][2],3)}' if new_ids else 'empty'
        print(f'Q: {q}', flush=True)
        print(f'  text2vec 768d: {top1_old} ids={old_ids}', flush=True)
        print(f'  Qwen3 1024d:   {top1_new} ids={new_ids}', flush=True)
        print(f'  overlap: {overlap}/5', flush=True)


asyncio.run(main())
