"""A tiny stand-in for psycopg, used only by the tests.

It speaks PostgreSQL's own network protocol to a real local PostgreSQL server (no password,
no TLS), and offers the few psycopg features the app uses: connect(), cursor().execute()
with %s placeholders, description, fetchall(), rowcount, closed/broken and the error classes.
"""
import socket
import struct
from decimal import Decimal
from urllib.parse import parse_qs, unquote, urlsplit


class Error(Exception):
    pass


class OperationalError(Error):
    pass


class DatabaseError(Error):
    pass


class IntegrityError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class _Column:
    def __init__(self, name, oid):
        self.name, self.type_code = name, oid


_CONVERT = {16: lambda v: v == "t", 20: int, 21: int, 23: int, 26: int, 700: float, 701: float, 1700: Decimal}


def _placeholders(sql):
    """psycopg style (%s, %%) -> PostgreSQL ($1, %)."""
    out, n, i = [], 0, 0
    while i < len(sql):
        if sql.startswith("%%", i):
            out.append("%"); i += 2
        elif sql.startswith("%s", i):
            n += 1; out.append(f"${n}"); i += 2
        else:
            out.append(sql[i]); i += 1
    return "".join(out)


def _text(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return b"true" if v else b"false"
    return str(v).encode()


class Cursor:
    def __init__(self, conn):
        self.conn, self.description, self.rowcount, self._rows = conn, None, -1, []

    def execute(self, sql, params=None):
        if params is None:
            self.description, self._rows, self.rowcount = self.conn._simple(sql)
        else:
            self.description, self._rows, self.rowcount = self.conn._extended(_placeholders(sql), params)
        return self

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class Connection:
    def __init__(self, url):
        u = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.sock = socket.create_connection((u.hostname or "127.0.0.1", u.port or 5432), timeout=10)
        self.closed = self.broken = False
        params = {"user": unquote(u.username or "postgres"), "database": (u.path or "/postgres")[1:] or "postgres",
                  "client_encoding": "UTF8"}
        if "options" in q:
            params["options"] = q["options"]
        body = struct.pack("!i", 196608) + b"".join(k.encode() + b"\0" + v.encode() + b"\0" for k, v in params.items()) + b"\0"
        self.sock.sendall(struct.pack("!i", len(body) + 4) + body)
        while True:
            t, data = self._read()
            if t == b"R" and struct.unpack("!i", data[:4])[0] != 0:
                raise OperationalError("the test server must allow connections without a password")
            if t == b"E":
                raise OperationalError(self._error(data)[1])
            if t == b"Z":
                break

    # -- wire helpers
    def _recv(self, n):
        buf = b""
        while len(buf) < n:
            try:
                chunk = self.sock.recv(n - len(buf))
            except OSError as exc:
                self.broken = True
                raise OperationalError(str(exc)) from exc
            if not chunk:
                self.broken = True
                raise OperationalError("server closed the connection")
            buf += chunk
        return buf

    def _read(self):
        head = self._recv(5)
        return head[:1], self._recv(struct.unpack("!i", head[1:])[0] - 4)

    def _send(self, kind, payload=b""):
        try:
            self.sock.sendall(kind + struct.pack("!i", len(payload) + 4) + payload)
        except OSError as exc:
            self.broken = True
            raise OperationalError(str(exc)) from exc

    @staticmethod
    def _error(data):
        fields = {f[:1]: f[1:].decode() for f in data.split(b"\0") if f}
        return fields.get(b"C", ""), fields.get(b"M", "error")

    def _collect(self):
        cols, rows, count, error = None, [], -1, None
        while True:
            t, data = self._read()
            if t == b"T":
                n, pos, cols = struct.unpack("!h", data[:2])[0], 2, []
                for _ in range(n):
                    end = data.index(b"\0", pos)
                    name = data[pos:end].decode()
                    oid = struct.unpack("!i", data[end + 7:end + 11])[0]
                    cols.append(_Column(name, oid))
                    pos = end + 19
            elif t == b"D":
                n, pos, row = struct.unpack("!h", data[:2])[0], 2, []
                for i in range(n):
                    size = struct.unpack("!i", data[pos:pos + 4])[0]; pos += 4
                    if size == -1:
                        row.append(None)
                    else:
                        v = data[pos:pos + size].decode(); pos += size
                        row.append(_CONVERT.get(cols[i].type_code, str)(v))
                rows.append(tuple(row))
            elif t == b"C":
                tag = data.rstrip(b"\0").decode().split()
                count = int(tag[-1]) if tag and tag[-1].isdigit() else -1
            elif t == b"E":
                error = self._error(data)
            elif t == b"Z":
                break
        if error:
            code, msg = error
            if code.startswith(("57P", "08")):          # server shut the connection
                self.broken = True
                raise OperationalError(msg)
            raise (IntegrityError if code.startswith("23") else ProgrammingError)(msg)
        return cols, rows, count

    def _simple(self, sql):
        self._send(b"Q", sql.encode() + b"\0")
        return self._collect()

    def _extended(self, sql, params):
        # like psycopg: numbers go as typed numbers, text and None as "unknown" (the server decides)
        oids = [16 if isinstance(p, bool) else 20 if isinstance(p, int) else 701 if isinstance(p, float) else 0 for p in params]
        self._send(b"P", b"\0" + sql.encode() + b"\0" + struct.pack("!h", len(oids)) + b"".join(struct.pack("!i", o) for o in oids))
        values = [_text(p) for p in params]
        bind = b"\0\0" + struct.pack("!h", 0) + struct.pack("!h", len(values))
        for v in values:
            bind += struct.pack("!i", -1) if v is None else struct.pack("!i", len(v)) + v
        self._send(b"B", bind + struct.pack("!h", 0))
        self._send(b"D", b"P\0")
        self._send(b"E", b"\0" + struct.pack("!i", 0))
        self._send(b"S")
        return self._collect()

    # -- psycopg-like API
    def cursor(self):
        return Cursor(self)

    def close(self):
        if not self.closed:
            try:
                self._send(b"X")
                self.sock.close()
            finally:
                self.closed = True


def connect(url, autocommit=True, prepare_threshold=None, **_):
    return Connection(url)
