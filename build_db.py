from pathlib import Path
import sqlite3

HERE = Path(__file__).resolve().parent
db_path = HERE / "university.db"

if db_path.exists():
    db_path.unlink()

conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON")
conn.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
conn.executescript((HERE / "sample_data.sql").read_text(encoding="utf-8"))
conn.commit()

# Sanity checks
violations = conn.execute("PRAGMA foreign_key_check").fetchall()
if violations:
    raise SystemExit(f"Foreign key violations: {violations}")

print(f"Created database: {db_path}")
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
for t in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t:<22} {count:>4} rows")

conn.close()
