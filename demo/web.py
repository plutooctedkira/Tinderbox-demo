"""极简看板：搜索 L1，点开看原文片段。零依赖（stdlib http.server）。

跑法：  python demo/web.py      → http://127.0.0.1:8777
"""
from __future__ import annotations

import hmac
import json
import os
import uuid
import threading
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
    """真实客户端 IP。

    只在 TB_TRUST_PROXY=1 时采信 X-Forwarded-For——否则任何人都能伪造来源，
    "导入只允许本机"就形同虚设。放到 Caddy/Nginx 后面时才设这个变量。
    """
    if os.environ.get("TB_TRUST_PROXY") == "1":
        xff = handler.headers.get("X-Forwarded-For") or ""
        first = xff.split(",")[0].strip()
        if first:
            return first
    return handler.client_address[0] if handler.client_address else "-"


LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def import_allowed(ip: str) -> tuple[bool, str]:
    """导入会读服务端任意路径，默认只允许本机。

    远程要开：环境变量 TB_ALLOW_IMPORT=1（放到反代后面时务必想清楚）。
    """
    if ip in LOOPBACK:
        return True, ""
    if os.environ.get("TB_ALLOW_IMPORT") == "1":
        return True, ""
    return False, "出于安全，导入只允许在本机操作（远程需设 TB_ALLOW_IMPORT=1）"


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
 body{margin:0;font-family:"Segoe UI","Microsoft YaHei",sans-serif;color:var(--ink);
   background:var(--bg);display:flex;flex-direction:column;height:100vh;overflow:hidden}
 header{flex:none;display:flex;align-items:center;justify-content:space-between;
   padding:20px 28px 14px;border-bottom:1px solid var(--line);background:#fff}
 #setbtn{padding:6px 14px;border:1px solid var(--line);background:#fff;border-radius:7px;
   font-size:12.5px;color:#5f6b7e;cursor:pointer}
 #setbtn:hover{border-color:var(--blue);color:var(--navy)}
 #setbtn.on{background:var(--navy);color:#fff;border-color:var(--navy)}
 h1{margin:0;font-size:20px;color:var(--navy);letter-spacing:.5px}
 .sub{color:var(--muted);font-size:12px;margin-top:6px}
 main{flex:1;min-height:0;display:flex;gap:18px;padding:18px 28px 0;align-items:stretch;
   overflow:hidden}
 .col{flex:1;min-width:0;min-height:0;overflow-y:auto;overscroll-behavior:contain;
   padding-bottom:18px;padding-right:4px}
 .col::-webkit-scrollbar{width:9px}
 .col::-webkit-scrollbar-thumb{background:#d3dbe6;border-radius:5px}
 .col::-webkit-scrollbar-thumb:hover{background:#b9c5d6}
 .col::-webkit-scrollbar-track{background:transparent}
 @media (max-width: 900px){
   body{height:auto;overflow:auto}
   main{flex-direction:column;overflow:visible;padding:12px}
   .col{overflow:visible;max-width:none!important;width:100%;padding-right:0}
   .bar{position:static}
 }

 .bar{display:flex;gap:8px;align-items:center;position:sticky;top:0;z-index:3;
   background:var(--bg);padding:2px 0 8px}
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
 #settings{flex:1;min-height:0;overflow-y:auto;padding:18px 28px 28px}
 .sethead{display:flex;align-items:center;gap:12px;margin:0 0 14px}
 .sethead h2{margin:0;font-size:16px;color:var(--navy)}
 .sethead button{padding:5px 12px;border:1px solid var(--line);background:#fff;border-radius:7px;
   font-size:12.5px;cursor:pointer}
 .setgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;max-width:1100px}
 .setcard{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px}
 .setcard.wide{grid-column:1/-1}
 .setcard h3{margin:0 0 6px;font-size:13.5px;color:var(--navy)}
 .setcard .cnt{font-size:11px;color:#fff;background:var(--navy);border-radius:10px;padding:1px 7px;margin-left:6px}
 .sethint{margin:0 0 12px;font-size:12px;color:#8a97ab;line-height:1.6}
 .setcard input[type=text]{width:100%;box-sizing:border-box;margin:0 0 8px;padding:8px 10px;
   font-size:13px;border:1px solid var(--line);border-radius:7px}
 .setcard input[type=text]:focus{outline:none;border-color:var(--blue)}
 .setrow{display:flex;gap:8px;align-items:center;margin-top:4px}
 .setrow button{padding:7px 16px;border:1px solid var(--line);background:#fff;border-radius:7px;
   font-size:12.5px;cursor:pointer}
 #imf-go,#bakbtn{background:var(--navy);color:#fff;border-color:var(--navy)}
 .setcard .imfmsg{margin-top:10px;font-size:12px;color:#5f6b7e;white-space:pre-wrap;display:none}
 .uprow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
 .uprow input[type=file]{flex:1;font-size:12px;color:#5f6b7e}
 .pathimp{margin-top:12px}
 .pathimp summary{font-size:12px;color:#5f6b7e;cursor:pointer;margin-bottom:8px}
 .pathimp input[type=text]{width:100%;box-sizing:border-box;margin:6px 0;padding:8px 10px;
   font-size:13px;border:1px solid var(--line);border-radius:7px}
 .cleanmode{display:flex;gap:6px;margin:0 0 12px;flex-wrap:wrap}
 .cleanmode button{padding:6px 14px;border:1px solid var(--line);background:#fff;border-radius:7px;
   font-size:12.5px;color:#5f6b7e;cursor:pointer}
 .cleanmode button.on{background:var(--navy);color:#fff;border-color:var(--navy)}
 .cleanrow{padding:10px 12px;border:1px solid var(--line);border-radius:9px;margin:0 0 8px;background:#fff}
 .cleanrow .cs{font-size:12.5px;color:#33405a;line-height:1.6}
 .cleanrow .cn{font-size:12.5px;color:#1f5130;background:#f3faf5;border-radius:6px;
   padding:6px 8px;margin-top:6px;line-height:1.6}
 .cleanrow .cacts{display:flex;gap:8px;margin-top:8px}
 .cbtn{padding:3px 12px;font-size:11.5px;border:1px solid var(--line);background:#fff;
   border-radius:6px;cursor:pointer}
 .cbtn.ok{background:var(--navy);color:#fff;border-color:var(--navy)}
 .cbtn.del{color:#b4232c}
 .archrow{display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px dashed #eef1f6;font-size:12.5px}
 .archrow .as{flex:1;color:#33405a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .archrow .ad{color:#a3b0c2;font-size:11px;flex:none}
 .archrow .restore{flex:none;padding:2px 10px;font-size:11.5px;border:1px solid var(--line);
   background:#fff;border-radius:6px;cursor:pointer}
 .onboard{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px 24px;
   max-width:560px;margin:8px 0}
 .onboard h3{margin:0 0 8px;font-size:15px;color:var(--navy)}
 .onboard p{margin:0 0 10px;font-size:13px;color:#5f6b7e;line-height:1.7}
 .onboard ol{margin:0 0 14px;padding-left:20px;font-size:13px;color:#33405a;line-height:1.9}
 .onboard button{padding:8px 18px;border:0;border-radius:7px;background:var(--navy);color:#fff;
   font-size:13px;cursor:pointer}
 .revbtn{padding:1px 8px;font-size:11px;border:1px solid var(--line);background:#fff;
   border-radius:5px;cursor:pointer;flex:none;margin-left:auto}
 .audit{margin:0 0 10px}
 .audit h4{margin:0 0 6px;font-size:12px;color:var(--muted);font-weight:600}
 .arow{display:flex;gap:8px;font-size:11px;color:#5f6b7e;padding:2px 0;border-bottom:1px dashed #eef1f6}
 .aat{color:#93a0b4;flex:none}
 .aac{flex:none;color:#3d5a86}
 .aac2{flex:none;color:#8a5a00}
 .adt{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .acts{display:flex;gap:8px;margin:6px 0 10px}
 .acts button{padding:4px 12px;font-size:12px;border:1px solid var(--line);background:#fff;
   border-radius:6px;cursor:pointer}
   border:1px solid var(--line);border-radius:7px;font-family:inherit;resize:vertical}
   font-size:12.5px;cursor:pointer}
 .impform{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px;margin:0 0 8px}
 .impform input[type=text]{width:100%;box-sizing:border-box;margin:0 0 6px;padding:8px 10px;
   font-size:13px;border:1px solid var(--line);border-radius:7px}
 .impform input[type=text]:focus{outline:none;border-color:var(--blue)}
 .imfrow{display:flex;gap:8px;align-items:center}
 .imfrow input[type=text]{margin:0;flex:1}
 .imfchk{font-size:12px;color:#5f6b7e;white-space:nowrap}
 .imfrow button{padding:6px 14px;border:1px solid var(--line);background:#fff;border-radius:6px;
   font-size:12.5px;cursor:pointer;white-space:nowrap}
 .imfrow button[type=submit]{background:var(--navy);color:#fff;border-color:var(--navy)}
 .imfmsg{font-size:12px;color:#5f6b7e;margin-top:8px;white-space:pre-wrap;display:none}
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
<header><h1>Tinderbox</h1><button id="setbtn" title="设置">设置</button></header>
<main>
 <div class="col">
  <div class="bar">
    <input id="q" type="text" placeholder="检索" autofocus>
    <div class="modes" id="modes">
      <button data-mode="chains">演变</button>
      <button data-mode="net">星网</button>
      <button data-mode="conflicts">冲突<span id="cfn"></span></button>
      <button id="refbtn" title="把规则摘要改写成「结论——因为依据」">精修<span id="refn"></span></button>
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
<section id="settings" hidden>
  <div class="sethead"><button id="setback">← 返回</button><h2>设置</h2></div>
  <div class="setgrid">
    <div class="setcard wide">
      <h3>导入</h3>
      <p class="sethint">选择本机文件（.txt .md .docx .pdf），或按文件夹路径整批导入。</p>
      <div class="uprow">
        <input type="file" id="up-files" multiple>
        <button id="up-go">上传并导入</button>
      </div>
      <div class="setrow" style="margin-top:8px">
        <input id="imf-proj" type="text" placeholder="项目名（留空=用文件夹名）">
        <label class="imfchk"><input id="imf-dry" type="checkbox"> 试跑（不写库）</label>
      </div>
      <div class="imfmsg" id="up-msg"></div>
      <details class="pathimp">
        <summary>或者：按本机路径导入整个文件夹</summary>
        <input id="imf-path" type="text" placeholder="D:\笔记">
        <div class="setrow"><button id="imf-go">从路径导入</button>
          <button id="imf-cancel" hidden>取消</button></div>
        <div class="imfmsg" id="imf-msg"></div>
      </details>
    </div>

    <div class="setcard wide">
      <h3>清洗</h3>
      <p class="sethint">规则提炼出的摘要比较糙；清洗把它改写成「结论 —— 因为依据」。</p>
      <div class="cleanmode" id="cleanmode">
        <button data-cm="manual" class="on">手动清洗</button>
        <button data-cm="auto">自动清洗（需审核）</button>
        <button data-cm="none">不清洗</button>
      </div>
      <div id="clean-body"></div>
    </div>

    <div class="setcard">
      <h3>备份</h3>
      <p class="sethint">把数据库与原文打包到数据目录下的 backup/，保留最近 5 份。</p>
      <div class="setrow"><button id="bakbtn">立即备份</button></div>
      <div class="imfmsg" id="bakmsg"></div>
    </div>

    <div class="setcard wide">
      <h3>已归档 <span class="cnt" id="archn"></span></h3>
      <p class="sethint">归档只是从现行检索里移走，随时可以恢复。</p>
      <div id="archlist"></div>
    </div>
  </div>
</section>
<script>
const $=s=>document.querySelector(s);
let mode='search';
function setMode(m){
  mode=m;
  document.querySelectorAll('#modes button').forEach(x=>x.classList.toggle('on',x.dataset.mode===m));
}
document.querySelectorAll('#modes button').forEach(b=>b.onclick=()=>{ setMode(b.dataset.mode); search(); });
async function refreshList(){
  // 按当前模式重绘左栏 + 顶部浮现（编辑/归档后必须调，否则左栏是旧的）
  await search();
  await renderContext();
}
async function search(keepSel){
  if(mode==='chains'){ return renderChains(); }
  if(mode==='net'){ return renderNet(); }
  if(mode==='conflicts'){ return renderConflicts(); }
  mode='search';
  const q=$('#q').value.trim();
  if(!q){$('#list').innerHTML='';$('#hint').textContent='输入词后回车';return;}
  const r=await fetch(`/api/search?q=${encodeURIComponent(q)}&mode=hybrid`);
  const d=await r.json();
  d.items = d.items.filter(catKeep);
  const hist = d.items.filter(i=>i.status!=='active').length;
  $('#hint').textContent = d.items.length
      ? `${d.items.length} 条${hist ? ` · ${hist} 条旧版本` : ''} · ${d.ms} ms`
      : '没有命中';
  if(!d.items.length){$('#list').innerHTML=chipsHTML()+'<div class="empty">没有命中</div>';bindChips();return;}
  $('#list').innerHTML = chipsHTML() + d.items.map(it=>`
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
    <div class="meta">${(d.origin && d.origin.doc_title) ? `来源《${esc(d.origin.doc_title)}》` : ''}${(d.origin && d.origin.project) ? ` · 项目「${esc(d.origin.project)}」` : ''}<br>
      ${d.entry_id}<br>创建 ${fmtFull(d.created_at)}<br>
      L0 区间 [${d.offset}, ${d.offset+d.length}) · ${d.length} 字</div>
    ${d.chain && d.chain.length>1 ? `<div class="chain"><h4>版本链</h4>${chain}</div>`:''}
    ${(d.relations && d.relations.length) ? `<div class="rel"><h4>相关记忆</h4>${
      d.relations.map(r=>`<div class="relrow" data-id="${r.entry_id}">
        <span class="rtag">${esc(r.relation)}</span>
        <span class="rs">${esc(r.l1_summary)}</span>
        <span class="rc">${r.confidence.toFixed(2)}</span></div>`).join('')}</div>`:''}
    ${(d.revisions && d.revisions.length) ? `<div class="audit"><h4>历史版本（可回滚）</h4>${
      d.revisions.map(r=>`<div class="arow"><span class="aat">${fmtFull(r.at)}</span>
        <span class="adt" title="${esc(r.old)}">${esc(r.old.slice(0,40))}</span>
        <button class="revbtn" data-rev="${r.revision_id}">回滚</button></div>`).join('')}</div>`:''}
    ${(d.audit && d.audit.length) ? `<div class="audit"><h4>操作轨迹</h4>${
      d.audit.map(a=>`<div class="arow"><span class="aat">${fmtFull(a.at)}</span>
        <span class="aac">${esc(a.actor)}</span>
        <span class="aac2">${esc(a.action)}</span>
        <span class="adt">${esc(a.detail||'')}</span></div>`).join('')}</div>`:''}
    <div class="acts"><button id="act-edit">编辑</button>
      <button id="act-arch">${d.status==='archived'?'恢复':'归档'}</button></div>
    <pre>${esc(d.text)}</pre>`;
  document.querySelectorAll('.revbtn').forEach(b=>b.onclick=async ev=>{
    ev.stopPropagation();
    const r=await fetch('/api/entry/revert',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({entry_id:d.entry_id, revision_id:b.dataset.rev})});
    const j=await r.json();
    if(!j.ok){ alert(j.error||'回滚失败'); return; }
    await refreshList(); open(d.entry_id);
  });
  $('#act-edit').onclick=async()=>{
    const next=prompt('改摘要（会留痕，可回滚）', d.l1_summary);
    if(!next || next.trim()===d.l1_summary) return;
    const r=await fetch('/api/entry/update',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({entry_id:d.entry_id,summary:next.trim()})});
    const j=await r.json();
    if(!j.ok){ alert(j.error||'改不了'); return; }
    await refreshList();
    open(d.entry_id);
  };
  $('#act-arch').onclick=async()=>{
    const toArchive = d.status!=='archived';
    const r=await fetch('/api/entry/archive',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({entry_id:d.entry_id,archived:toArchive})});
    const j=await r.json();
    if(!j.ok){ alert(j.error||'操作失败'); return; }
    await refreshList();
    open(d.entry_id);
  };
  document.querySelectorAll('.relrow').forEach(el=>el.onclick=()=>open(el.dataset.id));
  document.querySelectorAll('.node').forEach(n=>n.onclick=()=>open(n.dataset.id));
}
function fmtGap(g){ if(g==null) return '';
  if(g<1) return `${Math.max(1,Math.round(g*24))} 小时`;
  return `${Math.round(g)} 天`; }
let openCols = {}, openGroups = {}, netCache = {}, netFilter = 'all';
let catFilter = 'all';
const CATS = ['all','decision','preference','task','knowledge'];
function chipsHTML(){
  return `<div class="netfilter">${CATS.map(k=>`<button class="fchip ${catFilter===k?'on':''}"
    data-cat="${k}">${k==='all'?'全部':k}</button>`).join('')}</div>`;
}
function bindChips(){
  document.querySelectorAll('#list .fchip').forEach(b=>b.onclick=()=>{
    catFilter=b.dataset.cat; search();
  });
}
function catKeep(it){ return catFilter==='all' || it.category===catFilter; }

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
  if(!groups.length && root){
    // 没有子概念：直接显示这个项目自己挂的记忆（按分类分组）
    const e=await (await fetch('/api/concept?name='+encodeURIComponent(root.name))).json();
    const byCat={};
    e.items.forEach(it=>{ (byCat[it.category]=byCat[it.category]||[]).push(it); });
    for(const [cat,items] of Object.entries(byCat)) groups.push({name:cat, items});
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
/* ---------------- 设置界面 ---------------- */
function openSettings(){
  document.querySelector('main').hidden = true;
  $('#settings').hidden = false;
  $('#setbtn').classList.add('on');
  loadArchived(); renderClean();
}
function closeSettings(){
  $('#settings').hidden = true;
  document.querySelector('main').hidden = false;
  $('#setbtn').classList.remove('on');
}
$('#setbtn').onclick=()=>{ $('#settings').hidden ? openSettings() : closeSettings(); };
$('#setback').onclick=closeSettings;

/* ---------- 通用：轮询导入任务 ---------- */
function pollJob(jobId, msg, onDone){
  let timer=setInterval(async()=>{
    const j=await (await fetch('/api/import/status?id='+jobId)).json();
    if(!j.ok){ clearInterval(timer); msg.textContent=j.error; return; }
    const J=j.job, pct=J.total? Math.round(J.done*100/J.total):0;
    msg.textContent=`${J.state==='running'?'进行中':'完成'} ${J.done}/${J.total}（${pct}%）`
      +` · 新增 ${J.added} · 更新 ${J.updated} · 跳过 ${J.skipped} · 失败 ${J.failed} · ${J.entries} 条`
      + (J.project?` · 项目 ${J.project}`:'');
    if(J.state!=='running'){
      clearInterval(timer);
      if(J.failures && J.failures.length) msg.textContent += '\n问题：'+J.failures.slice(0,5).join('；');
      if(onDone) await onDone(J);
    }
  }, 600);
}

/* ---------- 文件上传导入 ---------- */
$('#up-go').onclick=async()=>{
  const files=[...($('#up-files').files||[])];
  const msg=$('#up-msg'); msg.style.display='block';
  if(!files.length){ msg.textContent='先选择文件'; return; }
  msg.textContent='读取文件中…';
  const payload=[];
  for(const f of files){
    const buf=await f.arrayBuffer();
    let bin=''; const bytes=new Uint8Array(buf);
    for(let i=0;i<bytes.length;i+=0x8000)
      bin+=String.fromCharCode.apply(null, bytes.subarray(i,i+0x8000));
    payload.push({name:f.webkitRelativePath||f.name, b64:btoa(bin)});
  }
  msg.textContent=`上传 ${payload.length} 个文件…`;
  const r=await fetch('/api/upload',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({files:payload, project:$('#imf-proj').value.trim(),
                         dry_run:$('#imf-dry').checked})});
  const j=await r.json();
  if(!j.ok){ msg.textContent=j.error||'上传失败'; return; }
  pollJob(j.job, msg, async()=>{ await loadMeta(); await loadArchived(); });
};

/* ---------- 路径导入 ---------- */
$('#imf-go').onclick=async()=>{
  const msg=$('#imf-msg'); msg.style.display='block'; msg.textContent='正在扫描…';
  const go=$('#imf-go'), cancel=$('#imf-cancel');
  go.disabled=true; cancel.hidden=false; let jobId=null;
  cancel.onclick=async()=>{ cancel.disabled=true;
    if(jobId) await fetch('/api/import/cancel',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({id:jobId})}); };
  try{
    const r=await fetch('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:$('#imf-path').value.trim(), project:$('#imf-proj').value.trim(),
                           dry_run:$('#imf-dry').checked})});
    const j=await r.json();
    if(!j.ok){ msg.textContent=j.error||'导入失败'; go.disabled=false; cancel.hidden=true; return; }
    jobId=j.job; pollJob(jobId, msg, async()=>{ go.disabled=false; cancel.hidden=true;
      await loadMeta(); await loadArchived(); });
  }catch(e){ msg.textContent='出错：'+e; go.disabled=false; cancel.hidden=true; }
};

/* ---------- 备份 ---------- */
$('#bakbtn').onclick=async()=>{
  const b=$('#bakbtn'), msg=$('#bakmsg');
  b.disabled=true; msg.style.display='block'; msg.textContent='备份中…';
  try{
    const r=await fetch('/api/backup',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({keep:5})});
    const j=await r.json();
    msg.textContent = j.ok ? `已备份 ${j.result.counts.entries} 条 · 校验${j.result.ok?'通过':'不通过'}\n${j.result.dest}`
                           : (j.error||'备份失败');
  }catch(e){ msg.textContent='出错：'+e; }
  finally{ b.disabled=false; }
};

/* ---------- 归档 ---------- */
async function loadArchived(){
  const d=await (await fetch('/api/list?status=archived&limit=200')).json();
  $('#archn').textContent = d.items.length? d.items.length : '';
  if(!d.items.length){ $('#archlist').innerHTML='<div class="sethint">还没有归档的记忆</div>'; return; }
  $('#archlist').innerHTML = d.items.map(it=>`
    <div class="archrow" data-id="${it.entry_id}">
      <span class="tag ${it.category}">${it.category}</span>
      <span class="as">${esc(it.l1_summary)}</span>
      <span class="ad">${fmt(it.created_at)}</span>
      <button class="restore" data-id="${it.entry_id}">恢复</button>
    </div>`).join('');
  document.querySelectorAll('.restore').forEach(b=>b.onclick=async ev=>{
    ev.stopPropagation(); b.disabled=true;
    await fetch('/api/entry/archive',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({entry_id:b.dataset.id, archived:false})});
    await loadArchived(); await loadMeta();
  });
}

/* ---------- 清洗 ---------- */
let cleanMode='manual';
$('#cleanmode').querySelectorAll('button').forEach(b=>b.onclick=()=>{
  cleanMode=b.dataset.cm;
  $('#cleanmode').querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));
  renderClean();
});
function cleanRow(it, extra){
  return `<div class="cleanrow" data-id="${it.entry_id||''}">
    <div class="cs">${esc(it.l1_summary||it.new_summary||'')}</div>
    ${(it.new_summary && it.new_summary!==it.l1_summary)?`<div class="cn">建议：${esc(it.new_summary)}</div>`:''}
    <div class="cacts">${extra}</div></div>`;
}
async function renderClean(){
  const body=$('#clean-body');
  if(cleanMode==='none'){
    body.innerHTML='<div class="sethint">已选择不清洗：摘要保持规则提炼的样子，不改写、不调模型。</div>';
    return;
  }
  if(cleanMode==='manual'){
    body.innerHTML='<div class="sethint">逐条改或删。改动会留痕，可回滚。</div><div id="manual-list">加载中…</div>';
    const d=await (await fetch('/api/list?status=provisional&limit=50')).json();
    if(!d.items.length){ $('#manual-list').innerHTML='<div class="sethint">没有待清洗的记忆</div>'; return; }
    $('#manual-list').innerHTML = d.items.map(it=>cleanRow(it,
      `<button class="cbtn edit" data-id="${it.entry_id}">编辑</button>
       <button class="cbtn del" data-id="${it.entry_id}">删除</button>`)).join('');
    document.querySelectorAll('.cbtn.edit').forEach(b=>b.onclick=async()=>{
      const cur=b.closest('.cleanrow').querySelector('.cs').textContent;
      const next=prompt('改摘要（留痕，可回滚）', cur);
      if(!next || next.trim()===cur) return;
      const r=await fetch('/api/entry/update',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({entry_id:b.dataset.id, summary:next.trim()})});
      const j=await r.json();
      if(!j.ok){ alert(j.error||'改不了'); return; }
      renderClean(); loadMeta();
    });
    document.querySelectorAll('.cbtn.del').forEach(b=>b.onclick=async()=>{
      if(!confirm('彻底删除这条记忆？（不可恢复，归档才可恢复）')) return;
      const r=await fetch('/api/entry/delete',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({entry_id:b.dataset.id})});
      const j=await r.json();
      if(!j.ok){ alert(j.error||'删不掉'); return; }
      renderClean(); loadMeta();
    });
    return;
  }
  // auto
  body.innerHTML=`<div class="sethint">模型只给建议，采纳后才写入；采纳前你可以先改。</div>
    <div class="setrow"><button id="gen-clean">生成 5 条建议</button></div>
    <div id="prop-list" class="sethint" style="margin-top:8px">加载中…</div>`;
  $('#gen-clean').onclick=async()=>{
    const btn=$('#gen-clean'); btn.disabled=true; btn.textContent='生成中…';
    const r=await fetch('/api/clean/suggest',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:5})});
    const j=await r.json();
    btn.disabled=false; btn.textContent='生成 5 条建议';
    if(!j.ok){ alert(j.error||'生成失败'); return; }
    await renderProposals();
    alert(`生成 ${j.result.suggested} 条 · 失败 ${j.result.failed} 条`);
  };
  await renderProposals();
}
async function renderProposals(){
  const list=$('#prop-list'); if(!list) return;
  const d=await (await fetch('/api/clean/list?state=pending')).json();
  if(!d.items.length){ list.innerHTML='<div class="sethint">没有待审建议</div>'; return; }
  list.innerHTML = d.items.map(it=>`
    <div class="cleanrow">
      <div class="cs">原：${esc(it.old_summary)}</div>
      <div class="cn">建议：${esc(it.new_summary)}</div>
      <div class="cacts">
        <button class="cbtn ok" data-id="${it.proposal_id}">采纳</button>
        <button class="cbtn editp" data-id="${it.proposal_id}" data-new="${esc(it.new_summary)}">改后采纳</button>
        <button class="cbtn no" data-id="${it.proposal_id}">忽略</button>
      </div>
    </div>`).join('');
  list.querySelectorAll('.cbtn.ok').forEach(b=>b.onclick=async()=>{
    b.disabled=true;
    const r=await fetch('/api/clean/apply',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({proposal_id:b.dataset.id})});
    const j=await r.json();
    if(!j.ok){ alert(j.error||'采纳失败'); b.disabled=false; return; }
    renderProposals(); loadMeta();
  });
  list.querySelectorAll('.cbtn.editp').forEach(b=>b.onclick=async()=>{
    const next=prompt('改完再采纳', b.dataset.new);
    if(!next) return;
    b.disabled=true;
    const r=await fetch('/api/clean/apply',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({proposal_id:b.dataset.id, summary:next.trim()})});
    const j=await r.json();
    if(!j.ok){ alert(j.error||'采纳失败'); b.disabled=false; return; }
    renderProposals(); loadMeta();
  });
  list.querySelectorAll('.cbtn.no').forEach(b=>b.onclick=async()=>{
    b.disabled=true;
    await fetch('/api/clean/reject',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({proposal_id:b.dataset.id})});
    renderProposals();
  });
}

function showOnboarding(){
  $('#hint').textContent='还没有记忆';
  $('#list').innerHTML=`<div class="onboard">
    <h3>记忆库还是空的</h3>
    <p>它靠导入你的笔记来积累记忆：一条条决定、偏好、任务会被提炼出来，原文按块冷存，随时能回看。</p>
    <ol>
      <li>点 <b>导入</b>，填一个文件夹路径（支持 .txt .md .docx .pdf）</li>
      <li>给这批材料起个<b>项目名</b>，比如「咖啡车生意」</li>
      <li>先勾<b>试跑</b>看看会导入什么，确认后去掉勾真跑</li>
    </ol>
    <button id="ob-import">导入笔记</button>
  </div>`;
  const b=$('#ob-import');
  if(b) b.onclick=()=>{ openSettings(); $('#imf-path').focus(); };
}
async function loadMeta(){
  try{
    const m=await (await fetch('/api/meta')).json();
    if(m.provisional) $('#refn').textContent=m.provisional;
    if(m.total===0) showOnboarding();
    return m;
  }catch(e){ return null; }
}
$('#refbtn').onclick=async()=>{
  const btn=$('#refbtn'); btn.disabled=true;
  const txt=btn.textContent; btn.textContent='精修中…';
  try{
    const r=await fetch('/api/refine',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({limit:10})});
    const j=await r.json();
    if(!j.ok){ alert(j.error||'精修失败'); }
    else{
      const s=j.result;
      alert(`扫描 ${s.scanned} 条 · 采纳 ${s.refined} · 驳回 ${s.failed}`);
      await refreshList(); await loadMeta();
    }
  }catch(e){ alert('出错：'+e); }
  finally{ btn.disabled=false; btn.textContent=txt; }
};
$('#bakbtn').onclick=async()=>{
  const b=$('#bakbtn'); b.disabled=true; b.textContent='备份中…';
  try{
    const r=await fetch('/api/backup',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({keep:5})});
    const j=await r.json();
    if(!j.ok){ alert(j.error||'备份失败'); }
    else alert(`已备份 ${j.result.counts.entries} 条记忆\n${j.result.dest}\n校验${j.result.ok?'通过':'不通过'}`);
  }finally{ b.disabled=false; b.textContent='备份'; }
};
loadMeta().then(m=>{ if(!m || m.total!==0) document.querySelector('[data-mode=chains]').click(); });
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
<h1>Tinderbox</h1>
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


_JOBS: dict = {}
_JOBS_LOCK = threading.Lock()
_IMPORT_MAX_FILES = 2000


def _start_upload(files: list, project: str, dry: bool) -> dict:
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "state": "running", "done": 0, "total": len(files), "added": 0,
           "updated": 0, "skipped": 0, "failed": 0, "entries": 0, "cancel": False,
           "failures": [], "started": time.time(), "path": "上传", "project": project}
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    threading.Thread(target=_upload_worker, args=(job, files, project, dry), daemon=True).start()
    return job


def _upload_worker(job: dict, files: list, project: str, dry: bool) -> None:
    import base64
    import shutil
    import tbc

    conn = None
    tmp_root = Path(os.environ.get("TB_DATA") or tb.DB_PATH.parent) / ".upload_tmp"
    try:
        conn = tb.connect()
        tmp_root.mkdir(parents=True, exist_ok=True)
        for item in files:
            if job["cancel"]:
                job["state"] = "cancelled"
                return
            name = str(item.get("name") or "未命名").replace("\\", "/")
            try:
                raw = base64.b64decode(item.get("b64") or "")
                if len(raw) > 12 * 1024 * 1024:
                    job["failed"] += 1
                    job["failures"].append(f"{name}：超过 12 MB")
                    continue
                dest = tmp_root / name.replace("/", "__")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                text, why = tbc.read_text(dest)
                if text is None:
                    job["failed"] += 1
                    job["failures"].append(f"{name}：{why or '读不了'}")
                    continue
                text = text.strip()
                if len(text) < 20:
                    job["skipped"] += 1
                    continue
                action, n = tbc.ingest_one(conn, name, text, dry=dry, project=project)
                job[action] += 1
                job["entries"] += n
            except Exception as e:
                job["failed"] += 1
                job["failures"].append(f"{name}：{type(e).__name__}: {e}")
            finally:
                job["done"] += 1
        job["state"] = "done"
        tb.log_event("import", "upload done", files=len(files), added=job["added"],
                     entries=job["entries"])
    except Exception as e:
        job["state"] = "error"
        job["failures"].append(f"{type(e).__name__}: {e}")
    finally:
        if conn is not None:
            conn.close()
        shutil.rmtree(tmp_root, ignore_errors=True)


def _start_import(target: Path, project: str, dry: bool) -> dict:
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "state": "running", "done": 0, "total": 0, "added": 0,
           "updated": 0, "skipped": 0, "failed": 0, "entries": 0, "cancel": False,
           "failures": [], "started": time.time(), "path": str(target), "project": project}
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    threading.Thread(target=_import_worker, args=(job, target, project, dry),
                     daemon=True).start()
    return job


def _import_worker(job: dict, target: Path, project: str, dry: bool) -> None:
    import tbc
    conn = None
    try:
        conn = tb.connect()
        data_root = Path(os.environ.get("TB_DATA") or tb.DB_PATH.parent)
        if not project and target.is_dir():
            project = target.name
            job["project"] = project
        targets = list(tbc.iter_targets([str(target)], {}, exclude=data_root))
        targets = targets[:_IMPORT_MAX_FILES]
        job["total"] = len(targets)
        for title, f in targets:
            if job["cancel"]:
                job["state"] = "cancelled"
                return
            try:
                text, why = tbc.read_text(f)
                if text is None:
                    job["failed"] += 1
                    job["failures"].append(f"{title}：{why or '读不了'}")
                    continue
                text = text.strip()
                if len(text) < 20:
                    job["skipped"] += 1
                    continue
                action, n = tbc.ingest_one(conn, title, text, dry=dry, project=project)
                job[action] += 1
                job["entries"] += n
            except Exception as e:
                job["failed"] += 1
                job["failures"].append(f"{title}：{type(e).__name__}: {e}")
            finally:
                job["done"] += 1
        job["state"] = "done"
        tb.log_event("import", "panel import done", path=str(target), project=project,
                     added=job["added"], entries=job["entries"])
    except Exception as e:
        job["state"] = "error"
        job["failures"].append(f"{type(e).__name__}: {e}")
    finally:
        if conn is not None:
            conn.close()
            if not dry:
                try:
                    conn2 = tb.connect()
                    conn2.close()
                except Exception:
                    pass


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

        if u.path == "/api/import":
            allowed, why = import_allowed(_client_ip(self))
            if not allowed:
                self._json({"ok": False, "error": why}, 403)
                return
            path = (data.get("path") or "").strip()
            project = (data.get("project") or "").strip()
            dry = bool(data.get("dry_run"))
            if not path:
                self._json({"ok": False, "error": "请填写要导入的路径"}, 422)
                return
            target = Path(path).expanduser()
            if not target.exists():
                self._json({"ok": False, "error": f"路径不存在：{target}"}, 404)
                return
            job = _start_import(target, project, dry)
            self._json({"ok": True, "job": job["id"]})
            return

        if u.path == "/api/import/status":
            job = _JOBS.get((data.get("id") or qs.get("id", [""])[0]))
            if job is None:
                self._json({"ok": False, "error": "没有这个任务"}, 404)
                return
            self._json({"ok": True, "job": dict(job)})
            return

        if u.path == "/api/import/cancel":
            job = _JOBS.get((data.get("id") or ""))
            if job is None:
                self._json({"ok": False, "error": "没有这个任务"}, 404)
                return
            job["cancel"] = True
            self._json({"ok": True})
            return

        if u.path == "/api/entry/revert":
            conn = tb.connect()
            try:
                out = tb.revert_summary(conn, (data.get("entry_id") or ""),
                                        (data.get("revision_id") or ""))
            except KeyError as e:
                self._json({"ok": False, "error": str(e)}, 404)
                return
            except ValueError as e:
                self._json({"ok": False, "error": str(e)}, 422)
                return
            finally:
                conn.close()
            self._json({"ok": True, "result": out})
            return

        if u.path == "/api/backup":
            root = Path(os.environ.get("TB_DATA") or tb.DB_PATH.parent)
            try:
                out = tb.make_backup(root, keep=int(data.get("keep") or 0))
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
                return
            self._json({"ok": True, "result": out})
            return

        if u.path == "/api/clean/suggest":
            limit = int(data.get("limit") or 5)
            conn2 = tb.connect()
            try:
                out = tb.suggest_cleanup(conn2, limit=max(1, min(limit, 20)))
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
                return
            finally:
                conn2.close()
            self._json({"ok": True, "result": out})
            return

        if u.path == "/api/clean/apply":
            conn2 = tb.connect()
            try:
                out = tb.apply_cleanup(conn2, (data.get("proposal_id") or ""),
                                       (data.get("summary") or None))
            except KeyError as e:
                self._json({"ok": False, "error": str(e)}, 404)
                return
            except ValueError as e:
                self._json({"ok": False, "error": str(e)}, 422)
                return
            finally:
                conn2.close()
            self._json({"ok": True, "result": out})
            return

        if u.path == "/api/clean/reject":
            conn2 = tb.connect()
            try:
                out = tb.reject_cleanup(conn2, (data.get("proposal_id") or ""))
            finally:
                conn2.close()
            self._json({"ok": True, "result": out})
            return

        if u.path == "/api/entry/delete":
            conn2 = tb.connect()
            try:
                out = tb.delete_entry(conn2, (data.get("entry_id") or ""))
            except KeyError as e:
                self._json({"ok": False, "error": str(e)}, 404)
                return
            finally:
                conn2.close()
            self._json({"ok": True, "result": out})
            return

        if u.path == "/api/upload":
            allowed, why = import_allowed(_client_ip(self))
            if not allowed:
                self._json({"ok": False, "error": why}, 403)
                return
            files = data.get("files") or []
            if not isinstance(files, list) or not files:
                self._json({"ok": False, "error": "没有文件"}, 422)
                return
            if len(files) > 50:
                self._json({"ok": False, "error": "一次最多 50 个文件"}, 422)
                return
            project = (data.get("project") or "").strip()
            dry = bool(data.get("dry_run"))
            job = _start_upload(files, project, dry)
            self._json({"ok": True, "job": job["id"]})
            return

        if u.path == "/api/refine":
            limit = int(data.get("limit") or 10)
            conn = tb.connect()
            try:
                out = tb.refine(conn, limit=max(1, min(limit, 50)))
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
                return
            finally:
                conn.close()
            self._json({"ok": True, "result": out})
            return

        if u.path == "/api/entry/update":
            conn = tb.connect()
            try:
                out = tb.update_summary(conn, (data.get("entry_id") or ""),
                                        (data.get("summary") or ""))
            except KeyError as e:
                self._json({"ok": False, "error": str(e)}, 404)
                return
            except ValueError as e:
                self._json({"ok": False, "error": str(e)}, 422)
                return
            finally:
                conn.close()
            self._json({"ok": True, "result": out})
            return

        if u.path == "/api/entry/archive":
            eid = (data.get("entry_id") or "").strip()
            archived = bool(data.get("archived", True))
            conn = tb.connect()
            try:
                row = conn.execute("SELECT status FROM memory_entries WHERE entry_id=?",
                                   (eid,)).fetchone()
                if row is None:
                    self._json({"ok": False, "error": "没有这条记忆"}, 404)
                    return
                new_status = "archived" if archived else "active"
                with tb.tx(conn):
                    conn.execute("UPDATE memory_entries SET status=? WHERE entry_id=?",
                                 (new_status, eid))
                    tb._reindex(conn, eid)
            finally:
                conn.close()
            _c = tb.connect()
            tb.audit(_c, "owner", "archive" if archived else "restore", eid)
            _c.close()
            tb.log_event("manual", "memory archived" if archived else "memory restored", entry=eid)
            self._json({"ok": True, "status": new_status})
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

        if u.path == "/healthz":
            try:
                c = tb.connect()
                n = c.execute("SELECT count(*) n FROM memory_entries").fetchone()["n"]
                c.close()
                self._json({"ok": True, "entries": n})
            except Exception:
                self._json({"ok": False}, 500)
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
            elif u.path == "/api/list":
                status = (qs.get("status") or ["archived"])[0]
                category = (qs.get("category") or [""])[0]
                limit = int((qs.get("limit") or ["60"])[0])
                self._json({"items": tb.list_entries(conn, status=status,
                                                     category=category, limit=limit),
                            "status": status})
            elif u.path == "/api/import/status":
                job = _JOBS.get((qs.get("id") or [""])[0])
                if job is None:
                    self._json({"ok": False, "error": "没有这个任务"}, 404)
                else:
                    self._json({"ok": True, "job": dict(job)})
            elif u.path == "/api/clean/list":
                state = (qs.get("state") or ["pending"])[0]
                self._json({"items": tb.list_cleanup(conn, state=state)})
            elif u.path == "/api/meta":
                row = conn.execute(
                    "SELECT sum(extract_state='provisional' AND status IN ('active','pending_merge')) p,"
                    " sum(status='archived') a, sum(status='pending_merge') m,"
                    " sum(status='active') t, count(*) n FROM memory_entries").fetchone()
                self._json({"provisional": row["p"] or 0, "archived": row["a"] or 0,
                            "pending": row["m"] or 0, "active": row["t"] or 0,
                            "total": row["n"] or 0})
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
                audit_rows = [dict(r) for r in conn.execute(
                    "SELECT at, actor, action, detail FROM memory_audit "
                    "WHERE entry_id=? ORDER BY at DESC LIMIT 8", (eid,))]
                origin = tb.entry_origin(conn, eid)
                revisions = tb.entry_revisions(conn, eid)
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
                            "chain": nodes, "relations": rels, "audit": audit_rows, "origin": origin,
                       "revisions": [{"revision_id": r["revision_id"],
                                      "old": r["old_summary"], "reason": r["reason"],
                                      "at": r["created_at"]} for r in revisions]})
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
