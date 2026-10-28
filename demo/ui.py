"""新版界面（毛毡书库风格）。

和 web.py 的逻辑完全解耦：这里只有 HTML/CSS/JS 三段，接口沿用现有的。
"""

PAGE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tinderbox</title>
<style>
:root{
  --paper:#f5efe3; --card:#fffdf7; --ink:#2c2a25; --muted:#8b8577; --line:#e6ddcc;
  --green:#1f3a2b; --green2:#2f5d43; --green3:#3f7355; --gold:#a8834a;
  --red:#a8442c; --amber:#a97a22; --shadow:0 8px 26px rgba(58,44,28,.07);
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);
  font:14px/1.65 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
h1,h2,h3,h4,.serif{font-family:"Noto Serif SC","Songti SC",Georgia,serif;font-weight:600}
a{color:inherit}
.app{display:flex;min-height:100vh}

/* ---------- 侧栏 ---------- */
.side{width:214px;flex:none;background:var(--green);color:#dfe5d5;position:sticky;top:0;
  height:100vh;display:flex;flex-direction:column;padding:22px 14px 18px}
.brand{display:flex;align-items:center;gap:9px;color:#fff;font-family:"Noto Serif SC",Georgia,serif;
  font-size:17px;letter-spacing:.3px;padding:2px 8px 22px}
.brand .mark{width:26px;height:26px;border-radius:7px;background:#e7dcc4;color:var(--green);
  display:grid;place-items:center;font-size:14px}
.nav{display:flex;flex-direction:column;gap:2px}
.nav a{display:flex;align-items:center;gap:10px;padding:9px 11px;border-radius:9px;
  color:#c8d2bf;font-size:13.5px;text-decoration:none;cursor:pointer;user-select:none}
.nav a:hover{background:rgba(255,255,255,.07);color:#fff}
.nav a.on{background:rgba(255,255,255,.14);color:#fff;font-weight:600}
.nav a .ic{width:16px;text-align:center;opacity:.85;font-size:13px}
.side .foot{margin-top:auto;padding:0 10px;font-size:11px;color:#93a58c;line-height:1.9;
  font-family:"Noto Serif SC",Georgia,serif}
.side .foot .leaf{display:block;margin-bottom:6px;opacity:.6;font-size:15px}

/* ---------- 主区 ---------- */
.main{flex:1;min-width:0;display:flex;flex-direction:column}
.topbar{display:flex;align-items:center;gap:16px;padding:16px 26px 10px}
.searchbox{flex:1;display:flex;align-items:center;gap:10px;background:var(--card);
  border:1px solid var(--line);border-radius:22px;padding:9px 16px;box-shadow:var(--shadow)}
.searchbox input{flex:1;border:0;outline:none;background:transparent;font-size:13.5px;color:var(--ink);
  font-family:inherit}
.searchbox .go{width:26px;height:26px;border-radius:50%;border:0;background:var(--green);
  color:#fff;cursor:pointer;font-size:13px}
.who{font-size:12.5px;color:var(--muted);white-space:nowrap}
.who b{color:var(--ink);font-weight:600}
.wrap{padding:6px 26px 40px;flex:1;min-height:0;overflow:auto}
.view{display:none}
.view.on{display:block}

/* ---------- 首页 ---------- */
.hero{position:relative;border-radius:18px;overflow:hidden;padding:40px 38px 34px;margin:4px 0 18px;
  color:#f7efe1;box-shadow:var(--shadow);
  background:
    radial-gradient(900px 320px at 78% -30%,rgba(255,233,190,.30),transparent 60%),
    radial-gradient(600px 260px at 8% 120%,rgba(0,0,0,.35),transparent 60%),
    linear-gradient(112deg,#413126 0%,#5c4733 42%,#332a21 100%);}
.hero .kicker{font-size:11.5px;letter-spacing:.28em;color:#c8bda6;text-transform:uppercase}
.hero h1{margin:10px 0 6px;font-size:31px;letter-spacing:1px;color:#fff8ea}
.hero p{margin:0 0 20px;color:#cfc4b1;font-size:13px;letter-spacing:.12em}
.hero form{display:flex;align-items:center;gap:10px;background:rgba(255,252,244,.96);
  border-radius:24px;padding:10px 16px;max-width:620px}
.hero input{flex:1;border:0;outline:none;background:transparent;font-size:13.5px;color:#3a332a;font-family:inherit}
.hero button{width:30px;height:30px;border-radius:50%;border:0;background:var(--green);color:#fff;cursor:pointer}
.hero .hue{position:absolute;right:38px;top:34px;font-size:11px;color:#b9ac95;text-align:right;line-height:1.9}
.homegrid{display:flex;gap:18px;align-items:flex-start}
.homeleft{flex:1;min-width:0}
.homeright{width:250px;flex:none;display:flex;flex-direction:column;gap:12px}
.statgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:13px 15px;box-shadow:var(--shadow)}
.stat .t{font-size:11.5px;color:var(--muted);display:flex;align-items:center;gap:6px}
.stat .n{font-family:"Noto Serif SC",Georgia,serif;font-size:26px;line-height:1.2;margin-top:2px}
.stat .d{font-size:11px;color:#a9a294;margin-top:2px}
.qa{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:var(--shadow)}
.qa h4{margin:0 0 10px;font-size:12.5px;color:var(--muted);font-weight:600;letter-spacing:.05em}
.qa button{display:flex;align-items:center;gap:9px;width:100%;padding:9px 10px;margin-bottom:6px;
  border:1px solid var(--line);border-radius:9px;background:#fffef9;font-size:12.5px;color:var(--ink);
  cursor:pointer;font-family:inherit;text-align:left}
.qa button:hover{border-color:var(--green3);background:#f4f8f2}
.qa button .ic{color:var(--green2)}
.quote{background:linear-gradient(160deg,#f0e7d3,#e7dcc2);border:1px solid #e0d3b8;border-radius:14px;
  padding:18px;color:#6c5a3d;font-family:"Noto Serif SC",Georgia,serif;font-size:13px;line-height:2;
  text-align:center;letter-spacing:.04em}

/* ---------- 卡片 / 列表 ---------- */
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);overflow:hidden}
.phead{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid var(--line)}
.phead h3{margin:0;font-size:14px}
.phead .more{margin-left:auto;font-size:12px;color:var(--green2);cursor:pointer}
.row{display:flex;align-items:center;gap:12px;padding:13px 18px;border-bottom:1px solid #f0e9da;cursor:pointer}
.row:last-child{border-bottom:0}
.row:hover{background:#fbf7ec}
.row .ic{width:26px;height:26px;border-radius:8px;background:#f2ece0;color:var(--green2);
  display:grid;place-items:center;font-size:13px;flex:none}
.row .tx{flex:1;min-width:0}
.row .tx .s{font-size:13px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .tx .m{font-size:11px;color:var(--muted);margin-top:1px}
.row .ts{font-size:11.5px;color:#a9a294;white-space:nowrap}

/* ---------- 标签 ---------- */
.badge{font-size:11px;padding:1px 9px;border-radius:20px;border:1px solid;white-space:nowrap;
  display:inline-block;line-height:1.8}
.badge.ok{color:#2f5d43;border-color:#bfd8c6;background:#f1f8f3}
.badge.wait{color:#8a5a00;border-color:#e5cf9f;background:#fdf6e6}
.badge.conf{color:#8c3b28;border-color:#e3c2b5;background:#fbeee8}
.badge.gray{color:#7c776b;border-color:#ded7c7;background:#f5f2e9}
.badge.dim{color:#8b8577;border-color:#e6ddcc;background:#faf7ef}
.cat{font-size:10.5px;color:#6b6558;background:#f2ece0;border-radius:6px;padding:0 6px;line-height:1.9}

/* ---------- 搜索 ---------- */
.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:2px 0 14px}
.chip{font-size:12px;padding:4px 12px;border-radius:18px;border:1px solid var(--line);
  background:var(--card);color:#6b6558;cursor:pointer;font-family:inherit}
.chip.on{background:var(--green);border-color:var(--green);color:#fff}
.chip:hover{border-color:var(--green3)}
.rescard{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:14px 18px;
  margin-bottom:10px;box-shadow:var(--shadow);cursor:pointer}
.rescard:hover{border-color:#cdbfa1}
.rescard .hd{display:flex;align-items:center;gap:9px;margin-bottom:5px}
.rescard .ti{font-family:"Noto Serif SC",Georgia,serif;font-size:14.5px;color:#3a332a}
.rescard .sn{font-size:12.5px;color:#6f6a5d;line-height:1.75;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.rescard .mt{display:flex;gap:14px;margin-top:8px;font-size:11px;color:#a9a294}

/* ---------- 表格（记忆库 / 资料） ---------- */
.tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.tbl th{text-align:left;font-weight:600;color:var(--muted);font-size:11.5px;padding:10px 14px;
  border-bottom:1px solid var(--line);background:#faf6ec}
.tbl td{padding:11px 14px;border-bottom:1px solid #f2ecdd;vertical-align:middle}
.tbl tr[data-id]{cursor:pointer}
.tbl tr[data-id]:hover{background:#fbf7ec}
.tbl .sum{max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.filter{width:190px;flex:none}
.filter h4{margin:0 0 8px;font-size:12px;color:var(--muted)}
.filter label{display:flex;align-items:center;gap:8px;font-size:12.5px;color:#5f5a4e;
  padding:5px 2px;cursor:pointer}
.libgrid{display:flex;gap:16px;align-items:flex-start}

/* ---------- 详情 ---------- */
.detailgrid{display:flex;gap:16px;align-items:flex-start}
.dcard{flex:1;min-width:0;background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:22px 24px;box-shadow:var(--shadow)}
.dcard .badges{display:flex;gap:8px;align-items:center;margin-bottom:10px}
.dcard h2{margin:0 0 14px;font-size:19px;line-height:1.6;color:#332c22}
.dsrc{display:flex;gap:12px;align-items:center;border:1px solid var(--line);border-radius:11px;
  padding:11px 13px;background:#fdfaf1;margin-bottom:14px}
.dsrc .ic{width:30px;height:32px;border-radius:6px;background:#f0e8d6;display:grid;place-items:center;color:#8a7c5f}
.dsrc .meta{flex:1;min-width:0}
.dsrc .meta .t{font-size:12.5px;font-weight:600}
.dsrc .meta .s{font-size:11px;color:var(--muted)}
.dmeta{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;font-size:11.5px;color:var(--muted);
  padding:12px 0;border-top:1px dashed var(--line);border-bottom:1px dashed var(--line);margin-bottom:14px}
.dmeta b{display:block;color:#4a4437;font-weight:600;font-size:12.5px;margin-top:2px}
.dacts{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.btn{padding:7px 16px;border:1px solid var(--line);border-radius:8px;background:#fffef9;
  font-size:12.5px;color:#4a4437;cursor:pointer;font-family:inherit}
.btn:hover{border-color:var(--green3);color:var(--green2)}
.btn.primary{background:var(--green);border-color:var(--green);color:#fff}
.btn.danger{color:var(--red);border-color:#e8cfc7}
.btn:disabled{opacity:.55;cursor:default}
.dtext{font-size:12.5px;color:#5f5a4e;line-height:1.95;background:#fdfaf1;border:1px solid var(--line);
  border-radius:11px;padding:13px 15px;white-space:pre-wrap;max-height:280px;overflow:auto}
.sidecol{width:300px;flex:none;display:flex;flex-direction:column;gap:12px}
.vtl{position:relative;padding-left:18px}
.vtl:before{content:"";position:absolute;left:5px;top:6px;bottom:6px;width:1px;background:#e2d8c4}
.vtn{position:relative;padding:8px 0 10px}
.vtn:before{content:"";position:absolute;left:-16px;top:13px;width:8px;height:8px;border-radius:50%;
  background:#cdbe9f;border:2px solid var(--card)}
.vtn.on:before{background:var(--green2)}
.vtn .h{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--muted)}
.vtn .s{font-size:12px;color:#4a4437;margin-top:3px;line-height:1.7}
.vtn .why{font-size:11px;color:#7d7768;margin-top:3px}
.relrow{display:flex;gap:8px;padding:9px 18px;border-bottom:1px solid #f2ecdd;cursor:pointer;font-size:12px}
.relrow:last-child{border-bottom:0}
.relrow:hover{background:#fbf7ec}
.auditrow{display:flex;gap:8px;font-size:11px;color:#7d7768;padding:6px 18px;border-bottom:1px dashed #f0e9da}
.auditrow .a{color:#4a4437}
.revrow{display:flex;gap:8px;align-items:center;padding:8px 18px;border-bottom:1px dashed #f0e9da;font-size:11.5px}
.revrow .txt{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#6f6a5d}
.mini{padding:2px 10px;font-size:11px;border:1px solid var(--line);border-radius:6px;background:#fffef9;
  cursor:pointer}
.mini:hover{border-color:var(--green3)}

/* ---------- 设置 ---------- */
.setwrap{max-width:900px}
.setcard{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;
  box-shadow:var(--shadow);margin-bottom:14px}
.setcard h3{margin:0 0 6px;font-size:14px}
.setcard .hint{font-size:12px;color:var(--muted);margin:0 0 14px;line-height:1.7}
.setcard input[type=text]{width:100%;padding:9px 12px;border:1px solid var(--line);border-radius:8px;
  font-size:13px;font-family:inherit;margin-bottom:8px;background:#fffef9}
.inputrow{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.inputrow input[type=text]{flex:1;min-width:200px;margin-bottom:0}
input[type=file]{font-size:12px;color:#6b6558}
.msg{font-size:12px;color:#6b6558;margin-top:10px;white-space:pre-wrap;display:none}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;margin-bottom:12px}
.seg button{border:0;background:#fffef9;padding:7px 15px;font-size:12.5px;color:#6b6558;cursor:pointer;
  font-family:inherit}
.seg button.on{background:var(--green);color:#fff}
.cleanrow{border:1px solid var(--line);border-radius:10px;padding:11px 13px;margin-bottom:8px;background:#fffef9}
.cleanrow .old{font-size:12px;color:#6f6a5d;line-height:1.7}
.cleanrow textarea{width:100%;margin-top:7px;padding:8px 10px;border:1px solid var(--line);
  border-radius:7px;font-size:12.5px;font-family:inherit;color:#4a4437;resize:vertical;background:#fff}
.cleanrow .acts{display:flex;gap:8px;margin-top:8px}
.sysrow{display:flex;justify-content:space-between;font-size:12.5px;padding:7px 0;
  border-bottom:1px dashed #f0e9da;color:#5f5a4e}
.sysrow:last-child{border-bottom:0}

/* ---------- 提示 ---------- */
#toasts{position:fixed;right:22px;bottom:22px;display:flex;flex-direction:column;gap:8px;z-index:99}
.toast{background:#2c3a2f;color:#f2f4ec;font-size:12.5px;padding:10px 16px;border-radius:10px;
  box-shadow:0 10px 26px rgba(30,40,30,.28);opacity:0;transform:translateY(8px);
  transition:.22s ease;max-width:340px}
.toast.on{opacity:1;transform:none}
.toast.err{background:#5c2a20}
.empty{padding:40px 18px;text-align:center;color:#a9a294;font-size:12.5px}
.spin{display:inline-block;width:12px;height:12px;border:2px solid #cfc6b3;border-top-color:var(--green2);
  border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px}
@keyframes sp{to{transform:rotate(360deg)}}

/* ---------- 手机 ---------- */
@media (max-width:920px){
  .app{flex-direction:column}
  .side{width:auto;height:auto;position:static;flex-direction:row;align-items:center;gap:6px;
    padding:10px 12px;overflow-x:auto}
  .brand{padding:0 10px 0 4px;font-size:15px;white-space:nowrap}
  .nav{flex-direction:row}
  .nav a{white-space:nowrap;padding:7px 10px}
  .side .foot{display:none}
  .homegrid,.detailgrid,.libgrid{flex-direction:column}
  .homeright,.sidecol,.filter{width:auto}
  .statgrid{grid-template-columns:repeat(2,1fr)}
  .hero{padding:26px 20px}
  .hero h1{font-size:23px}
  .wrap,.topbar{padding-left:14px;padding-right:14px}
}
</style></head><body>
<div class="app">
  <aside class="side">
    <div class="brand"><span class="mark">▤</span>Tinderbox</div>
    <nav class="nav">
      <a data-v="home"><span class="ic">⌂</span>首页</a>
      <a data-v="search"><span class="ic">⌕</span>记忆搜索</a>
      <a data-v="library"><span class="ic">▦</span>记忆库</a>
      <a data-v="sources"><span class="ic">▤</span>原始资料</a>
      <a data-v="settings"><span class="ic">⚙</span>设置</a>
    </nav>
    <div class="foot"><span class="leaf">❧</span>让重要的记忆<br>成为你行动的起点</div>
  </aside>

  <div class="main">
    <div class="topbar">
      <form class="searchbox" id="topsearch">
        <span style="color:#b3ab9b">⌕</span>
        <input id="q" placeholder="搜索记忆、对话、文件，或问一句…" autocomplete="off">
        <button class="go" type="submit">→</button>
      </form>
      <div class="who">你好，<b>主人</b></div>
    </div>

    <div class="wrap">
      <!-- 首页 -->
      <section class="view on" id="v-home">
        <div class="hero">
          <div class="kicker">Tinderbox</div>
          <h1>你的记忆，都在这里</h1>
          <p>记录 · 整理 · 连接 · 成长</p>
          <form id="herosearch">
            <input id="heroq" placeholder="试一试：我之前为什么决定 Tinderbox？">
            <button type="submit">→</button>
          </form>
          <div class="hue">知识是时间的沉淀<br>记忆是人生的底色</div>
        </div>

        <div class="homegrid">
          <div class="homeleft">
            <div class="statgrid" id="stats"></div>
            <div class="panel">
              <div class="phead"><h3>最近记忆</h3><span class="more" data-go="library">查看全部 →</span></div>
              <div id="recent"></div>
            </div>
          </div>
          <div class="homeright">
            <div class="qa">
              <h4>快捷操作</h4>
              <button data-go="settings"><span class="ic">⤒</span>导入资料</button>
              <button data-go="library"><span class="ic">▦</span>浏览记忆库</button>
              <button data-go="search"><span class="ic">⌕</span>搜索记忆</button>
            </div>
            <div class="quote">好的记忆<br>是留给未来的自己<br>的一句提醒</div>
          </div>
        </div>
      </section>

      <!-- 搜索 -->
      <section class="view" id="v-search">
        <div class="phead" style="padding:0 0 12px;border:0">
          <h2 style="margin:0;font-size:17px">记忆搜索</h2>
          <span id="srchint" style="margin-left:auto;font-size:12px;color:var(--muted)"></span>
        </div>
        <div class="toolbar" id="srchips"></div>
        <div id="srclist"></div>
      </section>

      <!-- 记忆库 -->
      <section class="view" id="v-library">
        <div class="libgrid">
          <div style="flex:1;min-width:0">
            <div class="panel">
              <div class="phead"><h3 id="libcount">记忆库</h3>
                <span class="more" data-go="settings">＋ 新建</span></div>
              <table class="tbl" id="libtable">
                <thead><tr><th>内容</th><th style="width:80px">类型</th>
                  <th style="width:90px">状态</th><th style="width:110px">更新时间</th></tr></thead>
                <tbody></tbody>
              </table>
            </div>
          </div>
          <div class="filter panel" style="padding:14px 16px">
            <h4>状态</h4>
            <div id="libstatus"></div>
            <h4 style="margin-top:12px">类型</h4>
            <div id="libcat"></div>
          </div>
        </div>
      </section>

      <!-- 原始资料 -->
      <section class="view" id="v-sources">
        <div class="detailgrid">
          <div class="dcard" style="padding:18px 20px">
            <div class="phead" style="padding:0 0 12px;border:0">
              <h3 id="srcCount">原始资料</h3>
              <span class="more" style="margin-left:auto" data-go="settings">＋ 导入</span>
            </div>
            <table class="tbl" id="srctable">
              <thead><tr><th>文件</th><th style="width:70px">记忆</th><th style="width:110px">导入时间</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
          <div class="sidecol">
            <div class="panel"><div class="phead"><h3 id="docTitle">选择一份资料</h3></div>
              <div id="docBody"><div class="empty">点左侧文件查看其中的记忆</div></div>
            </div>
          </div>
        </div>
      </section>

      <!-- 详情 -->
      <section class="view" id="v-detail">
        <div style="margin-bottom:10px"><button class="btn" id="backbtn">← 返回</button></div>
        <div class="detailgrid">
          <div class="dcard" id="detailcard"></div>
          <div class="sidecol" id="detailside"></div>
        </div>
      </section>

      <!-- 设置 -->
      <section class="view" id="v-settings">
        <div class="setwrap">
          <div class="setcard">
            <h3>导入</h3>
            <p class="hint">选择本机文件（.txt .md .docx .pdf），或按文件夹路径整批导入。
              记忆只从导入进来，不在面板里手写。</p>
            <div class="inputrow" style="margin-bottom:8px">
              <input type="file" id="upfiles" multiple>
              <button class="btn primary" id="upgo">上传并导入</button>
            </div>
            <div class="inputrow">
              <input type="text" id="proj" placeholder="项目名（留空=用文件夹名）">
              <label class="who"><input type="checkbox" id="dry"> 试跑</label>
            </div>
            <div class="msg" id="upmsg"></div>
            <details style="margin-top:12px">
              <summary style="font-size:12px;color:var(--muted);cursor:pointer">或者：按本机路径导入整个文件夹</summary>
              <div class="inputrow" style="margin-top:8px">
                <input type="text" id="imppath" placeholder="D:\笔记">
                <button class="btn" id="impgo">从路径导入</button>
                <button class="btn" id="impcancel" hidden>取消</button>
              </div>
              <div class="msg" id="impmsg"></div>
            </details>
          </div>

          <div class="setcard">
            <h3>清洗</h3>
            <p class="hint">规则提炼出的摘要比较糙；清洗把它改写成「结论 —— 因为依据」。
              自动清洗只给建议，采纳后才写入。</p>
            <div class="seg" id="cleanseg">
              <button data-cm="manual" class="on">手动清洗</button>
              <button data-cm="auto">自动清洗（需审核）</button>
              <button data-cm="none">不清洗</button>
            </div>
            <div id="cleanbody"></div>
          </div>

          <div class="setcard">
            <h3>备份</h3>
            <p class="hint">把数据库与原文打包到数据目录下的 backup/，保留最近 5 份。</p>
            <button class="btn primary" id="bakbtn">立即备份</button>
            <div class="msg" id="bakmsg"></div>
          </div>

          <div class="setcard">
            <h3>已归档 <span class="badge dim" id="archn" style="margin-left:6px"></span></h3>
            <p class="hint">归档只是从现行检索里移走，随时可以恢复。</p>
            <div id="archlist"></div>
          </div>

          <div class="setcard">
            <h3>系统状态</h3>
            <div id="sysinfo"></div>
          </div>
        </div>
      </section>
    </div>
  </div>
</div>
<div id="toasts"></div>

<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const CATNAME={decision:'决策',preference:'偏好',task:'计划',knowledge:'事实'};
const STNAME={active:'已确认',pending_merge:'待确认',archived:'已归档',superseded:'已过期'};
const STCLS={active:'ok',pending_merge:'wait',archived:'gray',superseded:'dim'};

function toast(msg,err){
  const el=document.createElement('div');
  el.className='toast'+(err?' err':''); el.textContent=msg;
  $('#toasts').appendChild(el);
  requestAnimationFrame(()=>el.classList.add('on'));
  setTimeout(()=>{ el.classList.remove('on'); setTimeout(()=>el.remove(),260); },2600);
}
async function api(path,opt){
  const r=await fetch(path,opt);
  const t=await r.text();
  let j={}; try{ j=JSON.parse(t); }catch(e){ throw new Error(t.slice(0,80)); }
  if(!r.ok || j.ok===false) throw new Error(j.error||('HTTP '+r.status));
  return j;
}
const post=(p,b)=>api(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});
function fmt(iso){ if(!iso) return ''; return String(iso).slice(0,10); }
function rel(iso){
  if(!iso) return '';
  const t=new Date(iso), d=Date.now()-t.getTime(), h=d/3.6e6;
  if(h<1) return Math.max(1,Math.round(d/6e4))+' 分钟前';
  if(h<24) return Math.round(h)+' 小时前';
  if(h<24*30) return Math.round(h/24)+' 天前';
  return fmt(iso);
}
function badge(it){
  const st=it.status||'active';
  return `<span class="badge ${STCLS[st]||'dim'}">${STNAME[st]||st}</span>`;
}
function catTag(c){ return `<span class="cat">${CATNAME[c]||c||'其他'}</span>`; }

/* ---------------- 导航 ---------------- */
let view='home', lastDetail=null;
function go(v){
  view=v;
  $$('.view').forEach(x=>x.classList.toggle('on', x.id==='v-'+v));
  $$('.nav a').forEach(a=>a.classList.toggle('on', a.dataset.v===v));
  if(v==='home') loadHome();
  if(v==='library') loadLibrary();
  if(v==='sources') loadSources();
  if(v==='settings'){ loadArch(); loadSys(); renderClean(); }
}
$$('.nav a').forEach(a=>a.onclick=()=>go(a.dataset.v));
$$('[data-go]').forEach(el=>el.onclick=()=>go(el.dataset.go));

/* ---------------- 首页 ---------------- */
async function loadHome(){
  try{
    const m=await api('/api/meta');
    $('#stats').innerHTML=`
      <div class="stat"><div class="t">✦ 已整理的记忆</div><div class="n">${m.total}</div>
        <div class="d">${m.active} 条现行</div></div>
      <div class="stat"><div class="t">▤ 原始资料</div><div class="n" id="stDocs">–</div>
        <div class="d">按块冷存</div></div>
      <div class="stat"><div class="t">◷ 待确认的清洗</div><div class="n">${m.provisional}</div>
        <div class="d">可在设置里处理</div></div>
      <div class="stat"><div class="t">⚑ 存在冲突</div><div class="n">${m.pending}</div>
        <div class="d">需要你裁决</div></div>`;
    const d=await api('/api/sources?limit=500');
    $('#stDocs').textContent=d.items.length;
    const r=await api('/api/recent?limit=6');
    $('#recent').innerHTML = r.items.length? r.items.map(it=>`
      <div class="row" data-id="${it.entry_id}">
        <div class="ic">${it.category==='decision'?'◆':it.category==='task'?'▢':it.category==='preference'?'❖':'▤'}</div>
        <div class="tx"><div class="s">${esc(it.l1_summary)}</div>
          <div class="m">${catTag(it.category)} <span style="margin-left:6px">${fmt(it.created_at)}</span></div></div>
        ${badge(it)}<div class="ts">${rel(it.created_at)}</div>
      </div>`).join('') : '<div class="empty">还没有记忆，去「设置 → 导入」放一些进来</div>';
    bindRows('#recent');
  }catch(e){ toast(e.message,true); }
}
function bindRows(sel){
  $$(sel+' .row[data-id], '+sel+' .rescard[data-id]').forEach(el=>{
    el.onclick=()=>openDetail(el.dataset.id);
  });
}

/* ---------------- 搜索 ---------------- */
let srchCat='all', srchQ='';
function srchChips(){
  const cats=[['all','全部'],['decision','决策'],['preference','偏好'],['task','计划'],['knowledge','事实']];
  $('#srchips').innerHTML = cats.map(([k,n])=>
    `<button class="chip ${srchCat===k?'on':''}" data-cat="${k}">${n}</button>`).join('');
  $$('#srchips .chip').forEach(b=>b.onclick=()=>{ srchCat=b.dataset.cat; renderSearch(); });
}
async function renderSearch(){
  srchChips();
  if(!srchQ){ $('#srclist').innerHTML='<div class="empty">输入关键词开始搜索</div>'; $('#srchint').textContent=''; return; }
  $('#srclist').innerHTML='<div class="empty"><span class="spin"></span> 搜索中…</div>';
  try{
    const d=await api('/api/search?q='+encodeURIComponent(srchQ)+'&mode=hybrid');
    let items=d.items;
    if(srchCat!=='all') items=items.filter(it=>it.category===srchCat);
    $('#srchint').textContent=`找到 ${items.length} 条 · ${d.ms} ms`;
    $('#srclist').innerHTML = items.length? items.map(it=>`
      <div class="rescard" data-id="${it.entry_id}">
        <div class="hd">${badge(it)}${catTag(it.category)}</div>
        <div class="ti">${esc(it.l1_summary)}</div>
        <div class="sn">${esc(it.l1_summary)}</div>
        <div class="mt"><span>${fmt(it.created_at)}</span>
          <span>相关度 ${Math.round((it.score||0)*100)}%</span>
          ${it.rel_count?`<span>相关 ${it.rel_count}</span>`:''}</div>
      </div>`).join('') : '<div class="empty">没有命中</div>';
    bindRows('#srclist');
  }catch(e){ $('#srclist').innerHTML='<div class="empty">'+esc(e.message)+'</div>'; }
}
function doSearch(q){ srchQ=(q||'').trim(); go('search'); renderSearch(); }
$('#topsearch').onsubmit=e=>{ e.preventDefault(); doSearch($('#q').value); };
$('#herosearch').onsubmit=e=>{ e.preventDefault(); doSearch($('#heroq').value); };

/* ---------------- 记忆库 ---------------- */
let libStatus='active', libCat='';
const STF=[['active','已确认'],['pending_merge','待确认'],['archived','已归档'],['all','全部']];
const CATF=[['','全部类型'],['decision','决策'],['preference','偏好'],['task','计划'],['knowledge','事实']];
async function loadLibrary(){
  $('#libstatus').innerHTML=STF.map(([k,n])=>
    `<label><input type="radio" name="ls" ${libStatus===k?'checked':''} data-k="${k}">${n}</label>`).join('');
  $('#libcat').innerHTML=CATF.map(([k,n])=>
    `<label><input type="radio" name="lc" ${libCat===k?'checked':''} data-k="${k}">${n}</label>`).join('');
  $$('#libstatus input').forEach(i=>i.onchange=()=>{ libStatus=i.dataset.k; loadLibrary(); });
  $$('#libcat input').forEach(i=>i.onchange=()=>{ libCat=i.dataset.k; loadLibrary(); });
  try{
    const st=libStatus==='all'?'active':libStatus;
    const d=await api('/api/list?status='+st+'&limit=200'+(libCat?'&category='+libCat:''));
    let items=d.items;
    if(libStatus==='all'){
      const a=await api('/api/list?status=archived&limit=200'+(libCat?'&category='+libCat:''));
      items=items.concat(a.items);
    }
    $('#libcount').textContent = `记忆库 · ${items.length} 条`;
    $('#libtable tbody').innerHTML = items.length? items.map(it=>`
      <tr data-id="${it.entry_id}">
        <td class="sum">${esc(it.l1_summary)}</td>
        <td>${catTag(it.category)}</td>
        <td>${badge(it)}</td>
        <td style="color:#a9a294">${fmt(it.created_at)}</td>
      </tr>`).join('') : '<tr><td colspan="4"><div class="empty">这里还没有记忆</div></td></tr>';
    $$('#libtable tbody tr[data-id]').forEach(tr=>tr.onclick=()=>openDetail(tr.dataset.id));
  }catch(e){ toast(e.message,true); }
}

/* ---------------- 原始资料 ---------------- */
async function loadSources(){
  try{
    const d=await api('/api/sources?limit=200');
    $('#srcCount').textContent=`原始资料 · ${d.items.length}`;
    $('#srctable tbody').innerHTML = d.items.length? d.items.map(it=>`
      <tr data-id="${it.doc_id}">
        <td class="sum">${esc(it.title)}</td>
        <td>${it.entry_count||0}</td>
        <td style="color:#a9a294">${fmt(it.created_at)}</td>
      </tr>`).join('') : '<tr><td colspan="3"><div class="empty">还没有资料，去设置里导入</div></td></tr>';
    $$('#srctable tbody tr[data-id]').forEach(tr=>tr.onclick=()=>openDoc(tr.dataset.id));
  }catch(e){ toast(e.message,true); }
}
async function openDoc(id){
  try{
    const d=await api('/api/doc?id='+encodeURIComponent(id));
    $('#docTitle').textContent=d.doc.title;
    $('#docBody').innerHTML = d.items.length? d.items.map(it=>`
      <div class="row" data-id="${it.entry_id}">
        <div class="tx"><div class="s">${esc(it.l1_summary)}</div>
          <div class="m">${catTag(it.category)}</div></div>${badge(it)}
      </div>`).join('') : '<div class="empty">这份材料还没提炼出记忆</div>';
    bindRows('#docBody');
  }catch(e){ toast(e.message,true); }
}

/* ---------------- 详情 ---------------- */
async function openDetail(id){
  lastDetail=id; go('detail');
  $('#detailcard').innerHTML='<div class="empty"><span class="spin"></span> 读取中…</div>';
  $('#detailside').innerHTML='';
  try{
    const d=await api('/api/entry?id='+encodeURIComponent(id));
    const o=d.origin||{};
    $('#detailcard').innerHTML=`
      <div class="badges">${badge(d)}${catTag(d.category)}<span style="font-size:11px;color:#a9a294">v${d.version_no}</span></div>
      <h2>${esc(d.l1_summary)}</h2>
      ${o.doc_title?`<div class="dsrc"><div class="ic">▤</div><div class="meta">
          <div class="t">${esc(o.doc_title)}</div>
          <div class="s">${o.project?'项目「'+esc(o.project)+'」':'来源材料'}</div></div></div>`:''}
      <div class="dmeta">
        <div>创建时间<b>${fmt(d.created_at)}</b></div>
        <div>记忆类型<b>${CATNAME[d.category]||d.category}</b></div>
        <div>精修状态<b>${d.extract_state==='refined'?'已精修':'规则提炼'}</b></div>
      </div>
      <div class="dacts">
        <button class="btn" id="d-edit">编辑</button>
        <button class="btn" id="d-arch">${d.status==='archived'?'恢复':'归档'}</button>
        <button class="btn danger" id="d-del">删除</button>
      </div>
      <div style="font-size:11.5px;color:var(--muted);margin-bottom:6px">原文片段</div>
      <div class="dtext">${esc(d.text||'（没有原文）')}</div>`;
    $('#d-edit').onclick=async()=>{
      const next=prompt('改摘要（会留痕，可回滚）', d.l1_summary);
      if(!next || next.trim()===d.l1_summary) return;
      try{ await post('/api/entry/update',{entry_id:id,summary:next.trim()});
        toast('已保存'); openDetail(id); }catch(e){ toast(e.message,true); }
    };
    $('#d-arch').onclick=async()=>{
      const to=d.status!=='archived';
      try{ await post('/api/entry/archive',{entry_id:id,archived:to});
        toast(to?'已归档':'已恢复'); openDetail(id); }catch(e){ toast(e.message,true); }
    };
    $('#d-del').onclick=async()=>{
      if(!confirm('彻底删除这条记忆？不可恢复。')) return;
      try{ await post('/api/entry/delete',{entry_id:id}); toast('已删除'); go('library'); }
      catch(e){ toast(e.message,true); }
    };

    const chain=(d.chain||[]).map(n=>`
      <div class="vtn ${n.status==='active'?'on':''}" data-id="${n.entry_id}">
        <div class="h"><b>v${n.version_no}</b><span>${STNAME[n.status]||n.status}</span>
          <span style="margin-left:auto">${fmt(n.created_at)}</span></div>
        <div class="s">${esc(n.l1_summary)}</div>
        ${n.reason?`<div class="why">为什么：${esc(n.reason)}</div>`:''}
      </div>`).join('');
    const rels=(d.relations||[]).map(r=>`
      <div class="relrow" data-id="${r.entry_id}">
        <span class="cat">${esc(r.relation)}</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.l1_summary)}</span>
      </div>`).join('');
    const revs=(d.revisions||[]).map(r=>`
      <div class="revrow"><span style="color:#a9a294">${fmt(r.at)}</span>
        <span class="txt" title="${esc(r.old)}">${esc(r.old)}</span>
        <button class="mini" data-rev="${r.revision_id}">回滚</button></div>`).join('');
    const auds=(d.audit||[]).map(a=>`
      <div class="auditrow"><span class="a">${esc(a.action)}</span>
        <span>${esc(a.actor)}</span><span style="margin-left:auto">${fmt(a.at)}</span></div>`).join('');

    $('#detailside').innerHTML=`
      <div class="panel"><div class="phead"><h3>版本历史</h3>
        ${d.chain&&d.chain.length>1?`<span class="badge dim" style="margin-left:auto">${d.chain.length} 版</span>`:''}</div>
        <div style="padding:10px 18px 14px"><div class="vtl">${chain||'<div class="empty" style="padding:10px 0">只有这一版</div>'}</div></div>
      </div>
      ${revs?`<div class="panel"><div class="phead"><h3>修改记录</h3></div>${revs}</div>`:''}
      ${rels?`<div class="panel"><div class="phead"><h3>相关记忆</h3></div>${rels}</div>`:''}
      ${auds?`<div class="panel"><div class="phead"><h3>操作轨迹</h3></div>${auds}</div>`:''}`;
    $$('#detailside .vtn[data-id]').forEach(x=>x.onclick=()=>openDetail(x.dataset.id));
    $$('#detailside .relrow[data-id]').forEach(x=>x.onclick=()=>openDetail(x.dataset.id));
    $$('#detailside .mini[data-rev]').forEach(b=>b.onclick=async()=>{
      try{ await post('/api/entry/revert',{entry_id:id,revision_id:b.dataset.rev});
        toast('已回滚'); openDetail(id); }catch(e){ toast(e.message,true); }
    });
  }catch(e){ $('#detailcard').innerHTML='<div class="empty">'+esc(e.message)+'</div>'; }
}
$('#backbtn').onclick=()=>go('library');

/* ---------------- 设置：导入 ---------------- */
function pollJob(jobId,msgEl,done){
  const timer=setInterval(async()=>{
    try{
      const j=await api('/api/import/status?id='+jobId);
      const J=j.job, pct=J.total?Math.round(J.done*100/J.total):0;
      msgEl.style.display='block';
      msgEl.textContent=`${J.state==='running'?'进行中':'完成'} ${J.done}/${J.total}（${pct}%）`
        +` · 新增 ${J.added} · 更新 ${J.updated} · 跳过 ${J.skipped} · 失败 ${J.failed} · ${J.entries} 条`
        +(J.project?` · 项目 ${J.project}`:'');
      if(J.state!=='running'){
        clearInterval(timer);
        if(J.failures&&J.failures.length) msgEl.textContent+='\n问题：'+J.failures.slice(0,5).join('；');
        if(done) done(J);
      }
    }catch(e){ clearInterval(timer); msgEl.textContent=e.message; }
  },600);
}
$('#upgo').onclick=async()=>{
  const files=[...($('#upfiles').files||[])], msg=$('#upmsg');
  msg.style.display='block';
  if(!files.length){ msg.textContent='先选择文件'; return; }
  msg.textContent='读取文件中…';
  const payload=[];
  for(const f of files){
    const buf=new Uint8Array(await f.arrayBuffer());
    let bin=''; for(let i=0;i<buf.length;i+=0x8000)
      bin+=String.fromCharCode.apply(null,buf.subarray(i,i+0x8000));
    payload.push({name:f.webkitRelativePath||f.name,b64:btoa(bin)});
  }
  msg.textContent=`上传 ${payload.length} 个文件…`;
  try{
    const j=await post('/api/upload',{files:payload,project:$('#proj').value.trim(),
      dry_run:$('#dry').checked});
    pollJob(j.job,msg,()=>{ loadHome(); });
  }catch(e){ msg.textContent=e.message; }
};
$('#impgo').onclick=async()=>{
  const msg=$('#impmsg'); msg.style.display='block'; msg.textContent='正在扫描…';
  const go=$('#impgo'), cancel=$('#impcancel'); go.disabled=true; cancel.hidden=false;
  let jobId=null;
  cancel.onclick=async()=>{ cancel.disabled=true;
    if(jobId) await post('/api/import/cancel',{id:jobId}); };
  try{
    const j=await post('/api/import',{path:$('#imppath').value.trim(),
      project:$('#proj').value.trim(), dry_run:$('#dry').checked});
    jobId=j.job;
    pollJob(jobId,msg,()=>{ go.disabled=false; cancel.hidden=true; loadHome(); });
  }catch(e){ msg.textContent=e.message; go.disabled=false; cancel.hidden=true; }
};

/* ---------------- 设置：清洗 ---------------- */
let cleanMode='manual';
function segBind(){
  $$('#cleanseg button').forEach(b=>b.onclick=()=>{
    cleanMode=b.dataset.cm;
    $$('#cleanseg button').forEach(x=>x.classList.toggle('on',x===b));
    renderClean();
  });
}
function renderClean(){
  segBind();
  const body=$('#cleanbody');
  if(cleanMode==='none'){
    body.innerHTML='<p class="hint">已选择不清洗：摘要保持规则提炼的样子，不改写、不调模型。</p>';
    return;
  }
  if(cleanMode==='manual'){ renderManual(); return; }
  body.innerHTML=`<p class="hint">模型只给建议，采纳后才写入；采纳前可以改。</p>
    <button class="btn primary" id="genclean">生成 5 条建议</button>
    <div id="proplist" style="margin-top:12px"></div>`;
  $('#genclean').onclick=async()=>{
    const b=$('#genclean'); b.disabled=true; b.textContent='生成中…';
    try{
      const j=await post('/api/clean/suggest',{limit:5});
      toast(`生成 ${j.result.suggested} 条 · 失败 ${j.result.failed} 条`);
      await renderProps();
    }catch(e){ toast(e.message,true); }
    b.disabled=false; b.textContent='生成 5 条建议';
  };
  renderProps();
}
async function renderManual(){
  const body=$('#cleanbody');
  try{
    const d=await api('/api/list?status=provisional&limit=50');
    if(!d.items.length){ body.innerHTML='<p class="hint">没有待清洗的记忆。</p>'; return; }
    body.innerHTML=d.items.map(it=>`
      <div class="cleanrow" data-id="${it.entry_id}">
        <div class="old">${esc(it.l1_summary)}</div>
        <textarea rows="2">${esc(it.l1_summary)}</textarea>
        <div class="acts">
          <button class="btn" data-act="save">保存</button>
          <button class="btn danger" data-act="del">删除</button>
        </div>
      </div>`).join('');
    $$('#cleanbody .cleanrow').forEach(row=>{
      const id=row.dataset.id, ta=row.querySelector('textarea');
      row.querySelector('[data-act=save]').onclick=async()=>{
        const v=ta.value.trim(); if(v.length<6){ toast('太短了',true); return; }
        try{ await post('/api/entry/update',{entry_id:id,summary:v}); toast('已保存');
          renderManual(); loadHome(); }catch(e){ toast(e.message,true); }
      };
      row.querySelector('[data-act=del]').onclick=async()=>{
        if(!confirm('彻底删除这条记忆？不可恢复。')) return;
        try{ await post('/api/entry/delete',{entry_id:id}); toast('已删除');
          renderManual(); loadHome(); }catch(e){ toast(e.message,true); }
      };
    });
  }catch(e){ body.innerHTML='<p class="hint">'+esc(e.message)+'</p>'; }
}
async function renderProps(){
  const list=$('#proplist'); if(!list) return;
  try{
    const d=await api('/api/clean/list?state=pending');
    if(!d.items.length){ list.innerHTML='<p class="hint">没有待审建议。</p>'; return; }
    list.innerHTML=d.items.map(it=>`
      <div class="cleanrow" data-pid="${it.proposal_id}">
        <div class="old">原：${esc(it.old_summary)}</div>
        <textarea rows="2">${esc(it.new_summary)}</textarea>
        <div class="acts">
          <button class="btn primary" data-act="ok">采纳</button>
          <button class="btn" data-act="edit">采用上面这版</button>
          <button class="btn" data-act="no">忽略</button>
        </div>
      </div>`).join('');
    $$('#proplist .cleanrow').forEach(row=>{
      const pid=row.dataset.pid, ta=row.querySelector('textarea');
      const done=async(fn)=>{ try{ await fn(); await renderProps(); loadHome(); }
        catch(e){ toast(e.message,true); } };
      row.querySelector('[data-act=ok]').onclick=()=>done(()=>post('/api/clean/apply',{proposal_id:pid}));
      row.querySelector('[data-act=edit]').onclick=()=>done(()=>post('/api/clean/apply',
        {proposal_id:pid,summary:ta.value.trim()}));
      row.querySelector('[data-act=no]').onclick=()=>done(()=>post('/api/clean/reject',{proposal_id:pid}));
    });
  }catch(e){ list.innerHTML='<p class="hint">'+esc(e.message)+'</p>'; }
}

/* ---------------- 设置：备份 / 归档 / 系统 ---------------- */
$('#bakbtn').onclick=async()=>{
  const b=$('#bakbtn'), m=$('#bakmsg'); b.disabled=true; m.style.display='block'; m.textContent='备份中…';
  try{
    const j=await post('/api/backup',{keep:5});
    m.textContent=`已备份 ${j.result.counts.entries} 条 · 校验${j.result.ok?'通过':'不通过'}\n${j.result.dest}`;
  }catch(e){ m.textContent=e.message; }
  b.disabled=false;
};
async function loadArch(){
  try{
    const d=await api('/api/list?status=archived&limit=200');
    $('#archn').textContent=d.items.length?d.items.length:'';
    $('#archlist').innerHTML=d.items.length? d.items.map(it=>`
      <div class="relrow" data-id="${it.entry_id}">
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(it.l1_summary)}</span>
        <button class="mini" data-restore="${it.entry_id}">恢复</button>
      </div>`).join('') : '<p class="hint">还没有归档的记忆。</p>';
    $$('#archlist [data-restore]').forEach(b=>b.onclick=async e=>{
      e.stopPropagation();
      try{ await post('/api/entry/archive',{entry_id:b.dataset.restore,archived:false});
        toast('已恢复'); loadArch(); loadHome(); }catch(err){ toast(err.message,true); }
    });
    $$('#archlist .relrow[data-id]').forEach(r=>r.onclick=()=>openDetail(r.dataset.id));
  }catch(e){ /* 静默 */ }
}
async function loadSys(){
  try{
    const m=await api('/api/meta'), s=await api('/api/sources?limit=1');
    const docs=await api('/api/sources?limit=500');
    $('#sysinfo').innerHTML=`
      <div class="sysrow"><span>记忆条目</span><b>${m.total}</b></div>
      <div class="sysrow"><span>现行 / 待确认 / 已归档</span><b>${m.active} / ${m.pending} / ${m.archived}</b></div>
      <div class="sysrow"><span>待清洗</span><b>${m.provisional}</b></div>
      <div class="sysrow"><span>原始资料</span><b>${docs.items.length}</b></div>
      <div class="sysrow"><span>健康检查</span><b><a href="/healthz" target="_blank">/healthz</a></b></div>`;
  }catch(e){ $('#sysinfo').innerHTML='<p class="hint">'+esc(e.message)+'</p>'; }
}

/* ---------------- 启动 ---------------- */
loadHome();
</script></body></html>"""


LOGIN_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tinderbox</title><style>
body{margin:0;height:100vh;display:grid;place-items:center;background:#f5efe3;
  font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif;color:#2c2a25;
  background-image:radial-gradient(700px 300px at 70% 0%,#fbf5e6,transparent 70%)}
form{background:#fffdf7;border:1px solid #e6ddcc;border-radius:16px;padding:30px 32px;width:320px;
  box-shadow:0 12px 40px rgba(58,44,28,.10)}
.mark{width:34px;height:34px;border-radius:9px;background:#1f3a2b;color:#f0e6d2;display:grid;
  place-items:center;font-size:16px;margin-bottom:14px}
h1{font-family:"Noto Serif SC",Georgia,serif;font-size:18px;margin:0 0 4px;color:#1f3a2b}
p{color:#8b8577;font-size:12px;margin:0 0 16px;line-height:1.7}
input{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #e6ddcc;border-radius:8px;
  font-size:13px;margin-bottom:10px;background:#fffdf7;font-family:inherit}
input:focus{outline:none;border-color:#2f5d43}
button{width:100%;padding:10px;border:0;border-radius:8px;background:#1f3a2b;color:#fff;
  font-size:13px;cursor:pointer;font-family:inherit}
#err{color:#a8442c;font-size:12px;margin:0 0 10px}
</style></head><body>
<form method="post" action="/login">
<div class="mark">▤</div>
<h1>Tinderbox</h1>
<p>需要访问令牌（数据目录的 token.txt，或 demo/.env 的 API_TOKEN）</p>
<p id="err"></p>
<input name="token" type="password" placeholder="粘贴令牌" autofocus>
<button type="submit">进入</button>
</form>
<script>
const e = new URLSearchParams(location.search).get('e');
const box = document.getElementById('err');
if (e === '1') box.textContent = '令牌不对：服务器用的是数据目录里的 token.txt';
if (e === '2') box.textContent = '请输入令牌';
</script>
</body></html>"""
