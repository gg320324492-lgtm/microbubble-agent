"""会议转录 AI 润色 prompt"""


SYSTEM_PROMPT = """给以下对话文本添加标点符号。不要改内容。

规则：
- 只加逗号、句号、问号、感叹号
- 不改任何字词中的标点
- 不删任何内容
- 不添加任何解释"""


USER_PROMPT_TEMPLATE = """给这段对话文本加标点，输出 JSON：

{segments_json}

输出格式（严格）：
{{"polished":[{{"speaker":"原speaker","text":"加标点后的文本","ts":原ts}}]}}"""
