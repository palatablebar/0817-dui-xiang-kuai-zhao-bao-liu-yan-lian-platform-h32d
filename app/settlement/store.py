"""退租结算期次的持久化。

两张表：

- ``settlements``：期次清单本身，带乐观锁 revision 与签发状态；
- ``settled_identifiers``：所有已签发清单中已结算的源对象与快照，
  供后续期次做历史去重（已结算的不再计入）。

只保存成功（可对账）批次；阻断批次不写入，旧版清单原样保留。
"""

import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.business import DomainIssue

SCHEMA = """
CREATE TABLE IF NOT EXISTS settlements (
    id TEXT PRIMARY KEY, report TEXT NOT NULL, created TEXT NOT NULL,
    period INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
    revision INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
    reviewed TEXT
);
CREATE TABLE IF NOT EXISTS settled_identifiers (
    kind TEXT NOT NULL, identifier TEXT NOT NULL, settlement_id TEXT NOT NULL,
    period INTEGER NOT NULL, PRIMARY KEY (kind, identifier)
);
"""


class SettlementStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.row_factory = sqlite3.Row
            db.executescript(SCHEMA)
            yield db

    # ---- 期次清单 ------------------------------------------------------
    def register(self, run_id, report):
        with self.connect() as db:
            db.execute(
                "INSERT INTO settlements(id,report,created,period) "
                "VALUES (?,?,?,?) ON CONFLICT(id) DO NOTHING",
                (
                    run_id,
                    json.dumps(report, ensure_ascii=False),
                    report["manifest"]["created"],
                    report["period"],
                ),
            )
        return self.load(run_id)

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM settlements WHERE id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise DomainIssue("SETTLEMENT_NOT_FOUND")
        result = dict(row)
        result["report"] = json.loads(result["report"])
        return result

    def list(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,created,period,status,revision,note "
                    "FROM settlements ORDER BY period DESC, created DESC, id LIMIT 50"
                )
            ]

    def revise(self, run_id, revision, status, note, now):
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE settlements SET status=?,note=?,reviewed=?,"
                "revision=revision+1 WHERE id=? AND revision=?",
                (status, note, now, run_id, revision),
            )
            if cursor.rowcount != 1:
                raise DomainIssue("STALE_REVIEW")
            # 签发时把本期结算标识固化进历史表。
            if status == "APPROVED":
                report = json.loads(
                    db.execute(
                        "SELECT report FROM settlements WHERE id=?", (run_id,)
                    ).fetchone()["report"]
                )
                period = report["period"]
                batch = [
                    ("object", item["id"], run_id, period)
                    for dept in report["departments"]
                    for item in dept["items"]
                    if item["kind"] == "object"
                ] + [
                    ("snapshot", item["id"], run_id, period)
                    for dept in report["departments"]
                    for item in dept["items"]
                    if item["kind"] == "snapshot"
                ]
                db.executemany(
                    "INSERT OR IGNORE INTO settled_identifiers"
                    "(kind,identifier,settlement_id,period) VALUES (?,?,?,?)",
                    batch,
                )
        return self.load(run_id)

    # ---- 历史去重 ------------------------------------------------------
    def next_period(self):
        with self.connect() as db:
            row = db.execute("SELECT COALESCE(MAX(period),0) AS m FROM settlements").fetchone()
        return row["m"] + 1

    def settled_history(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT kind, identifier FROM settled_identifiers"
            ).fetchall()
        history = {"objects": set(), "snapshots": set()}
        bucket = {"object": "objects", "snapshot": "snapshots"}
        for row in rows:
            history[bucket[row["kind"]]].add(row["identifier"])
        return history
