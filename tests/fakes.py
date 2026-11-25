"""Stand-ins for the online services, so the Vercel setup can be tested offline.

FakeTurso  a local HTTP server speaking Turso's /v2/pipeline format, backed by SQLite
FakeBlob   records put_blob / delete_blob calls like the Vercel Blob SDK
"""
import base64
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace


def _arg(v):
    t = v["type"]
    if t == "null":
        return None
    if t == "integer":
        return int(v["value"])
    if t == "float":
        return float(v["value"])
    if t == "blob":
        d = v["base64"]
        return base64.b64decode(d + "=" * (-len(d) % 4))
    return v["value"]


def _val(x):
    if x is None:
        return {"type": "null"}
    if isinstance(x, int):
        return {"type": "integer", "value": str(x)}
    if isinstance(x, float):
        return {"type": "float", "value": x}
    if isinstance(x, bytes):
        return {"type": "blob", "base64": base64.b64encode(x).decode()}
    return {"type": "text", "value": x}


class FakeTurso:
    TOKEN = "test-token"

    def __init__(self, path):
        self.path, self.requests = path, 0
        self.lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"   # keep-alive, like the real service

            def log_message(self, *a):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path != "/v2/pipeline" or self.headers.get("Authorization") != f"Bearer {fake.TOKEN}":
                    self._send(401, {"error": "unauthorized"})
                    return
                fake.requests += 1
                self._send(200, fake.pipeline(json.loads(body)))

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def pipeline(self, body):
        results = []
        with self.lock:
            db = sqlite3.connect(self.path)   # a fresh connection per pipeline, like a new Turso stream
            try:
                for req in body["requests"]:
                    try:
                        if req["type"] == "execute":
                            st = req["stmt"]
                            cur = db.execute(st["sql"], [_arg(a) for a in st.get("args", [])])
                            rows = cur.fetchall()
                            db.commit()
                            cols = [{"name": d[0], "decltype": None} for d in (cur.description or [])]
                            results.append({"type": "ok", "response": {"type": "execute", "result": {
                                "cols": cols, "rows": [[_val(v) for v in r] for r in rows],
                                "affected_row_count": max(cur.rowcount, 0),
                                "last_insert_rowid": str(cur.lastrowid) if cur.lastrowid else None}}})
                        elif req["type"] == "sequence":
                            db.executescript(req["sql"])
                            results.append({"type": "ok", "response": {"type": "sequence"}})
                        elif req["type"] == "close":
                            results.append({"type": "ok", "response": {"type": "close"}})
                    except sqlite3.Error as e:
                        results.append({"type": "error", "error": {"message": str(e), "code": "SQLITE_ERROR"}})
            finally:
                db.close()
        return {"baton": None, "base_url": None, "results": results}

    def stop(self):
        self.server.shutdown()


class FakeBlob:
    BASE = "https://teststore.public.blob.vercel-storage.com/"

    def __init__(self):
        self.files, self.deleted = {}, []

    def put_blob(self, pathname, body, access, content_type=None, cache_control_max_age=None, **kw):
        assert access == "public"
        url = self.BASE + pathname
        self.files[url] = (bytes(body), content_type, cache_control_max_age)
        return SimpleNamespace(url=url, pathname=pathname)

    def delete_blob(self, target):
        for t in (target if isinstance(target, list) else [target]):
            self.deleted.append(t)
            self.files.pop(t, None)
