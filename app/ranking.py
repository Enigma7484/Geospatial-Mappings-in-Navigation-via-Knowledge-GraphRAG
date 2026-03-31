from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def rank_route_texts(route_texts: list[str], user_pref: str):
    model = get_model()
    emb_routes = model.encode(route_texts, normalize_embeddings=True)
    emb_user = model.encode([user_pref], normalize_embeddings=True)
    scores = cosine_similarity(emb_user, emb_routes)[0]
    return scores