/* 网盘视觉稿共享交互层 — 仅用于 docs/design-proposals/drive-2026-09 演示, 不进生产代码 */
(function () {
  'use strict';
  var root = document.documentElement;

  /* ---------- 主题 ---------- */
  try {
    var saved = localStorage.getItem('dp-theme');
    if (saved) root.setAttribute('data-theme', saved);
  } catch (e) {}
  function themeLabel() {
    var btn = document.querySelector('.prop-bar button[data-theme-btn]');
    if (btn) btn.textContent = root.getAttribute('data-theme') === 'dark' ? '☀ 浅色' : '☾ 深色';
  }
  document.addEventListener('click', function (ev) {
    if (ev.target.closest('[data-theme-btn]')) {
      var dark = root.getAttribute('data-theme') === 'dark';
      root.setAttribute('data-theme', dark ? 'light' : 'dark');
      try { localStorage.setItem('dp-theme', dark ? 'light' : 'dark'); } catch (e) {}
      themeLabel();
    }
  });

  /* ---------- 工具 ---------- */
  function $(s, c) { return (c || document).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
  function ext(name) {
    var m = /\.(pptx?|docx?|xlsx?|csv|pdf|png|jpe?g|tiff?|mp4|m4a|mp3|md|txt|zip)$/i.exec(name || '');
    if (!m) return '';
    var e = m[1].toLowerCase();
    if (/^ppt/.test(e)) return 'ppt';
    if (/^doc/.test(e)) return 'doc';
    if (e === 'xlsx' || e === 'csv' || e === 'xls') return 'excel';
    if (e === 'pdf') return 'pdf';
    if (/^(png|jpe?g|tiff?)$/.test(e)) return 'image';
    if (/^(mp4|m4a|mp3)$/.test(e)) return e === 'mp4' ? 'video' : 'audio';
    return 'text';
  }
  function toast(msg) {
    var t = $('#dp-toast');
    if (!t) {
      t = document.createElement('div'); t.id = 'dp-toast';
      t.style.cssText = 'position:fixed;left:50%;top:18px;transform:translateX(-50%);z-index:200;font-size:12.5px;padding:9px 18px;border-radius:999px;background:rgba(20,16,14,.88);color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.3);backdrop-filter:blur(6px);transition:opacity .25s;pointer-events:none;font-family:inherit';
      document.body.appendChild(t);
    }
    t.textContent = msg; t.style.opacity = '1';
    clearTimeout(t._h); t._h = setTimeout(function () { t.style.opacity = '0'; }, 1600);
  }

  /* ---------- 页面配置 ---------- */
  var page = (document.body.dataset.page || '');
  var cfg = {
    a: { item: '.grid .card:not(.fcard)', name: '.name', batch: '.batch', ctx: '#ctxmenu', search: '.search input', viewsw: true, grid: '.grid' },
    b: { item: 'tr.row:not(.frow)', name: '.nm', batch: '.dock', ctx: null, search: '.gsearch input', table: true },
    c: { item: '.bcard', name: '.foot .t', batch: null, ctx: null, search: null },
    d: { item: '.ledger tbody tr', name: '.nmcell .n', batch: null, ctx: '#rowmenu', search: '.finder input' }
  }[page] || {};

  /* ---------- chip / f / pill 组: 单选 + 类型过滤 ---------- */
  function applyTypeFilter(type) {
    if (!cfg.item) return;
    $$(cfg.item).forEach(function (el) {
      var n = ($(cfg.name, el) || el).textContent;
      var ok = !type || ext(n) === type || !ext(n);
      el.style.display = ok ? '' : 'none';
    });
  }
  document.addEventListener('click', function (ev) {
    var chip = ev.target.closest('.chip, .f, .ctools .fchip, .pop .chip, .pill[data-filter]');
    if (!chip || chip.closest('.prop-bar')) return;
    var group = chip.parentElement;
    $$('.on', group).forEach(function (s) { if (s !== chip) s.classList.remove('on'); });
    chip.classList.add('on');
    var f = chip.dataset.filter;
    if (f !== undefined || /PDF|Word|PPT|Excel|图片|视频|音频|全部/.test(chip.textContent)) {
      applyTypeFilter(f === '' || f === undefined ? (chip.textContent.indexOf('全部') >= 0 ? '' : ({ 'PDF': 'pdf', 'Word': 'doc', 'PPT': 'ppt', 'Excel': 'excel', '图片': 'image', '视频': 'video', '音频': 'audio' }[chip.textContent.trim()] || '')) : f);
    }
    if (chip.textContent.trim().length < 12) toast('演示: 筛选态已切换「' + chip.textContent.trim() + '」');
  });

  /* ---------- 选中 → 批量条 ---------- */
  function refreshBatch() {
    if (!cfg.batch) return;
    var batch = $(cfg.batch); if (!batch) return;
    var sel = $$(cfg.item + '.picked, ' + cfg.item + '.sel');
    if (page === 'b') sel = $$('tr.row.sel');
    var ck = $$('input[type=checkbox]', document).filter(function (c) { return c.checked && c.closest(cfg.item); });
    if (page === 'b') sel = $$('tr.row').filter(function (r) { var c = $('input[type=checkbox]', r); return c && c.checked; });
    batch.style.display = (sel.length + ck.length) > 0 || $$('.picked', document).length || (page === 'b' && sel.length) ? '' : 'none';
    $$('[data-sel-count]').forEach(function (n) { n.textContent = sel.length || $$('.picked').length; });
  }
  document.addEventListener('click', function (ev) {
    if (ev.target.closest('.prop-bar, .acts, .batch button, .dock button, .ctx, .note-demo, a, input, .star, .mini, .pg')) return;
    var item = cfg.item && ev.target.closest(cfg.item);
    if (!item) return;
    if (page === 'b') {
      var cb = $('input[type=checkbox]', item);
      if (cb && ev.target !== cb) cb.checked = !cb.checked;
      item.classList.toggle('sel', cb ? cb.checked : !item.classList.contains('sel'));
    } else {
      item.classList.toggle('picked');
    }
    refreshBatch();
  });
  document.addEventListener('change', function (ev) {
    if (ev.target.type === 'checkbox' && cfg.item) {
      var row = ev.target.closest(cfg.item);
      if (row) row.classList.toggle('sel', ev.target.checked);
      refreshBatch();
    }
  });
  document.addEventListener('click', function (ev) {
    var all = ev.target.closest('thead input[type=checkbox]');
    if (all && cfg.item) {
      $$('tr.row ' + (page === 'b' ? '' : ''), document).forEach(function () {});
      $$(cfg.item).forEach(function (r) {
        var cb = $('input[type=checkbox]', r);
        if (cb) { cb.checked = all.checked; r.classList.toggle('sel', all.checked); }
      });
      refreshBatch();
    }
  });

  /* ---------- 搜索 (客户端假过滤) ---------- */
  if (cfg.search) {
    var si = $(cfg.search);
    if (si) si.addEventListener('input', function () {
      var q = si.value.trim().toLowerCase();
      $$(cfg.item).forEach(function (el) {
        var n = (($($(cfg.name, el)) || el).textContent || '').toLowerCase();
        el.style.display = (!q || n.indexOf(q) >= 0) ? '' : 'none';
      });
    });
  }

  /* ---------- 右键菜单 ---------- */
  var ctx = cfg.ctx ? $(cfg.ctx) : null;
  if (ctx) {
    ctx.style.display = 'none';
    document.addEventListener('contextmenu', function (ev) {
      var item = cfg.item && ev.target.closest(cfg.item);
      if (!item) return;
      ev.preventDefault();
      ctx.style.display = 'block';
      var x = Math.min(ev.clientX, window.innerWidth - 240);
      var y = Math.min(ev.clientY, window.innerHeight - ctx.offsetHeight - 20);
      ctx.style.left = x + 'px'; ctx.style.top = y + 'px'; ctx.style.right = 'auto'; ctx.style.bottom = 'auto';
    });
    document.addEventListener('click', function (ev) {
      if (ctx.style.display === 'block' && !ev.target.closest('.ctx, .note-demo')) { ctx.style.display = 'none'; }
    });
    $$('.ctx .it, .note-demo .it').forEach(function (it) {
      it.addEventListener('click', function () { toast('演示: 点击「' + it.textContent.trim().split(/[\s⌘⇧F D]+/)[0] + '」— 生产版将真实执行'); ctx.style.display = 'none'; });
    });
  }

  /* ---------- A: 视图切换 grid/list ---------- */
  if (cfg.viewsw) {
    $$('.vsw button').forEach(function (b, i) {
      b.addEventListener('click', function () {
        $$('.vsw button').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        var g = $$('.grid');
        g.forEach(function (el) { el.classList.toggle('as-list', i === 1); });
      });
    });
  }

  /* ---------- A: 星标 toggle ---------- */
  $$('.card .star').forEach(function (s) {
    s.addEventListener('click', function (ev) {
      ev.stopPropagation();
      var on = s.closest('.card').classList.toggle('starred');
      toast(on ? '已收藏 (仅自己可见)' : '已取消收藏');
    });
  });

  /* ---------- B: 右栏 tabs ---------- */
  if (page === 'b') {
    $$('.d-tab').forEach(function (t) {
      t.addEventListener('click', function () {
        $$('.d-tab').forEach(function (x) { x.classList.remove('on'); });
        t.classList.add('on');
        var v = t.textContent.indexOf('版本') >= 0;
        $$('.d-pane .cmt').forEach(function (c) { c.style.display = v ? 'none' : ''; });
        $$('.d-pane .ver').forEach(function (c) { c.style.display = v ? '' : 'none'; });
      });
    });
    /* 行点击 → 右栏换档 (只换名字, 演示) */
    $$('tr.row').forEach(function (r) {
      r.addEventListener('click', function (ev) {
        if (ev.target.closest('input, .stararrow')) return;
        var n = $('.nm', r); if (!n) return;
        $$('.d-name').forEach(function (d) { d.textContent = n.textContent.trim(); });
      });
    });
    /* 键盘导航演示: ↑↓ 移动 .kbd 焦点行 */
    document.addEventListener('keydown', function (ev) {
      if (!/ArrowDown|ArrowUp/.test(ev.key)) return;
      var rows = $$('tr.row:not(.frow)');
      var cur = rows.indexOf($('.row.kbd'));
      var next = Math.max(0, Math.min(rows.length - 1, cur + (ev.key === 'ArrowDown' ? 1 : -1)));
      rows.forEach(function (r) { r.classList.remove('kbd'); });
      rows[next].classList.add('kbd');
      $$('.d-name').forEach(function (d) { d.textContent = $('.nm', rows[next]).textContent.trim(); });
      ev.preventDefault();
    });
    /* 真拖拽: 行拖到树节点 = 移动示意 */
    $$('tr.row .nm').forEach(function (nm) {
      nm.setAttribute('draggable', 'true');
      nm.addEventListener('dragstart', function (ev) {
        ev.dataTransfer.setData('text/plain', nm.textContent.trim());
        nm.closest('tr').classList.add('dragging');
      });
      nm.addEventListener('dragend', function () { nm.closest('tr').classList.remove('dragging'); });
    });
    $$('.tnode').forEach(function (nd) {
      nd.addEventListener('dragover', function (ev) { ev.preventDefault(); nd.classList.add('drop-target'); });
      nd.addEventListener('dragleave', function () { nd.classList.remove('drop-target'); });
      nd.addEventListener('drop', function (ev) {
        ev.preventDefault(); nd.classList.remove('drop-target');
        toast('已移动「' + (ev.dataTransfer.getData('text/plain') || '').slice(0, 18) + '」→「' + $('.n', nd).textContent + '」(演示)');
      });
    });
  }

  /* ---------- B: 树折叠 ---------- */
  $$('.tw').forEach(function (tw) {
    tw.addEventListener('click', function (ev) {
      ev.stopPropagation();
      tw.classList.toggle('open');
      var nest = tw.closest('li').querySelector('ul');
      if (nest) nest.style.display = tw.classList.contains('open') ? '' : 'none';
    });
  });

  /* ---------- C: 抽屉 ---------- */
  if (page === 'c') {
    var drawer = $('.drawer'), scrim = $('.scrim'), ftag = $('.float-tag'), pop = $('.pop');
    [drawer, scrim, ftag].forEach(function (el) { if (el) el.style.display = 'none'; });
    if (pop) pop.style.display = 'none';
    var openD = function () { [drawer, scrim, ftag].forEach(function (el) { if (el) el.style.display = ''; }); };
    var closeD = function () { [drawer, scrim, ftag].forEach(function (el) { if (el) el.style.display = 'none'; }); };
    $$('.burger').forEach(function (b) { b.addEventListener('click', openD); });
    if (scrim) scrim.addEventListener('click', closeD);
    $$('[data-pop-toggle]').forEach(function (b) {
      b.addEventListener('click', function () { if (pop) pop.style.display = pop.style.display === 'none' ? '' : 'none'; });
    });
    if (pop) {
      var demo = $('.demo', pop); if (demo) demo.remove();
    }
  }

  /* ---------- D: 藏章 toggle + 展开成员卷 ---------- */
  if (page === 'd') {
    $$('.star').forEach(function (s) {
      s.addEventListener('click', function () { s.classList.toggle('on'); toast(s.classList.contains('on') ? '钤「藏」印 (仅本人可见)' : '已销印'); });
    });
    var members = $$('.spec.member'), expanded = false;
    members.forEach(function (m, i) { if (i >= 4) m.style.display = 'none'; });
    $$('[data-expand-members]').forEach(function (b) {
      b.addEventListener('click', function (ev) {
        ev.preventDefault(); expanded = !expanded;
        members.forEach(function (m, i) { m.style.display = (expanded || i < 4) ? '' : 'none'; });
        b.textContent = expanded ? '收起成员卷 ‹' : '展开成员卷 ' + members.length + ' 宗 ›';
      });
    });
    $$('.spec').forEach(function (sp) {
      sp.addEventListener('click', function () { if (sp.classList.contains('add')) { toast('演示: 生产版弹「新建卷宗」对话框'); return; } var h = $('h3', sp) || $('.n', sp); if (h) toast('开卷 · ' + h.textContent); });
    });
    $$('.mini, .pg').forEach(function (m) {
      m.addEventListener('click', function () { toast('演示: 「' + m.textContent.trim() + '」'); });
    });
  }

  /* ---------- 通用: 上传/新建等 CTA 提示 ---------- */
  $$('[data-demo]').forEach(function (b) {
    b.addEventListener('click', function () { toast('演示: ' + b.dataset.demo); });
  });

  /* A 列表视图样式注入 */
  if (page === 'a') {
    var st = document.createElement('style');
    st.textContent = '.grid.as-list{grid-template-columns:1fr;gap:8px}.grid.as-list .card{display:flex;align-items:center}.grid.as-list .card .cover{width:74px;height:52px;flex:none;border-top:none;border-left:3px solid var(--cc,transparent)}.grid.as-list .card .body{flex:1;display:flex;align-items:center;gap:18px;padding:8px 14px}.grid.as-list .card .name{min-height:0}.grid.as-list .card .mock-slide,.grid.as-list .card .mock-photo,.grid.as-list .card .mock-chart{transform:scale(.6);transform-origin:top left}.grid.as-list .card .ftag{display:none}.grid.as-list .card .acts{position:static;opacity:1;transform:none;background:none;margin-left:auto}.grid.as-list .card .star,.grid.as-list .card .pick{position:static;opacity:1}';
    document.head.appendChild(st);
  }

  themeLabel();
  refreshBatch();
})();
