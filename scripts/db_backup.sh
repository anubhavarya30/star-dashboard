#!/usr/bin/env bash
# STAR — DB backup. Snapshots star_trading.db (the trade ledger STAR is learning
# from) to backups/ using SQLite's safe .backup (consistent even while in use),
# timestamped, keeping the last 72 hourly snapshots + a daily copy. Runs hourly via
# com.star.dbbackup so a disk failure / corruption never wipes the dataset.
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1
DB="star_trading.db"
DIR="backups"
mkdir -p "$DIR"
[ -f "$DB" ] || { echo "no $DB"; exit 0; }
TS=$(date +%Y%m%d_%H%M)
DAY=$(date +%Y%m%d)
# consistent snapshot (works while the DB is open by other processes)
./venv/bin/python3 - "$DB" "$DIR/star_${TS}.db" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(src); d = sqlite3.connect(dst)
with d:
    s.backup(d)
s.close(); d.close()
PY
# keep a daily snapshot too
cp -f "$DIR/star_${TS}.db" "$DIR/daily_${DAY}.db"
# OFFSITE copy: a single gzipped latest committed to git (survives server death).
# The autosave Stop hook pushes it to GitHub, so the dataset lives off the machine.
gzip -c "$DIR/star_${TS}.db" > "$DIR/star_latest.db.gz"
# prune: keep last 72 hourly + 14 daily snapshots locally
ls -1t "$DIR"/star_2*.db 2>/dev/null | tail -n +73 | xargs -I{} rm -f {} 2>/dev/null || true
ls -1t "$DIR"/daily_*.db 2>/dev/null | tail -n +15 | xargs -I{} rm -f {} 2>/dev/null || true
echo "backed up -> $DIR/star_${TS}.db ($(du -h "$DIR/star_${TS}.db" | cut -f1)) + offsite star_latest.db.gz"
