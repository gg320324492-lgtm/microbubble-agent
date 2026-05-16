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
                    "description": "负责人姓名"
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
                    "description": "截止日期，格式：YYYY-MM-DD"
                },
                "description": {
                    "type": "string",
                    "description": "任务详细描述"
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
                    "enum": ["todo", "in_progress", "blocked", "review", "done", "cancelled"],
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
                    "enum": ["todo", "in_progress", "blocked", "review", "done", "cancelled"],
                    "description": "新状态"
                },
                "progress": {
                    "type": "integer",
                    "description": "进度百分比（0-100）"
                },
                "due_date": {
                    "type": "string",
                    "description": "新的截止日期"
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
        "description": "查询会议记录。当用户询问最近的会议、某次的会议纪要等时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "开始日期，格式：YYYY-MM-DD"
                },
                "date_to": {
                    "type": "string",
                    "description": "结束日期，格式：YYYY-MM-DD"
                },
                "keyword": {
                    "type": "string",
                    "description": "关键词搜索"
                }
            }
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
    }
]
