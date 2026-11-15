#!/usr/bin/env bash
set -u

PROJECT_DIR="/opt/v-trende"
SERVICE="v-trende-scheduler@prepare.service"

service_state="$(systemctl show "$SERVICE" -p ActiveState --value)"
if [[ "$service_state" == "active" || "$service_state" == "activating" || "$service_state" == "reloading" ]]; then
  echo "Сервис systemd: работает ($service_state)"
  service_active=1
else
  echo "Сервис systemd: не работает ($service_state)"
  service_active=0
fi

cd "$PROJECT_DIR" || exit 1
docker compose --ansi never --profile scheduler -f deploy/docker-compose.yml \
  run --rm --no-TTY parser python -m parser.weekly_status
status=$?

if [[ $status -eq 2 && $service_active -eq 0 ]]; then
  echo "ВНИМАНИЕ: журнал не содержит завершения, но сервис уже остановлен."
  systemctl show "$SERVICE" -p Result -p ExecMainStatus --no-pager
  exit 1
fi
exit "$status"
