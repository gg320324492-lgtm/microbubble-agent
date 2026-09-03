# -*- coding: utf-8 -*-
# tasks-dedup-2026-09 生成器 part2: 四稿 body + 落盘
import io, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

exec(io.open('_gen_part1.py', encoding='utf-8').read())

# ---------- J · 简报瘦身 ----------
j_after = '''
  <div class="frame">
    <div class="pg">
      <div class="pg-bar"><svg class="s"><use href="#i-gauge"/></svg> 仪表盘 · 纯简报 (读+跳转)<span class="t">FUNNEL HEAD</span></div>
      <div class="pg-body">
        <div class="brief"><span class="tag">DAILY BRIEF · 卷首</span><h3>早上好,杜同贺</h3><div class="bs">2026-09-04 THU · 19 进行中 · 7 已逾期 · 例行例会 #254 今天 16:00</div></div>
        <div class="stats3"><div class="st t"><div class="n">19</div><div class="l">进行中 ↑3</div></div><div class="st g"><div class="n">75</div><div class="l">完成 +12/wk</div></div><div class="st c"><div class="n">7</div><div class="l">逾期 最久75d</div></div></div>
        <div class="blk new"><span class="tagpin">NEW · 需关注 ≤8 行</span><div class="bt">OVERDUE ∪ DUE≤3D · 逾期与临近</div>''' + R1 + R2 + R3 + '''<div class="bs">行点击 → /tasks?overdue=true / ?assignee_id=X, 落地组高亮描边 1.5s · 本块无任何写按钮</div></div>
        <div class="feed3"><div class="blk"><div class="bt">今日听会</div><div class="bs">#254 · 16:00 · 入日历</div></div><div class="blk"><div class="bt">知识库</div><div class="bs">471 · 今日 +2 · 1 冲突待复核</div></div><div class="blk"><div class="bt">DFT 队列</div><div class="bs">2 running · 3 done</div></div></div>
      </div>
    </div>
    <div class="pg">
      <div class="pg-bar"><svg class="s"><use href="#i-list"/></svg> 任务管理 · 原样 = 唯一操作台<span class="t">UNCHANGED + 高亮</span></div>
      <div class="pg-body">
        <div class="blk keep"><div class="bt">卷首计数 + 筛选 + 负责人配对卷宗 + 垃圾桶</div><div class="bs">完成/编辑/删除/批量唯一入口 — 「在哪里干活」只有一个答案</div></div>
        <div class="blk new"><span class="tagpin">小改</span><div class="bt">深链落地高亮</div><div class="bs">?assignee_id / ?overdue 到达时目标组滚动 + 档案描边脉冲; 两参数 TaskView 现已支持, 只补动画</div></div>
        <div class="blk ghost"><div class="bt">(被删的仪表盘列表块) → 迁徒完成, 无双份维护</div></div>
      </div>
    </div>
  </div>'''

j_notes = '''<li>仪表盘只读+跳转: 删「按负责人任务列表」, 换 <code>需关注</code> 摘要 (逾期 ∪ 3 天内到期, ≤8 行, 按 due 升序)</li>
<li>跳转零后端成本: <code>/tasks?assignee_id=X</code> 与 <code>?overdue=true</code> TaskView <b>已实现</b>, 本次只补落地高亮</li>
<li><b>单一写入口原则</b>: 完成动作只存在于 /tasks, 两页状态永不打架; 仪表盘第一次名副其实 (简报+导航)</li>
<li>腾出的首屏给 听会/知识库/DFT 三路 feed — 都是只有仪表盘该干的事</li>
<li>侧栏徽标 (19/471) 与统计三卡语义分离: 徽标=导航状态, 三卡=带趋势的决策数据</li>
<li>改动面: Dashboard.vue 单文件做减法 + TaskView 加一个高亮 class; <b>0 后端改动</b></li>'''

# ---------- K · 今日焦点 ----------
k_after = '''
  <div class="frame">
    <div class="pg">
      <div class="pg-bar"><svg class="s"><use href="#i-gauge"/></svg> 仪表盘 · 保留「今日焦点」微列表<span class="t">READ + ≤5 WRITE</span></div>
      <div class="pg-body">
        <div class="brief"><span class="tag">DAILY BRIEF · 卷首</span><h3>早上好,杜同贺</h3><div class="bs">晨读 30 秒, 今天的事当场勾掉 5 件</div></div>
        <div class="stats3"><div class="st t"><div class="n">19</div><div class="l">进行中</div></div><div class="st g"><div class="n">75</div><div class="l">完成</div></div><div class="st c"><div class="n">7</div><div class="l">逾期</div></div></div>
        <div class="blk new"><span class="tagpin">NEW · 今日焦点 ≤5</span><div class="bt">TODAY · 今天到期 + 最老逾期 2 件</div>
        <div class="nrow"><span class="who" style="color:var(--green);border-color:var(--green)">✓</span><div>正式实验 <span class="chip c-hi">P-高</span></div><span class="chip c-st">就地完成</span></div>''' + R2 + R4 + '''<div class="bs">子集规则: due==today ∪ oldest-overdue(2), 排序 due asc; 行尾 ✓ 走同一 useTask composable (乐观更新)</div></div>
        <div class="bs" style="text-align:right"><a style="color:var(--dteal)">完整卷宗 → /tasks</a></div>
      </div>
    </div>
    <div class="pg">
      <div class="pg-bar"><svg class="s"><use href="#i-list"/></svg> 任务管理 · 原样 (全量卷宗)<span class="t">SUPERSET</span></div>
      <div class="pg-body">
        <div class="blk keep"><div class="bt">负责人配对 + 筛选 + 垃圾桶 + 批量</div><div class="bs">今日焦点是它的受控子集 (≤5 vs 95), 语义不再镜像</div></div>
        <div class="blk"><div class="bt">双入口同步</div><div class="bs">同一 store + WS 广播兜底; 完成按钮出现在两处 = 长期维护面 ×2</div></div>
      </div>
    </div>
  </div>'''

k_notes = '''<li>折中派: 保住「晨读顺手清尾巴」的爽感, 但列表压到 ≤5 行, 是子集不是镜像</li>
<li>与 J 的差别只有一个: <b>是否允许第二个写入口</b> — 好处体验, 代价双处完成按钮的长期同步成本</li>
<li>乐观更新底座已有 (useTask); 移动端不受影响</li>
<li>改动面: Dashboard.vue 单文件; 子集计算 3 行 filter; <b>0 后端改动</b></li>'''

# ---------- L · 单页合并 ----------
l_after = '''
  <div class="frame one">
    <div class="pg" style="max-width:1000px;width:100%;margin:0 auto">
      <div class="pg-bar"><svg class="s"><use href="#i-aim"/></svg> 工作台 /dashboard · 简报+卷宗同屏 · 侧栏 9→8 项<span class="t">MERGED</span></div>
      <div class="pg-body" style="flex-direction:row;align-items:stretch">
        <div style="flex:0 0 320px;display:flex;flex-direction:column;gap:9px">
          <div class="brief"><span class="tag">DAILY BRIEF</span><h3>早上好,杜同贺</h3><div class="bs">19 进行中 · 7 逾期 · #254 今天 16:00</div></div>
          <div class="stats3" style="grid-template-columns:1fr 1fr"><div class="st t"><div class="n">19</div><div class="l">进行中</div></div><div class="st c"><div class="n">7</div><div class="l">逾期</div></div></div>
          <div class="blk"><div class="bt">听会 / 知识库 / DFT feed</div><div class="bs">竖排</div></div>
          <div class="blk ghost"><div class="bt">侧栏「仪表盘」+「任务管理」两项</div><div class="bs">合并为「工作台」; /tasks → 301 redirect 保老链接</div></div>
        </div>
        <div style="flex:1;border-left:1px dashed var(--hair);padding-left:14px;display:flex;flex-direction:column;gap:9px">
          <div class="blk new"><span class="tagpin">/tasks 全量迁入</span><div class="bt">TASK DOSSIER · 筛选 + 负责人配对卷宗 + 完成/编辑/删除/批量</div>''' + R1 + R2 + R3 + R4 + '''</div>
          <div class="blk keep"><div class="bt">Tab: 卷宗 | 垃圾桶</div><div class="bs">el-tabs 移入右栏; 面包屑「首页 / 工作台」</div></div>
        </div>
      </div>
    </div>
  </div>'''

l_notes = '''<li>从根上消灭重复: 一份列表只渲染一次; 左简报右卷宗同屏</li>
<li>代价: <b>路由级手术</b> — menuRoutes/router/meta.icon/面包屑/移动端 TabBar/22 视图巡检基线全跟改; Dashboard 与 TaskView 两文件合体 (1000+ 行巨型页回归风险)</li>
<li>1366×768 笔记本: 配对卷宗双列挤进 ~640px 右栏, 需退化单列 → 体验分叉</li>
<li>回滚成本最高, 不建议与其他档案化改造并行</li>'''

# ---------- M · 维度分工 ----------
m_after = '''
  <div class="frame">
    <div class="pg">
      <div class="pg-bar"><svg class="s"><use href="#i-gauge"/></svg> 仪表盘 · 升维到项目/里程碑周报<span class="t">PROJECT LENS</span></div>
      <div class="pg-body">
        <div class="brief"><span class="tag">WEEKLY BRIEF · WK36</span><h3>本周组里在推什么</h3><div class="bs">3 项目 · 里程碑 M3 09/15 到期 · 速率 12/wk</div></div>
        <div class="blk new"><span class="tagpin">NEW · 项目维度</span><div class="bt">微纳气泡稳定性研究 ▸ M3 中期评审 09/15</div><div class="bs">关联任务 9 · 逾期 2 · 本周完成 4</div><div class="meter"><i style="width:68%"></i></div></div>
        <div class="blk"><div class="bt">产泡装置工程化 ▸ M1 选型</div><div class="bs">任务 6 · 逾期 3 · 完成 2</div><div class="meter"><i style="width:40%"></i></div></div>
        <div class="blk"><div class="bt">大棚水质监测 ▸ M2 部署</div><div class="bs">任务 5 · 逾期 2 · 完成 6</div><div class="meter"><i style="width:85%"></i></div></div>
        <div class="blk"><div class="bt">未立项 · 23 件</div><div class="bs">兜底组 (无 project_id 任务) → /tasks</div></div>
      </div>
    </div>
    <div class="pg">
      <div class="pg-bar"><svg class="s"><use href="#i-list"/></svg> 任务管理 · 人/状态维度 (原样)<span class="t">PEOPLE LENS</span></div>
      <div class="pg-body">
        <div class="blk keep"><div class="bt">负责人配对卷宗 + 筛选 + 垃圾桶</div><div class="bs">任务=人的动词; 项目=事的进度 — 维度正交后两页结构上不可能再重复</div></div>
        <div class="blk new"><span class="tagpin">小补</span><div class="bt">/tasks?project_id=X 筛选</div><div class="bs">项目行点击跳卷宗按项目过滤 (TaskView filters.project_id 后端已支持则零改)</div></div>
      </div>
    </div>
  </div>'''

m_notes = '''<li>釜底抽薪: 重复的根源是两页用<b>同一维度</b> (都按人列任务); 仪表盘换项目/里程碑透镜后天然正交</li>
<li>信息增益最大: 现仪表盘看不到任何项目进度, 而这才是组长/PI 晨读最想要的</li>
<li>数据现成: projects + milestones + task.project_id 均在库; 需一个小聚合端点 <code>/dashboard/project-weekly</code></li>
<li>注意 未立项任务兜底组 (23 件, 占 24%), 否则周报数字对不上</li>
<li>改动面: Dashboard.vue 版式重写 + 1 新 API; 后端有件但都是只读聚合</li>'''

files = {
  'J-brief.html':    page('J', '简报瘦身 · 漏斗制', 'BRIEF TRIM', BEFORE_LEDE, j_after, j_notes, 'S', 'L', True),
  'K-focus.html':    page('K', '今日焦点 · 受控子集', 'TODAY FOCUS', BEFORE_LEDE, k_after, k_notes, 'S', 'M'),
  'L-merged.html':   page('L', '单页合并 · 工作台', 'MERGE', BEFORE_LEDE, l_after, l_notes, 'L', 'M-H'),
  'M-perm.html':     page('M', '维度分工 · 项目透镜', 'ORTHOGONAL', BEFORE_LEDE, m_after, m_notes, 'M', 'M'),
}
for fn, content in files.items():
    io.open(fn, 'w', encoding='utf-8', newline='\n').write(content)
    print('wrote', fn, len(content))
