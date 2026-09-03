BEGIN;
CREATE TEMP TABLE _pw_backup AS
  SELECT id, content, formatted_content, summary FROM knowledge
   WHERE content LIKE '%\n%' OR formatted_content LIKE '%\n%' OR formatted_content LIKE '%\r\n%' OR summary LIKE '%\n%';
SELECT count(*) AS backed_up FROM _pw_backup;
UPDATE knowledge
   SET content           = replace(replace(replace(content, '\r\n', chr(10)), '\n', chr(10)), '\r', chr(10)),
       formatted_content = replace(replace(replace(formatted_content, '\r\n', chr(10)), '\n', chr(10)), '\r', chr(10)),
       summary           = replace(replace(replace(summary, '\r\n', chr(10)), '\n', chr(10)), '\r', chr(10)),
       updated_at        = NOW()
 WHERE content LIKE '%\n%' OR formatted_content LIKE '%\n%' OR formatted_content LIKE '%\r\n%' OR summary LIKE '%\n%';
SELECT count(*) AS still_dirty FROM knowledge WHERE (content LIKE '%\n%' OR formatted_content LIKE '%\n%' OR formatted_content LIKE '%\r\n%') AND id IN (SELECT id FROM _pw_backup);
COMMIT;
