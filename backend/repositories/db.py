import warnings
import warnings
import pymysql
import pymysql.cursors

try:
    from backend.config.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
except ModuleNotFoundError:
    from config.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


class DictAndIndexRow(dict):
    def __getitem__(self, item):
        if isinstance(item, int):
            return list(self.values())[item]
        return super().__getitem__(item)


def _wrap_row(row):
    if row is None:
        return None
    if isinstance(row, dict) and not isinstance(row, DictAndIndexRow):
        return DictAndIndexRow(row)
    return row


class MySQLCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query: str, args=None):
    # Direct execution without modifying the query string structure
        if args is not None:
            self._cursor.execute(query, args)
        else:
            self._cursor.execute(query)
        return self

    def executemany(self, query: str, args=None):
        if args is not None:
            self._cursor.executemany(query, args)
        else:
            self._cursor.executemany(query)
        return self


    def fetchone(self):
        return _wrap_row(self._cursor.fetchone())

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [_wrap_row(r) for r in rows] if rows else []

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        return [_wrap_row(r) for r in rows] if rows else []

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class MySQLConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        cursor = self._conn.cursor(pymysql.cursors.DictCursor)
        return MySQLCursorWrapper(cursor)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        autocommit=True,
    )
    return MySQLConnectionWrapper(conn)

