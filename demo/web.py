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

from ui import PAGE, LOGIN_HTML  # noqa: E402  （界面模板独立成文件）


# ------------------------------------------------------------------ 后台导入任务
_JOBS: dict = {}
_JOBS_LOCK = threading.Lock()
_IMPORT_MAX_FILES = 2000


def _new_job(total: int, project: str, path_label: str) -> dict:
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "state": "running", "done": 0, "total": total, "added": 0,
           "updated": 0, "skipped": 0, "failed": 0, "entries": 0, "cancel": False,
           "failures": [], "started": time.time(), "path": path_label, "project": project}
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    return job


def _start_import(target: Path, project: str, dry: bool) -> dict:
    job = _new_job(0, project, str(target))
    threading.Thread(target=_import_worker, args=(job, target, project, dry), daemon=True).start()
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
        targets = list(tbc.iter_targets([str(target)], {}, exclude=data_root))[:_IMPORT_MAX_FILES]
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


def _start_upload(files: list, project: str, dry: bool) -> dict:
    job = _new_job(len(files), project, "上传")
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
            elif u.path == "/api/recent":
                limit = int((qs.get("limit") or ["8"])[0])
                self._json({"items": tb.recent_entries(conn, limit=limit)})
            elif u.path == "/api/sources":
                limit = int((qs.get("limit") or ["100"])[0])
                self._json({"items": tb.list_documents(conn, limit=limit)})
            elif u.path == "/api/doc":
                did = (qs.get("id") or [""])[0]
                doc = conn.execute("SELECT doc_id, title, created_at, char_count, entry_count "
                                   "FROM memory_documents WHERE doc_id=?", (did,)).fetchone()
                if doc is None:
                    self._json({"error": "not found"}, 404)
                else:
                    self._json({"doc": dict(doc), "items": tb.document_entries(conn, did)})
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
