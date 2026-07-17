#!/bin/sh
# Runs once on first Postgres startup: create Langfuse's database alongside
# the app database, owned by the same single-node role.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE langfuse OWNER $POSTGRES_USER;
EOSQL
