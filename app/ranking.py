import os


_model = None

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


def rank_route_texts(route_texts: list[str], user_pref: str):
    from sklearn.metrics.pairwise import cosine_similarity

    model = get_model()
    emb_routes = model.encode(route_texts, normalize_embeddings=True)
    emb_user = model.encode([user_pref], normalize_embeddings=True)
    scores = cosine_similarity(emb_user, emb_routes)[0]
    return scores
