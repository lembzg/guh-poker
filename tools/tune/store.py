"""Single-writer SQLite journal; crash recovery imports completed atomic worker results."""
import sqlite3
from pathlib import Path

from .common import canonical, read_json


class Store:
    def __init__(self, run):
        self.run = Path(run)
        self.db = sqlite3.connect(self.run / "results.sqlite", timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS results (id TEXT PRIMARY KEY, kind TEXT, phase TEXT, candidate TEXT, data TEXT)")
        self.db.execute("CREATE INDEX IF NOT EXISTS phase ON results(phase, candidate)")
        self.db.commit()

    def add(self, row):
        self.db.execute("INSERT OR IGNORE INTO results VALUES(?,?,?,?,?)", (
            row["id"], row["kind"], row.get("phase"), row.get("candidate"), canonical(row)))
        self.db.commit()

    def get(self, identity):
        row = self.db.execute("SELECT data FROM results WHERE id=?", (identity,)).fetchone()
        import json
        return json.loads(row[0]) if row else None

    def rows(self):
        import json
        return [json.loads(r[0]) for r in self.db.execute("SELECT data FROM results WHERE kind='match'")]

    def recover(self, plan_hash=None):
        count = 0
        for result in sorted((self.run / "jobs").glob("*/result.json")):
            job_file = result.parent / "job.json"
            if not job_file.exists():
                continue
            row, job = read_json(result), read_json(job_file)
            if row.get("id") != job.get("id") or row.get("plan_hash") != job.get("plan_hash"):
                raise RuntimeError(f"Mismatched recovery result: {result}")
            if plan_hash is not None and job.get("plan_hash") != plan_hash:
                raise RuntimeError(f"Recovery result belongs to another plan: {result}")
            if not self.get(row["id"]):
                self.add(row)
                count += 1
        return count

    def close(self):
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.db.close()
