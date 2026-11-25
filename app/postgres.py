"""
PostgreSQL (Neon) connection with the same small interface the rest of the app uses for SQLite:
    conn.execute(sql, args) -> cursor with fetchall(), fetchone(), lastrowid, rowcount
    conn.executescript(sql), conn.commit(), conn.close()
Rows behave like sqlite3.Row: row["name"], row[0] and dict(row).

The app's queries are written once, SQLite style; `translate()` adapts them:
    ?            -> %s           (psycopg placeholders; a literal % becomes %%)
    LIKE         -> ILIKE        (SQLite's LIKE ignores upper/lower case; PostgreSQL's doesn't)
    INSERT INTO  -> … RETURNING id, so the new row's id is known (like sqlite's lastrowid)

Each statement commits on its own (autocommit), like the SQLite setup.
"""
import re
import threading

_local = threading.local()          # one connection per worker thread, reused between requests


class Row(tuple):
    """Read-only row: by position, by column name, and dict(row)."""

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
    def __init__(self, rows, rowcount, lastrowid=None):
        self._rows, self.rowcount, self.lastrowid = rows, rowcount, lastrowid

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


_INSERT = re.compile(r"^\s*INSERT\s+INTO\s+(\w+)", re.I)
_NO_ID = {"settings"}                 # tables keyed by something other than an id column


def translate(sql):
    """SQLite-style SQL -> psycopg/PostgreSQL. Text inside '…' quotes is left alone."""
    out, quoted = [], False
    for part in re.split(r"('(?:[^']|'')*')", sql):
        quoted = part.startswith("'") and part.endswith("'") and len(part) > 1
        if not quoted:
            part = part.replace("%", "%%").replace("?", "%s")
            part = re.sub(r"(?<![\w])LIKE(?![\w])", "ILIKE", part)
        else:
            part = part.replace("%", "%%")
        out.append(part)
    sql = "".join(out)
    m = _INSERT.match(sql)
    if m and m.group(1).lower() not in _NO_ID and "RETURNING" not in sql.upper():
        sql = sql.rstrip().rstrip(";") + " RETURNING id"
    return sql


def _driver(app_config):
    return app_config.get("PG_DRIVER") or __import__("psycopg")


class Connection:
    def __init__(self, url, driver):
        self.url, self.driver = url, driver

    def _conn(self, fresh=False):
        conns = getattr(_local, "conns", None)
        if conns is None:
            conns = _local.conns = {}
        c = conns.get(self.url)
        if fresh or c is None or c.closed or getattr(c, "broken", False):
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass
            # prepare_threshold=None: Neon's pooled address (…-pooler…) runs PgBouncer, which
            # doesn't keep prepared statements between transactions
            c = conns[self.url] = self.driver.connect(self.url, autocommit=True, prepare_threshold=None)
        return c

    def _run(self, sql, params):
        for attempt in (1, 2):
            try:
                cur = self._conn(fresh=attempt == 2).cursor()
                cur.execute(sql, params)
                return cur
            except self.driver.OperationalError:
                # the connection went away (e.g. the server function slept): reconnect once
                if attempt == 2:
                    raise

    def execute(self, sql, args=()):
        pg_sql = translate(sql)
        # yes/no values are stored as 1/0 (as in SQLite); PostgreSQL won't put true/false there
        params = tuple(int(a) if isinstance(a, bool) else a for a in args) if args else None
        cur = self._run(pg_sql, params)
        rows = []
        if cur.description:
            names = tuple(d.name for d in cur.description)
            index = {n: i for i, n in enumerate(names)}
            rows = [Row(r, names, index) for r in cur.fetchall()]
        lastrowid = rows[0]["id"] if (_INSERT.match(sql) and rows and "id" in rows[0].keys()) else None
        return Cursor(rows, cur.rowcount, lastrowid)

    def executescript(self, script):
        self._run(script, None)

    def commit(self):
        pass                         # autocommit

    def close(self):
        pass                         # kept open for the next request (see _conn)


def connect(url, app_config):
    return Connection(url, _driver(app_config))


def is_postgres_url(url):
    return bool(url) and url.split(":", 1)[0] in ("postgres", "postgresql")
