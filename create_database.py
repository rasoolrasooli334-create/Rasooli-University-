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
conn.close()
print(f"Created database: {db_path}")
