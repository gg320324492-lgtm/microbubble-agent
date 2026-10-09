"""knowledge_images.ocr_status 拆出 done_no_text

**Revision ID**: 143_ocr_status_done_no_text
**Revises**: 142_recording_presence_at
**Create Date**: 2026-10-09

为什么
----
``ocr_status='done'`` 同时表示两种**语义相反**的含义：

- 「OCR 成功**且**图里有文字」
- 「OCR 成功**但**图里没抽到文字」

排查时这两者完全相反（一个是可用数据，一个是待办/可疑数据），却共用一个
状态值 —— 类 20.220「状态字段会撒谎」的教科书案例。存量 3315 行落在这个
含混区间（另有 5 行已由 ``scripts/rerun_single_image_ocr.py`` 单独处理，
合计 3320）。

⚠️ **``done_no_text`` 描述的是「这一次 OCR 调用」，不是对图片内容的断言。**
2026-10-09 实测 id=6368（本项目核心装置标注图，图上明确有「出水管/进水管/
取样口/O₂MNBs/O₃CBs…」十余处中文标注）此前正是 ``done`` + 空文本，而
``classify_and_extract`` 的多任务 JSON prompt 会随机把 ``text`` 字段填
``null``（同图同 prompt 5 连测，0/5 有字；换单一「提取所有文字」的
``extract_text`` 则稳定拿到完整标注）。

所以**不要**把 ``done_no_text`` 当成「已确认无字、免检」。它只是把
「跑完了但返回空」这个事实从「跑成了有字」里摘出来，让两种行可分别统计、
分别重跑。是否真无字仍需按几何排除装饰图后逐张看。

安全性
------
- 列是 ``character varying(20)``，``done_no_text`` 12 字符，放得下。
- 该列**无 CHECK 约束**（2026-10-09 实测 ``pg_constraint`` 只有 PK + FK），
  所以本迁移不需要先放宽约束。
- 只 UPDATE，不 INSERT / DELETE / TRUNCATE；不动 ``ocr_text``、不动
  ``knowledge_extractions``、不动 ``knowledge.content``。
- 反向迁移 ``downgrade`` 把 ``done_no_text`` 并回 ``done``，恢复原状。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# 与写入路径同源：multimodal_extraction_service._save_extractions
DONE_NO_TEXT = "done_no_text"

revision: str = "143_ocr_status_done_no_text"
down_revision: Union[str, None] = "142_recording_presence_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 只有「跑完且成功」且「文本为空」的行才改；pending/failed/partial/skipped 一律不动
SRC = "ocr_status = 'done' AND (ocr_text IS NULL OR btrim(ocr_text) = '')"


def upgrade():
    op.execute(
        sa.text(
            f"UPDATE knowledge_images SET ocr_status = '{DONE_NO_TEXT}' WHERE {SRC}"
        )
    )


def downgrade():
    op.execute(
        sa.text(
            f"UPDATE knowledge_images SET ocr_status = 'done' WHERE ocr_status = '{DONE_NO_TEXT}'"
        )
    )
