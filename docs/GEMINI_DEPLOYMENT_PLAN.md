# Gemini Deployment Plan

The backend now supports hosted prompt ranking through Gemini while keeping the existing local profile logic.

## Ranking Modes

- `prompt`: uses Gemini when `GEMINI_API_KEY` is set. If no key is present and `GEOROUTE_PROMPT_RANKER=auto`, it falls back to local SBERT.
- `profile`: stays fully local and uses user history plus route features from `app/profile.py`.
- `hybrid`: computes the profile score locally and combines it with the Gemini/SBERT prompt score.

The current hybrid formula remains:

```python
combined = 0.75 * profile_scores + 0.25 * prompt_scores
```

## Local Setup

Create a local `.env` file in the backend repo root:

```bash
GEMINI_API_KEY=your_key_here
GEOROUTE_PROMPT_RANKER=auto
GEMINI_MODEL=gemini-2.5-flash
```

Then run the backend normally:

```bash
uvicorn app.main:app --reload
```

## Provider Controls

Use `GEOROUTE_PROMPT_RANKER` to choose the prompt scorer:

- `auto`: Gemini if a key is present, otherwise local SBERT.
- `gemini`: require Gemini and fail if no key is configured.
- `sbert`: force the original local SentenceTransformer ranking.
- `lexical`: lightweight no-model fallback for debugging.

## Deployment Dependencies

For a Gemini-backed deployment, use:

```bash
pip install -r requirements-deploy.txt
```

For the original full local research stack, use:

```bash
pip install -r requirements.txt
```

This keeps the deployable backend free of `torch`, `sentence-transformers`, and `scikit-learn`, while preserving the original full local demo path.

