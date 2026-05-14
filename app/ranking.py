import os
import re
from collections import Counter

import numpy as np


_model = None
USE_SBERT = os.getenv("GEOROUTE_USE_SBERT", "0").lower() in {"1", "true", "yes"}

# Windows can fail to initialize PyTorch DLLs when the transformer stack imports
# torch indirectly under heavier CPU-thread defaults. Keep the SBERT baseline
# deterministic and CPU-only for the research prototype.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(1)
        _model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return _model


def lexical_rank_route_texts(route_texts: list[str], user_pref: str):
    query_terms = Counter(re.findall(r"[a-z0-9]+", user_pref.lower()))
    if not query_terms:
        return np.ones(len(route_texts), dtype=float) * 0.5

    scores = []
    query_norm = np.sqrt(sum(v * v for v in query_terms.values()))
    for text in route_texts:
        route_terms = Counter(re.findall(r"[a-z0-9]+", text.lower()))
        route_norm = np.sqrt(sum(v * v for v in route_terms.values()))
        if route_norm == 0:
            scores.append(0.0)
            continue
        dot = sum(query_terms[t] * route_terms.get(t, 0) for t in query_terms)
        scores.append(dot / (query_norm * route_norm))
    return np.asarray(scores, dtype=float)


def rank_route_texts(route_texts: list[str], user_pref: str):
    if not USE_SBERT:
        return lexical_rank_route_texts(route_texts, user_pref)

    try:
        model = get_model()
    except ImportError:
        return lexical_rank_route_texts(route_texts, user_pref)

    emb_routes = np.asarray(model.encode(route_texts, normalize_embeddings=True))
    emb_user = np.asarray(model.encode([user_pref], normalize_embeddings=True))[0]
    return emb_routes @ emb_user
