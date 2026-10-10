-- 2026-09-30 清理前快照（回滚用）
-- 待删：ZB 演练残留（根目录形态）+ 各轮探针文件
SELECT id, storage_mode, folder_id, visibility, file_name, created_by, created_at
  FROM knowledge
 WHERE id IN (2829,2830,2833,2835,2837,2839,2841,2842,2845,2846,2849,2853,2856)
 ORDER BY id;
-- 保留（现场实证，勿删）：2863/2864 = v1.3.2 首次真实运行落在 backups/CI_冒烟/
SELECT id, file_name, folder_id FROM knowledge WHERE id IN (2863,2864);
-- 待停用：测试账号
SELECT id, username, name, is_active FROM members WHERE id = 1459;
