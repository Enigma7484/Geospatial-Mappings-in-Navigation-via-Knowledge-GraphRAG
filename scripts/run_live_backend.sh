#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements-deploy.txt

export GEOROUTE_PROMPT_RANKER="${GEOROUTE_PROMPT_RANKER:-lexical}"
export GEOROUTE_USER_HISTORY_PATH="${GEOROUTE_USER_HISTORY_PATH:-data/user_histories_osm_trace.json}"
export GEOROUTE_ALLOWED_ORIGINS="${GEOROUTE_ALLOWED_ORIGINS:-http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173}"
export GEOROUTE_MAX_DIST_METERS="${GEOROUTE_MAX_DIST_METERS:-6000}"
export GEOROUTE_MAX_K_ROUTES="${GEOROUTE_MAX_K_ROUTES:-10}"
export OSMNX_CACHE_FOLDER="${OSMNX_CACHE_FOLDER:-osmnx_cache}"

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
