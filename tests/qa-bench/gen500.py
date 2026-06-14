"""
qa-bench/gen500.py — 动态生成 500 题测试集

从 DB 真实数据中提取成员/任务/会议/项目/知识，用模板+真实数据填充
生成多种角度、多变体的问题。

分类：
- A: 成员 (90)  — 查单个 / 模糊 / 关系 / 跨字段
- B: 任务 (80)   — 状态/优先级/分配/创建/编辑
- C: 会议 (70)   — 时间/标题/参与人/详情
- D: 项目 (60)   — 进度/状态/成员
- E: 知识 (60)   — 概念/检索/保存
- F: 跨域 (60)   — 多工具协作/组合查询
- G: 多轮 (40)   — 指代消解
- H: 闲聊/记忆/边界 (40)

用法：
  python tests/qa-bench/gen500.py --output tests/qa-bench/questions_500.jsonl
"""
import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Windows GBK 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import psycopg2
import psycopg2.extras


# 引导短句（让问题更口语化）
LEAD_PHRASES = [
    "", "请问", "帮我看看", "我想知道", "请教", "请帮我查", "嗯",
    "麻烦问下", "诶", "那个", "诶诶", "话说", "对了", "我想了解",
]

# 成员常见问法模板
MEMBER_TEMPLATES = [
    "{name} 是研究什么的？",
    "{name} 做什么方向？",
    "{name} 是做什么的？",
    "请教谁研究 {research_area}？",
    "课题组有谁做 {research_area}？",
    "谁研究 {research_area} 方向？",
    "{name} 现在在哪？",
    "查一下 {name}",
    "{name} 的邮箱？",
    "查 {name} 的联系方式",
    "列出所有 {role}",
    "课题组有几个人？",
    "组里有哪些 {role}？",
    "{name} 有几个任务？",
    "{name} 参与了哪些项目？",
    "{name} 的研究方向是？",
    "{name} 研究什么具体技术？",
    "{name} 有什么产出？",
    "介绍一下 {name}",
    "{name} 是不是做水处理的？",
    "{name} 的导师是谁？",
    "跟 {name} 同方向的人还有谁？",
    "{name} 跟 {other} 一起做什么？",
    "{name} 的课题组是？",
    "{name} 的项目编号？",
    "{name} 的技能专长有哪些？",
    "饮用水方向都有谁？",
    "水处理方向谁最强？",
    "找一个会 {skill} 的人",
    "谁做 {research_area}？",
    "请推荐做 {research_area} 的成员",
    "{name} 是不是做自由基的？",
    "{name} 哪一级？",
    "{name} 现在在做什么实验？",
    "{name} 毕业了吗？",
    "{name} 现在带学生吗？",
    "{name} 联系电话多少？",
    "找 {grade} 阶段做 {research_area} 的",
    "{name} 简介",
    "查 {name} 详细资料",
    "{name} 的 bio",
    "{name} 简介写完了吗？",
    "谁能做 {skill} 这事？",
    "{name} 是不是 alumni",
    "{name} 现在是博士吗？",
    "{name} 在读研几？",
    "{name} 何时入学？",
    "{name} 主攻方向是",
    "{name} 项目经验",
    "{name} 拿过什么奖？",
    "杨慈 做 饮用水 的人吗？",
    "咱们组里做水产的",
    "做农业的成员",
    "做设备的成员",
    "做表面清洗的",
    "做黑臭水体的",
    "做管网水质的",
    "{name} 任务多吗？",
    "谁还没交周报？",
    "谁在延期？",
    "组里谁最近最忙？",
    "{name} 哪个学校毕业的？",
    "近期入职的成员",
    "老成员是谁？",
    "谁是博士？",
    "找博士做 {research_area}",
    "在 {research_area} 方面积累最多的人",
    "{name} 是哪个实验室的？",
    "{name} 的论文发了几篇？",
    "组里微纳米气泡方向的代表人物",
    "组里最熟悉 {research_area} 的是谁？",
    "找在水产方向的",
    "做膜处理的",
    "做管网生物膜的",
    "{name} {other} 谁更擅长 {research_area}",
    "{name} 和 {other} 哪个做得好",
    "组里谁是 {research_area} 的 leader",
    "管理员里有谁？",
    "组长里有谁？",
    "组员里有谁？",
    "组里 admin 角色",
    "组里 leader 角色",
    "组里 member 角色",
    "除了 {name} 还能找谁？",
    "{name} 有什么事需要帮忙？",
    "周末谁有空？",
    "周五有谁在？",
    "我现在能和谁讨论 {research_area}",
    "下周谁有空？",
    "把 {name} 介绍给我认识",
    "{name} 是博后吗？",
    "{name} 是专硕还是学硕？",
    "{name} 是工程博士吗？",
    "组里做 {research_area} 的博后",
    "能推荐一个博后做 {research_area} 吗",
    "AI 一下 {name}",
    "教我做 {research_area}",
    "{name} 能带我吗",
    "{name} 性格如何？",
    "谁幽默？",
    "谁好相处？",
]

# 任务模板
TASK_TEMPLATES = [
    "我最近有什么任务？",
    "我有多少进行中任务？",
    "我有多少未完成任务？",
    "列出所有 {status} 的任务",
    "紧急任务有哪些？",
    "高优先级任务",
    "延期任务",
    "本周要完成的任务",
    "下周要做的任务",
    "今天该做什么？",
    "给我看看 {status} 的任务",
    "{name} 的任务",
    "谁负责任务 #{id}？",
    "任务 #{id} 是什么？",
    "任务 #{id} 完成了吗？",
    "任务 #{id} 截止日期？",
    "把任务 #{id} 标记为完成",
    "把任务 #{id} 分配给 {name}",
    "创建一个任务：{title}",
    "新建任务 {title}",
    "删除任务 #{id}",
    "取消任务 #{id}",
    "把任务 #{id} 改优先级为 high",
    "把任务 #{id} 改优先级为 low",
    "任务 #{id} 的负责人是谁？",
    "把任务 #{id} 改成 {status}",
    "列出 {name} 所有的任务",
    "{name} 还有什么任务没完成？",
    "{name} 最近忙什么？",
    "本月要交付的任务",
    "下周截止的任务",
    "我做过的任务",
    "组里现在最紧急的任务",
    "谁在 {status} 任务最多",
    "统计所有任务状态",
    "我有哪些高优先级任务？",
    "{priority} 优先级的任务",
    "我完成过哪些任务？",
    "我参与的项目当前任务",
    "{name} {priority} 任务",
    "查任务 #{id} 详情",
    "把 {name} 的所有 {status} 任务列出来",
    "把 {name} 改成 {status}",
    "我今天该做啥？",
    "列一下我明天的任务",
    "{status} 任务按截止日期排",
    "距离截止日最近的任务",
    "我做过的项目任务",
    "{name} 项目相关任务",
    "本周新增任务",
    "过去一周完成的任务",
    "我创建过的所有任务",
    "查任务 #{id} 创建时间",
    "项目 {name} 的任务",
    "项目 #{id} 当前任务",
    "我所有的 in_progress 任务",
    "我所有 done 任务",
    "我所有 cancelled 任务",
    "在研项目任务",
    "已结题项目任务",
    "任务总数",
    "每人任务数",
    "{name} 手上还有多少活",
    "把任务 #{id} 截止日推到下周五",
    "把任务 #{id} 移到 {name}",
    "把任务 #{id} 复制给 {name}",
    "高优先级 {status} 任务",
    "我今天的待办",
    "把任务 #{id} 状态改成 {status}",
    "标记任务 #{id} 完成",
    "{name} 的紧急任务",
    "{name} 过去一周新增任务",
    "任务 #{id} 优先级",
    "你能做任务 #{id} 吗",
    "重新打开任务 #{id}",
    "{status} 任务都列一下",
    "cancelled 状态任务",
    "cancelled 任务理由",
    "项目当前任务状态",
    "紧急且高优先级",
    "{name} 完成的论文",
    "我今天完成了什么？",
    "我今天新建了什么？",
    "这周提交了什么",
    "今天有截止的吗",
    "明天有 deadline 吗",
    "这周要交的",
    "项目 deadline 排序",
]

# 会议模板
MEETING_TEMPLATES = [
    "最近的会议",
    "上周开了什么会？",
    "今天有什么会议？",
    "明天有什么会议？",
    "昨天的会议",
    "这周开了什么会？",
    "下周有什么会议？",
    "本月所有会议",
    "列出所有 {status} 会议",
    "有什么关于 {topic} 的会议？",
    "远紫外相关会议",
    "UV 相关会议",
    "臭氧相关会议",
    "微纳米气泡相关会议",
    "饮用水相关会议",
    "组会一般讨论什么",
    "最近一次组会讲了什么",
    "组会安排",
    "下次组会什么时候",
    "查一下第 {id} 个会议",
    "会议 #{id}",
    "第 {id} 场会议",
    "列出 {name} 参加的会议",
    "{name} 最近开过什么会",
    "我有哪些待开的会议？",
    "我开过哪些会？",
    "未来一周的会议",
    "今天开的会议",
    "今天做学术报告的人",
    "今天做报告的主题",
    "上次例会讲了什么",
    "本月的会议",
    "{name} 做报告的会议",
    "徐佳乐博士学术报告",
    "列出所有学术报告",
    "实验进展相关的会议",
    "开过的会里涉及 {topic}",
    "组会时间",
    "下次开会在哪",
    "未来会议",
    "过去会议",
    "本周学术报告",
    "近 7 天会议",
    "近 30 天会议",
    "未开始的会议",
    "已完成的会议",
    "{name} 参加过的会",
    "把 {name} 加到会议 #{id}",
    "把 {name} 从会议 #{id} 移除",
    "修改会议 #{id} 时间",
    "新增一个会议：讨论 {topic}",
    "预约 {topic} 会议",
    "本周 {topic} 会议",
    "我所有会议",
    "会议 #{id} 详情",
    "查询会议 #{id}",
    "组里最近一次例会的纪要",
    "上周会议总结",
    "近一周的会议纪要",
    "未来 3 天会议",
    "未来 7 天会议",
    "本月所有例行会议",
    "已完成的例会",
    "未开始的例会",
    "{topic} 主题会议",
    "搜索 {topic} 会议",
    "哪些会议讲过 {topic}",
    "组里本周开了几次会",
    "本月开了几次会",
    "{topic} 相关的所有会议",
    "把 {topic} 会议都列一下",
    "未完成的会议",
    "我做过报告的会议",
    "我做主持的会议",
    "我做主持的几号",
    "会议时间冲突检查",
    "本周会议安排",
    "下周会议安排",
    "本月会议安排",
    "找会议 #{id}",
    "查会议 #{id} 议程",
    "查 {name} 做主持的会议",
    "{topic} 例会",
    "请描述会议 #{id}",
    "本季度所有会议",
    "{name} 主持的会议",
    "我发起过的会议",
    "我主持过的会议",
]

# 项目模板
PROJECT_TEMPLATES = [
    "列出所有项目",
    "在研项目有几个？",
    "已结题项目",
    "项目 #{id}",
    "项目 {name}",
    "项目进度如何？",
    "{name} 项目状态",
    "{name} 项目成员",
    "{name} 项目的负责人",
    "项目 {name} 当前任务",
    "项目 {name} 进度",
    "已立项的项目",
    "未立项的项目",
    "新增一个项目：{name}",
    "立项一个 {name} 项目",
    "把项目 #{id} 标记完成",
    "项目 #{id} 当前阶段",
    "项目 #{id} 预算",
    "项目 {name} 周期",
    "项目 {name} 团队",
    "我参与了哪些项目？",
    "{name} 参与的项目",
    "项目 #{id} 起止时间",
    "项目 #{id} 任务",
    "项目 #{id} 文档",
    "项目 {name} 经费",
    "项目 {name} 进展",
    "在研项目总览",
    "已完成项目",
    "{topic} 相关项目",
    "项目 #{id} 立项书",
    "项目 {id} 验收",
    "项目 {id} 中期",
    "{name} 项目会议",
    "{name} 项目结题",
    "{name} 项目阶段",
    "新立项的项目",
    "我做的项目",
    "谁立项了 {name}",
    "{name} 项目负责人",
    "项目 {id} 状态",
    "项目 {name} 详细",
    "项目 {id} 简介",
    "{name} 项目时间线",
    "{name} 项目背景",
    "项目 {id} 当前阶段任务",
    "新加项目：{name}",
    "{name} 课题",
    "项目 {id} 成员变动",
    "{name} 项目预算",
    "项目 {id} 当前进展",
    "{name} 项目周期",
    "项目 {id} 当前 status",
    "项目状态变更",
    "{name} 项目立项",
    "我需要新立 {name} 项目",
    "项目 {name} 的里程碑",
    "项目 {name} 当前任务",
    "完成项目 #{id}",
    "项目 {id} 状态更新",
    "{name} 项目当前在做什么",
    "新立项的项目有",
    "我负责的项目",
    "我创建过的项目",
    "项目 {id} 报告",
    "{name} 项目交付",
    "项目 {id} 时间线",
    "项目 {name} 还在进行吗",
    "项目 {name} 是 active 吗",
    "项目 {name} 状态变更历史",
    "项目 {id} 验收材料",
    "{name} 项目周报",
    "项目 {id} 月报",
    "项目 {name} 已完成",
    "新立一个 {name} 项目",
    "项目 {id} 取消",
    "项目 {name} 暂停",
    "新立项",
    "新加一个项目",
    "我做的课题",
    "组里所有项目",
    "已立项的",
    "{name} 项目立项书",
    "{name} 项目背景",
    "我新立一个项目 {name}",
    "新立项目 {name}",
    "{name} 项目的概要",
    "项目 {id} 状态",
    "项目 {id} 摘要",
    "我负责的项目",
    "我现在的项目",
    "我正在做的项目",
    "我手头项目",
    "项目 {id} 立项背景",
    "{name} 项目的周期",
    "{name} 项目阶段",
    "{name} 项目立项",
    "项目 {id} 立项背景",
    "{name} 项目立项时间",
    "我 {name} 项目",
    "我现在做的 {name}",
    "立项 {name}",
]

# 知识库模板
KNOWLEDGE_TEMPLATES = [
    "什么是 {term}？",
    "{term} 是什么？",
    "{term} 原理",
    "{term} 怎么测？",
    "怎么检测 {term}？",
    "{term} 的优缺点",
    "知识库里有几篇文献？",
    "搜一下 {term}",
    "查一下 {term}",
    "知识库关于 {term} 的内容",
    "{term} 应用",
    "{term} 实验方法",
    "{term} 案例",
    "微纳米气泡有哪些表征方法？",
    "什么是 zeta 电位？",
    "什么是溃灭？",
    "什么是 NTA？",
    "什么是 DLS？",
    "微纳米气泡应用领域",
    "微纳米气泡表征",
    "什么是微纳米气泡",
    "微纳米气泡和传统气泡区别",
    "微纳米气泡的优势",
    "微纳米气泡的稳定性",
    "微纳米气泡带电性",
    "微纳米气泡崩溃现象",
    "臭氧在水处理中的应用",
    "臭氧氧化原理",
    "超声法原理",
    "加压溶气法怎么工作",
    "文丘里管法",
    "电解法",
    "膜法",
    "微纳米气泡 + 农业",
    "微纳米气泡 + 饮用水",
    "微纳米气泡 + 黑臭水体",
    "微纳米气泡 + 自由基",
    "微纳米气泡 + 表面清洗",
    "微纳米气泡 + 水产养殖",
    "{term} 与 {term2} 的区别",
    "保存这段对话到知识库",
    "保存到知识库：{term}",
    "搜索 {term}",
    "知识库 '{term}'",
    "{term} 最新研究",
    "{term} 实验案例",
    "{term} 综述",
    "{term} 论文",
    "{term} 博士论文",
    "硕士论文关于 {term}",
    "我们组关于 {term} 的论文",
    "组里 {term} 论文",
    "知识库 {term} 标签",
    "查 {term} 相关公式",
    "公式: {term}",
    "{term} 假设",
    "{term} 实验",
    "{term} 方法对比",
    "知识库中 {term} 公式",
    "知识库 {term} 实体",
    "{term} 知识图谱",
    "我以前查过 {term}",
    "上次问的 {term}",
    "{term} 之前讲过",
    "我之前存过 {term}",
    "{term} 知识",
    "{term} 哪一年发表的",
    "{term} 综述论文",
    "{term} 实验论文",
    "我需要查 {term}",
    "查 {term} 文献",
    "{term} 核心观点",
    "知识库里有什么？",
    "知识库分类",
    "知识库统计",
    "{term} 实验方案",
    "找关于 {term} 的所有文档",
    "查所有 {term} 知识",
    "{term} 综合",
    "知识库索引",
    "{term} 假设库",
    "{term} 公式库",
    "知识库里 {term}",
    "哪些知识与 {term} 相关",
    "知识图谱 {term}",
    "{term} 实体",
    "知识图谱上 {term} 节点",
    "知识图谱 {term} 的相邻节点",
    "我之前在知识库看到过 {term}",
    "再讲一下 {term}",
    "我记得 {term}",
    "知识库我搜过 {term}",
    "{term} 我记得是这样",
    "{term} 我之前提过",
    "回忆一下 {term}",
    "{term} 是何时入库的",
    "知识库里最新的 {term} 知识",
    "{term} 综述",
    "{term} 国际研究",
    "{term} 综述",
    "{term} 知识库已存",
    "知识库命中 {term}",
    "{term} 关联公式",
    "{term} 公式",
]

# 多轮 + 跨域
CROSS_TEMPLATES = [
    "把 {task_title} 跟 {name} 的研究结合",
    "为 {name} 推荐 {research_area} 的资源",
    "杨慈的研究跟 {project} 项目关系？",
    "{name} 项目的 {task_title}",
    "我今天做完 {task_title} 的概率",
    "让 {name} 帮忙 {task_title}",
    "把会议 #{meeting_id} 的纪要发给 {name}",
    "{name} 做的 {task_title} 进展如何？",
    "推荐 {name} 做 {project}",
    "把 {name} 加到 {project} 项目",
    "把 {name} 加到 {meeting_id} 会议",
    "{name} 下一个会议是",
    "{name} 下一步任务",
    "{name} 项目当前任务",
    "{name} 的 {research_area} 进展",
    "把 {name} 推荐的 {research_area} 资料给我",
    "{name} 和 {name2} 谁的 {research_area} 更强",
    "比一下 {name} 和 {name2}",
    "{name} 能不能帮 {name2}",
    "组里 {research_area} 讨论过几次",
    "{project} 项目的 {research_area} 会议",
    "查询 {project} 项目 {name} 的任务",
    "{name} 的 {task_title} 该找谁协助",
    "让 {name} 准备 {task_title} 的资料",
    "{name} 的 {task_title} deadline 是哪天",
    "安排 {name} 和 {name2} 讨论 {research_area}",
    "{name} 上周会议讲了什么",
    "把 {meeting_id} 会议内容总结发给 {name}",
    "把 {task_title} 安排给 {name}",
    "{name} 的 {task_title} 和 {research_area} 关联",
    "{project} 项目和 {research_area} 关联",
    "{name} 的 {task_title} 关联到 {meeting_id}",
    "{task_title} 关联 {name}",
    "{task_title} 在哪个项目",
    "{project} 当前任务状态",
    "{project} 项目当前在做的任务",
    "{name} 任务最近一次更新",
    "{meeting_id} 议程里有 {task_title} 吗",
    "{name} 在 {meeting_id} 讲了 {research_area}",
    "{name} 跟 {research_area} 相关的项目",
    "{meeting_id} 提到了 {name}",
    "推荐 {research_area} 的人做 {project}",
    "{name} 的 {task_title} 还差多久",
    "今天完成 {task_title} 的概率",
    "{name} 能不能同时做 {project}",
    "{name} 和 {task_title}",
    "把 {name} 和 {task_title} 关联",
    "把 {name} 列为 {project} 成员",
    "做 {research_area} 的同事",
    "找 {name}",
    "我在 {project} 里的角色",
    "{name} 在 {project} 里的角色",
    "{name} 给我推荐 {research_area} 资源",
    "杨慈 推荐",
    "找 {research_area} 的人",
]

# 闲聊/记忆/边界
CASUAL_TEMPLATES = [
    "你好",
    "谢谢",
    "再见",
    "你叫什么名字",
    "你能做什么",
    "今天天气怎么样",
    "吃饭了吗",
    "我心情不好",
    "你累不累",
    "周末了",
    "周一好",
    "周末愉快",
    "我下班了",
    "想睡觉了",
    "我饿了",
    "加班中",
    "上班中",
    "想家了",
    "在吗",
    "你在吗",
    "回个话",
    "在吗在吗",
    "我无聊",
    "你会不会唱歌",
    "唱歌给我听",
    "讲个笑话",
    "你累不",
    "晚安",
    "早上好",
    "下午好",
    "晚上好",
    "你多大了",
    "你几岁",
    "我多大了",
    "你聪明吗",
    "你觉得怎么样",
    "你爱我吗",
    "今天开心吗",
    "你几岁",
    "hi",
    "hello",
    "HI",
    "嗨",
    "你",
    "嗯嗯",
    "呵呵",
    "哈",
    "呀",
    "你好呀",
    "那",
    "好的",
    "嗯",
    "对的",
    "是",
    "不是",
    "也许",
    "大概",
    "也许吧",
    "我想想",
    "考虑下",
    "明天再聊",
    "回聊",
    "下次聊",
    "拜拜",
    "88",
    "cu",
    "see you",
    "thanks",
    "3q",
    "ok",
    "OK",
    "好的好的",
    "嗯嗯好的",
    "我先去了",
    "先这样",
    "回头说",
    "我走了",
    "byebye",
    "再见~",
]

MEMORY_TEMPLATES = [
    "记住：我叫 {name}",
    "记住：我在 {research_area} 组",
    "记住：我喜欢 {skill}",
    "记住：我讨厌 emoji",
    "记住：以后回答都用中文",
    "记住：{name} 是我导师",
    "记住：我不太会 {skill}",
    "记住：{name} 团队",
    "以后用 {term} 称呼我",
    "以后我问你任何问题都用 {term}",
    "以后回答都要 {term}",
    "以后我说的 {term} 你就理解成 {term2}",
    "以后 {term} = {term2}",
    "我名字叫 {name}",
    "我叫 {name}",
    "我是 {name}",
    "你忘掉我的名字",
    "忘掉 {name}",
    "忘掉我的信息",
    "忘掉你记住的东西",
    "你记住了什么",
    "你记了什么",
    "我之前让你记的",
    "你记下了什么",
    "我之前说了什么",
    "你记得我吗",
    "我还说过什么",
    "我之前说过 {name} 吗",
    "我说过 {name} 对吗",
    "你还记得我吗",
    "你忘了什么",
    "忘掉我之前说过的 {term}",
    "我再告诉你一次我叫 {name}",
    "我叫 {name}, 再记一下",
    "你之前有 {term} 的记录吗",
    "删除我之前说的 {name}",
    "我之前让你记的忘掉",
    "记下来 {term}",
    "save {term}",
    "save memory {term}",
    "你现在的偏好是什么",
    "my preferences",
    "你记住我名字了吗",
    "你记得我名字吗",
    "我叫什么来着",
    "我刚才说啥了",
    "前面我提过什么",
    "记一下我之前问的",
    "你记下了吗",
    "记笔记 {term}",
    "记住 {term}",
    "我新名字叫 {name}",
    "你记下我说的 {term} 了吗",
    "我说过 {name} 吗",
    "我之前说 {name} 你记下了吗",
    "我之前说 {name} 你怎么不记得",
    "我之前说 {name}",
    "记下 {term}",
    "你记不记得我",
    "忘掉一切",
    "从头开始",
    "你是什么模型",
    "你底层用 GPT 吗",
    "你训练数据是",
    "你权重多少",
    "你是开源的吗",
    "你跟 GPT 什么关系",
    "你会写代码吗",
    "你能写 Python 吗",
    "你能写 SQL 吗",
    "你会画画吗",
    "你会唱歌吗",
    "你讲个冷笑话",
    "再讲个笑话",
    "你有什么特长",
    "你弱点是什么",
    "你今天心情怎么样",
    "你会算命吗",
    "你星座",
    "你生日",
    "我心里有事",
    "我有压力",
    "我失恋了",
    "我被骂了",
    "今天运气不好",
    "我中彩票了",
    "我想换工作",
    "我想辞职",
    "我想休学",
    "我毕业了",
    "我考上了",
    "我没考上",
    "我心情好",
    "我心情不好",
    "我焦虑",
    "我睡不着",
    "我失眠",
    "我吃了火锅",
    "我吃了烧烤",
    "我吃了麻辣烫",
    "我生病了",
    "我感冒了",
]

# 边角/极端
EXTREME_TEMPLATES = [
    "a", "b", "?", "？", "你好吗", "好的吧", "或许",
    "赵航佳 杨慈 宋洋 三个人谁更适合做饮用水",
    "杨慈 + 饮用水 + 微纳米气泡",
    "水处理水处理水处理水处理水处理水处理水处理",
    "abc def ghi jkl mno pqr stu vwx yz",
    "1234567890",
    "1 + 1 = ?",
    "1000000000 + 2000000000",
    "100 万 + 200 万",
    "什么是真理",
    "人生的意义",
    "我该不该读博",
    "我要不要发论文",
    "课题组还要不要做 {research_area}",
    "{research_area} 还有前途吗",
    "{research_area} 是不是夕阳方向",
    "我想换导师",
    "我想换方向",
    "换到 {research_area}",
    "该不该转行",
    "我应不应该 {action}",
    "{name} 是不是不合适",
    "我该不该招 {name}",
    "课题组要不要扩招",
    "要招几个 {research_area}",
    "能给我建议吗",
    "在吗",
    "?" * 10,
    "。",
    "...",
    "  ",
    "我想退出 {project}",
    "{project} 还要继续吗",
    "该不该砍掉 {project}",
    "我能加入 {project} 吗",
    "{name} 是不是该毕业了",
    "{name} 该不该延毕",
    "{research_area} 这个方向 5 年后还火吗",
    "{research_area} 跟 {research_area2} 比哪个好",
    "AI 时代 {research_area} 会被替代吗",
    "GPT 能做 {research_area} 吗",
    "AI 能取代 {research_area} 吗",
    "{name} 是不是比 {name2} 更强",
    "我能不能打败 {name}",
    "我要比 {name} 强",
    "{name} 是不是混子",
    "{name} 是不是很水",
    "我比 {name} 强吗",
    "{name} 是不是水货",
    "我能不能挖 {name}",
    "{name} 会跳槽吗",
    "未来 {research_area} 五年会怎样",
    "{research_area} 哪个学校最强",
    "{research_area} 国家排名",
    "{research_area} 哪个院士最强",
    "我想问个开放问题",
    "我有个 idea",
    "我有个点子",
    "我有个疑问",
    "我有个想法",
    "我有 {research_area} 的 idea",
    "{research_area} 怎么做",
    "{research_area} 怎么入手",
    "{research_area} 有什么坑",
    "我能做 {research_area} 吗",
    "{research_area} 我能做吗",
    "我啥都不会",
    "组里我啥都不会",
    "我学不会",
    "我毕业不了",
    "我延毕了",
    "我被开除了",
    "我答辩没过",
    "我焦虑",
    "我失眠",
    "我的论文被拒了",
    "我被审稿人骂了",
    "我被编辑拒稿了",
    "我被导师骂了",
    "我被同门坑了",
    "我被实验室开了",
    "我退学了",
    "我退组了",
    "我跑路了",
    "课题组会不会解散",
    "我们组会不会裁人",
    "我们组会不会缩招",
    "老板会不会跑路",
    "老板是不是要退休",
    "老板是不是要跳槽",
    "老师是不是不要我了",
    "{name} 是不是要走了",
    "{name} 是不是要离职",
    "{name} 是不是要毕业",
    "{name} 是不是要延期",
    "我能不能保研",
    "我能不能直博",
    "我能不能硕转博",
    "我能不能去 {name} 那里",
    "我能不能去 {research_area} 强组",
    "我该不该跳 {research_area}",
    "我该不该换 {research_area}",
    "我该不该转 {research_area}",
    "{research_area} 跨专业可行吗",
    "我是机械能转 {research_area} 吗",
    "我是化学能转 {research_area} 吗",
    "我是环境能转 {research_area} 吗",
    "我本科不是环境能读 {research_area} 博吗",
    "我本科不是 {research_area} 能读吗",
    "跨专业 {research_area} 现实吗",
    "我快 30 还能读博吗",
    "我 35 还能读博吗",
    "我本科毕业 10 年了还能读博吗",
    "读博值吗",
    "读博后悔吗",
    "读博对就业有用吗",
    "读博对找教职有用吗",
    "去企业读博值得吗",
    "学 {research_area} 能去哪些企业",
    "{research_area} 出来能去哪些企业",
    "{research_area} 出来能去哪些高校",
    "{research_area} 出来能去哪些研究院",
    "我们 {research_area} 行业薪资",
    "我们 {research_area} 行业前景",
    "{research_area} 行业 5 年后会更好吗",
    "{research_area} 行业未来 5 年",
    "{research_area} 行业未来 10 年",
]


def fetch_db_data() -> Dict[str, List[Dict[str, Any]]]:
    """从 DB 提取所有真实数据"""
    conn = psycopg2.connect(
        host="db", port=5432, dbname="microbubble",
        user="postgres", password="microbubble2026",
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    data = {"members": [], "tasks": [], "meetings": [], "projects": [], "knowledge": []}

    # 成员
    cur.execute("""
        SELECT id, name, role, grade, research_area, skills, bio, is_active
        FROM members WHERE is_active = true
        ORDER BY id
    """)
    data["members"] = cur.fetchall()

    # 任务
    cur.execute("""
        SELECT id, title, status, priority
        FROM tasks WHERE deleted_at IS NULL
        ORDER BY id
    """)
    data["tasks"] = cur.fetchall()

    # 会议
    cur.execute("""
        SELECT id, title, status, start_time
        FROM meetings ORDER BY start_time DESC
    """)
    data["meetings"] = cur.fetchall()

    # 项目
    cur.execute("""
        SELECT id, name, status, research_area
        FROM projects ORDER BY id
    """)
    data["projects"] = cur.fetchall()

    # 知识 (knowledge 表 schema 不同)
    cur.execute("""
        SELECT id, title, category
        FROM knowledge ORDER BY id
    """)
    try:
        data["knowledge"] = cur.fetchall()
    except Exception:
        data["knowledge"] = []

    conn.close()
    return data


def make_question(qid: str, category: str, question: str,
                  expect: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": qid, "category": category, "question": question, "expect": expect}


def gen_member_questions(members: List[Dict]) -> List[Dict]:
    """生成成员类问题"""
    out = []
    active = [m for m in members if m.get("is_active")]
    names = [m["name"] for m in active]
    directions = list({m["research_area"] for m in active if m.get("research_area")})
    skills_pool = []
    for m in active:
        if m.get("skills"):
            for s in m["skills"]:
                skills_pool.append(s)
    skills_pool = list(set(skills_pool))
    roles = list({m["role"] for m in active if m.get("role")})
    grades = list({m["grade"] for m in active if m.get("grade")})

    qid_counter = [0]

    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    # 模板填充
    rng = random.Random(hash("member") & 0xffffffff)
    rng.shuffle(MEMBER_TEMPLATES)

    for tmpl in MEMBER_TEMPLATES[:90]:
        lead = rng.choice(LEAD_PHRASES)
        # 选名字
        if "{name}" in tmpl and "{other}" in tmpl:
            # 双名字模板
            if len(names) < 2:
                continue
            a, b = rng.sample(names, 2)
            # 先填充所有 {research_area} {role} {skill} {grade} 避免 KeyError
            question = lead + tmpl
            for ph, options in [
                ("{research_area}", directions or ["微纳米气泡"]),
                ("{role}", roles or ["member"]),
                ("{skill}", skills_pool or ["水处理"]),
                ("{grade}", grades or ["研二"]),
                ("{name}", [a]),
                ("{other}", [b]),
            ]:
                while ph in question:
                    question = question.replace(ph, rng.choice(options), 1)
        elif "{name}" in tmpl:
            name = rng.choice(names)
            question = lead + tmpl
            for ph, options in [
                ("{research_area}", directions or ["微纳米气泡"]),
                ("{role}", roles or ["member"]),
                ("{skill}", skills_pool or ["水处理"]),
                ("{grade}", grades or ["研二"]),
                ("{other}", names or ["杨慈"]),
                ("{name}", [name]),
            ]:
                while ph in question:
                    question = question.replace(ph, rng.choice(options), 1)
        elif "{research_area}" in tmpl:
            ra = rng.choice(directions) if directions else "微纳米气泡"
            question = lead + tmpl
            for ph, options in [
                ("{research_area}", [ra]),
                ("{role}", roles or ["member"]),
                ("{skill}", skills_pool or ["水处理"]),
                ("{grade}", grades or ["研二"]),
            ]:
                while ph in question:
                    question = question.replace(ph, rng.choice(options), 1)
        elif "{role}" in tmpl:
            r = rng.choice(roles) if roles else "member"
            question = lead + tmpl
            for ph, options in [
                ("{research_area}", directions or ["微纳米气泡"]),
                ("{role}", [r]),
                ("{skill}", skills_pool or ["水处理"]),
                ("{grade}", grades or ["研二"]),
            ]:
                while ph in question:
                    question = question.replace(ph, rng.choice(options), 1)
        elif "{skill}" in tmpl:
            s = rng.choice(skills_pool) if skills_pool else "水处理"
            question = lead + tmpl
            for ph, options in [
                ("{research_area}", directions or ["微纳米气泡"]),
                ("{role}", roles or ["member"]),
                ("{skill}", [s]),
                ("{grade}", grades or ["研二"]),
            ]:
                while ph in question:
                    question = question.replace(ph, rng.choice(options), 1)
        elif "{grade}" in tmpl:
            g = rng.choice(grades) if grades else "研二"
            question = lead + tmpl
            for ph, options in [
                ("{research_area}", directions or ["微纳米气泡"]),
                ("{role}", roles or ["member"]),
                ("{skill}", skills_pool or ["水处理"]),
                ("{grade}", [g]),
            ]:
                while ph in question:
                    question = question.replace(ph, rng.choice(options), 1)
        else:
            question = lead + tmpl
            for ph, options in [
                ("{research_area}", directions or ["微纳米气泡"]),
                ("{role}", roles or ["member"]),
                ("{skill}", skills_pool or ["水处理"]),
                ("{grade}", grades or ["研二"]),
            ]:
                while ph in question:
                    question = question.replace(ph, rng.choice(options), 1)

        # 必填字段
        expect = {
            "tools_any": ["get_member_profile", "query_members"],
            "intent_any": ["search_info", "data_query", "recommend_person"],
        }
        out.append(make_question(next_id("M"), "member", question, expect))

    return out


def gen_task_questions(tasks: List[Dict], members: List[Dict]) -> List[Dict]:
    out = []
    active_members = [m["name"] for m in members if m.get("is_active") and m.get("name")]
    statuses = ["in_progress", "done", "cancelled", "todo"]
    priorities = ["high", "medium", "low"]

    qid_counter = [0]
    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    rng = random.Random(hash("task") & 0xffffffff)
    rng.shuffle(TASK_TEMPLATES)

    for tmpl in TASK_TEMPLATES[:80]:
        lead = rng.choice(LEAD_PHRASES)
        if "{id}" in tmpl:
            tid = rng.choice([t["id"] for t in tasks]) if tasks else 1
            if "{name}" in tmpl:
                name = rng.choice(active_members) if active_members else "杨慈"
                question = lead + tmpl.format(id=tid, name=name)
            elif "{title}" in tmpl:
                title = rng.choice([t["title"] for t in tasks if t.get("title")]) or "完成实验"
                question = lead + tmpl.format(id=tid, title=title)
            elif "{status}" in tmpl:
                st = rng.choice(statuses)
                question = lead + tmpl.format(id=tid, status=st)
            elif "{priority}" in tmpl:
                p = rng.choice(priorities)
                question = lead + tmpl.format(id=tid, priority=p)
            else:
                question = lead + tmpl.format(id=tid)
        elif "{name}" in tmpl:
            name = rng.choice(active_members) if active_members else "杨慈"
            if "{status}" in tmpl:
                st = rng.choice(statuses)
                question = lead + tmpl.format(name=name, status=st)
            elif "{priority}" in tmpl:
                p = rng.choice(priorities)
                question = lead + tmpl.format(name=name, priority=p)
            else:
                question = lead + tmpl.format(name=name)
        elif "{status}" in tmpl:
            st = rng.choice(statuses)
            question = lead + tmpl.format(status=st)
        elif "{priority}" in tmpl:
            p = rng.choice(priorities)
            question = lead + tmpl.format(priority=p)
        elif "{title}" in tmpl:
            title = rng.choice([t["title"] for t in tasks if t.get("title")]) or "完成实验"
            question = lead + tmpl.format(title=title)
        else:
            question = lead + tmpl

        expect = {
            "tools_any": ["query_tasks", "create_task", "update_task", "delete_task"],
            "intent_any": ["data_query", "execute_action", "casual_chat"],
        }
        out.append(make_question(next_id("T"), "task", question, expect))

    return out


def gen_meeting_questions(meetings: List[Dict], members: List[Dict]) -> List[Dict]:
    out = []
    active_members = [m["name"] for m in members if m.get("is_active") and m.get("name")]
    topics = ["UV", "臭氧", "微纳米气泡", "饮用水", "水处理", "远紫外", "黑臭水体", "农业", "设备开发"]

    qid_counter = [0]
    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    rng = random.Random(hash("meeting") & 0xffffffff)
    rng.shuffle(MEETING_TEMPLATES)

    for tmpl in MEETING_TEMPLATES[:70]:
        lead = rng.choice(LEAD_PHRASES)
        if "{id}" in tmpl:
            mid = rng.choice([m["id"] for m in meetings]) if meetings else 1
            if "{name}" in tmpl:
                name = rng.choice(active_members) if active_members else "杨慈"
                question = lead + tmpl.format(id=mid, name=name)
            else:
                question = lead + tmpl.format(id=mid)
        elif "{status}" in tmpl:
            st = rng.choice(["completed", "scheduled", "in_progress"])
            question = lead + tmpl.format(status=st)
        elif "{topic}" in tmpl:
            t = rng.choice(topics)
            question = lead + tmpl.format(topic=t)
        elif "{name}" in tmpl:
            name = rng.choice(active_members) if active_members else "杨慈"
            question = lead + tmpl.format(name=name)
        else:
            question = lead + tmpl

        expect = {
            "tools_any": ["query_meetings", "get_meeting_detail", "create_meeting"],
            "intent_any": ["data_query", "execute_action", "explain_concept"],
        }
        out.append(make_question(next_id("C"), "meeting", question, expect))

    return out


def gen_project_questions(projects: List[Dict], members: List[Dict]) -> List[Dict]:
    out = []
    project_names = [p["name"] for p in projects if p.get("name")]

    qid_counter = [0]
    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    rng = random.Random(hash("project") & 0xffffffff)
    rng.shuffle(PROJECT_TEMPLATES)

    for tmpl in PROJECT_TEMPLATES[:60]:
        lead = rng.choice(LEAD_PHRASES)
        if "{id}" in tmpl:
            pid = rng.choice([p["id"] for p in projects]) if projects else 1
            if "{name}" in tmpl:
                name = rng.choice(project_names) if project_names else "饮用水项目"
                question = lead + tmpl.format(id=pid, name=name)
            else:
                question = lead + tmpl.format(id=pid)
        elif "{name}" in tmpl:
            name = rng.choice(project_names) if project_names else "饮用水项目"
            if "{topic}" in tmpl:
                t = rng.choice(["饮用水", "微纳米气泡", "水处理"])
                question = lead + tmpl.format(name=name, topic=t)
            else:
                question = lead + tmpl.format(name=name)
        elif "{topic}" in tmpl:
            t = rng.choice(["饮用水", "微纳米气泡", "水处理"])
            question = lead + tmpl.format(topic=t)
        else:
            question = lead + tmpl

        expect = {
            "tools_any": ["query_projects", "create_project", "get_project_summary"],
            "intent_any": ["data_query", "execute_action"],
        }
        out.append(make_question(next_id("P"), "project", question, expect))

    return out


def gen_knowledge_questions(knowledge: List[Dict], members: List[Dict]) -> List[Dict]:
    out = []
    directions = list({m["research_area"] for m in members if m.get("is_active") and m.get("research_area")})
    terms_pool = [
        "zeta 电位", "NTA", "DLS", "溃灭", "臭氧", "超声", "微纳米气泡", "蜡样芽孢杆菌",
        "黑臭水体", "饮用水", "生物稳定性", "管网生物膜", "膜耦合", "加压溶气", "文丘里管",
        "电解法", "PEM", "PEM 电解", "电解水", "微气泡", "纳气泡", "粒径分布", "zeta",
        "OH 自由基", "·OH", "气泡溃灭", "•OH", "高级氧化", "AOP", "Fenton",
        "高铁酸盐", "高铁酸钾", "次氯酸钠", "紫外高级氧化", "UV/H2O2", "UV/O3",
        "UV/TiO2", "光催化", "TiO2", "ZnO", "石墨烯", "碳纳米管",
        "微生物消杀", "致病菌", "灭活", "生物膜", "MBR", "UF", "NF", "RO",
    ]

    qid_counter = [0]
    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    rng = random.Random(hash("knowledge") & 0xffffffff)
    rng.shuffle(KNOWLEDGE_TEMPLATES)

    for tmpl in KNOWLEDGE_TEMPLATES[:60]:
        lead = rng.choice(LEAD_PHRASES)
        if "{term}" in tmpl and "{term2}" in tmpl:
            t1, t2 = rng.sample(terms_pool, 2)
            question = lead + tmpl.format(term=t1, term2=t2)
        elif "{term}" in tmpl:
            t = rng.choice(terms_pool)
            question = lead + tmpl.format(term=t)
        else:
            question = lead + tmpl

        expect = {
            "tools_any": ["search_knowledge", "save_conversation_knowledge"],
            "intent_any": ["explain_concept", "search_info", "execute_action"],
        }
        out.append(make_question(next_id("K"), "knowledge", question, expect))

    return out


def gen_cross_questions(members: List[Dict], tasks: List[Dict], meetings: List[Dict], projects: List[Dict]) -> List[Dict]:
    out = []
    active_members = [m["name"] for m in members if m.get("is_active") and m.get("name")]
    directions = list({m["research_area"] for m in members if m.get("is_active") and m.get("research_area")})
    project_names = [p["name"] for p in projects if p.get("name")]
    task_titles = [t["title"] for t in tasks if t.get("title")]

    qid_counter = [0]
    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    rng = random.Random(hash("cross") & 0xffffffff)
    rng.shuffle(CROSS_TEMPLATES)

    for tmpl in CROSS_TEMPLATES[:60]:
        lead = rng.choice(LEAD_PHRASES)
        # 替换各种占位
        question = lead + tmpl
        # 一次性把 {name} {name2} {task_title} {project} {meeting_id} {research_area} {action} 都替换
        for placeholder, options in [
            ("{name}", active_members or ["杨慈"]),
            ("{name2}", active_members or ["宋洋"]),
            ("{task_title}", task_titles or ["完成实验"]),
            ("{project}", project_names or ["饮用水项目"]),
            ("{research_area}", directions or ["微纳米气泡"]),
            ("{action}", ["投稿", "做实验", "开组会", "写报告"]),
        ]:
            while placeholder in question:
                question = question.replace(placeholder, rng.choice(options), 1)
        if "{meeting_id}" in question:
            mid = rng.choice([m["id"] for m in meetings]) if meetings else 1
            question = question.replace("{meeting_id}", str(mid))

        expect = {
            "intent_any": ["data_query", "search_info", "recommend_person", "execute_action", "explain_concept", "casual_chat"],
        }
        out.append(make_question(next_id("X"), "cross", question, expect))

    return out


def gen_casual_questions() -> List[Dict]:
    out = []
    qid_counter = [0]
    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    rng = random.Random(hash("casual") & 0xffffffff)
    rng.shuffle(CASUAL_TEMPLATES)

    for tmpl in CASUAL_TEMPLATES[:30]:
        lead = rng.choice(LEAD_PHRASES)
        question = lead + tmpl
        expect = {"intent_any": ["casual_chat", "data_query", "execute_action", "search_info"]}
        out.append(make_question(next_id("U"), "casual", question, expect))

    return out


def gen_memory_questions(members: List[Dict]) -> List[Dict]:
    out = []
    active_members = [m["name"] for m in members if m.get("is_active") and m.get("name")]
    directions = list({m["research_area"] for m in members if m.get("is_active") and m.get("research_area")})
    skills_pool = []
    for m in members:
        if m.get("is_active") and m.get("skills"):
            for s in m["skills"]:
                skills_pool.append(s)
    skills_pool = list(set(skills_pool))[:20]

    qid_counter = [0]
    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    rng = random.Random(hash("memory") & 0xffffffff)
    rng.shuffle(MEMORY_TEMPLATES)

    for tmpl in MEMORY_TEMPLATES[:30]:
        lead = rng.choice(LEAD_PHRASES)
        question = lead + tmpl
        for placeholder, options in [
            ("{name}", active_members or ["小明"]),
            ("{research_area}", directions or ["微纳米气泡"]),
            ("{skill}", skills_pool or ["水处理"]),
            ("{term}", ["实验", "论文", "项目"]),
            ("{term2}", ["文章", "汇报", "讨论"]),
        ]:
            while placeholder in question:
                question = question.replace(placeholder, rng.choice(options), 1)

        expect = {"intent_any": ["execute_action", "casual_chat", "data_query", "search_info"]}
        out.append(make_question(next_id("Y"), "memory", question, expect))

    return out


def gen_extreme_questions(members: List[Dict]) -> List[Dict]:
    out = []
    active_members = [m["name"] for m in members if m.get("is_active") and m.get("name")]
    directions = list({m["research_area"] for m in members if m.get("is_active") and m.get("research_area")})
    project_names = [p["name"] for p in members if p.get("is_active") and p.get("research_area")]

    qid_counter = [0]
    def next_id(prefix):
        qid_counter[0] += 1
        return f"{prefix}{qid_counter[0]:03d}"

    rng = random.Random(hash("extreme") & 0xffffffff)
    rng.shuffle(EXTREME_TEMPLATES)

    for tmpl in EXTREME_TEMPLATES[:20]:
        lead = rng.choice(LEAD_PHRASES)
        question = lead + tmpl
        for placeholder, options in [
            ("{name}", active_members or ["杨慈"]),
            ("{name2}", active_members or ["宋洋"]),
            ("{research_area}", directions or ["微纳米气泡"]),
            ("{research_area2}", directions or ["饮用水"]),
            ("{action}", ["投稿", "做实验", "开组会"]),
            ("{project}", ["饮用水项目", "黑臭水体项目"]),
        ]:
            while placeholder in question:
                question = question.replace(placeholder, rng.choice(options), 1)

        expect = {"intent_any": ["casual_chat", "data_query", "execute_action", "search_info", "explain_concept"]}
        out.append(make_question(next_id("Z"), "extreme", question, expect))

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="tests/qa-bench/questions_500.jsonl")
    parser.add_argument("--total", type=int, default=500)
    args = parser.parse_args()

    print("📊 提取 DB 真实数据...")
    data = fetch_db_data()
    print(f"  成员: {len(data['members'])}")
    print(f"  任务: {len(data['tasks'])}")
    print(f"  会议: {len(data['meetings'])}")
    print(f"  项目: {len(data['projects'])}")
    print(f"  知识: {len(data['knowledge'])}")

    print()
    print("🎲 生成动态题...")
    all_questions = []
    all_questions += gen_member_questions(data["members"])
    all_questions += gen_task_questions(data["tasks"], data["members"])
    all_questions += gen_meeting_questions(data["meetings"], data["members"])
    all_questions += gen_project_questions(data["projects"], data["members"])
    all_questions += gen_knowledge_questions(data["knowledge"], data["members"])
    all_questions += gen_cross_questions(data["members"], data["tasks"], data["meetings"], data["projects"])
    all_questions += gen_casual_questions()
    all_questions += gen_memory_questions(data["members"])
    all_questions += gen_extreme_questions(data["members"])

    print(f"  原始生成: {len(all_questions)} 题")

    # 去重 + 截断到 total
    seen = set()
    unique = []
    for q in all_questions:
        if q["question"] in seen:
            continue
        seen.add(q["question"])
        unique.append(q)

    # 重排序 id
    if len(unique) > args.total:
        unique = unique[:args.total]
    print(f"  去重后: {len(unique)} 题")

    # 按 category 统计
    from collections import Counter
    cat = Counter(q["category"] for q in unique)
    for c, n in cat.most_common():
        print(f"    {c:15s} {n}")

    # 写文件
    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        for q in unique:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"\n✅ 写入 {out_path} ({len(unique)} 题)")


if __name__ == "__main__":
    main()
