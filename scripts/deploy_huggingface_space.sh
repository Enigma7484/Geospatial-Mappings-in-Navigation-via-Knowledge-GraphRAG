#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT_DIR/.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|[[:space:]]*'#'*) continue ;;
    esac

    key="${line%%=*}"
    value="${line#*=}"
    case "$key" in
      HF_SPACE_ID|HF_USERNAME|HF_TOKEN)
        value="$(printf '%s' "$value" | tr -d '\140')"
        if [[ "$value" == \"*\" ]]; then
          value="${value:1:${#value}-2}"
        elif [[ "$value" == \'*\' ]]; then
          value="${value:1:${#value}-2}"
        fi
        export "$key=$value"
        ;;
    esac
  done < "$ROOT_DIR/.env"
fi

SPACE_ID="${HF_SPACE_ID:-}"
TOKEN="${HF_TOKEN:-}"
USERNAME="${HF_USERNAME:-${SPACE_ID%%/*}}"
COMMIT_MESSAGE="${1:-Deploy MyWay backend}"

if [ -z "$SPACE_ID" ]; then
  echo "HF_SPACE_ID is required, for example: Enigma543/georoute-backend" >&2
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
title: MyWay API
emoji: 🗺️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# MyWay API

FastAPI backend for MyWay preference-aware route ranking with OpenStreetMap-derived route candidates.

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
git config user.name "MyWay Deploy"
git config user.email "deploy@myway.local"
git add .
git commit -m "$COMMIT_MESSAGE"
git branch -M main
git remote add space "https://huggingface.co/spaces/$SPACE_ID"
git -c credential.helper= \
  -c "credential.helper=!f() { echo username=$USERNAME; echo password=$TOKEN; }; f" \
  push --force space main

echo "Deployed to https://huggingface.co/spaces/$SPACE_ID"
