"""
A tiny sqlite3-style connection to Turso (hosted SQLite / libSQL) over its HTTP API.

Why: on Vercel the code folder is read-only and /tmp is wiped, so a local SQLite file would lose
every product you add. Turso keeps the same SQLite database online, so all the SQL in this project
works unchanged. Only the standard library is used.

    conn = connect("libsql://vision-yourname.turso.io", "token")
    conn.execute("SELECT * FROM products WHERE slug = ?", ("x",)).fetchall()

Each statement is sent to POST /v2/pipeline and runs in its own transaction (autocommit), so
`commit()` has nothing to do. Rows behave like sqlite3.Row: row["name"], row[0] and dict(row).
"""
import base64
import http.client
import json
import threading
from urllib.parse import urlsplit


class Error(Exception):
    """A statement failed on the Turso side (bad SQL, constraint …)."""


class Row(tuple):
    """Read-only row: by position, by column name, and dict(row)."""
    _names = ()

    def __new__(cls, values, names, index):
        row = super().__new__(cls, values)
        row._names, row._index = names, index
        return row

    def __getitem__(self, key):
        if isinstance(key, str):
            return tuple.__getitem__(self, self._index[key])
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._names)


class Cursor:
    def __init__(self, result):
        names = tuple(c.get("name") or "" for c in result.get("cols", []))
        index = {n: i for i, n in enumerate(names)}
        self._rows = [Row([_from_value(v) for v in r], names, index) for r in result.get("rows", [])]
        rowid = result.get("last_insert_rowid")
        self.lastrowid = int(rowid) if rowid is not None else None
        self.rowcount = result.get("affected_row_count", -1)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


def _to_value(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"type": "blob", "base64": base64.b64encode(bytes(v)).decode().rstrip("=")}
    return {"type": "text", "value": str(v)}


def _from_value(v):
    t = v.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(v["value"])
    if t == "float":
        return float(v["value"])
    if t == "blob":
        data = v.get("base64", "")
        return base64.b64decode(data + "=" * (-len(data) % 4))
    return v.get("value")


class _Http:
    """One kept-alive HTTPS connection per server process (saves a TLS handshake per query)."""

    def __init__(self, url, token):
        parts = urlsplit(url.replace("libsql://", "https://", 1))
        self.secure = parts.scheme == "https"
        self.host, self.port = parts.hostname, parts.port
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._conn, self._lock = None, threading.Lock()

    def _new(self):
        cls = http.client.HTTPSConnection if self.secure else http.client.HTTPConnection
        return cls(self.host, self.port, timeout=15)

    def post(self, body):
        payload = json.dumps(body).encode()
        with self._lock:
            for attempt in (1, 2):   # a kept-alive connection may have been closed by the server: retry once
                try:
                    if self._conn is None:
                        self._conn = self._new()
                    self._conn.request("POST", "/v2/pipeline", payload, self.headers)
                    res = self._conn.getresponse()
                    data = res.read()
                    break
                except (http.client.HTTPException, OSError):
                    if self._conn:
                        self._conn.close()
                    self._conn = None
                    if attempt == 2:
                        raise
        if res.status != 200:
            raise Error(f"Turso answered {res.status}: {data[:300].decode(errors='replace')}")
        return json.loads(data)


_clients = {}
_clients_lock = threading.Lock()


def _client(url, token):
    with _clients_lock:
        key = (url, token)
        if key not in _clients:
            _clients[key] = _Http(url, token)
        return _clients[key]


class Connection:
    """Enough of sqlite3.Connection for this app: execute, executescript, commit, close."""

    row_factory = None   # accepted and ignored: rows are always Row objects

    def __init__(self, url, token):
        self._http = _client(url, token)

    def _run(self, requests):
        out = self._http.post({"requests": requests + [{"type": "close"}]})
        results = out.get("results", [])
        for r in results:
            if r.get("type") == "error":
                raise Error(r.get("error", {}).get("message", "Turso error"))
        return results

    def execute(self, sql, args=()):
        stmt = {"sql": sql, "args": [_to_value(a) for a in args]}
        requests = [{"type": "execute", "stmt": stmt}]
        if not sql.lstrip().upper().startswith(("SELECT", "PRAGMA")):
            # foreign keys (ON DELETE CASCADE) are a per-connection setting: switch them on for writes
            requests.insert(0, {"type": "execute", "stmt": {"sql": "PRAGMA foreign_keys = ON"}})
        results = self._run(requests)
        return Cursor(results[len(requests) - 1]["response"]["result"])

    def executescript(self, script):
        self._run([{"type": "sequence", "sql": script}])

    def commit(self):
        pass

    def close(self):
        pass


def connect(url, token):
    return Connection(url, token)
