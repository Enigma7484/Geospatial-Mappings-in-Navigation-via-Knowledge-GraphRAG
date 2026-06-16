# Free Backend Deployment Plan

This backend is heavier than a tiny CRUD API because OSMnx, GeoPandas, Shapely, and live Overpass queries all need real CPU and memory. The two no-payment paths that make sense are:

1. **Hugging Face Spaces with Docker** for a hosted public demo.
2. **Mac M5 plus Cloudflare Tunnel** for the live engine when you want your local machine to do the heavy lifting.

## Recommended Hosted Demo: Hugging Face Spaces

Use this when you want a shareable backend URL without paying for infrastructure.

- Create a new Hugging Face Space.
- Select **Docker** as the SDK.
- Push this backend repo to the Space.
- Leave `GEOROUTE_PROMPT_RANKER=lexical` unless you intentionally add a paid/API-backed model key.
- Set frontend `VITE_API_BASE_URL` to the Space URL, for example `https://YOUR_NAME-georoute-api.hf.space`.

Why this is the best hosted free fit: Hugging Face documents free CPU Spaces with enough memory for geospatial Python dependencies. Free 512 MB web-service tiers are likely to fail once GeoPandas/OSMnx import and build route graphs.

Tradeoffs:

- Cold starts can be slow.
- Disk is ephemeral, so cache warms again after rebuild/restart.
- Overpass API calls are still external and rate-limited.
- This is good for demos, not uptime-sensitive production.

## Best Zero-Dollar Live Engine: Mac M5 + Cloudflare Tunnel

Use this when you want the real backend engine to run with local horsepower.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-deploy.txt
export GEOROUTE_PROMPT_RANKER=lexical
export GEOROUTE_USER_HISTORY_PATH=data/user_histories_osm_trace.json
export GEOROUTE_ALLOWED_ORIGINS="http://localhost:3000,http://localhost:5173,https://YOUR_FRONTEND_DOMAIN"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then expose it:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Point the React frontend at the tunnel URL with:

```bash
VITE_API_BASE_URL=https://YOUR-TUNNEL.trycloudflare.com
```

Tradeoffs:

- No hosting bill and no cloud memory ceiling.
- Your Mac and internet connection are the uptime boundary.
- For a stable branded URL, use a Cloudflare-managed domain tunnel. The tunnel itself is free, but a domain may not be.

## No-Terminal Mac Service

Use this when the Mac will be awake but you do not want a terminal window keeping the backend alive.

```bash
./scripts/install_macos_backend_service.sh
```

This installs a macOS LaunchAgent named `com.georoute.backend`. It starts the FastAPI backend at login and restarts it if it crashes.

The installer copies the deployable backend into:

```text
~/.georoute-backend
```

That avoids macOS privacy restrictions that can prevent background services from reading files under `Documents`.

Check it:

```bash
curl http://127.0.0.1:8000/health
```

Logs are written to:

```text
~/.georoute-backend/logs/backend.launchd.out.log
~/.georoute-backend/logs/backend.launchd.err.log
```

Remove it:

```bash
./scripts/uninstall_macos_backend_service.sh
```

Important limitation: this still depends on the Mac being awake, online, and logged into the user session. It is not the same as a cloud deployment.

## Actually Always-On Without Your Mac

If the backend must keep running when the Mac is asleep, closed, restarted, or offline, it needs a host outside the laptop.

The no-payment path is still Hugging Face Spaces with Docker:

- URL stays stable.
- No terminal session required.
- Cold starts and free-tier availability are the tradeoff.
- The included `Dockerfile` is ready for this.

To deploy there, you need a Hugging Face account and either push this repo to a Docker Space manually or provide a Hugging Face token for CLI/Git-based deployment.

## Frontend Connection

The sibling frontend at `../GraphRAG-NavEng-FrontEnd/frontend` already reads:

```js
import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
```

For local development, create `../GraphRAG-NavEng-FrontEnd/frontend/.env.local`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

For a hosted frontend, set the same variable in Vercel, Netlify, or your static host.

## Production Hardening Next

- Add a small job queue if requests become concurrent or long-running.
- Pre-cache common demo geographies so first request latency is lower.
- Add rate limiting at Cloudflare or the hosting edge.
- Replace live Overpass dependency with a region extract and local routing service when you move beyond demo scale.
