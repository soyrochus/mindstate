from dataclasses import replace

from mindstate.config import get_settings
from mindstate.memory_db import ensure_memory_schema


class FakeCursor:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))


class FakeConn:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


def test_ensure_memory_schema_adds_structures_without_destructive_sql():
    settings = get_settings()
    settings = replace(settings, memory=replace(settings.memory, embedding_dimensions=8))
    cur = FakeCursor()
    conn = FakeConn()

    ensure_memory_schema(cur, conn, settings)

    sql_blob = "\n".join(stmt for stmt, _ in cur.statements).lower()
    assert "create table if not exists memory_items" in sql_blob
    assert "create table if not exists memory_chunks" in sql_blob
    assert "create table if not exists memory_embeddings" in sql_blob
    assert "create table if not exists memory_links" in sql_blob
    assert "drop table" not in sql_blob
    assert conn.committed is True
