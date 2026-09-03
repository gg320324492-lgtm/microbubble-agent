# -*- coding: utf-8 -*-
# 一次性生成器: tasks-dedup-2026-09 四方案静态稿 (J/K/L/M)
import io, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

SPRITE = io.open('_sprite.snippet', encoding='utf-8').read()
BASE_CSS = io.open('_base.css.snippet', encoding='utf-8').read()

def page(letter, name, tagline, before_dup, after_html, notes, effort, risk, recommended=False):
    return ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
        f'<title>{letter} · {name} — 仪表盘/任务页去重方案</title>\n'
        f'<style>{BASE_CSS}</style>\n</head>\n<body>\n{SPRITE}\n<div class="page">\n'
        '  <div class="meta">\n'
        f'    <span>TASKS/DASH DEDUP PROPOSAL {letter} · 2026-09</span>\n'
        f'    <h1>{letter} 稿 · {name}{"" if not recommended else " — ★ 推荐"}</h1>\n'
        '    <button class="darkbtn" onclick="document.querySelectorAll(\'.frame\').forEach(f=>f.toggleAttribute(\'data-dark\'))">☾ 夜览</button>\n'
        '  </div>\n'
        '  <h2 class="sec">BEFORE · 现状重叠面</h2>\n'
        '  <div class="frame">\n'
        '    <div class="pg">\n'
        '      <div class="pg-bar"><svg class="s"><use href="#i-gauge"/></svg> 仪表盘 /dashboard<span class="t">DAILY BRIEF</span></div>\n'
        '      <div class="pg-body">\n'
        '        <div class="blk keep"><div class="bt">卷首 DAILY BRIEF</div><div class="bs">问候 + 团队快照 · 保留</div></div>\n'
        '        <div class="blk keep"><div class="bt">统计三卡 19 / 75 / 7</div><div class="bs">趋势 sparkline · 保留</div></div>\n'
        '        <div class="blk dup"><span class="tagpin red">DUP</span><div class="bt">进行中任务 · 按负责人分组 (20 行, 带完成按钮)</div><div class="bs">≈ /tasks 主列表的只读+写子集</div></div>\n'
        '      </div>\n'
        '    </div>\n'
        '    <div class="pg">\n'
        '      <div class="pg-bar"><svg class="s"><use href="#i-list"/></svg> 任务管理 /tasks<span class="t">TASK DOSSIER</span></div>\n'
        '      <div class="pg-body">\n'
        '        <div class="blk keep"><div class="bt">卷首计数行 20·75·95</div><div class="bs">与三卡/侧栏徽标数字同源</div></div>\n'
        '        <div class="blk dup"><span class="tagpin red">DUP</span><div class="bt">负责人配对卷宗 (左进行中/右已完成) + 筛选 + 垃圾桶</div><div class="bs">完成/编辑/删除/批量 · 全功能</div></div>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>\n'
        f'  <p class="lede">{before_dup}</p>\n'
        f'  <h2 class="sec">AFTER · {letter} 方案版面</h2>\n'
        f'  {after_html}\n'
        f'  <ul class="notes">{notes}</ul>\n'
        f'  <div class="verdict"><b>EFFORT {effort}</b><b class="{"risk-b" if "H" in risk or risk=="L" else ""}">RISK {risk}</b></div>\n'
        '</div>\n</body>\n</html>\n')

def row(who, tt, chipcls, chiptx, duecls, due):
    return (f'<div class="nrow"><span class="who">{who}</span><div>{tt} <span class="chip {chipcls}">{chiptx}</span></div>'
            f'<span class="due {duecls}">{due}</span></div>')

R1 = row('胡', '正式实验', 'c-hi', 'P-高', 'late', '明天到期')
R2 = row('陈', '文献调研:微纳米气泡稳定性', 'c-md', 'P-中', 'late', '05/31 已逾期')
R3 = row('李', '12#棚水质微生物测试', 'c-md', 'P-中', '', '09/20')
R4 = row('蒋', '看文献', 'c-md', 'P-中', '', '09/30')

BEFORE_LEDE = '两块红斜纹是同一份数据的两份视图: 仪表盘的分组列表 ⊂ /tasks 配对卷宗, 且都带「完成」写按钮。19/75/7 同时在仪表盘三卡、/tasks 卷首行、侧栏徽标出现三处。'
