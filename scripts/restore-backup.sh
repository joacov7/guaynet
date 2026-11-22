#!/bin/sh
# Restore a Guaynet backup made by the "backup" service.
# Usage (from the guaynet folder):  sh scripts/restore-backup.sh backups/guaynet_2026-11-22_0300.dump
# Stops the services that write to the database, REPLACES its content with the
# backup, and starts everything again.
set -eu
FILE="${1:-}"
if [ -z "$FILE" ] || [ ! -s "$FILE" ]; then
  echo "Uso: sh scripts/restore-backup.sh backups/guaynet_AAAA-MM-DD_HHMM.dump"
  echo "Backups disponibles:"; ls -1t backups/guaynet_*.dump 2>/dev/null | head -20
  exit 1
fi
echo "Esto REEMPLAZA todos los datos actuales de Guaynet por los del backup:"
echo "  $FILE"
printf "Escribí RESTAURAR para continuar: "
read -r answer
[ "$answer" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }

docker compose stop backend worker worker-critical worker-low beat bot
docker compose exec -T db pg_restore -U guaynet -d guaynet --clean --if-exists --no-owner < "$FILE"
docker compose up -d
echo "Listo: datos restaurados desde $FILE"
