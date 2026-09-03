-- 2026-09-03 知识文本反斜杠残渣清理 (微信问答导入时代的 \r\n\ 转义残留)
-- 上轮已把字面量 \r\n / \n / \r 还原为真实换行, 本轮清除残留的孤立反斜杠
BEGIN;
UPDATE knowledge
   SET content           = replace(content, chr(92), ''),
       formatted_content = replace(formatted_content, chr(92), ''),
       summary           = replace(summary, chr(92), ''),
       search_text       = replace(search_text, chr(92), ''),
       updated_at        = NOW()
 WHERE position(chr(92) IN content) > 0
    OR position(chr(92) IN formatted_content) > 0
    OR position(chr(92) IN summary) > 0
    OR position(chr(92) IN search_text) > 0;
SELECT count(*) AS rows_with_backslash_after FROM knowledge
 WHERE position(chr(92) IN content) > 0 OR position(chr(92) IN formatted_content) > 0;
COMMIT;
