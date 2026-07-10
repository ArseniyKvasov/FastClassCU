#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-fastclass-analytics}"

docker compose up -d db redis
docker compose build analytics-migrate analytics-service
docker compose run --rm analytics-migrate
docker compose up -d analytics-service

echo "Waiting for analytics-service readiness..."
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8010/ready" >/dev/null; then
    break
  fi
  sleep 2
done

event_id="${EVENT_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"
occurred_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
user_id="${USER_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"

read -r -d '' ENVELOPE <<JSON || true
{"event_id":"${event_id}","event_type":"generation_requested","occurred_at":"${occurred_at}","producer":"ai-assistant-service","schema_version":1,"trace_id":null,"payload":{"job_id":"22222222-2222-2222-2222-222222222222","requester_id":"${user_id}","intent":"generate_image"}}
JSON

docker compose exec -T redis redis-cli XADD events.ai-assistant-service '*' envelope "$ENVELOPE" >/dev/null

echo "Waiting for event consumption..."
sleep 5

docker compose exec -T db psql -U analytics -d analytics -c \
  "select activity_date, user_id, ai_jobs_requested from user_activity_daily where user_id = '${user_id}' order by activity_date desc limit 5;"

docker compose exec -T db psql -U analytics -d analytics -c \
  "select activity_date, ai_jobs_requested from platform_overview_daily order by activity_date desc limit 5;"
