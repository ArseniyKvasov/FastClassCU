#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE DATABASE auth;
CREATE DATABASE content;
CREATE DATABASE classroom;
CREATE DATABASE assignments;
CREATE DATABASE answers;
CREATE DATABASE ai_assistant;
CREATE DATABASE collaboration;
CREATE DATABASE analytics;
SQL
