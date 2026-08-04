"""回归测试：prompts.py 禁止元数据后缀 (W100 +58)

防止 LLM 在回答末尾追加"数据来源: query_xxx 工具返回..."这种干扰正式回复的元数据段。
- 主拍拦截 +001b prompt 教程反例对比 (line 418) 后, LLM 学会自动追加 meta 后缀
- 治本方案: 在 get_system_prompt() 末尾加硬规则, 明确禁止
- 兜底方案 (前端): useChatStream text_delta 后处理过滤
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

from app.agent.prompts import get_system_prompt


class TestMetaCleanRule:
    """W100 +58 禁止元数据后缀 — 关键句永久保留"""

    def _prompt(self) -> str:
        return get_system_prompt()

    def test_meta_clean_section_present(self):
        """W100 +58 段必须存在, 关键禁用语全部命中"""
        p = self._prompt()
        assert "禁止元数据后缀" in p, "W100 +58 禁止元数据后缀 section must exist"
        assert "W100 +58" in p, "W100 +58 anchor must be referenced"

    def test_data_source_meta_forbidden(self):
        """「数据来源: query_xxx 工具返回的 XXX」明确禁止"""
        p = self._prompt()
        # 锁定 W100 +58 section
        section_start = p.find("## 禁止元数据后缀")
        assert section_start != -1
        section_end = p.find("\n## ", section_start + 1)
        if section_end == -1:
            section_end = len(p)
        section = p[section_start:section_end]
        # 关键禁用语 (反例)
        assert "数据来源" in section, "数据来源 meta 后缀必须明确禁止"
        assert "query_members" in section, "query_members tool 名必须明确禁止"
        # 正向禁用
        assert "不要" in section, "必须用'不要'作为禁止语义"

    def test_tool_name_listing_forbidden(self):
        """tool 名 (search_knowledge / query_tasks / get_member_profile) 不可在引用列表出现"""
        p = self._prompt()
        section_start = p.find("## 禁止元数据后缀")
        assert section_start != -1
        section_end = p.find("\n## ", section_start + 1)
        if section_end == -1:
            section_end = len(p)
        section = p[section_start:section_end]
        # 关键 tool 名 (不应作为引用列表条目出现)
        for tool_name in ("search_knowledge", "query_members", "query_all_member_tasks", "query_tasks"):
            assert tool_name in section, f"{tool_name} must be explicitly named in forbidden list"
