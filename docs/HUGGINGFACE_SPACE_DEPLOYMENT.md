# Hugging Face Space Deployment

This is the external no-terminal backend deployment path.

## One-Time Setup

1. Create a Hugging Face account.
2. Create a new Space.
3. Choose **Docker** as the Space SDK.
4. Name it something like:

```text
Enigma7484/georoute-backend
```

## Manual Deploy From This Machine

Create a Hugging Face write token, then run:

```bash
export HF_SPACE_ID="Enigma7484/georoute-backend"
export HF_TOKEN="hf_..."
./scripts/deploy_huggingface_space.sh
```

The deployed backend URL will usually be:

```text
https://Enigma7484-georoute-backend.hf.space
```

Health check:

```bash
curl https://Enigma7484-georoute-backend.hf.space/health
```

## GitHub Actions Deploy

Set these in the backend GitHub repository:

- Repository variable `HF_SPACE_ID`: `Enigma7484/georoute-backend`
- Repository secret `HF_TOKEN`: Hugging Face write token

Then run the **Deploy Hugging Face Space** workflow manually, or let it run after pushes to backend deployment files.

## Frontend

Once the Space is live, point the frontend at:

```bash
VITE_API_BASE_URL=https://Enigma7484-georoute-backend.hf.space
```

For Vercel/Netlify/GitHub Pages, set `VITE_API_BASE_URL` in the frontend host environment settings and rebuild.

## Limits

This is external hosting, so it keeps working when the Mac terminal is closed. On the free tier, cold starts and occasional sleeps are expected. First route requests can still take a while because OSM graph data is fetched and processed live.
