-- 149_meetings_pk_fk 的独立回滚 (应急用; 常规回滚走 `alembic downgrade -1`)
-- 回到 149 之前的状态: meetings 无主键、三表无外键、裁决表无 meeting_id 索引。
-- 全部带存在性守卫 (IF EXISTS) ⇒ 可重复执行。
-- ⚠️ 执行前确认没有迁移链停在 149 (alembic current 应为 148_cluster_adjudications)。

DROP INDEX IF EXISTS meeting_speaker_adjudications.idx_msa_meeting_start;
DROP INDEX IF EXISTS meeting_speaker_adjudications.ix_meeting_speaker_adjudications_meeting_id;

ALTER TABLE meeting_cluster_adjudications DROP CONSTRAINT IF EXISTS fk_mca_meeting;
ALTER TABLE meeting_speaker_adjudications DROP CONSTRAINT IF EXISTS fk_msa_meeting;
ALTER TABLE meeting_participants DROP CONSTRAINT IF EXISTS fk_mpt_meeting;

ALTER TABLE meetings DROP CONSTRAINT IF EXISTS meetings_pkey;

-- 若 alembic_version 停在 149, 需先降版本号 (在 alembic downgrade -1 失败时才手工做):
-- UPDATE alembic_version SET version_num = '148_cluster_adjudications' WHERE version_num = '149_meetings_pk_fk';
