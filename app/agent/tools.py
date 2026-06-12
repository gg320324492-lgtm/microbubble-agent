"""Agent工具定义"""

TOOLS = [
    # 任务相关工具
    {
        "name": "create_task",
        "description": "创建新任务。当用户要求创建任务、分配任务给某人时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "任务标题"
                },
                "assignee_name": {
                    "type": "string",
                    "description": "负责人姓名。不填则默认为当前用户自己（如'提醒我'场景无需填写）"
                },
                "project_name": {
                    "type": "string",
                    "description": "所属项目名称（可选）"
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "优先级"
                },
                "due_date": {
                    "type": "string",
                    "description": "截止日期，格式：YYYY-MM-DD HH:MM（如 2026-05-20 17:30）。仅提供日期则默认为当天 18:00"
                },
                "description": {
                    "type": "string",
                    "description": "任务详细描述"
                },
                "reminders": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "remind_at": {
                                "type": "string",
                                "description": "提醒时间，格式：YYYY-MM-DD HH:MM"
                            },
                            "remind_type": {
                                "type": "string",
                                "enum": ["wechat", "email"],
                                "description": "提醒方式"
                            }
                        },
                        "required": ["remind_at"]
                    },
                    "description": "自定义提醒时间列表。重要：当用户要求在特定时间提醒（如'5分钟后提醒我'、'下午3点提醒我'），必须使用此参数设置精确的提醒时间，不要只设置due_date。不填则使用默认提醒策略。"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "query_tasks",
        "description": "查询任务列表。当用户询问某人的任务、某项目的任务、逾期任务等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignee_name": {
                    "type": "string",
                    "description": "按负责人姓名筛选"
                },
                "status": {
                    "type": "string",
                    "enum": ["in_progress", "blocked", "review", "done", "cancelled"],
                    "description": "按状态筛选"
                },
                "project_name": {
                    "type": "string",
                    "description": "按项目名称筛选"
                },
                "overdue": {
                    "type": "boolean",
                    "description": "是否只查询逾期任务"
                }
            }
        }
    },
    {
        "name": "query_all_member_tasks",
        "description": "查询所有成员的任務状况，按状态分组显示（进行中/待办/已完成）。仅管理员或组长可用。当管理员或组长询问所有人的任務进度、团队任务分布时使用。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "update_task",
        "description": "更新任务状态。当用户要求标记任务完成、修改进度、延期等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "任务ID"
                },
                "status": {
                    "type": "string",
                    "enum": ["in_progress", "blocked", "review", "done", "cancelled"],
                    "description": "新状态"
                },
                "progress": {
                    "type": "integer",
                    "description": "进度百分比（0-100）"
                },
                "due_date": {
                    "type": "string",
                    "description": "新的截止日期，格式：YYYY-MM-DD HH:MM 或 YYYY-MM-DD"
                }
            },
            "required": ["task_id"]
        }
    },

    # 成员相关工具
    {
        "name": "query_members",
        "description": "查询成员信息。当用户询问某人信息、某研究方向的成员等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "按姓名查询"
                },
                "research_area": {
                    "type": "string",
                    "description": "按研究方向查询"
                },
                "grade": {
                    "type": "string",
                    "description": "按年级查询"
                }
            }
        }
    },

    # 会议相关工具
    {
        "name": "query_meetings",
        "description": """【必调工具】查询课题组会议记录并返回会议列表（id/title/start_time/status/summary）。
当用户问题涉及任何会议相关内容时**必须调用此工具**：包括但不限于「最近的会议」「近期组会」「有哪些会议」「查会议」「会议纪要」「有什么会议」「哪些会议可以学习」「上次会议讲了什么」「今天/昨天/上周/本月开过什么会」「UV相关会议」「远紫外会议」「开过哪些学术报告」等。
**禁止编造「系统故障/技术问题/无法访问/需要联系管理员」等借口**——这些借口都是错的，系统正常，数据可查。""",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "开始日期，格式：YYYY-MM-DD。无需过滤时省略"
                },
                "date_to": {
                    "type": "string",
                    "description": "结束日期，格式：YYYY-MM-DD。无需过滤时省略"
                },
                "keyword": {
                    "type": "string",
                    "description": "关键词搜索（如'远紫外'、'UV'、'微纳米气泡'等从用户问句中提取的关键词）。无需过滤时省略"
                }
            }
        }
    },
    {
        "name": "summarize_meeting_transcript",
        "description": "对会议转录文字进行自动归纳总结，同时将总结存入 Agent 长期记忆。当用户提供会议转录文本、要求总结会议内容时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "transcript_text": {
                    "type": "string",
                    "description": "会议转录的完整文本内容（可以是纯文本或包含【发言人】格式的对话）"
                }
            },
            "required": ["transcript_text"]
        }
    },
    {
        "name": "analyze_meeting_transcript",
        "description": "对粘贴的会议转录文本进行完整的 AI 分析——自动识别发言者、生成摘要、提取要点/决策/行动项、自动创建任务。当用户粘贴会议文本并需要智能分析时调用此工具，不要用 summarize_meeting_transcript（旧版简化工具）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "transcript_text": {
                    "type": "string",
                    "description": "会议转录的完整文本内容（支持【发言人】格式或纯文本）"
                },
                "speaker_mapping": {
                    "type": "object",
                    "description": "可选的发言者映射，如 {\"王老师\": \"王建国\"}。不传则自动检测"
                },
                "create_meeting": {
                    "type": "boolean",
                    "description": "是否同时创建会议记录并自动创建任务，默认 true"
                }
            },
            "required": ["transcript_text"]
        }
    },
    {
        "name": "create_meeting",
        "description": "创建会议。当用户要求预约会议、安排组会等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "会议主题"
                },
                "start_time": {
                    "type": "string",
                    "description": "开始时间，格式：YYYY-MM-DD HH:MM"
                },
                "participants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "参与者姓名列表"
                },
                "agenda": {
                    "type": "string",
                    "description": "会议议程"
                },
                "location": {
                    "type": "string",
                    "description": "会议地点"
                }
            },
            "required": ["title", "start_time"]
        }
    },

    # 项目相关工具
    {
        "name": "query_projects",
        "description": "查询项目信息。当用户询问课题进度、项目列表等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "paused", "completed", "archived"],
                    "description": "按状态筛选"
                }
            }
        }
    },
    {
        "name": "generate_project_plan",
        "description": "生成项目计划。当用户要求规划新课题、制定项目计划时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "项目/课题名称"
                },
                "duration_months": {
                    "type": "integer",
                    "description": "预计时长（月）"
                },
                "team_size": {
                    "type": "integer",
                    "description": "团队人数"
                },
                "research_area": {
                    "type": "string",
                    "description": "研究方向"
                }
            },
            "required": ["project_name"]
        }
    },

    # 知识库相关工具
    {
        "name": "search_knowledge",
        "description": "搜索知识库。当用户询问专业问题、查找文献、查询实验方法等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题"
                },
                "category": {
                    "type": "string",
                    "enum": ["文献", "实验", "方法", "FAQ"],
                    "description": "分类筛选"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "explore_knowledge_graph",
        "description": "探索知识图谱。当用户询问实体之间的关系、某个概念的关联知识、多跳推理等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "实体名称（如'微纳米气泡'、'zeta电位'）"
                },
                "hops": {
                    "type": "integer",
                    "description": "遍历跳数（默认 1，最大 3）"
                }
            },
            "required": ["entity_name"]
        }
    },
    {
        "name": "find_knowledge_gaps",
        "description": "发现知识库中的空白领域。当用户询问'我们还缺什么知识'、'哪些方面需要补充'时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "要检查空白的主题（可选，不填则全局检查）"
                }
            }
        }
    },
    {
        "name": "auto_research",
        "description": "自主研究某个主题。当用户要求研究某个主题、补充知识空白时使用。会联网搜索并自动入库。",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "要研究的主题"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大搜索结果数（默认 5）"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "compare_knowledge",
        "description": "对比分析多个知识条目。当用户询问'A和B哪个好'、'对比XX和YY'时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要对比的知识条目名称列表"
                },
                "criteria": {
                    "type": "string",
                    "description": "对比维度（可选）"
                }
            },
            "required": ["items"]
        }
    },
    {
        "name": "summarize_topic",
        "description": "总结某个主题的知识。当用户询问'课题组研究方向有哪些'、'总结一下XX领域'时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "要总结的主题"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "suggest_research",
        "description": "基于知识图谱和假设生成研究建议。当用户询问'下一步该研究什么'、'有什么研究方向'时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "area": {
                    "type": "string",
                    "description": "研究领域（可选）"
                }
            }
        }
    },

    # 统计相关工具
    {
        "name": "get_task_stats",
        "description": "获取任务统计数据。当用户询问整体进度、任务统计等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "按项目统计（可选）"
                },
                "member_name": {
                    "type": "string",
                    "description": "按成员统计（可选）"
                }
            }
        }
    },

    # 联网搜索工具
    {
        "name": "web_search",
        "description": "搜索互联网获取最新信息。当用户询问最新新闻、实时信息、天气、网上资料、或知识库中找不到答案的问题时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认5"
                }
            },
            "required": ["query"]
        }
    },

    # 长期记忆工具
    {
        "name": "save_memory",
        "description": "保存重要信息到长期记忆。当用户表达偏好、提供重要信息、或你发现值得记住的内容时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_type": {
                    "type": "string",
                    "enum": ["preference", "summary", "entity"],
                    "description": "记忆类型：preference(偏好)/summary(摘要)/entity(实体关系)"
                },
                "key": {
                    "type": "string",
                    "description": "记忆键名（偏好类型建议填写）"
                },
                "content": {
                    "type": "string",
                    "description": "记忆内容"
                },
                "importance": {
                    "type": "number",
                    "description": "重要性 0.0-1.0，默认0.7"
                }
            },
            "required": ["memory_type", "content"]
        }
    },
    {
        "name": "search_memory",
        "description": "搜索长期记忆。当需要回忆用户偏好、历史对话信息、实体关系时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索内容"
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["preference", "summary", "entity"],
                    "description": "限定记忆类型（可选）"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "forget_memory",
        "description": "遗忘特定记忆。当用户要求删除或纠正某条记忆时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "integer",
                    "description": "记忆ID"
                }
            },
            "required": ["memory_id"]
        }
    },

    # 对话知识保存工具
    {
        "name": "save_conversation_knowledge",
        "description": "将对话中的重要知识保存到知识库。当对话中讨论了有价值的实验方法、研究发现、技术方案、经验总结等内容时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "知识标题，简洁概括"
                },
                "content": {
                    "type": "string",
                    "description": "知识内容，完整的知识描述"
                },
                "category": {
                    "type": "string",
                    "enum": ["基础", "方法", "文献", "FAQ"],
                    "description": "知识分类"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表"
                }
            },
            "required": ["title", "content"]
        }
    },

    # 声纹录入工具
    {
        "name": "enroll_voice",
        "description": "录入用户的声纹特征。当用户说'小气，我是XXX'、'帮我录入声纹'、'记住我的声音'等时使用。需要先通过 query_members 确认成员身份。",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_name": {
                    "type": "string",
                    "description": "要录入声纹的成员姓名"
                }
            },
            "required": ["member_name"]
        }
    },

    # 自定义指令工具
    {
        "name": "set_custom_instructions",
        "description": "设置用户的自定义指令。当用户说'设置你的风格'、'以后回复要...'、'记住我的偏好'等个性化要求时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "instructions": {
                    "type": "string",
                    "description": "用户自定义指令内容，如'回复要简洁'、'用英文回复'、'多用表格'等"
                }
            },
            "required": ["instructions"]
        }
    },

    # 反馈工具
    {
        "name": "submit_feedback",
        "description": "记录用户对回复的反馈。当用户说'没用'、'不对'、'很好'、'太棒了'等评价性内容时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "rating": {
                    "type": "integer",
                    "description": "评分：1=很差, 2=较差, 3=一般, 4=较好, 5=很好"
                },
                "comment": {
                    "type": "string",
                    "description": "用户的反馈内容（可选）"
                }
            },
            "required": ["rating"]
        }
    }
]
