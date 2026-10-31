-- Phase 0 (声纹换代) 安全网 —— 生产 members 的**只读快照**
--
-- 用途: Phase 0 只做离线重建与评测, **不修改 members**; 这张表是「将来若主指挥
--       拍板写库」时的回滚点 (类 20.220: 写库前先留可回读的前态)。
--
-- 命名带判据版本 (类 20.249 ⑧): 表名里写清「这是 enrollment 重建之前」,
-- 否则跑过多次不同口径的重建后分不清是哪一次的前态。
--
-- 幂等: 可重复执行 (已存在的行不会重复插入)。
-- 用法:
--   docker exec -i microbubble-agent-db-1 psql -U postgres -d microbubble \
--     -v ON_ERROR_STOP=1 < scripts/voiceprint/phase0_backup_snapshot.sql

CREATE TABLE IF NOT EXISTS members_backup_pre_enrollment_rebuild AS
    SELECT * FROM members WITH NO DATA;

INSERT INTO members_backup_pre_enrollment_rebuild
    SELECT * FROM members m
    WHERE NOT EXISTS (
        SELECT 1 FROM members_backup_pre_enrollment_rebuild b WHERE b.id = m.id
    );

SELECT count(*) AS backup_rows,
       (SELECT count(*) FROM members) AS live_rows
FROM members_backup_pre_enrollment_rebuild;
