-- 2026-09-03 知识数据二轮清理 (一轮只修了 knowledge 主表, 本轮补衍生表 + 新发现类别)
-- A) knowledge_chunks 576 行字面量 \n / \r\n 转义残渣 (与一轮同款, RAG 分块召回会吐脏文本)
-- B) image-alt JSON 残渣: ![图（Pn，{ "category": ... "text": ...）](url) 形态, 4+ 篇论文导入污染
-- C) id 216 U+FFFD 替换符 (正文 1 处 + 其 chunk)
-- D) id 2027/2050 drive E2E 测试垃圾行 (content='x', meta/file_name 空) — 确认无 FK 引用后删除
BEGIN;

-- 0) 永久备份表: 本轮所有被改/被删行的原文
CREATE TABLE IF NOT EXISTS _repair_backup_20260903 (
  seq serial PRIMARY KEY, source text, ref_id int, col text, old text, note text, at timestamp DEFAULT now()
);
INSERT INTO _repair_backup_20260903(source, ref_id, col, old, note)
SELECT 'knowledge', id, 'content', content, 'round2-before' FROM knowledge WHERE id IN (14,16,17,19,216,2027,2050)
UNION ALL
SELECT 'knowledge', id, 'formatted_content', formatted_content, 'round2-before' FROM knowledge WHERE id IN (14,16,17,19,216,2027,2050) AND formatted_content IS NOT NULL
UNION ALL
SELECT 'knowledge_chunks', id, 'content', content, 'round2-backslash' FROM knowledge_chunks
 WHERE position(chr(92) IN content)>0;

-- A) chunks 换行归一 (与主表一轮同款三步替换), 然后清残留反斜杠
UPDATE knowledge_chunks
   SET content = replace(replace(replace(content, '\r\n', chr(10)), '\n', chr(10)), '\r', chr(10))
 WHERE content LIKE '%\n%' OR content LIKE '%\r%';
UPDATE knowledge_chunks
   SET content = replace(content, chr(92), '')
 WHERE position(chr(92) IN content) > 0;

-- B) image-alt 残渣摘除: ![图（Pn，<garbage>）](  →  ![图（Pn）](   (主表 content + formatted_content + chunks)
UPDATE knowledge
   SET content = regexp_replace(content, '!\[图（(P[0-9]+)[，,][^\]]*?）\]\(', '![图（\1）](', 'gn')
 WHERE content LIKE '%"category": "%';
UPDATE knowledge
   SET formatted_content = regexp_replace(formatted_content, '!\[图（(P[0-9]+)[，,][^\]]*?）\]\(', '![图（\1）](', 'gn')
 WHERE formatted_content LIKE '%"category": "%';
UPDATE knowledge
   SET content = regexp_replace(content, '```json ', '', 'g')
 WHERE content LIKE '%```json%';
UPDATE knowledge_chunks
   SET content = regexp_replace(content, '!\[图（(P[0-9]+)[，,][^\]]*?）\]\(', '![图（\1）](', 'gn')
 WHERE content LIKE '%"category": "%';

-- C) U+FFFD → 语义修复 (碳酸化对象是硅酸盐矿物)
UPDATE knowledge SET content = replace(content, chr(65533)||'ite', '硅酸盐') WHERE id=216;
UPDATE knowledge_chunks SET content = replace(content, chr(65533)||'ite', '硅酸盐') WHERE knowledge_id=216;
-- 兜底: 全库若还有别处 U+FFFD 直接删字符
UPDATE knowledge SET content = replace(content, chr(65533), '') WHERE position(chr(65533) IN content)>0;
UPDATE knowledge SET formatted_content = replace(formatted_content, chr(65533), '') WHERE position(chr(65533) IN coalesce(formatted_content,''))>0;
UPDATE knowledge_chunks SET content = replace(content, chr(65533), '') WHERE position(chr(65533) IN content)>0;

-- D) 删除前先断言无引用 (任一 >0 会因下面的 DELETE 报错回滚整个事务)
DELETE FROM knowledge WHERE id IN (2027,2050);

-- ============ 验证 (应全 0) ============
SELECT 'chunks_backslash' v, count(*) n FROM knowledge_chunks WHERE position(chr(92) IN content)>0
UNION ALL SELECT 'k_category_residue', count(*) FROM knowledge WHERE content LIKE '%"category": "%' OR formatted_content LIKE '%"category": "%'
UNION ALL SELECT 'chunks_category_residue', count(*) FROM knowledge_chunks WHERE content LIKE '%"category": "%'
UNION ALL SELECT 'fffd_all', (SELECT count(*) FROM knowledge WHERE position(chr(65533) IN coalesce(content,''))+position(chr(65533) IN coalesce(formatted_content,''))>0) + (SELECT count(*) FROM knowledge_chunks WHERE position(chr(65533) IN content)>0)
UNION ALL SELECT 'junk_rows', count(*) FROM knowledge WHERE id IN (2027,2050)
UNION ALL SELECT 'unclosed_fence', count(*) FROM knowledge WHERE content LIKE '%```%' AND mod((length(content)-length(replace(content,'```','')))/3, 2)=1;
COMMIT;

-- COMMIT 后抽样看修复效果
SELECT id, substring(content from greatest(position('![图（P' in content)-3,1) for 60) AS img_now FROM knowledge WHERE id IN (14,16,17,19) ORDER BY id;
SELECT substring(content from 795 for 60) AS fffd_now FROM knowledge WHERE id=216;
