"""默认成员 seed 服务 — 启动时幂等初始化 22 个课题组成员

W2 +N 2026-08-04: 修复 init_db.py 永跳 bug + 接入 lifespan
- 按 username 检测 (不是 count > 0)
- 现有用户不动 (UPDATE 不安全, 留给显式 fix script)
- wechat_id 缺失时用 username + '_default' (避免 NOT NULL 违规)
- voice/drive 字段清 NULL (避免 NULL constraint)

2026-09-05 角色扁平化: 不再区分 admin/leader, 所有成员 role 恒为 'member',
对外只带年级身份称谓 (由 grade 派生, 见 app/core/member_identity.py)。

数据来源: scripts/init_db.py line 52-312 (原 24 个真实成员数据)
"""
from typing import Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.member import Member

logger = logging.getLogger("microbubble.member_seeder")


# 22 个默认成员数据 (从 scripts/init_db.py 抽取, 字段对齐 Member model;
# 2026-09-05: 杨雪/邓国祥 账号已删除, 移出 seed 名单)
DEFAULT_MEMBERS: list[dict[str, Any]] = [
    # 副教授/PI
    {
        "username": "wangtianzhi",
        "name": "王天志",
        "grade": "副教授",
        "research_area": "微纳米气泡技术与应用",
        "skills": ["项目管理", "气泡生成", "水处理", "技术产业化"],
        "bio": "副教授，课题组负责人，长期从事微纳米气泡技术研究与应用开发",
        "is_active": True,
    },
    # 博士生
    {
        "username": "zhaohangjia",
        "name": "赵航佳",
        "grade": "博士",
        "research_area": "黑臭水体治理",
        "skills": ["臭氧微纳米气泡", "底泥-水界面", "污染物去除"],
        "email": "zhaohangjia@tju.edu.cn",
        "bio": "围绕微纳米气泡在黑臭水体治理中的应用开展研究，重点关注微纳米气泡与底泥-水界面污染物之间的相互作用机制",
        "is_active": True,
    },
    # 硕士生（2025级）
    {
        "username": "dutonghe",
        "name": "杜同贺",
        "grade": "研一",
        "research_area": "污染控制与水质提升",
        "skills": ["微纳米气泡", "水质提升", "数据分析"],
        "bio": "围绕污染控制与水质提升，开展微纳米气泡强化工艺研究与数据分析",
        "is_active": True,
    },
    {
        "username": "chentianxiang",
        "name": "陈天祥",
        "grade": "研一",
        "research_area": "表面清洗技术",
        "skills": ["清洗工艺", "去除工艺", "表面清洗"],
        "bio": "构建微纳米气泡清洗/去除工艺并评估关键去污指标",
        "is_active": True,
    },
    {
        "username": "zhangyi",
        "name": "张懿",
        "grade": "研一",
        "research_area": "智能化运行",
        "skills": ["发生器优化", "在线监测", "过程控制"],
        "bio": "面向智能化运行，探索发生器参数优化与在线监测/控制思路",
        "is_active": True,
    },
    {
        "username": "gengjiadong",
        "name": "耿嘉栋",
        "grade": "研一",
        "research_area": "装备开发",
        "skills": ["装备开发", "系统集成", "发生器优化"],
        "bio": "面向工程化落地，参与发生器结构优化与系统集成验证",
        "is_active": True,
    },
    # 硕士生（2024级）
    {
        "username": "chenjinxin",
        "name": "陈金薪",
        "grade": "研二",
        "research_area": "气泡成核过程调控",
        "skills": ["自由基", "界面反应", "气泡溃灭"],
        "bio": "解析气泡溃灭过程的界面活化特征与·OH生成动力学",
        "is_active": True,
    },
    {
        "username": "guanxiaowei",
        "name": "关小未",
        "grade": "研二",
        "research_area": "鱼菜共生",
        "skills": ["鱼菜共生", "水产养殖", "农业应用"],
        "bio": "研究微纳米气泡在鱼菜共生系统中的应用与优化",
        "is_active": True,
    },
    {
        "username": "huxiaoqi",
        "name": "胡小琪",
        "grade": "研二",
        "research_area": "臭氧微纳米气泡对黑臭水体泥/水界面微生境修复机理研究",
        "skills": ["消毒/抑菌", "微生物控制", "臭氧气泡"],
        "bio": "臭氧微纳米气泡对黑臭水体泥/水界面微生境修复机理研究",
        "is_active": True,
    },
    {
        "username": "lishengjing",
        "name": "李胜景",
        "grade": "研二",
        "research_area": "水产养殖",
        "skills": ["高密度养殖", "无抗鱼养殖", "水产应用"],
        "bio": "微纳米气泡应用于高密度无抗鱼养殖",
        "is_active": True,
    },
    {
        "username": "liuziyi",
        "name": "刘子毅",
        "grade": "研二",
        "research_area": "水质评价",
        "skills": ["过程评价", "数据分析", "水质提升"],
        "bio": "构建水质提升工艺的评价体系与实验数据处理流程",
        "is_active": True,
    },
    {
        "username": "songyang",
        "name": "宋洋",
        "grade": "研二",
        "research_area": "饮用水处理",
        "skills": ["生物稳定性", "管网生物膜", "膜耦合"],
        "bio": "微纳米气泡饮用水处理组，研究气泡与膜的耦合应用",
        "is_active": True,
    },
    {
        "username": "wangshuxin",
        "name": "王书馨",
        "grade": "研二",
        "research_area": "农业灌溉",
        "skills": ["农业应用", "土壤修复", "工程化应用"],
        "bio": "探索微纳米气泡在农业灌溉与土壤修复中的工程化应用方法",
        "is_active": True,
    },
    {
        "username": "wumengquan",
        "name": "吴孟铨",
        "grade": "研二",
        "research_area": "自由基生成",
        "skills": ["气泡溃灭", "传质强化", "分子动力学"],
        "bio": "研究溃灭诱导自由基生成与传质强化的关键影响因素",
        "is_active": True,
    },
    # 硕士生（2023级）
    {
        "username": "hanchongyang",
        "name": "韩重阳",
        "grade": "研三",
        "research_area": "设备开发",
        "skills": ["装备研发", "工程验证", "发生器优化"],
        "bio": "面向设备开发，推进发生器与供气/供水单元的工程优化与验证",
        "is_active": True,
    },
    {
        "username": "liruiyuan",
        "name": "李锐远",
        "grade": "研三",
        "research_area": "管网水质",
        "skills": ["生物膜控制", "管网系统", "水质稳定"],
        "bio": "研究微纳米气泡在管网生物膜控制与水质稳定性提升中的作用",
        "is_active": True,
    },
    {
        "username": "yangci",
        "name": "杨慈",
        "grade": "研三",
        "research_area": "饮用水安全",
        "skills": ["饮用水安全", "蜡样芽孢杆菌", "微生物消杀"],
        "email": "yc3259672120@163.com",
        "bio": "探索微纳米气泡在饮用水安全保障领域的应用",
        "is_active": True,
    },
    {
        "username": "yuxinrui",
        "name": "余歆睿",
        "grade": "研三",
        "research_area": "藻华控制",
        "skills": ["藻华控制", "水质净化", "小球藻抑制"],
        "bio": "探索微纳米气泡技术在藻华控制与水质净化领域的应用",
        "is_active": True,
    },
    {
        "username": "zhanghongkui",
        "name": "张宏魁",
        "grade": "研三",
        "research_area": "设施农业",
        "skills": ["设施农业", "盐碱土修复", "农业应用"],
        "bio": "探索微纳米气泡在设施农业与盐碱土修复场景中的增效机制",
        "is_active": True,
    },
    # 本科生
    {
        "username": "jiaqi",
        "name": "贾琦",
        "grade": "大四",
        "research_area": "表面清洗",
        "skills": ["实验辅助", "数据整理", "表面清洗"],
        "bio": "参与表面清洗去除实验与指标测定，协助数据整理与记录",
        "is_active": True,
    },
    {
        "username": "zhouchao",
        "name": "周之超",
        "grade": "大三",
        "research_area": "表面污染去除",
        "skills": ["表面去除", "文献调研", "实验辅助"],
        "bio": "参与表面污染去除实验与数据整理，支持文献调研与材料准备",
        "is_active": True,
    },
    # 已毕业
    {
        "username": "luopeiyuan",
        "name": "雒培媛",
        "grade": "已毕业",
        "research_area": "微纳米气泡水处理",
        "skills": ["微纳米气泡", "水处理", "同济大学博士"],
        "is_active": False,  # 已毕业, 保留但禁用
        "bio": "曾参与微纳米气泡相关研究与实验工作，现于同济大学攻读博士",
    },
]


async def seed_default_members(db: AsyncSession) -> dict:
    """按 username 幂等 seed 默认成员

    Returns: {"added": int, "skipped": int, "total": int}
    """
    # W2 +N 2026-08-04: 一次性 hash, 避免每个成员重复计算
    password_hash = get_password_hash("123456")

    added = 0
    skipped = 0

    for member_data in DEFAULT_MEMBERS:
        # 按 username 检测 (修复 init_db.py count > 0 永跳 bug)
        existing = await db.scalar(
            select(Member).where(Member.username == member_data["username"])
        )
        if existing is not None:
            skipped += 1
            continue

        # 构造 Member 对象
        m = Member(
            username=member_data["username"],
            password_hash=password_hash,
            name=member_data["name"],
            grade=member_data.get("grade"),
            research_area=member_data.get("research_area", ""),
            skills=member_data.get("skills", []),
            role="member",  # 2026-09-05 角色扁平化: 全员等权
            email=member_data.get("email"),
            personal_wechat_id=member_data.get("personal_wechat_id"),
            bio=member_data.get("bio", ""),
            is_active=member_data.get("is_active", True),
        )

        # 处理 NOT NULL 约束
        # wechat_id 是 NOT NULL, seed 数据里多数没设
        if not m.wechat_id:
            m.wechat_id = m.username + "_default"

        # 清 NULL 字段 (这些字段在 base model 里有默认 None, 但有些 migration 加了 NOT NULL)
        m.voice_embedding = None
        m.voice_enrolled_at = None
        m.voice_confirmed_at = None
        m.drive_quota_updated_at = None

        db.add(m)
        added += 1

    # W2 +N 类 20.152 强化: 逐行 commit, 避免 unique constraint 失败导致整 batch rollback
    # (例如 self-heal 路径, 24 个 members 中部分已存在, 整体 INSERT 失败 → added=0)
    try:
        await db.commit()
    except Exception as batch_err:
        await db.rollback()
        added = 0
        for member_data in DEFAULT_MEMBERS:
            existing = await db.scalar(
                select(Member).where(Member.username == member_data["username"])
            )
            if existing is not None:
                skipped += 1
                continue
            try:
                m = Member(
                    username=member_data["username"],
                    password_hash=password_hash,
                    name=member_data["name"],
                    grade=member_data.get("grade"),
                    research_area=member_data.get("research_area", ""),
                    skills=member_data.get("skills", []),
                    role="member",  # 2026-09-05 角色扁平化: 全员等权
                    email=member_data.get("email"),
                    personal_wechat_id=member_data.get("personal_wechat_id"),
                    bio=member_data.get("bio", ""),
                    is_active=member_data.get("is_active", True),
                )
                if not m.wechat_id:
                    m.wechat_id = m.username + "_default"
                m.voice_embedding = None
                m.voice_enrolled_at = None
                m.voice_confirmed_at = None
                m.drive_quota_updated_at = None
                db.add(m)
                await db.commit()
                added += 1
            except Exception as row_err:
                await db.rollback()
                # 单行失败不阻断后续

    return {"added": added, "skipped": skipped, "total": len(DEFAULT_MEMBERS)}