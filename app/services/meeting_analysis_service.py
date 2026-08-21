"""会议 AI 分析服务

提供发言者检测、转录解析、结构化分析和发言人统计功能。

P0 (2026-08-04): 全链路统一走 backend-aware `LLMClient`, 不再直接持有
anthropic 客户端. 老代码里的 `get_anthropic_client()` 在 `LLM_BACKEND=openai_compat`
或 `ollama` 时仍会直连 anthropic, 会复现会议 242 的 401 invalid_key 假成功 bug。
本类改为按需 lazy 注入 LLMClient, 调用方仍可替换 (e.g. test 注入 mock)。
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.llm import (
    LLMClient,
    extract_text_from_response,
    parse_llm_json,
)
from app.services.name_aliases import clean_text as clean_person_names

logger = logging.getLogger("microbubble.meeting_analysis")

SPEAKER_DETECTION_PROMPT = """你是一个会议分析助手。请分析以下会议转录文本，识别出不同发言者。

转录文本：
{transcript_text}

分析要求：
1. 识别所有不同的发言者标识（如 "王老师"、"Speaker A"、"张三" 等）
2. 从上下文推测每位发言者的姓名或角色
3. 统计每位发言者的发言次数
4. 提取每位发言者的 1-2 句代表性发言

注意：
- 发言者标识可能以【】包裹，也可能是纯文本中的"XXX说："、"XXX："格式
- 如果没有明确发言者标识，标记为 "未区分发言者"
- 如果无法确定中文名，suggested_name 设为 null
- 中文输出

请输出严格 JSON 格式：
{{
  "detected_speakers": [
    {{
      "original_label": "王老师",
      "suggested_name": null,
      "turn_count": 12,
      "sample_lines": ["今天我们讨论气泡生成效率的实验方案"]
    }}
  ],
  "total_turns": 30,
  "confidence": "high",
  "format_type": "marked"
}}"""

ANALYSIS_PROMPT = """你是一个专业的会议纪要生成助手。请分析以下会议转录内容。

必须按课题组标准会议纪要格式输出，风格参考“2026.5.28 例行例会”：
- 摘要要有背景、讨论过程、关键人物观点、结论和后续方向，不能只写一两句短摘要。
- 讨论要点必须有信息密度，每条都能独立说明一个观点、事实、问题、实验观察、软件模块或硬件要求。
- 决议事项必须写清楚“谁决定/共识 + 做什么 + 用于什么目的”。
- 所有 key_points 和 decisions 必须使用【发言人】前缀；无法确认姓名时使用【发言人A】/【发言人B】，不要强行猜测。
- 不得虚构转录里没有的人物、数据、结论或任务。

会议转录：
{transcript_text}

请完成以下分析，输出严格的 JSON 格式：

1. 会议摘要（3-6句话，概述会议主题、背景/演示/讨论过程、关键结论和后续方向）
2. 讨论要点（**严格 5-8 条上限**，短会议至少 3 条，信息充足时 5-8 条；**超过 8 条时合并相似观点**，保留最具代表性/最具行动价值的，去除细节重复、技术细节堆砌、可省略的礼貌性发言；格式：【发言人】内容）
3. 决议事项（会议中达成的共识和决定，每条标注来源发言人/双方/全组，并说明后续用途）
4. 待办任务（明确的行动项，包含负责人、截止日期、优先级）

输出格式：
{{
  "summary": "会议围绕...展开了讨论...",
  "key_points": [
    "【张三】提出了气泡稳定性实验的新方案，建议调整pH值参数",
    "【李四】汇报了上周实验进展，数据表明..."
  ],
  "decisions": [
    "【全组决定】下周三前确定实验方案",
    "【王老师】批准采购新的粒径分析仪"
  ],
  "action_items": [
    {{
      "title": "修改气泡稳定性实验方案",
      "assignee_name": "张三",
      "description": "根据讨论调整气泡稳定性实验的参数设置和测试流程",
      "due_date": "2026-06-04",
      "priority": "high",
      "confidence": "confirmed"
    }}
  ]
}}

注意事项：
- 每条关键点和决议都要标注来源发言人
- 同一发言人多次提到的相同主题，合并为一条最完整的要点，不要重复罗列
- 格式严格为【发言人】内容，每条要点只出现一次发言人前缀
- 摘要和要点要达到“例行例会纪要”信息密度，不允许只输出简单概括
- 对软件演示、实验异常、硬件清单、参数记录、任务安排等内容要展开到可执行/可追溯程度
- 截止日期根据会议时间和事务紧急性合理推断
- 优先级参考：high=本周完成，medium=两周内，low=一月内
- 如果没有明确负责人，assignee_name 设为 null
- confidence 标注：confirmed=明确指派，tentative=建议性
- 只提取明确的行动项，不要过度推断
- 中文输出"""


class MeetingAnalysisService:
    """会议 AI 分析服务

    LLM 客户端按需 lazy 构造, 不在 `__init__` 阶段创建. 调用方可注入 `llm_client`
    用于测试, 未注入时按 backend-aware 单例走 `LLMClient()`.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm: Optional[LLMClient] = llm_client

    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    # === 发言者检测 ===

    def _parse_summary_format(self, text: str) -> Optional[Dict[str, Any]]:
        """解析结构化摘要格式，提取发言人姓名。

        识别模式：
        - 发言人：张三、李四、王五
        - 参会人：张三、李四
        - 主讲人：张三
        - 参与人：张三、李四
        """
        speaker_pattern = re.compile(
            r'(?:发言人|参会人|参与人|主讲人|主持人|报告人)[：:]\s*(.+?)(?:\n|$|。|，)'
        )
        match = speaker_pattern.search(text)
        if not match:
            return None

        names_str = match.group(1).strip()
        # 分割姓名：、，, 空格
        names = re.split(r'[、，,\s]+', names_str)
        names = [n.strip() for n in names if n.strip() and len(n.strip()) >= 2]

        # 过滤文档结构标签（NON_SPEAKER 黑名单）
        NON_SPEAKER = {
            "会议主题", "会议标题", "会议摘要", "会议时间", "会议地点",
            "发言人", "参会人", "参与者", "记录人", "主持人",
            "讨论要点", "决议事项", "待办事项", "行动项",
            "摘要", "主题", "时间", "地点", "备注", "注",
            "总结", "结论", "后续", "附件", "关键词",
        }
        names = [n for n in names if n not in NON_SPEAKER]

        if not names:
            return None

        # 提取会议标题（如果有）
        title = None
        title_match = re.search(r'会议主题[：:]\s*(.+?)(?:\n|$)', text)
        if not title_match:
            title_match = re.search(r'会议标题[：:]\s*(.+?)(?:\n|$)', text)
        if title_match:
            title = title_match.group(1).strip()[:50]

        detected = []
        for name in names:
            detected.append({
                "original_label": name,
                "suggested_name": name,
                "turn_count": 1,
                "sample_lines": [text[:150]],
            })

        result = {
            "detected_speakers": detected,
            "total_turns": len(detected),
            "confidence": "high",
            "format_type": "summary",
        }
        if title:
            result["extracted_title"] = title
        return result

    def _quick_parse_speakers(self, text: str) -> Optional[Dict[str, Any]]:
        """本地快速解析发言者（不调用 AI），处理明确的【发言人】格式。

        成功检测到多位发言者时返回结果，否则返回 None 交由 AI 处理。
        """
        # 匹配 【名称】: ... 或 【名称】：... 格式
        pattern = re.compile(r'【(.+?)】[:：]')
        matches = pattern.findall(text)

        if not matches:
            # 尝试匹配 "名称说：" "名称：" 格式
            pattern2 = re.compile(r'(?:(?:^|\n)([^\s【】]{2,6})(?:说|：|:))')
            matches = pattern2.findall(text)

        if not matches:
            return None

        # 过滤非发言人标签（文档结构字段、摘要关键词等）
        NON_SPEAKER = {
            "会议主题", "会议标题", "会议摘要", "会议时间", "会议地点",
            "发言人", "参会人", "参与者", "记录人", "主持人",
            "讨论要点", "决议事项", "待办事项", "行动项",
            "摘要", "主题", "时间", "地点", "备注", "注",
            "总结", "结论", "后续", "附件", "关键词",
        }

        speaker_counts: Dict[str, int] = {}
        speaker_lines: Dict[str, List[str]] = {}
        lines = text.split("\n")

        for label in matches:
            # 跳过文档结构标签
            if label.strip() in NON_SPEAKER:
                continue
            speaker_counts[label] = speaker_counts.get(label, 0) + 1

        for label in set(matches):
            if label.strip() in NON_SPEAKER:
                continue
            sample = []
            for line in lines:
                if label in line and len(sample) < 2:
                    clean = line.strip()[:120]
                    if clean not in sample:
                        sample.append(clean)
            speaker_lines[label] = sample

        unique_speakers = list(speaker_counts.keys())
        # 至少需要 2 位真正的发言者，否则交由 AI 检测
        if len(unique_speakers) < 2:
            return None

        detected = []
        for label in unique_speakers:
            detected.append({
                "original_label": label,
                "suggested_name": None,
                "turn_count": speaker_counts[label],
                "sample_lines": speaker_lines.get(label, [])[:2],
            })

        return {
            "detected_speakers": detected,
            "total_turns": sum(speaker_counts.values()),
            "confidence": "high" if len(unique_speakers) <= 5 else "medium",
            "format_type": "marked",
        }

    async def detect_speakers(self, transcript_text: str) -> Dict[str, Any]:
        """自动识别转录文本中的发言者。

        检测顺序：
        1. 结构化摘要格式（发言人：张三、李四）→ 直接提取
        2. 对话转录格式（【张三】/ 张三说）→ 正则解析
        3. 纯文本 → Claude AI 检测
        """
        # 1. 先尝试摘要格式
        summary = self._parse_summary_format(transcript_text)
        if summary:
            return summary

        # 2. 再尝试对话转录格式
        local = self._quick_parse_speakers(transcript_text)
        if local:
            return local

        try:
            response = await self.llm.complete(
                messages=[{
                    "role": "user",
                    "content": SPEAKER_DETECTION_PROMPT.format(
                        transcript_text=transcript_text[:12000]
                    ),
                }],
                system="你是会议分析助手。只输出 JSON，不要其他内容。",
                max_tokens=2048,
                thinking={"type": "disabled"},
            )
            text = extract_text_from_response(response)
            return parse_llm_json(text)
        except Exception as e:
            logger.error(f"发言者检测失败: {e}")
            return {
                "detected_speakers": [
                    {"original_label": "未区分发言者", "suggested_name": None,
                     "turn_count": 1, "sample_lines": [transcript_text[:100]]}
                ],
                "total_turns": 1,
                "confidence": "low",
                "format_type": "unknown",
                "error": str(e),
            }

    # === 转录解析 ===

    def parse_with_mapping(
        self, transcript_text: str, speaker_mapping: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """将原始文本 + 发言者映射转换为结构化转录 JSON。

        输出格式与 Meeting.transcript JSON 兼容：
        [{"speaker": "张三", "text": "..."}, ...]

        v28 step 60: 额外对 speaker_mapping 做 alias 清洗（"洪辉"→"张宏魁"）
        """
        # 清洗映射值（避免硬编码 speaker_mapping 也含谐音）
        if speaker_mapping:
            speaker_mapping = {
                k: clean_person_names(v) if isinstance(v, str) else v
                for k, v in speaker_mapping.items()
            }

        entries: List[Dict[str, str]] = []

        # 尝试按【发言人】: 格式切分
        pattern = re.compile(r'【(.+?)】[:：]\s*(.+?)(?=【|$)', re.DOTALL)
        matches = pattern.findall(transcript_text)

        if matches:
            for label, text in matches:
                text = text.strip()
                if not text:
                    continue
                real_name = speaker_mapping.get(label, label)
                entries.append({"speaker": real_name, "text": text})
        else:
            # 按换行切分，尝试匹配 "名称说/：" 格式
            lines = transcript_text.split("\n")
            current_speaker = "参会者"
            current_text: List[str] = []

            for line in lines:
                line = line.strip()
                if not line:
                    if current_text:
                        entries.append({
                            "speaker": speaker_mapping.get(current_speaker, current_speaker),
                            "text": " ".join(current_text),
                        })
                        current_text = []
                    continue

                # 检测说话人切换
                speaker_match = re.match(r'^(.{2,6})(?:说|：|:)\s*(.+)', line)
                if speaker_match:
                    if current_text:
                        entries.append({
                            "speaker": speaker_mapping.get(current_speaker, current_speaker),
                            "text": " ".join(current_text),
                        })
                        current_text = []
                    current_speaker = speaker_match.group(1)
                    text_part = speaker_match.group(2).strip()
                    if text_part:
                        current_text.append(text_part)
                else:
                    current_text.append(line)

            if current_text:
                entries.append({
                    "speaker": speaker_mapping.get(current_speaker, current_speaker),
                    "text": " ".join(current_text),
                })

        return entries

    # === 结构化分析 ===

    MAX_CHUNK_CHARS = 8000  # 单次分析最多 8000 字

    async def analyze_transcript(
        self,
        transcript_text: str,
        speaker_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """分块分析会议转录（支持 3h+ 长会议）。

        短文本直接分析；长文本分块分析 + 汇总合并。

        2026-08-04 P0: 返回结构化结果，包含 success_chunk_count / failure_chunk_count
        / errors。0/N 成功 → success=False, failure=True；部分成功 → success=True,
        warning=True, errors=[...]。
        """
        if speaker_mapping:
            applied = []
            for issue, resolved in speaker_mapping.items():
                applied.append(f"【{issue}】→ {resolved}")
            transcript_text = (
                f"发言者映射：{', '.join(applied)}\n\n{transcript_text}"
            )

        # 短文本直接分析
        if len(transcript_text) <= self.MAX_CHUNK_CHARS:
            result, err = await self._analyze_chunk_safe(transcript_text)
            if err is not None:
                return {
                    "summary": "",
                    "key_points": [],
                    "decisions": [],
                    "action_items": [],
                    "success": False,
                    "failure": True,
                    "warning": False,
                    "success_chunk_count": 0,
                    "failure_chunk_count": 1,
                    "errors": [err],
                }
            return self._finalize_analysis_result([result], [])

        # 长文本：分块分析
        lines = transcript_text.split('\n')
        chunks = []
        current_chunk = []
        current_len = 0

        for line in lines:
            if current_len + len(line) > self.MAX_CHUNK_CHARS and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_len = len(line)
            else:
                current_chunk.append(line)
                current_len += len(line)
        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        logger.info(f"长会议分块分析: {len(chunks)} 块（总长 {len(transcript_text)} 字）")

        # 分析每一块；任一失败不静默 drop，要保留错误码
        chunk_results: List[Dict[str, Any]] = []
        chunk_errors: List[Dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            result, err = await self._analyze_chunk_safe(
                chunk, chunk_index=i, total_chunks=len(chunks)
            )
            if err is not None:
                logger.error(f"分块 {i+1}/{len(chunks)} 分析失败: {err}")
                chunk_errors.append({"chunk_index": i, **err})
                continue
            chunk_results.append(result)

        return self._finalize_analysis_result(chunk_results, chunk_errors)

    async def _analyze_chunk_safe(
        self, chunk_text: str, chunk_index: int = 0, total_chunks: int = 1
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """分析单个文本块，失败时返回 (None, error_dict)；成功返回 (result, None)"""
        import asyncio

        header = ""
        if total_chunks > 1:
            header = f"（第 {chunk_index + 1}/{total_chunks} 部分）\n\n"

        last_err: Optional[Dict[str, Any]] = None
        for attempt in range(2):
            try:
                response = await self.llm.complete(
                    messages=[{
                        "role": "user",
                        "content": ANALYSIS_PROMPT.format(
                            transcript_text=header + chunk_text[: self.MAX_CHUNK_CHARS]
                        ),
                    }],
                    system="你是课题组会议分析专家。只输出 JSON，不要其他内容。",
                    max_tokens=8192,
                    thinking={"type": "disabled"},
                )
                text = extract_text_from_response(response)
                try:
                    parsed = parse_llm_json(text)
                except json.JSONDecodeError as e:
                    last_err = {
                        "stage": "json_parse",
                        "error_class": "JSONDecodeError",
                        "message": str(e),
                        "attempt": attempt + 1,
                    }
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    return None, last_err
                return _clean_result_person_names(parsed), None
            except Exception as e:
                # 鉴权 (401/403) 永久错误，禁止重试
                err_msg = str(e)
                err_class = type(e).__name__
                err_class_module = type(e).__module__ or ""
                permanent = (
                    "401" in err_msg
                    or "403" in err_msg
                    or "invalid_key" in err_msg.lower()
                    or "permission" in err_msg.lower()
                    or err_class in ("AuthenticationError", "PermissionDeniedError", "BadRequestError")
                    or err_class.endswith("AuthenticationError")
                )
                last_err = {
                    "stage": "llm_call",
                    "error_class": err_class,
                    "error_module": err_class_module,
                    "message": err_msg[:500],
                    "attempt": attempt + 1,
                    "retryable": not permanent,
                }
                if permanent or attempt >= 1:
                    return None, last_err
                await asyncio.sleep(1)
        return None, last_err

    def _finalize_analysis_result(
        self,
        chunk_results: List[Dict[str, Any]],
        chunk_errors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        all_key_points: List[str] = []
        all_decisions: List[str] = []
        all_action_items: List[Any] = []
        chunk_summaries: List[str] = []

        for result in chunk_results:
            all_key_points.extend(result.get("key_points", []))
            all_decisions.extend(result.get("decisions", []))
            all_action_items.extend(result.get("action_items", []))
            if result.get("summary"):
                chunk_summaries.append(result["summary"])

        # 同步合并需要 await; 此函数内不 await, 改为 outer 调度
        # 调用方是 `analyze_transcript` async context, 因此这里直接 inline 同步合并
        summary = ""
        if chunk_summaries:
            summary = chunk_summaries[0] if len(chunk_summaries) == 1 else self._combine_summaries_sync(chunk_summaries)
            summary = clean_person_names(summary)

        MAX_KEY_POINTS = 8
        trimmed_key_points = all_key_points[:MAX_KEY_POINTS]
        if len(all_key_points) > MAX_KEY_POINTS:
            logger.info(
                f"key_points 硬截断: {len(all_key_points)} 条 → {MAX_KEY_POINTS} 条 "
                f"(CLAUDE.md 2026-06-06 标准格式硬规则, 5-8 条上限)"
            )

        success = bool(chunk_results)
        failure = len(chunk_results) == 0
        warning = bool(chunk_errors) and not failure
        return {
            "summary": summary,
            "key_points": [clean_person_names(p) for p in trimmed_key_points],
            "decisions": [clean_person_names(d) for d in all_decisions],
            "action_items": [clean_person_names(a) if isinstance(a, str) else a for a in all_action_items],
            "success": success,
            "failure": failure,
            "warning": warning,
            "success_chunk_count": len(chunk_results),
            "failure_chunk_count": len(chunk_errors),
            "errors": chunk_errors,
        }

    def _combine_summaries_sync(self, summaries: List[str]) -> str:
        """同步合并多 chunk 摘要；异步合并版保留以备将来扩展.

        当前实现简单拼接并截断，避免再起一次 LLM 调用引入新失败面。
        真实合并将在 Batch B 的 `meeting_quality_service` 中重做。
        """
        joined = "；".join(s.strip("。； \n") for s in summaries if s.strip())
        if joined and not joined.endswith("。"):
            joined += "。"
        return joined[:2000]

    # === 标题自动生成 ===

    async def generate_title(self, transcript_text: str) -> str:
        """根据转录内容自动生成会议标题（15 字以内）。"""
        import asyncio

        short_text = transcript_text[:2000]
        if len(short_text) < 10:
            return "未命名会议"

        for attempt in range(3):
            try:
                response = await self.llm.complete(
                    messages=[{"role": "user", "content": f"会议内容：{short_text}\n\n标题（20字以内）："}],
                    system="根据会议全文生成一个精炼的中文标题（20字以内）。标题应概括会议核心内容和主题，不要编号列表。",
                    max_tokens=2048,
                    temperature=0.3,
                    thinking={"type": "disabled"},
                )
                # 从 response 提取文本
                raw = ""
                # 方法1: extract_text_from_response（已兼容 ThinkingBlock）
                raw = extract_text_from_response(response) or ""
                # 方法2: block 遍历（text + thinking）
                if not raw and hasattr(response, 'content') and response.content:
                    for block in response.content:
                        t = getattr(block, 'text', '') or getattr(block, 'thinking', '')
                        if t and str(t).strip():
                            raw = str(t).strip()
                            break
                # 方法3: 正则暴力提取
                if not raw:
                    raw_str = str(response)
                    import re
                    m = re.search(r'text=.(.{2,30}).', raw_str)
                    if not m:
                        m = re.search(r'thinking=.(.{2,30}).', raw_str)
                    if m:
                        raw = m.group(1).strip()
                if not raw:
                    block_types = [type(b).__name__ for b in (response.content or [])]
                    logger.warning(f"标题生成第{attempt+1}次: 无法提取文本, block_types={block_types}, stop_reason={getattr(response, 'stop_reason', None)}")
                    continue

                # 清洗：去掉 markdown 和常见前缀，只取第一行
                import re
                title = raw.strip()
                title = re.sub(r'\*\*[^*]+\*\*\s*', '', title)  # 去掉 **xxx**
                title = re.sub(r'^#+\s*', '', title)  # 去掉 # 标题前缀
                title = title.split('\n')[0].strip()
                title = title.strip('"').strip("'").strip("《》").strip()
                # 2026-08-21 #Step14.7: qwen3.5 thinking mode 把答案埋到 reasoning 末尾.
                # raw = reasoning 全文. 优先从结尾的 "Final decision" / "Final choice" /
                # "Final title" 块取最终答案, 否则回退到首行. 兼容性: 旧 content-only 路径不受影响.
                decision_match = re.search(
                    r'(?:Final decision|Final answer|Final choice|Final title|最终决策|最终标题)\s*[:：]?\s*(.{4,30}?)(?:\s*\(|\s*（|\n|$)',
                    raw,
                    re.IGNORECASE,
                )
                if decision_match:
                    candidate = decision_match.group(1).strip()
                    candidate = re.sub(r'^[\s:：\-*\d\.\)]+', '', candidate)
                    candidate = candidate.strip('"').strip("'").strip("《》").strip("。,")
                    if 4 <= len(candidate) <= 30 and re.search(r'[一-鿿]', candidate):
                        title = candidate
                # 2026-08-21 #Step14.8: qwen3.5 thinking 模式会陷入字符计数死循环.
                # 当首行不是有效标题 (Thinking Process / 等等) 时, 扫描全文
                # 抓所有 4-30 字的纯中文短语, 挑出现最多的 (model 反复在 reasoning 中
                # 投票最终标题), 作为兜底.
                if not re.search(r'[一-鿿]', title) or title.startswith("Thinking"):
                    candidates = re.findall(
                        r'(?:Draft\s*\d+\s*[:：]\s*|Title\s*[:：]\s*|^\s*)([一-鿿][一-鿿A-Za-z0-9·\s]{3,29}?)(?=\s*[\(（]\d|\s*$|\n)',
                        raw,
                        re.MULTILINE,
                    )
                    candidates = [
                        c.strip() for c in candidates
                        if 4 <= len(c.strip()) <= 30
                    ]
                    if candidates:
                        # Pick the most-frequent title (model voting)
                        from collections import Counter
                        title = Counter(candidates).most_common(1)[0][0]
                if 2 <= len(title) <= 30:
                    logger.info(f"标题生成成功（第{attempt+1}次）: {title}")
                    return title
                logger.warning(f"标题生成第{attempt+1}次无效: '{title}' ({len(title)}字)")
            except Exception as e:
                logger.error(f"标题生成第{attempt+1}次失败: {e}")
            if attempt < 2:
                await asyncio.sleep(1)

        logger.warning("标题生成3次均失败，使用默认")
        return "未命名会议"

    # === 发言人统计（纯本地计算） ===

    def compute_speaker_stats(
        self, transcript_entries: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """计算每位发言者的统计数据。

        2026-08-04 P0: 字符统计先清洗 SenseVoice 控制 token (`<|EMO_UNKNOWN|>` 等),
        再按 CJK 字符计字, 避免老逻辑 `len(text.replace(' ', ''))` 把 token 当词
        引起的 8x+ 膨胀。
        """
        speaker_data: Dict[str, Dict[str, Any]] = {}
        total_words = 0

        for entry in transcript_entries:
            name = entry.get("speaker", "未知")
            text = entry.get("text", "")
            words = _char_count(text)

            if name not in speaker_data:
                speaker_data[name] = {
                    "name": name,
                    "turn_count": 0,
                    "word_count": 0,
                }
            speaker_data[name]["turn_count"] += 1
            speaker_data[name]["word_count"] += words
            total_words += words

        stats = []
        for name, data in speaker_data.items():
            ratio = round(data["word_count"] / total_words, 3) if total_words > 0 else 0
            stats.append({
                "name": name,
                "turn_count": data["turn_count"],
                "word_count": data["word_count"],
                "speaking_ratio": ratio,
                "avg_turn_length": round(data["word_count"] / data["turn_count"]) if data["turn_count"] else 0,
                "topics": [],
            })

        stats.sort(key=lambda x: x["word_count"], reverse=True)
        return stats


def _clean_result_person_names(result: Dict[str, Any]) -> Dict[str, Any]:
    """v28 step 60: 清洗 LLM 输出的 summary/key_points/decisions/action_items 中的人名谐音

    处理嵌套 list[str] / str / 字段缺失等情况
    """
    if not isinstance(result, dict):
        return result
    out = dict(result)
    for field in ("summary", "title"):
        if isinstance(out.get(field), str):
            out[field] = clean_person_names(out[field])
    for field in ("key_points", "decisions", "action_items"):
        val = out.get(field)
        if isinstance(val, list):
            out[field] = [
                clean_person_names(v) if isinstance(v, str) else v
                for v in val
            ]
    return out


import re as _re_sanitize

# 2026-08-04 P0: ASR / 模型控制 token 清洗（保留为纯字符统计前的归一化步骤）
_SENSEVOICE_TAG_RE = _re_sanitize.compile(r"<\|[A-Z0-9_]+\|>")


def _strip_control_tokens(text: str) -> str:
    if not text:
        return ""
    return _SENSEVOICE_TAG_RE.sub("", text)


def _char_count(text: str) -> int:
    """清洗控制 token 后, 计算 CJK 字符数 (排除 ASCII 空白/标点)。

    老的 `len(text.replace(' ', ''))` 会把 `<|EMO_UNKNOWN|>` 这种泄漏 token
    当成"词", 大量污染 speaker_stats.word_count (会议 242 实测 8.8x 膨胀)。
    """
    cleaned = _strip_control_tokens(text or "")
    return sum(1 for c in cleaned if not c.isspace())


# 全局单例
meeting_analysis = MeetingAnalysisService()
