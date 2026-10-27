"""极简看板：搜索 L1，点开看原文片段。零依赖（stdlib http.server）。

跑法：  python demo/web.py      → http://127.0.0.1:8777
"""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import sys
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402

_data = os.environ.get("TB_DATA")
if _data:
    tb.DB_PATH = Path(_data) / "memory.db"
    tb.ARCHIVE = Path(_data) / "l0"


PORT = int(os.environ.get('TB_PORT') or 8777)
ENV_FILE = Path(__file__).resolve().parent / ".env"


def _load_token() -> str:
    """优先环境变量，其次 .env 的 API_TOKEN，最后生成一个并写回 .env。"""
    tok = os.environ.get("TB_TOKEN")
    if not tok:
        _tf = Path(os.environ.get("TB_DATA", "")) / "token.txt" if os.environ.get("TB_DATA") else None
        if _tf and _tf.exists():
            tok = _tf.read_text(encoding="utf-8").strip()
    if tok:
        return tok
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    m = re.search(r"^API_TOKEN=(\S+)", text, re.M)
    if m:
        return m.group(1)
    tok = secrets.token_urlsafe(18)
    line = f"\n# 看板访问令牌（自动生成；删掉此行会换一个）\nAPI_TOKEN={tok}\n"
    ENV_FILE.write_text(text + line, encoding="utf-8")
    print("⚠ 已生成访问令牌并写入 demo/.env（API_TOKEN=...）")
    return tok


TOKEN = _load_token()
# 限流：同一 IP 每分钟最多 N 次；连续 5 次错令牌则封 60 秒
RATE = {}
MAX_PER_MIN = 120
FAIL_LIMIT, FAIL_WINDOW = 5, 60


def _client_ip(handler) -> str:
    return handler.client_address[0] if handler.client_address else "-"


def _rate_blocked(ip: str) -> bool:
    now = time.time()
    hits = [t for t in RATE.get((ip, "all"), []) if now - t < 60]
    RATE[(ip, "all")] = hits + [now]
    return len(hits) >= MAX_PER_MIN


def _fail_blocked(ip: str) -> bool:
    now = time.time()
    hits = [t for t in RATE.get((ip, "fail"), []) if now - t < FAIL_WINDOW]
    RATE[(ip, "fail")] = hits
    return len(hits) >= FAIL_LIMIT


def _note_fail(ip: str):
    RATE.setdefault((ip, "fail"), []).append(time.time())

PAGE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Tinderbox · 记忆库</title>
<style>
 :root{--ink:#1a1a1a;--muted:#6b778a;--line:#e3e8ef;--navy:#1f3864;--blue:#2e5496;--bg:#fbfcfe}
 *{box-sizing:border-box}
 body{margin:0;font-family:"Segoe UI","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
 header{padding:20px 28px 14px;border-bottom:1px solid var(--line);background:#fff}
 h1{margin:0;font-size:20px;color:var(--navy);letter-spacing:.5px}
 .sub{color:var(--muted);font-size:12px;margin-top:6px}
 main{display:flex;gap:18px;padding:18px 28px;align-items:flex-start}
 .col{flex:1;min-width:0}
 .bar{display:flex;gap:8px;align-items:center}
 input[type=text]{flex:1;padding:11px 14px;border:1px solid var(--line);border-radius:8px;
   font-size:14px;outline:none;background:#fff}
 input[type=text]:focus{border-color:var(--blue)}
 .modes{display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff}
 .modes button{border:0;background:#fff;padding:11px 14px;font-size:13px;color:var(--muted);
   cursor:pointer;font-family:inherit}
 .modes button.on{background:var(--navy);color:#fff}
 .hint{color:var(--muted);font-size:12px;margin:8px 2px}
 .card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-top:10px;
   cursor:pointer;transition:.12s}
 .card:hover{border-color:var(--blue);box-shadow:0 2px 10px rgba(46,84,150,.08)}
 .card.sel{border-color:var(--blue);box-shadow:0 0 0 2px rgba(46,84,150,.12)}
 .row{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
 .l1{font-size:14px;line-height:1.6}
 .score{text-align:right;white-space:nowrap;line-height:1.5}
 .score b{display:block;font-size:13px;color:var(--blue);font-weight:600}
 .score span{font-size:11px;color:var(--muted)}
 .tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:20px;background:#eef3fa;
   color:var(--blue);margin-right:6px}
 .tag.decision{background:#eaf2ea;color:#2f6b4f}
 .tag.task{background:#fdf3e6;color:#9a5b18}
 .tag.preference{background:#f0eefa;color:#53408f}
 .tag.gone{background:#f2f3f5;color:#8a94a6}
 .l1.dead{color:#9aa3b2}
 .l1.dead *{text-decoration:line-through}
 .tag.pending{background:#fdf0e3;color:#a35a12;font-weight:600}
 .detail{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px;position:sticky;top:18px}
 .detail h3{margin:0 0 8px;font-size:14px;color:var(--navy)}
 .meta{color:var(--muted);font-size:12px;margin-bottom:10px;font-family:Consolas,monospace}
 pre{white-space:pre-wrap;word-break:break-word;background:#f6f7f9;border-left:3px solid #9aa7b8;
   padding:12px;border-radius:6px;font-size:13px;line-height:1.8;margin:0;max-height:62vh;overflow:auto;
   font-family:"Microsoft YaHei",Consolas,monospace}
 .empty{color:var(--muted);font-size:13px;padding:24px 0;text-align:center}
 .grp{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-top:10px}
 .grp .tl{display:flex;align-items:stretch;gap:0;overflow-x:auto;padding-bottom:4px}
 .step{min-width:190px;max-width:260px;border-left:2px solid var(--line);padding:0 10px 0 12px;
   cursor:pointer;border-radius:0 6px 6px 0}
 .step:hover{background:#f7f9fc}
 .step.on{border-left-color:var(--navy)}
 .step.gone{opacity:.62}
 .step .t{font-size:11px;color:var(--muted);font-family:Consolas,monospace}
 .step .h{font-size:11px;margin:2px 0 3px}
 .step .v{font-weight:700;color:var(--navy);margin-right:6px}
 .step .s{font-size:12.5px;line-height:1.55;color:#3a4454}
 .step .ctx{font-size:11px;color:#7d889b;background:#f6f8fb;border-radius:4px;
   padding:3px 6px;margin:3px 0;line-height:1.5}
 .step.gone .s{text-decoration:line-through;color:#9aa3b2}
 .arrow{align-self:center;color:#c3cbd8;font-size:14px;padding:0 2px}
 .rel{margin:2px 0 14px;border-left:2px solid #dbe6d6;padding-left:16px}
 .rel h4{margin:0 0 8px -18px;font-size:11px;letter-spacing:1px;color:#5f7a55;
   font-weight:600;background:#fff;padding:2px 0}
 .relrow{display:flex;gap:7px;align-items:baseline;padding:5px 6px;border-radius:6px;cursor:pointer}
 .relrow:hover{background:#f6faf4}
 .rtag{font-size:10px;color:#4f7a3f;background:#eef6e9;border-radius:10px;padding:1px 7px;
   white-space:nowrap}
 .rs{font-size:12.5px;color:#3a4454;line-height:1.5}
 .rc{margin-left:auto;font-size:11px;color:#8a94a6;font-family:Consolas,monospace}
 .relcount{display:block;font-size:10px;color:#4f7a3f}
 .ctxbox{margin:0 0 8px}
 .ticker{display:flex;align-items:baseline;gap:9px;padding:6px 2px;border-bottom:1px solid var(--line);
   cursor:pointer;overflow:hidden}
 .tk-label{font-size:11px;color:#8a97ab;letter-spacing:.04em;flex:none}
 .tk-body{flex:1;min-width:0;font-size:12.5px;color:#33405a;
   white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
   opacity:1;transform:translateY(0);
   transition:opacity .22s ease, transform .22s ease}
 .tk-body.out{opacity:0;transform:translateY(-4px)}
 .tk-why{flex:none;font-size:10.5px;color:#a3b0c2;max-width:34%;white-space:nowrap;
   overflow:hidden;text-overflow:ellipsis}
 .tk-badge{flex:none;font-size:10.5px;color:#8a5a00;background:#fdf3e0;border-radius:8px;padding:1px 6px}
 .ticker:hover .tk-body{color:#1f2b40}
 .cf{background:#fff;border:1px solid var(--line);border-left:3px solid #e8a33d;
   border-radius:10px;padding:12px 14px;margin-top:10px}
 .cfh{display:flex;align-items:center;gap:8px;margin-bottom:8px}
 .cfh .rtag{font-size:10px;color:#8a5a00;background:#fdf3e0;border-radius:10px;padding:1px 8px}
 .cfrow{display:flex;gap:8px;margin:5px 0}
 .cfrow .lbl{font-size:10px;color:#8a94a6;border:1px solid var(--line);border-radius:4px;
   padding:0 5px;height:18px;line-height:18px;flex:0 0 auto}
 .cfrow .lbl.new{color:#1f3864;border-color:#c9d6ec;background:#eef3fa}
 .cfrow .txt{font-size:13px;line-height:1.55;color:#3a4454}
 .cfwhy{font-size:11.5px;color:#7d889b;margin:8px 0 10px;padding-left:2px}
 .cfbtns{display:flex;gap:8px;flex-wrap:wrap}
 .cfbtns button{font-family:inherit;font-size:12px;border-radius:6px;padding:5px 12px;
   cursor:pointer;border:1px solid var(--line);background:#fff;color:#3a4454}
 .cfbtns button:hover{border-color:var(--blue)}
 .cfbtns button[data-res="supersede"]{background:var(--navy);color:#fff;border-color:var(--navy)}
 .cfbtns button[data-res="supersede"]:hover{opacity:.9}
 #cfn{margin-left:5px;background:#e8a33d;color:#fff;border-radius:8px;padding:0 5px;font-size:10px}
 #cfn:empty{display:none}
 .cols{display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap;margin-top:10px}
 .colbox{flex:1 1 300px;min-width:290px;max-width:100%;background:#fff;border:1px solid var(--line);
   border-radius:10px;overflow:hidden}
 .colhead{display:flex;align-items:center;gap:8px;padding:11px 14px;cursor:pointer;
   background:#f7f9fc;border-bottom:1px solid var(--line);user-select:none}
 .colhead:hover{background:#eef3fa}
 .colhead .nm{font-weight:600;font-size:13.5px;color:var(--navy)}
 .colhead .n{font-size:11px;color:#fff;background:var(--navy);border-radius:10px;padding:1px 7px}
 .colhead .cv{margin-left:auto;color:#8a94a6;font-size:11px;transition:.15s}
 .colhead.open .cv{transform:rotate(90deg)}
 .colbody{padding:8px 14px 14px;display:none}
 .colbody.open{display:block}
 .netfilter{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 0}
 .fchip{border:1px solid var(--line);background:#fff;border-radius:20px;padding:3px 11px;
   font-size:11.5px;color:#5f6b7e;cursor:pointer;font-family:inherit}
 .fchip:hover{border-color:var(--blue)}
 .fchip.on{background:var(--navy);color:#fff;border-color:var(--navy)}
 .ghead{display:flex;align-items:center;gap:6px;margin:10px 0 2px;padding:4px 6px;
   border-radius:6px;cursor:pointer;user-select:none}
 .ghead:hover{background:#f6f8fb}
 .ghead .cv{color:#a8b2c1;font-size:10px;transition:.15s;display:inline-block}
 .ghead.open .cv{transform:rotate(90deg)}
 .ghead .gn{font-size:12px;font-weight:600;color:#5f6b7e}
 .ghead .gc{font-size:10.5px;color:#8a94a6;background:#f2f4f8;border-radius:10px;padding:0 6px}
 .erow{display:flex;gap:7px;align-items:baseline;padding:5px 6px 5px 18px;border-radius:6px;
   cursor:pointer}
 .erow:hover{background:#f6f8fb}
 .erow .es{font-size:12.5px;line-height:1.55;color:#3a4454;flex:1}
 .erow .ed{font-size:10.5px;color:#9aa3b2;font-family:Consolas,monospace;white-space:nowrap}
 .erow.dead .es{color:#9aa3b2;text-decoration:line-through}
 .chain{margin:4px 0 14px;border-left:2px solid var(--line);padding-left:16px}
 .chain h4{margin:0 0 10px -18px;font-size:11px;letter-spacing:1px;color:var(--muted);
   font-weight:600;background:#fff;padding:2px 0}
 .node{position:relative;padding:2px 0 12px;cursor:pointer;border-radius:6px}
 .node:hover{background:#f7f9fc}
 .node:before{content:'';position:absolute;left:-22px;top:7px;width:8px;height:8px;
   border-radius:50%;background:#c9d2df;box-shadow:0 0 0 3px #fff}
 .node.on:before{background:var(--navy)}
 .node .head{display:flex;gap:8px;align-items:baseline;font-size:12px}
 .node .ver{font-weight:700;color:var(--navy)}
 .node .st{font-size:11px;color:var(--muted)}
 .node .ts{margin-left:auto;font-size:11px;color:var(--muted);font-family:Consolas,monospace}
 .node .gap{font-size:10px;color:#7d889b;background:#f0f3f8;padding:1px 6px;
   border-radius:10px;margin-left:6px}
 .node .sum{font-size:12.5px;color:#3a4454;margin-top:3px;line-height:1.6}
 .node.gone .sum{color:#9aa3b2;text-decoration:line-through}
 .node.gone .ver{color:#8a94a6}
</style></head><body>
<header><h1>Tinderbox · 记忆库</h1>
 <div class="sub">L1 摘要 · L0 原文 · 中文检索 · 版本链</div></header>
<main>
 <div class="col">
  <div class="bar">
    <input id="q" type="text" placeholder="检索" autofocus>
    <div class="modes" id="modes">
      <button data-mode="chains">演变</button>
      <button data-mode="net">星网</button>
      <button data-mode="conflicts">冲突<span id="cfn"></span></button>
    </div>
  </div>
  <div class="ctxbox" id="ctx"></div>
<div class="hint" id="hint">回车检索 · 历史含归档与旧版本</div>
  <div id="list"></div>
 </div>
 <div class="col" style="max-width:46%">
  <div class="detail" id="detail"><h3>原文片段</h3>
   <div class="meta">点任一条：上方版本链，下方原文片段。</div>
   <pre id="span">（尚未选择）</pre></div>
 </div>
</main>
<script>
const $=s=>document.querySelector(s);
let mode='search';
function setMode(m){
  mode=m;
  document.querySelectorAll('#modes button').forEach(x=>x.classList.toggle('on',x.dataset.mode===m));
}
document.querySelectorAll('#modes button').forEach(b=>b.onclick=()=>{ setMode(b.dataset.mode); search(); });
async function search(keepSel){
  if(mode==='chains'){ return renderChains(); }
  if(mode==='net'){ return renderNet(); }
  if(mode==='conflicts'){ return renderConflicts(); }
  mode='search';
  const q=$('#q').value.trim();
  if(!q){$('#list').innerHTML='';$('#hint').textContent='输入词后回车';return;}
  const r=await fetch(`/api/search?q=${encodeURIComponent(q)}&mode=hybrid`);
  const d=await r.json();
  const hist = d.items.filter(i=>i.status!=='active').length;
  $('#hint').textContent = d.items.length
      ? `${d.items.length} 条${hist ? ` · ${hist} 条旧版本` : ''} · ${d.ms} ms`
      : '没有命中';
  if(!d.items.length){$('#list').innerHTML='<div class="empty">没有命中</div>';return;}
  $('#list').innerHTML = d.items.map(it=>`
    <div class="card" data-id="${it.entry_id}">
      <div class="row">
        <div class="l1 ${it.status==='active'?'':'dead'}"><span class="tag ${it.status==='active'?it.category:(it.status==='pending_merge'?'pending':'gone')}">${
            it.status==='active'?it.category:(it.status==='pending_merge'?'待裁决':it.status)}</span>${esc(it.l1_summary)}</div>
        <div class="score"><b>${it.score.toFixed(3)}</b><span>${fmt(it.created_at)}</span>
          ${it.rel_count ? `<span class="relcount">相关 ${it.rel_count}</span>` : ''}</div>
      </div>
    </div>`).join('');
  document.querySelectorAll('.card').forEach(c=>c.onclick=()=>open(c.dataset.id, c));
  if(!keepSel){ const f=document.querySelector('.card'); open(f.dataset.id, f); }
}
async function open(id, card){
  document.querySelectorAll('.card').forEach(c=>c.classList.toggle('sel', c===card));
  const r=await fetch('/api/entry?id='+encodeURIComponent(id));
  const d=await r.json();
  const chain=(d.chain||[]).map((n,i)=>{
    const gone=n.status!=='active';
    const gap=i===0?'':`<span class="gap">+${fmtGap(n.gap_days)}</span>`;
    return `<div class="node ${gone?'gone':'on'}" data-id="${n.entry_id}">
      <div class="head"><span class="ver">v${n.version_no}</span>
        <span class="st">${esc(n.status)}</span>${gap}
        <span class="ts">${fmtFull(n.created_at)}</span></div>
      <div class="sum">${esc(n.l1_summary)}</div></div>`;
  }).join('');
  const st = d.status==='pending_merge' ? '待裁决' : d.status;
  $('#detail').innerHTML=`<h3>${esc(d.category)} · v${d.version_no} · ${esc(st)}</h3>
    <div class="meta">${d.entry_id}<br>创建 ${fmtFull(d.created_at)}<br>
      L0 区间 [${d.offset}, ${d.offset+d.length}) · ${d.length} 字</div>
    ${d.chain && d.chain.length>1 ? `<div class="chain"><h4>版本链</h4>${chain}</div>`:''}
    ${(d.relations && d.relations.length) ? `<div class="rel"><h4>相关记忆</h4>${
      d.relations.map(r=>`<div class="relrow" data-id="${r.entry_id}">
        <span class="rtag">${esc(r.relation)}</span>
        <span class="rs">${esc(r.l1_summary)}</span>
        <span class="rc">${r.confidence.toFixed(2)}</span></div>`).join('')}</div>`:''}
    <pre>${esc(d.text)}</pre>`;
  document.querySelectorAll('.relrow').forEach(el=>el.onclick=()=>open(el.dataset.id));
  document.querySelectorAll('.node').forEach(n=>n.onclick=()=>open(n.dataset.id));
}
function fmtGap(g){ if(g==null) return '';
  if(g<1) return `${Math.max(1,Math.round(g*24))} 小时`;
  return `${Math.round(g)} 天`; }
let openCols = {}, openGroups = {}, netCache = {}, netFilter = 'all';

let ctxItems=[], ctxIdx=0, ctxTimer=null;
function ctxShow(i){
  const m=ctxItems[i]; if(!m) return;
  const body=$('#tkbody'), why=$('#tkwhy');
  if(!body) return;
  body.classList.add('out');
  setTimeout(()=>{
    body.textContent=m.l1_summary;
    if(why) why.textContent=m.why||'';
    $('#ctxticker').dataset.id=m.entry_id;
    body.classList.remove('out');
  },200);
}
function ctxStart(){
  clearInterval(ctxTimer);
  if(ctxItems.length<2) return;
  ctxTimer=setInterval(()=>{ ctxIdx=(ctxIdx+1)%ctxItems.length; ctxShow(ctxIdx); },6000);
}
async function renderContext(){
  const el=$('#ctx');
  try{
    const d=await (await fetch('/api/context?k=4')).json();
    if(!d.memories || !d.memories.length){ el.innerHTML=''; return; }
    ctxItems=d.memories; ctxIdx=0;
    const badge=d.pending_conflicts
      ? `<span class="tk-badge">${d.pending_conflicts} 待裁决</span>` : '';
    el.innerHTML=`<div class="ticker" id="ctxticker" title="点开详情">
        <span class="tk-label">浮现</span>
        <span class="tk-body" id="tkbody"></span>
        <span class="tk-why" id="tkwhy"></span>${badge}
      </div>`;
    ctxShow(0);
    ctxStart();
    const box=$('#ctxticker');
    box.onclick=()=>{ if(box.dataset.id) open(box.dataset.id); };
    box.onmouseenter=()=>clearInterval(ctxTimer);
    box.onmouseleave=ctxStart;
  }catch(e){ el.innerHTML=''; }
}
async function renderConflicts(){
  const d=await (await fetch('/api/conflicts')).json();
  $('#hint').textContent = d.items.length
    ? `待裁决 ${d.items.length} 处：规则和模型都认为可能覆盖，最终由你定`
    : '没有待裁决的冲突';
  if(!d.items.length){
    $('#list').innerHTML='<div class="empty">全部裁决完了</div>'; return;
  }
  $('#list').innerHTML = d.items.map(c=>`
    <div class="cf" data-cid="${c.conflict_id}">
      <div class="cfh"><span class="rtag">${esc(c.relation)}</span>
        <span class="rc">置信 ${(c.confidence||0).toFixed(2)}</span></div>
      <div class="cfrow"><span class="lbl">旧</span><span class="txt">${esc((c.old&&c.old.l1_summary)||'')}</span></div>
      <div class="cfrow"><span class="lbl new">新</span><span class="txt">${esc((c.new&&c.new.l1_summary)||'')}</span></div>
      <div class="cfwhy">${esc(c.reason||'')}</div>
      <div class="cfbtns">
        <button data-res="supersede">旧作废，新版接管</button>
        <button data-res="keep_both">两条都留</button>
        <button data-res="ignore">忽略</button>
      </div>
    </div>`).join('');
  document.querySelectorAll('.cfbtns button').forEach(b=>b.onclick=async(ev)=>{
    const cid=ev.target.closest('.cf').dataset.cid;
    const res=b.dataset.res;
    b.disabled=true; b.textContent='处理中…';
    const r=await fetch('/api/conflicts/resolve',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({conflict_id:cid,resolution:res})});
    const j=await r.json();
    if(!j.ok){ alert('失败：'+j.error); b.disabled=false; return; }
    await renderConflicts();
  });
}
async function renderNet(){
  const d=await (await fetch('/api/concepts')).json();
  const by={};
  d.items.forEach(x=>{ (by[x.parent_id]=by[x.parent_id]||[]).push(x); });
  const kids=id=>by[id]||[];
  const rollup=x=>x.direct + kids(x.concept_id).reduce((a,k)=>a+rollup(k),0);
  const roots=kids(null);

  $('#hint').textContent = roots.length
    ? `${roots.length} 个项目 · 点标题展开，点分组再看具体记忆`
    : '还没有概念';
  if(!roots.length){ $('#list').innerHTML='<div class="empty">没有概念</div>'; return; }

  const cats=['all','decision','task','knowledge','preference'];
  $('#list').innerHTML =
    `<div class="netfilter">${cats.map(k=>`<button class="fchip ${netFilter===k?'on':''}"
        data-cat="${k}">${k==='all'?'全部':k}</button>`).join('')}</div>` +
    `<div class="cols">${roots.map(r=>`
      <div class="colbox">
        <div class="colhead ${openCols[r.name]?'open':''}" data-root="${esc(r.name)}">
          <span class="nm">${esc(r.name)}</span><span class="n">${rollup(r)}</span>
          <span class="cv">▸</span></div>
        <div class="colbody ${openCols[r.name]?'open':''}" data-col="${esc(r.name)}"></div>
      </div>`).join('')}</div>`;

  document.querySelectorAll('.fchip').forEach(b=>b.onclick=()=>{
    netFilter=b.dataset.cat;
    document.querySelectorAll('.fchip').forEach(x=>x.classList.toggle('on',x===b));
    document.querySelectorAll('.colbody.open').forEach(el=>paintCol(el, el.dataset.col));
  });

  document.querySelectorAll('.colhead').forEach(h=>h.onclick=async()=>{
    const name=h.dataset.root;
    openCols[name]=!openCols[name];
    h.classList.toggle('open', openCols[name]);
    const body=h.parentElement.querySelector('.colbody');
    body.classList.toggle('open', openCols[name]);
    if(openCols[name]) await fillCol(body, name);
  });

  for(const r of roots){
    if(openCols[r.name]){
      const body=document.querySelector(`.colbody[data-col="${CSS.escape(r.name)}"]`);
      if(body) await fillCol(body, r.name);
    }
  }
}

async function loadCol(rootName){
  if(netCache[rootName]) return netCache[rootName];
  const d=await (await fetch('/api/concepts')).json();
  const by={};
  d.items.forEach(x=>{ (by[x.parent_id]=by[x.parent_id]||[]).push(x); });
  const root=d.items.find(x=>x.name===rootName);
  const subs=root?(by[root.concept_id]||[]):[];
  const groups=[];
  for(const s of subs){
    const e=await (await fetch('/api/concept?name='+encodeURIComponent(s.name))).json();
    if(e.items.length) groups.push({name:s.name, items:e.items});
  }
  netCache[rootName]=groups;
  return groups;
}

async function fillCol(body, rootName){
  if(!netCache[rootName]){
    body.innerHTML='<div class="hint">加载中…</div>';
    await loadCol(rootName);
  }
  paintCol(body, rootName);
}

function paintCol(body, rootName){
  const groups=netCache[rootName]||[];
  const keep=it=>netFilter==='all'||it.category===netFilter;
  let html='';
  groups.forEach(g=>{
    const rows=g.items.filter(keep);
    if(!rows.length) return;
    const key=rootName+'|'+g.name;
    const open=!!openGroups[key];
    html+=`<div class="ghead ${open?'open':''}" data-key="${esc(key)}">
        <span class="cv">▸</span><span class="gn">${esc(g.name)}</span>
        <span class="gc">${rows.length}</span></div>`;
    if(open){
      html+=rows.map(it=>{
        const dead=it.status!=='active';
        return `<div class="erow ${dead?'dead':''}" data-id="${it.entry_id}">
          <span class="tag ${it.category}">${it.category}</span>
          <span class="es">${esc(it.l1_summary)}</span>
          <span class="ed">${fmt(it.created_at)}</span></div>`;
      }).join('');
    }
  });
  body.innerHTML = html || '<div class="hint">没有符合的记忆</div>';
  body.querySelectorAll('.ghead').forEach(h=>h.onclick=()=>{
    openGroups[h.dataset.key]=!openGroups[h.dataset.key];
    paintCol(body, rootName);
  });
  body.querySelectorAll('.erow').forEach(el=>el.onclick=()=>open(el.dataset.id));
}

async function renderChains(){
  const r=await fetch('/api/chains');
  const d=await r.json();
  $('#hint').textContent = d.items.length
      ? `${d.items.length} 组发生过更迭`
      : '还没有更迭';
  if(!d.items.length){ $('#list').innerHTML='<div class="empty">没有更迭</div>'; return; }
  $('#list').innerHTML = d.items.map((g,i)=>`
    <div class="grp"><div class="tl">${g.nodes.map((n,j)=>{
      const gap = j===0 ? '' : `<div class="arrow">→<br><span style="font-size:10px">${Math.round(n.gap_days)}天</span></div>`;
      const why = n.reason ? `<div class="ctx">为什么：${esc(n.reason)}</div>`
        : (n.version_no===1 && n.context ? `<div class="ctx">前因：${esc(n.context)}</div>` : '');
      return (j? gap : '') + `<div class="step ${n.status==='active'?'on':'gone'}" data-id="${n.entry_id}">
        <div class="t">${fmt(n.created_at)}</div>
        <div class="h"><span class="v">v${n.version_no}</span>${esc(n.status)}</div>
        ${why}<div class="s">${esc(n.l1_summary)}</div></div>`;
    }).join('')}</div></div>`).join('');
  document.querySelectorAll('.step').forEach(el=>el.onclick=()=>open(el.dataset.id));
}
function fmt(iso){ if(!iso) return ''; const t=new Date(iso);
  return `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`; }
function fmtFull(iso){ if(!iso) return ''; const t=new Date(iso);
  return `${fmt(iso)} ${String(t.getHours()).padStart(2,'0')}:${String(t.getMinutes()).padStart(2,'0')}`; }
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
$('#q').addEventListener('keydown',e=>{
  if(e.key!=='Enter') return;
  if(mode==='chains'||mode==='net') setMode('active');   // 输入了就是来搜的
  search();
});
$('#q').addEventListener('input',()=>{
  if((mode==='chains'||mode==='net') && $('#q').value.trim()) setMode('active');
});
(async()=>{                                    // 待裁决数：不点进去也知道有几件事等着
  try{
    const d=await (await fetch('/api/conflicts')).json();
    if(d.items.length) $('#cfn').textContent=d.items.length;
    $('#modes [data-mode=conflicts]').title=`${d.items.length} 处待裁决`;
  }catch(e){}
})();
renderContext();
document.querySelector('[data-mode=chains]').click();
</script></body></html>"""


LOGIN_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Tinderbox · 登录</title><style>
body{font:14px/1.6 -apple-system,"Microsoft YaHei",sans-serif;background:#f5f7fa;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
form{background:#fff;padding:28px 32px;border-radius:12px;border:1px solid #e3e8ef;
box-shadow:0 4px 24px rgba(31,56,100,.08);width:300px}
h1{font-size:15px;margin:0 0 4px;color:#1f3864}p{color:#7d889b;font-size:12px;margin:0 0 16px}
input{width:100%;box-sizing:border-box;padding:9px 11px;border:1px solid #dfe4ec;
border-radius:7px;font-size:13px;margin-bottom:12px}
button{width:100%;padding:9px;border:0;border-radius:7px;background:#1f3864;color:#fff;
font-size:13px;cursor:pointer}
</style></head><body>
<form method="post" action="/login">
<h1>Tinderbox 记忆库</h1>
<p>需要访问令牌（数据目录的 token.txt，或 demo/.env 的 API_TOKEN）</p>
<p id="err" style="color:#b4232c;font-size:13px;margin:0 0 8px"></p>
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


class Handler(BaseHTTPRequestHandler):
    server_version = "Tinderbox/0.1-demo"

    def log_message(self, *a):
        pass

    # ---------- 鉴权 ----------
    def _token_from_request(self) -> str:
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        raw = self.headers.get("Cookie") or ""
        if raw:
            c = SimpleCookie()
            try:
                c.load(raw)
            except Exception:
                return ""
            if "tb_token" in c:
                return c["tb_token"].value
        return ""

    def _authed(self) -> bool:
        got = self._token_from_request()
        return bool(got) and hmac.compare_digest(got, TOKEN)

    def _deny_api(self):
        tb.log_warn("web", "unauthorized", path=self.path[:80])
        self._json({"ok": False, "error": "需要访问令牌"}, 401)

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        # 故意不发任何 Access-Control-Allow-*：只允许同源

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        if "application/x-www-form-urlencoded" in (self.headers.get("Content-Type") or ""):
            data = {k: v[0] for k, v in parse_qs(raw).items()}
        else:
            try:
                data = json.loads(raw or "{}")
            except json.JSONDecodeError:
                data = {}
        ip = _client_ip(self)
        if u.path == "/login":
            token = (data.get("token") or "").strip()
            if not token:
                self.send_response(303)
                self.send_header("Location", "/login?e=2")
                self.end_headers()
                return
            if not hmac.compare_digest(token, TOKEN):
                _note_fail(ip)
                if _fail_blocked(ip):
                    self._json({"ok": False, "error": "尝试次数过多，稍后再试"}, 429)
                    return
                self.send_response(303)
                self.send_header("Location", "/login?e=1")
                self.end_headers()
                return
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie",
                             f"tb_token={TOKEN}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000")
            self._security_headers()
            self.end_headers()
            return

        if u.path.startswith("/api/"):
            if self._authed():
                RATE.pop((ip, "fail"), None)
            else:
                if self._token_from_request():
                    _note_fail(ip)
                if _fail_blocked(ip):
                    self._json({"ok": False, "error": "尝试次数过多"}, 429)
                    return
                self._deny_api()
                return

        if u.path == "/api/conflicts/resolve":
            cid = data.get("conflict_id")
            res = data.get("resolution", "supersede")
            if res not in ("supersede", "keep_both", "ignore"):
                self._json({"ok": False, "error": "resolution 不合法"}, 400)
                return
            conn = tb.connect()
            try:
                out = tb.resolve_conflict(conn, cid, res)
                self._json({"ok": True, "result": out})
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 400)
            finally:
                conn.close()
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def do_GET(self):
        u = urlparse(self.path)
        ip = _client_ip(self)
        if _rate_blocked(ip):
            self._json({"ok": False, "error": "请求过于频繁"}, 429)
            return

        if u.path.startswith("/api/"):
            if self._authed():
                RATE.pop((ip, "fail"), None)      # 成功即清零，合法用户不被连坐
            else:
                if self._token_from_request():
                    _note_fail(ip)
                if _fail_blocked(ip):
                    self._json({"ok": False, "error": "尝试次数过多，请一分钟后再试"}, 429)
                    return
                self._deny_api()
                return

        if u.path == "/login":
            body = LOGIN_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        if u.path == "/":
            if not self._authed():
                self.send_response(302)
                self.send_header("Location", "/login")
                self._security_headers()
                self.end_headers()
                return
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        qs = parse_qs(u.query)
        conn = tb.connect()
        try:
            if u.path == "/api/search":
                q = (qs.get("q") or [""])[0]
                mode = (qs.get("mode") or ["active"])[0]
                if mode not in ("active", "history"):
                    mode = "active"
                t = time.time()
                items = tb.search(conn, q, mode=mode, top_k=10)
                self._json({"items": items, "mode": mode,
                            "ms": round((time.time() - t) * 1000, 1),
                            "tokenizer": tb.TOKENIZER})
            elif u.path == "/api/concepts":
                self._json({"items": tb.concept_tree(conn)})
            elif u.path == "/api/concept":
                name = (qs.get("name") or [""])[0]
                self._json({"name": name, "items": tb.concept_entries(conn, name)})
            elif u.path == "/api/context":
                k = int((qs.get("k") or ["5"])[0])
                self._json(tb.active_context(conn, k=max(1, min(k, 10))))
            elif u.path == "/api/conflicts":
                rows = []
                for r in tb.list_conflicts(conn):
                    old = conn.execute("SELECT entry_id, l1_summary FROM memory_entries "
                                       "WHERE entry_id=?", (r["old_entry_id"],)).fetchone()
                    new = conn.execute("SELECT entry_id, l1_summary FROM memory_entries "
                                       "WHERE entry_id=?", (r["new_entry_id"],)).fetchone()
                    rows.append({"conflict_id": r["conflict_id"], "relation": r["relation"],
                                 "confidence": r["confidence"], "reason": r["reason"],
                                 "old": dict(old) if old else None,
                                 "new": dict(new) if new else None})
                self._json({"items": rows})
            elif u.path == "/api/chains":
                self._json({"items": tb.list_chains(conn)})
            elif u.path == "/api/entry":
                eid = (qs.get("id") or [""])[0]
                row = conn.execute(
                    "SELECT entry_id, category, version_no, status, l1_summary, "
                    "created_at, memory_group_id FROM memory_entries WHERE entry_id=?",
                    (eid,)).fetchone()
                if row is None:
                    self._json({"error": "not found"}, 404)
                    return
                span = tb.get_span(conn, eid, before=60, after=60)
                nodes = tb.chain(conn, row["memory_group_id"])
                prev = None
                for n in nodes:
                    if prev is None:
                        n["gap_days"] = None
                    else:
                        t0 = tb.datetime.strptime(prev, "%Y-%m-%dT%H:%M:%S.%fZ")
                        t1 = tb.datetime.strptime(n["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
                        n["gap_days"] = round((t1 - t0).total_seconds() / 86400, 2)
                    prev = n["created_at"]
                rels = []
                for r in tb.relations_of(conn, eid):
                    peer = r["to_entry"] if r["from_entry"] == eid else r["from_entry"]
                    p = conn.execute(
                        "SELECT entry_id, l1_summary, category FROM memory_entries "
                        "WHERE entry_id=?", (peer,)).fetchone()
                    if p:
                        rels.append({"entry_id": peer, "l1_summary": p["l1_summary"],
                                     "category": p["category"], "relation": r["relation"],
                                     "confidence": r["confidence"]})
                self._json({**dict(row), "offset": span["offset"],
                            "length": span["length"], "text": span["text"],
                            "chain": nodes, "relations": rels})
            else:
                self._json({"error": "not found"}, 404)
        finally:
            conn.close()


def run(port: int | None = None):
    p = port or PORT
    tb.log_event("web", "server start", port=p, db=str(tb.DB_PATH))
    print(f"压缩 {tb.CODEC} · 分词 {tb.TOKENIZER}")
    print(f"数据 {tb.DB_PATH}")
    ThreadingHTTPServer(("127.0.0.1", p), Handler).serve_forever()


if __name__ == "__main__":
    print(f"Tinderbox demo → http://127.0.0.1:{PORT}")
    run()
