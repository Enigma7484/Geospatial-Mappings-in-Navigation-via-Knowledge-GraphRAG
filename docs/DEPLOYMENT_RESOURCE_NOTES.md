# Deployment Resource Notes

The backend is CPU and memory sensitive because route ranking builds OpenStreetMap graphs, projects geospatial data, optionally fetches park polygons, and may load a SentenceTransformer model for prompt/hybrid ranking.

## Recommended Small-Instance Settings

For a low-memory Render/VPS deployment, start with profile-only demos and disable optional park polygon processing:

```bash
GEOROUTE_ENABLE_PARKS=0
GEOROUTE_GRAPH_CACHE_SIZE=1
GEOROUTE_ROUTE_CACHE_SIZE=8
GEOROUTE_MAX_DIST_METERS=2500
GEOROUTE_MAX_K_ROUTES=3
```

Use one worker process:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

Multiple workers multiply memory usage because each worker keeps its own OSM graph cache and, for prompt/hybrid mode, its own embedding model.

The default `requirements.txt` is intentionally lightweight and excludes `torch`, `sentence-transformers`, and `scikit-learn`. Prompt/hybrid ranking still works in this mode, but it uses a lightweight lexical fallback instead of SBERT embeddings. For full semantic prompt/hybrid ranking, switch the build command to:

```bash
pip install -r requirements-full.txt
```

Full semantic prompt/hybrid mode will need more memory because it loads the embedding model stack.

## Runtime Checks

The API exposes:

- `GET /health` for basic uptime checks.
- `GET /runtime` for current deployment limits and in-memory cache statistics.

## Scaling Path

1. Keep the frontend on cheap static hosting.
2. Keep the FastAPI API small and use `ranking_mode="profile"` for the lowest memory mode.
3. Move prompt/hybrid ranking or large-distance route generation to a stronger worker machine.
4. Add a background job queue if route generation starts timing out under real users.
5. Precompute/cache common demo routes before presentations when possible.
