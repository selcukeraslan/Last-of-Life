"""Bir kerelik aktarım: yerel SQLite (data/iddia.db) -> DATABASE_URL'deki Postgres.

Kullanım:
    DATABASE_URL=... .venv/bin/python scripts/import_sqlite_to_postgres.py [--sqlite data/iddia.db]

Hedef tablolar önce boşaltılır, sonra tek işlemde doldurulur (tekrar çalıştırmak güvenlidir).
Şema önce `supabase db push` ile kurulmuş olmalıdır. Kilit (update_lock) aktarılmaz.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import DB_PATH  # noqa: E402  (.env burada okunur)

TABLES = ["matches", "news", "fetch_log", "iddaa_events", "iddaa_odds", "meta"]
SKIP_META = {"update_lock"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sqlite", default=str(DB_PATH), help="Kaynak SQLite dosyası")
    args = ap.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL tanımlı değil")

    src = sqlite3.connect(f"file:{args.sqlite}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    counts = {}
    with psycopg.connect(url, prepare_threshold=None) as dst:
        dst.execute("TRUNCATE " + ", ".join(TABLES))
        for table in TABLES:
            rows = [dict(r) for r in src.execute(f"SELECT * FROM {table}")]
            if table == "meta":
                rows = [r for r in rows if r["key"] not in SKIP_META]
                legacy = next((r["value"] for r in rows if r["key"] == "last_update"), None)
                if legacy and not any(r["key"] == "last_updated_at" for r in rows):
                    rows.append({"key": "last_updated_at", "value": legacy})
            if rows:
                cols = list(rows[0])
                sql = (f"INSERT INTO {table} ({', '.join(cols)}) "
                       f"VALUES ({', '.join('%s' for _ in cols)})")
                with dst.cursor() as cur:
                    cur.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
            counts[table] = len(rows)
        # aktarımı doğrula (commit'ten önce): hedefteki satır sayıları kaynakla eşleşmeli
        for table, n in counts.items():
            got = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if got != n:
                raise SystemExit(f"{table}: kaynakta {n}, hedefte {got} satır; işlem geri alındı")
    for table, n in counts.items():
        print(f"{table}: {n} satır aktarıldı")


if __name__ == "__main__":
    main()
