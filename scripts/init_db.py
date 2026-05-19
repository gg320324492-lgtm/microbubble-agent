"""数据库初始化脚本 - 使用真实的课题组成员数据"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, Base, async_session
from app.core.security import get_password_hash
from app.models import Member, Task, Meeting, Project, Knowledge, Milestone


async def init_database():
    """初始化数据库"""
    print("开始初始化数据库...")

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("数据库表创建完成")

    # 插入初始数据
    await seed_data()

    print("数据库初始化完成")


async def seed_data():
    """插入初始数据"""
    async with async_session() as session:
        # 检查是否已有数据
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(Member.id)))
        count = result.scalar()

        if count > 0:
            print("数据库已有数据，跳过初始数据插入")
            return

        print("插入课题组成员数据...")

        # 默认密码（所有用户初始密码为 123456）
        default_password_hash = get_password_hash("123456")

        # ==================== 成员数据 ====================
        # 数据来源：Micro-Nano-Bubble-Technology-Lab 项目

        members = [
            # 副教授/PI
            Member(
                username="wangtianzhi",
                password_hash=default_password_hash,
                name="王天志",
                grade="副教授",
                research_area="微纳米气泡技术与应用",
                skills=["项目管理", "气泡生成", "水处理", "技术产业化"],
                role="admin",
                bio="副教授，课题组负责人，长期从事微纳米气泡技术研究与应用开发"
            ),

            # 博士生
            Member(
                username="zhaohangjia",
                password_hash=default_password_hash,
                name="赵航佳",
                grade="博士",
                research_area="黑臭水体治理",
                skills=["臭氧微纳米气泡", "底泥-水界面", "污染物去除"],
                email="zhaohangjia@tju.edu.cn",
                role="member",
                bio="围绕微纳米气泡在黑臭水体治理中的应用开展研究，重点关注微纳米气泡与底泥-水界面污染物之间的相互作用机制"
            ),

            # 硕士生（2025级）
            Member(
                username="dutonghe",
                password_hash=default_password_hash,
                name="杜同贺",
                grade="研一",
                research_area="污染控制与水质提升",
                skills=["微纳米气泡", "水质提升", "数据分析"],
                role="member",
                bio="围绕污染控制与水质提升，开展微纳米气泡强化工艺研究与数据分析"
            ),
            Member(
                username="chentianxiang",
                password_hash=default_password_hash,
                name="陈天祥",
                grade="研一",
                research_area="表面清洗技术",
                skills=["清洗工艺", "去除工艺", "表面清洗"],
                role="member",
                bio="构建微纳米气泡清洗/去除工艺并评估关键去污指标"
            ),
            Member(
                username="zhangyi",
                password_hash=default_password_hash,
                name="张懿",
                grade="研一",
                research_area="智能化运行",
                skills=["发生器优化", "在线监测", "过程控制"],
                role="member",
                bio="面向智能化运行，探索发生器参数优化与在线监测/控制思路"
            ),
            Member(
                username="gengjiadong",
                password_hash=default_password_hash,
                name="耿嘉栋",
                grade="研一",
                research_area="装备开发",
                skills=["装备开发", "系统集成", "发生器优化"],
                role="member",
                bio="面向工程化落地，参与发生器结构优化与系统集成验证"
            ),

            # 硕士生（2024级）
            Member(
                username="chenjinxin",
                password_hash=default_password_hash,
                name="陈金薪",
                grade="研二",
                research_area="气泡成核过程调控",
                skills=["自由基", "界面反应", "气泡溃灭"],
                role="leader",
                bio="解析气泡溃灭过程的界面活化特征与·OH生成动力学"
            ),
            Member(
                username="guanxiaowei",
                password_hash=default_password_hash,
                name="关小未",
                grade="研二",
                research_area="鱼菜共生",
                skills=["鱼菜共生", "水产养殖", "农业应用"],
                role="member",
                bio="研究微纳米气泡在鱼菜共生系统中的应用与优化"
            ),
            Member(
                username="huxiaoqi",
                password_hash=default_password_hash,
                name="胡小琪",
                grade="研二",
                research_area="臭氧微纳米气泡对黑臭水体泥/水界面微生境修复机理研究",
                skills=["消毒/抑菌", "微生物控制", "臭氧气泡"],
                role="member",
                bio="臭氧微纳米气泡对黑臭水体泥/水界面微生境修复机理研究"
            ),
            Member(
                username="lishengjing",
                password_hash=default_password_hash,
                name="李胜景",
                grade="研二",
                research_area="水产养殖",
                skills=["高密度养殖", "无抗鱼养殖", "水产应用"],
                role="member",
                bio="微纳米气泡应用于高密度无抗鱼养殖"
            ),
            Member(
                username="liuziyi",
                password_hash=default_password_hash,
                name="刘子毅",
                grade="研二",
                research_area="水质评价",
                skills=["过程评价", "数据分析", "水质提升"],
                role="member",
                bio="构建水质提升工艺的评价体系与实验数据处理流程"
            ),
            Member(
                username="songyang",
                password_hash=default_password_hash,
                name="宋洋",
                grade="研二",
                research_area="饮用水处理",
                skills=["生物稳定性", "管网生物膜", "膜耦合"],
                role="member",
                bio="微纳米气泡饮用水处理组，研究气泡与膜的耦合应用"
            ),
            Member(
                username="wangshuxin",
                password_hash=default_password_hash,
                name="王书馨",
                grade="研二",
                research_area="农业灌溉",
                skills=["农业应用", "土壤修复", "工程化应用"],
                role="member",
                bio="探索微纳米气泡在农业灌溉与土壤修复中的工程化应用方法"
            ),
            Member(
                username="wumengquan",
                password_hash=default_password_hash,
                name="吴孟铨",
                grade="研二",
                research_area="自由基生成",
                skills=["气泡溃灭", "传质强化", "分子动力学"],
                role="member",
                bio="研究溃灭诱导自由基生成与传质强化的关键影响因素"
            ),

            # 硕士生（2023级）
            Member(
                username="hanchongyang",
                password_hash=default_password_hash,
                name="韩重阳",
                grade="研三",
                research_area="设备开发",
                skills=["装备研发", "工程验证", "发生器优化"],
                role="member",
                bio="面向设备开发，推进发生器与供气/供水单元的工程优化与验证"
            ),
            Member(
                username="liruiyuan",
                password_hash=default_password_hash,
                name="李锐远",
                grade="研三",
                research_area="管网水质",
                skills=["生物膜控制", "管网系统", "水质稳定"],
                role="member",
                bio="研究微纳米气泡在管网生物膜控制与水质稳定性提升中的作用"
            ),
            Member(
                username="yangci",
                password_hash=default_password_hash,
                name="杨慈",
                grade="研三",
                research_area="饮用水安全",
                skills=["饮用水安全", "蜡样芽孢杆菌", "微生物消杀"],
                email="yc3259672120@163.com",
                role="member",
                bio="探索微纳米气泡在饮用水安全保障领域的应用"
            ),
            Member(
                username="yuxinrui",
                password_hash=default_password_hash,
                name="余歆睿",
                grade="研三",
                research_area="藻华控制",
                skills=["藻华控制", "水质净化", "小球藻抑制"],
                role="member",
                bio="探索微纳米气泡技术在藻华控制与水质净化领域的应用"
            ),
            Member(
                username="zhanghongkui",
                password_hash=default_password_hash,
                name="张宏魁",
                grade="研三",
                research_area="设施农业",
                skills=["设施农业", "盐碱土修复", "农业应用"],
                role="member",
                bio="探索微纳米气泡在设施农业与盐碱土修复场景中的增效机制"
            ),

            # 本科生
            Member(
                username="jiaqi",
                password_hash=default_password_hash,
                name="贾琦",
                grade="大四",
                research_area="表面清洗",
                skills=["实验辅助", "数据整理", "表面清洗"],
                role="member",
                bio="参与表面清洗去除实验与指标测定，协助数据整理与记录"
            ),
            Member(
                username="zhouchao",
                password_hash=default_password_hash,
                name="周之超",
                grade="大三",
                research_area="表面污染去除",
                skills=["表面去除", "文献调研", "实验辅助"],
                role="member",
                bio="参与表面污染去除实验与数据整理，支持文献调研与材料准备"
            ),
            Member(
                username="dengguoxiang",
                password_hash=default_password_hash,
                name="邓国祥",
                grade="大三",
                research_area="自由基研究",
                skills=["实验辅助", "数据分析", "自由基"],
                role="member",
                bio="参与溃灭与自由基相关实验辅助与基础数据分析"
            ),

            # 已毕业
            Member(
                username="luopeiyuan",
                password_hash=default_password_hash,
                name="雒培媛",
                grade="已毕业",
                research_area="微纳米气泡水处理",
                skills=["微纳米气泡", "水处理", "同济大学博士"],
                role="member",
                is_active=False,
                bio="曾参与微纳米气泡相关研究与实验工作，现于同济大学攻读博士"
            ),
        ]

        for member in members:
            session.add(member)

        await session.flush()
        print(f"插入 {len(members)} 名成员")

        # ==================== 项目数据 ====================
        projects = [
            Project(
                name="微纳米气泡在黑臭水体治理中的应用",
                description="研究臭氧微纳米气泡对黑臭水体底泥及上覆水中污染物去除、底泥污染物释放抑制、界面氧化转化机制",
                research_area="黑臭水体无药剂低能耗治理",
                status="active",
                start_date=datetime(2024, 9, 1).date(),
                end_date=datetime(2027, 6, 30).date(),
                members=[2, 3, 10, 24]
            ),
            Project(
                name="饮用水水质提升与安全保障",
                description="研究微纳米气泡在饮用水处理中的应用，包括消毒抑菌、生物稳定性提升等",
                research_area="饮用水水质提升与安全保障",
                status="active",
                start_date=datetime(2023, 9, 1).date(),
                end_date=datetime(2026, 6, 30).date(),
                members=[11, 13, 18, 19]
            ),
            Project(
                name="水产高密度无抗养殖技术",
                description="探索微纳米气泡在水产高密度无抗养殖中的应用，提升养殖水质和鱼产品品质",
                research_area="水产高密度无抗养殖与品质改善",
                status="active",
                start_date=datetime(2024, 3, 1).date(),
                end_date=datetime(2026, 12, 31).date(),
                members=[12, 10, 20]
            ),
            Project(
                name="气泡成核过程调控与设备研发",
                description="研究气泡成核机理、发生器结构优化，开发高效微纳米气泡发生设备",
                research_area="气泡成核过程调控与设备研发",
                status="active",
                start_date=datetime(2023, 1, 1).date(),
                end_date=datetime(2026, 12, 31).date(),
                members=[7, 5, 6, 17, 20]
            ),
            Project(
                name="农业灌溉与土壤修复应用",
                description="探索微纳米气泡在农业灌溉、盐碱土改良中的增效应用",
                research_area="农业应用",
                status="active",
                start_date=datetime(2024, 6, 1).date(),
                end_date=datetime(2027, 6, 30).date(),
                members=[9, 10, 15, 20]
            ),
        ]

        for project in projects:
            session.add(project)

        await session.flush()
        print(f"插入 {len(projects)} 个项目")

        # ==================== 任务数据 ====================
        now = datetime.utcnow()
        tasks = [
            # 项目1：黑臭水体
            Task(
                title="臭氧微纳米气泡底泥实验",
                description="开展臭氧微纳米气泡对底泥污染物去除效果实验",
                assignee_id=2,
                project_id=1,
                priority="high",
                status="in_progress",
                progress=60,
                due_date=now + timedelta(days=14),
                source="manual"
            ),
            Task(
                title="底泥-水界面机理分析",
                description="分析微纳米气泡与底泥-水界面污染物的相互作用机制",
                assignee_id=3,
                project_id=1,
                priority="medium",
                status="todo",
                progress=0,
                due_date=now + timedelta(days=30),
                source="manual"
            ),

            # 项目2：饮用水安全
            Task(
                title="蜡样芽孢杆菌消杀实验",
                description="开展不同气源微纳米气泡对蜡样芽孢杆菌消杀机制研究",
                assignee_id=19,
                project_id=2,
                priority="high",
                status="in_progress",
                progress=45,
                due_date=now + timedelta(days=21),
                source="manual"
            ),
            Task(
                title="气泡与膜耦合应用研究",
                description="研究微纳米气泡与膜技术的耦合应用效果",
                assignee_id=14,
                project_id=2,
                priority="medium",
                status="todo",
                progress=0,
                due_date=now + timedelta(days=45),
                source="manual"
            ),

            # 项目3：水产养殖
            Task(
                title="高密度养殖水质监测",
                description="监测微纳米气泡处理后的高密度养殖水质变化",
                assignee_id=12,
                project_id=3,
                priority="high",
                status="in_progress",
                progress=30,
                due_date=now + timedelta(days=7),
                source="manual"
            ),

            # 项目4：设备研发
            Task(
                title="发生器结构优化设计",
                description="优化微纳米气泡发生器的结构设计，提高气泡生成效率",
                assignee_id=5,
                project_id=4,
                priority="high",
                status="in_progress",
                progress=70,
                due_date=now + timedelta(days=10),
                source="manual"
            ),
            Task(
                title="系统集成验证",
                description="完成发生器与供气/供水单元的系统集成验证",
                assignee_id=6,
                project_id=4,
                priority="medium",
                status="blocked",
                progress=20,
                due_date=now + timedelta(days=20),
                source="manual"
            ),

            # 项目5：农业应用
            Task(
                title="盐碱土改良实验",
                description="开展微纳米气泡在盐碱土改良中的应用实验",
                assignee_id=10,
                project_id=5,
                priority="medium",
                status="todo",
                progress=0,
                due_date=now + timedelta(days=30),
                source="manual"
            ),
            Task(
                title="农业灌溉效果评估",
                description="评估微纳米气泡处理后灌溉水对作物生长的影响",
                assignee_id=15,
                project_id=5,
                priority="low",
                status="todo",
                progress=0,
                due_date=now + timedelta(days=60),
                source="manual"
            ),

            # 通用任务
            Task(
                title="文献调研：微纳米气泡稳定性",
                description="调研近3年微纳米气泡稳定性相关文献，整理研究进展",
                assignee_id=4,
                priority="medium",
                status="todo",
                progress=0,
                due_date=now + timedelta(days=14),
                source="manual"
            ),
            Task(
                title="NTA测试数据分析",
                description="整理并分析近期NTA测试数据，形成分析报告",
                assignee_id=7,
                priority="high",
                status="in_progress",
                progress=50,
                due_date=now + timedelta(days=5),
                source="manual"
            ),
            Task(
                title="组会PPT准备",
                description="准备下周组会的实验进展汇报PPT",
                assignee_id=8,
                priority="medium",
                status="todo",
                progress=0,
                due_date=now + timedelta(days=3),
                source="manual"
            ),
        ]

        for task in tasks:
            session.add(task)

        await session.flush()
        print(f"插入 {len(tasks)} 个任务")

        # ==================== 会议数据 ====================
        meetings = [
            Meeting(
                title="周组会",
                description="每周例行组会，汇报实验进展",
                start_time=now - timedelta(days=7),
                end_time=now - timedelta(days=7, hours=-2),
                location="会议室A301",
                status="completed",
                summary="各组汇报了本周实验进展。赵航佳汇报了臭氧气泡底泥实验初步结果；陈金薪分享了自由基生成动力学分析；发生器优化方案已确认，下周开始加工。",
                key_points=["臭氧气泡底泥实验进展顺利", "自由基生成动力学分析完成", "发生器优化方案确认"],
                decisions=["发生器优化方案进入加工阶段", "下周开展农业灌溉预实验"],
                created_by=1
            ),
            Meeting(
                title="周组会",
                description="每周例行组会",
                start_time=now + timedelta(days=3),
                location="会议室A301",
                status="scheduled",
                created_by=1
            ),
            Meeting(
                title="项目进展评审会",
                description="季度项目进展评审",
                start_time=now + timedelta(days=14),
                location="会议室B201",
                status="scheduled",
                created_by=1
            ),
        ]

        for meeting in meetings:
            session.add(meeting)

        await session.flush()
        print(f"插入 {len(meetings)} 个会议")

        # ==================== 知识库数据 ====================
        knowledge_items = [
            Knowledge(
                title="微纳米气泡基本概念",
                content="""微纳米气泡是指直径在微米到纳米级别的气泡。

微米级气泡：直径通常在1-100μm之间
纳米级气泡：直径小于1μm

主要特性：
1. 比表面积大：传质效率高
2. 带负电：Zeta电位通常为负值
3. 稳定性好：可在液体中长时间存在
4. 崩溃时产生自由基：可用于氧化反应
5. 增溶作用：可提高难溶物质的溶解度""",
                category="基础",
                tags=["气泡", "基础概念", "定义", "特性"]
            ),
            Knowledge(
                title="NTA测试方法",
                content="""纳米颗粒追踪分析（NTA）是一种用于测量悬浮液中颗粒粒径的技术。

原理：
通过激光照射样品，利用显微镜追踪单个颗粒的布朗运动，根据斯托克斯-爱因斯坦方程计算颗粒粒径。

操作步骤：
1. 样品制备：稀释至合适浓度（10^7-10^9个/mL）
2. 仪器校准：使用标准样品校准
3. 参数设置：设置相机曝光时间、检测阈值等
4. 数据采集：采集至少3个重复样品
5. 数据分析：统计粒径分布

注意事项：
- 样品需要充分稀释，避免颗粒重叠
- 测试温度需保持恒定
- 每个样品至少采集3次""",
                category="方法",
                tags=["NTA", "表征", "粒径测量", "操作规程"]
            ),
            Knowledge(
                title="DLS动态光散射测试",
                content="""动态光散射（DLS）是一种用于测量纳米颗粒粒径分布的技术。

原理：
通过测量散射光强度的波动，分析颗粒的布朗运动速度，从而计算颗粒粒径。

适用范围：
- 粒径范围：1nm-10μm
- 适合测量球形颗粒
- 需要颗粒分散均匀

与NTA的区别：
- DLS：基于统计平均，适合窄分布样品
- NTA：追踪单个颗粒，适合宽分布样品""",
                category="方法",
                tags=["DLS", "表征", "粒径测量", "对比"]
            ),
            Knowledge(
                title="微纳米气泡生成方法",
                content="""常见微纳米气泡生成方法：

1. 加压溶气法
   - 原理：通过加压使气体溶于水中，再减压释放形成气泡
   - 优点：设备简单，产量大
   - 缺点：气泡尺寸分布较宽

2. 旋流法
   - 原理：利用旋流产生负压区，吸入气体形成气泡
   - 优点：连续生产，尺寸可控
   - 缺点：能耗较高

3. 电解法
   - 原理：通过电解水产生氢气和氧气气泡
   - 优点：气泡尺寸小，纯度高
   - 缺点：产量有限

4. 膜法
   - 原理：气体通过微孔膜分散到液体中
   - 优点：尺寸均匀，可控性好
   - 缺点：膜易污染

5. 超声法
   - 原理：利用超声波空化效应产生气泡
   - 优点：设备简单
   - 缺点：产量小，不稳定""",
                category="基础",
                tags=["生成方法", "加压溶气", "旋流", "电解", "膜法", "超声"]
            ),
            Knowledge(
                title="气泡稳定性影响因素",
                content="""影响微纳米气泡稳定性的主要因素：

1. 气泡尺寸
   - 尺寸越小，稳定性越好
   - 纳米气泡可稳定数周甚至数月

2. 溶液pH
   - 影响气泡表面电荷
   - 碱性条件下稳定性通常更好

3. 离子强度
   - 高离子强度会压缩双电层
   - 降低气泡稳定性

4. 温度
   - 温度升高会降低气体溶解度
   - 可能影响气泡稳定性

5. 表面活性剂
   - 可吸附在气泡表面
   - 提高气泡稳定性

6. 气体类型
   - 不同气体的溶解度不同
   - 影响气泡的收缩和溶解速率""",
                category="基础",
                tags=["稳定性", "影响因素", "pH", "离子强度", "温度"]
            ),
            Knowledge(
                title="常见问题：气泡不稳定怎么办？",
                content="""问题：生成的微纳米气泡不稳定，快速消失

可能原因及解决方案：

1. 溶液问题
   - 检查溶液pH是否合适（建议7-9）
   - 检查离子强度是否过高
   - 尝试添加少量表面活性剂

2. 生成参数问题
   - 调整气体流量
   - 调整液体流速
   - 检查发生器是否正常工作

3. 环境因素
   - 控制溶液温度（建议20-25°C）
   - 避免剧烈搅拌
   - 减少外界振动

4. 设备问题
   - 检查气路是否漏气
   - 检查膜/微孔是否堵塞
   - 定期维护保养设备""",
                category="FAQ",
                tags=["气泡", "稳定性", "故障排除", "常见问题"]
            ),
            Knowledge(
                title="COD检测标准方法",
                content="""化学需氧量（COD）检测方法

重铬酸钾法（标准方法）：

原理：
在强酸性溶液中，用一定量的重铬酸钾氧化水样中的还原性物质，过量的重铬酸钾以试亚铁灵作指示剂，用硫酸亚铁铵溶液回滴。

试剂：
- 重铬酸钾标准溶液（0.25mol/L）
- 硫酸亚铁铵标准溶液
- 硫酸-硫酸银溶液
- 硫酸汞
- 试亚铁灵指示剂

操作步骤：
1. 取20mL水样于回流锥形瓶
2. 加入0.4g硫酸汞
3. 加入10mL重铬酸钾标准溶液
4. 慢慢加入30mL硫酸-硫酸银溶液
5. 回流2小时
6. 冷却后用硫酸亚铁铵滴定

计算：
COD(mg/L) = (V0-V1)×C×8×1000/V""",
                category="方法",
                tags=["COD", "检测", "水质", "标准方法"]
            ),
        ]

        for item in knowledge_items:
            session.add(item)

        await session.flush()
        print(f"插入 {len(knowledge_items)} 条知识")

        # ==================== 里程碑数据 ====================
        milestones = [
            # 项目1里程碑
            Milestone(
                project_id=1,
                name="文献调研完成",
                description="完成黑臭水体治理相关文献调研",
                due_date=(now - timedelta(days=30)).date(),
                status="completed",
                completed_at=now - timedelta(days=25)
            ),
            Milestone(
                project_id=1,
                name="预实验完成",
                description="完成臭氧微纳米气泡底泥预实验",
                due_date=(now + timedelta(days=14)).date(),
                status="pending"
            ),
            Milestone(
                project_id=1,
                name="正式实验完成",
                description="完成全部正式实验",
                due_date=(now + timedelta(days=90)).date(),
                status="pending"
            ),

            # 项目2里程碑
            Milestone(
                project_id=2,
                name="消杀机理研究完成",
                description="完成蜡样芽孢杆菌消杀机理研究",
                due_date=(now + timedelta(days=30)).date(),
                status="pending"
            ),
            Milestone(
                project_id=2,
                name="论文投稿",
                description="完成论文撰写并投稿",
                due_date=(now + timedelta(days=120)).date(),
                status="pending"
            ),

            # 项目4里程碑
            Milestone(
                project_id=4,
                name="发生器样机完成",
                description="完成新型发生器样机制造",
                due_date=(now + timedelta(days=20)).date(),
                status="pending"
            ),
            Milestone(
                project_id=4,
                name="系统集成测试",
                description="完成系统集成测试",
                due_date=(now + timedelta(days=45)).date(),
                status="pending"
            ),
        ]

        for milestone in milestones:
            session.add(milestone)

        await session.flush()
        print(f"插入 {len(milestones)} 个里程碑")

        # 提交所有数据
        await session.commit()
        print("所有数据插入完成！")


if __name__ == "__main__":
    asyncio.run(init_database())
