#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

SPACE_ID="${HF_SPACE_ID:-}"
TOKEN="${HF_TOKEN:-}"
USERNAME="${HF_USERNAME:-${SPACE_ID%%/*}}"
COMMIT_MESSAGE="${1:-Deploy GeoRoute backend}"

if [ -z "$SPACE_ID" ]; then
  echo "HF_SPACE_ID is required, for example: Enigma7484/georoute-backend" >&2
  exit 1
fi

if [ -z "$TOKEN" ]; then
  echo "HF_TOKEN is required. Create a write token in Hugging Face settings." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$TMP_DIR/app" "$TMP_DIR/data"

rsync -a --delete "$ROOT_DIR/app/" "$TMP_DIR/app/"
rsync -a "$ROOT_DIR/data/user_histories_osm_trace.json" "$TMP_DIR/data/user_histories_osm_trace.json"
rsync -a "$ROOT_DIR/Dockerfile" "$TMP_DIR/Dockerfile"
rsync -a "$ROOT_DIR/requirements-deploy.txt" "$TMP_DIR/requirements-deploy.txt"

cat > "$TMP_DIR/README.md" <<'README'
---
title: GeoRoute Preference API
emoji: 🗺️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# GeoRoute Preference API

FastAPI backend for preference-aware route ranking with OpenStreetMap-derived route candidates.

Health check:

```text
/health
```

Main endpoint:

```text
POST /rank-routes
```
README

cd "$TMP_DIR"
git init
git config user.name "GeoRoute Deploy"
git config user.email "deploy@georoute.local"
git add .
git commit -m "$COMMIT_MESSAGE"
git branch -M main
git remote add space "https://huggingface.co/spaces/$SPACE_ID"
git -c credential.helper= \
  -c "credential.helper=!f() { echo username=$USERNAME; echo password=$TOKEN; }; f" \
  push --force space main

echo "Deployed to https://huggingface.co/spaces/$SPACE_ID"
