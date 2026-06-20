"""v28 step 7 — 多论文 PDF 端到端验证脚本

针对 4 篇 PDF (id=14/16/17/19) 跑 5 大验证维度:
1. vision_analyzed_at 覆盖率 (100% 期望)
2. is_publisher_image 准确度 (Elsevier/Springer/Wiley logo 应该 t)
3. vision_confidence 分布 (>= 0.85 的占比)
4. figure_no 覆盖率 (>= 0% 就行, vision 模型看不到图外 caption 是已知)
5. anchor 完整性 (有 figure_no 的图 anchor_text 必填)

用法:
  docker exec microbubble-agent-db-1 psql -U postgres -d microbubble < /tmp/v28_results.sql
  OR
  docker cp scripts/verify_v28_figures.py microbubble-agent-app-1:/tmp/
  docker exec microbubble-agent-app-1 python /tmp/verify_v28_figures.py
"""
import asyncio
import sys
from typing import Dict, List

# 同步 psycopg2 查询（更简单，验证脚本不需要 ORM）
import psycopg2
from psycopg2.extras import RealDictCursor


PUBLISHER_KEYWORDS = [
    'elsevier', 'springer', 'wiley', 'copyright', 'all rights reserved',
    'published by', 'issn', 'isbn', 'doi.org', 'sciencedirect', 'acs',
    'journal of', 'copyright ©',
]

# 4 篇 PDF 出版商期望（基于文件名/标题人工判断）
PAPER_PUBLISHER_EXPECTATIONS = {
    14: 'Elsevier or 中文期刊',  # δ-MnO2活化PMS - 中文论文
    16: 'Elsevier',  # chlorine-resistant bacteria disinfection
    17: 'Elsevier',  # micro-nano bubbles UV disinfection
    19: 'Elsevier',  # toluene oxidation by ozone micro-nanobubbles
}


def get_conn():
    import os
    # 容器内连接 (docker exec): 用 'db' 作为 host
    # 本地直连 (psql): 用 'localhost'
    is_in_container = os.path.exists('/.dockerenv')
    return psycopg2.connect(
        host='db' if is_in_container else 'localhost',
        port=5432,
        dbname='microbubble',
        user='postgres',
        password=os.environ.get('POSTGRES_PASSWORD', 'postgres123'),
    )


def fetch_images(knowledge_id: int) -> List[Dict]:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, knowledge_id, page_number, figure_no, figure_type,
                       is_core_figure, is_publisher_image, is_supporting_figure,
                       section_hint, anchor_paragraph_index, anchor_text,
                       vision_confidence, vision_model_used, vision_analyzed_at,
                       LEFT(ocr_text, 200) AS ocr_text_preview
                FROM knowledge_images
                WHERE knowledge_id = %s
                ORDER BY page_number NULLS LAST, id
            """, (knowledge_id,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def verify_publisher_accuracy(images: List[Dict]) -> Dict:
    """Check 2: is_publisher_image 准确度

    对于 is_publisher_image=true 的图，OCR 文本应该含出版商关键词。
    对于 is_publisher_image=false 的图，OCR 文本不应该含出版商关键词（除特殊情况）。
    """
    true_positives = 0  # is_publisher=true + ocr 含关键词 = 正确
    true_negatives = 0  # is_publisher=false + ocr 不含关键词 = 正确
    false_positives = 0  # is_publisher=true + ocr 不含 = 误判
    false_negatives = 0  # is_publisher=false + ocr 含 = 漏判

    for img in images:
        ocr_lower = (img.get('ocr_text_preview') or '').lower()
        is_pub = img.get('is_publisher_image') is True
        has_keyword = any(kw in ocr_lower for kw in PUBLISHER_KEYWORDS)
        if is_pub and has_keyword:
            true_positives += 1
        elif not is_pub and not has_keyword:
            true_negatives += 1
        elif is_pub and not has_keyword:
            false_positives += 1
        else:
            false_negatives += 1

    total = len(images)
    accuracy = (true_positives + true_negatives) / total if total else 0
    return {
        'total': total,
        'true_positives': true_positives,
        'true_negatives': true_negatives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'accuracy': accuracy,
    }


def verify_confidence_distribution(images: List[Dict]) -> Dict:
    """Check 3: vision_confidence 分布"""
    confs = [img['vision_confidence'] for img in images if img.get('vision_confidence') is not None]
    if not confs:
        return {'count': 0, 'min': None, 'max': None, 'mean': None, 'median': None, 'above_085': 0}
    sorted_confs = sorted(confs)
    return {
        'count': len(confs),
        'min': min(confs),
        'max': max(confs),
        'mean': sum(confs) / len(confs),
        'median': sorted_confs[len(confs) // 2],
        'above_085': sum(1 for c in confs if c >= 0.85),
        'above_080': sum(1 for c in confs if c >= 0.80),
    }


def verify_figure_no_coverage(images: List[Dict]) -> Dict:
    """Check 4: figure_no 覆盖率

    已知 vision 模型看不到图外 caption，PDF id=19 实测仅 20%。
    但应该至少能识别 1 张（真实正文核心图）。
    """
    with_no = sum(1 for img in images if img.get('figure_no'))
    return {
        'total': len(images),
        'with_figure_no': with_no,
        'coverage': with_no / len(images) if images else 0,
    }


def verify_anchor_integrity(images: List[Dict]) -> Dict:
    """Check 5: anchor 完整性

    有 figure_no 的图，anchor_paragraph_index + anchor_text 必填
    """
    issues = []
    for img in images:
        if img.get('figure_no'):
            if img.get('anchor_paragraph_index') is None:
                issues.append(f"id={img['id']} 有 figure_no 但 anchor_paragraph_index=null")
            if not img.get('anchor_text'):
                issues.append(f"id={img['id']} 有 figure_no 但 anchor_text=null")
    return {
        'with_figure_no': sum(1 for img in images if img.get('figure_no')),
        'issues': issues,
    }


def verify_coverage(images: List[Dict]) -> Dict:
    """Check 1: vision_analyzed_at 覆盖率（必须 100%）"""
    total = len(images)
    analyzed = sum(1 for img in images if img.get('vision_analyzed_at') is not None)
    return {
        'total': total,
        'analyzed': analyzed,
        'coverage': analyzed / total if total else 0,
    }


def verify_paper(knowledge_id: int) -> Dict:
    images = fetch_images(knowledge_id)
    return {
        'knowledge_id': knowledge_id,
        'expected_publisher': PAPER_PUBLISHER_EXPECTATIONS.get(knowledge_id, 'unknown'),
        'image_count': len(images),
        'check1_coverage': verify_coverage(images),
        'check2_publisher': verify_publisher_accuracy(images),
        'check3_confidence': verify_confidence_distribution(images),
        'check4_figure_no': verify_figure_no_coverage(images),
        'check5_anchor': verify_anchor_integrity(images),
        'images': images,
    }


def format_report(result: Dict) -> str:
    k = result['knowledge_id']
    pub = result['expected_publisher']
    n = result['image_count']
    lines = []
    lines.append('=' * 70)
    lines.append(f'📄 Paper id={k} ({pub}) — {n} 张图')
    lines.append('=' * 70)

    # Check 1
    c1 = result['check1_coverage']
    cov1 = c1['coverage']
    icon1 = '✅' if cov1 == 1.0 else ('⚠️' if cov1 >= 0.5 else '❌')
    lines.append(f'\n[1] vision_analyzed_at 覆盖率: {c1["analyzed"]}/{c1["total"]} ({cov1*100:.0f}%) {icon1}')
    lines.append(f'    期望: 100% (所有图都必须被 vision 分析过)')

    # Check 2
    c2 = result['check2_publisher']
    icon2 = '✅' if c2['accuracy'] == 1.0 else ('⚠️' if c2['accuracy'] >= 0.7 else '❌')
    lines.append(f'\n[2] is_publisher_image 准确度: {c2["accuracy"]*100:.0f}% {icon2}')
    lines.append(f'    TP={c2["true_positives"]} TN={c2["true_negatives"]} '
                 f'FP={c2["false_positives"]} FN={c2["false_negatives"]}')
    if c2['false_positives'] or c2['false_negatives']:
        lines.append(f'    ⚠️ 有误判/漏判，需人工 review')

    # Check 3
    c3 = result['check3_confidence']
    if c3['count']:
        icon3 = '✅' if c3['mean'] >= 0.85 else ('⚠️' if c3['mean'] >= 0.7 else '❌')
        lines.append(f'\n[3] vision_confidence 分布 {icon3}')
        lines.append(f'    count={c3["count"]} min={c3["min"]:.2f} max={c3["max"]:.2f} '
                     f'mean={c3["mean"]:.2f} median={c3["median"]:.2f}')
        lines.append(f'    ≥0.85 (高置信度): {c3["above_085"]} 张 ({c3["above_085"]/c3["count"]*100:.0f}%)')
        lines.append(f'    ≥0.80 (可用): {c3["above_080"]} 张 ({c3["above_080"]/c3["count"]*100:.0f}%)')

    # Check 4
    c4 = result['check4_figure_no']
    icon4 = '✅' if c4['coverage'] >= 0.15 else ('⚠️' if c4['coverage'] >= 0.05 else '❌')
    lines.append(f'\n[4] figure_no 覆盖率: {c4["with_figure_no"]}/{c4["total"]} ({c4["coverage"]*100:.0f}%) {icon4}')
    lines.append(f'    已知局限: vision 模型看不到图外 caption, 20% 已不错')

    # Check 5
    c5 = result['check5_anchor']
    if c5['with_figure_no']:
        icon5 = '✅' if not c5['issues'] else '❌'
        lines.append(f'\n[5] anchor 完整性 {icon5}')
        lines.append(f'    有 figure_no 的图: {c5["with_figure_no"]}')
        if c5['issues']:
            for issue in c5['issues'][:5]:
                lines.append(f'    ⚠️ {issue}')

    # 详细列出所有图
    lines.append(f'\n📋 详细图清单:')
    for img in result['images']:
        conf = img.get('vision_confidence')
        conf_str = f'{conf:.2f}' if conf is not None else 'null'
        fn = img.get('figure_no') or '—'
        ft = img.get('figure_type') or '—'
        is_pub = '🅿️' if img.get('is_publisher_image') else ('🎯' if img.get('is_core_figure') else '📦')
        anchor = f'P{img["anchor_paragraph_index"]}' if img.get('anchor_paragraph_index') is not None else '—'
        lines.append(f'  [{img["page_number"] or "?":>2}] id={img["id"]:>3} {is_pub} '
                     f'{fn:<8} {ft:<22} conf={conf_str} anchor={anchor}')
        sh = img.get('section_hint')
        if sh:
            lines.append(f'        section: {sh[:60]}')

    return '\n'.join(lines)


def main():
    print('🔍 v28 step 7 — 多论文 PDF 端到端验证')
    print()
    overall_pass = True
    for kid in [14, 16, 17, 19]:
        result = verify_paper(kid)
        print(format_report(result))
        print()
        # Overall pass: check 1 + check 2 必须过
        if result['check1_coverage']['coverage'] < 1.0:
            overall_pass = False
        if result['check2_publisher']['accuracy'] < 0.7:
            overall_pass = False

    print('=' * 70)
    if overall_pass:
        print('✅ v28 集成核心不变量 PASS（覆盖率 100% + publisher 准确度 ≥70%）')
        return 0
    else:
        print('❌ v28 集成核心不变量 FAIL（覆盖率或 publisher 准确度不达标）')
        return 1


if __name__ == '__main__':
    sys.exit(main())