#!/bin/sh
# Daily backup of the Guaynet database (runs in the "backup" service of
# docker-compose.yml). Writes /backups/guaynet_YYYY-MM-DD_HHMM.dump (pg_dump
# custom format, compressed) and keeps the last BACKUP_KEEP_DAYS days.
#   BACKUP_HOUR       hour of the daily backup (default 3, local time)
#   BACKUP_KEEP_DAYS  days to keep (default 14)
#   "once" as first argument: one backup now and exit (manual/test)
set -u
HOUR=$(printf "%02d" "${BACKUP_HOUR:-3}")
KEEP="${BACKUP_KEEP_DAYS:-14}"
DIR=/backups

backup() {
  file="$DIR/guaynet_$(date +%F_%H%M).dump"
  tmp="$file.partial"
  if pg_dump -h "${PGHOST:-db}" -U "${PGUSER:-guaynet}" -d "${PGDATABASE:-guaynet}" -Fc -f "$tmp" \
      && [ -s "$tmp" ] && pg_restore --list "$tmp" > /dev/null; then
    mv "$tmp" "$file"
    date "+%F %T" > "$DIR/ULTIMO_BACKUP_OK"
    echo "$(date '+%F %T') backup OK: $file ($(du -h "$file" | cut -f1))"
    find "$DIR" -name 'guaynet_*.dump' -mtime +"$KEEP" -print -delete
  else
    rm -f "$tmp"
    echo "$(date '+%F %T') ERROR: el backup falló" >&2
    return 1
  fi
}

mkdir -p "$DIR"
if [ "${1:-}" = "once" ]; then
  backup
  exit $?
fi

echo "Backups diarios a las ${HOUR}:00, se guardan ${KEEP} días en $DIR"
last=""
while true; do
  today=$(date +%F)
  if [ "$(date +%H)" = "$HOUR" ] && [ "$last" != "$today" ]; then
    backup && last="$today"
  fi
  sleep 60
done
