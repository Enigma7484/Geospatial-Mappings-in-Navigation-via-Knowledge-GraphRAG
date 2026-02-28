import re
import time
import requests
from collections import Counter
from SPARQLWrapper import SPARQLWrapper, JSON
import spacy

# --------- Config ---------
nlp = spacy.load("en_core_web_sm")

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

USER_AGENT = "kg-rag-starter/0.2 (research; contact: omarhaque7484@gmail.com)"
HTTP_TIMEOUT = 30

# Predicates we consider "conceptual" (avoid IDs/files/DOIs/etc.)
INTERESTING_PREDICATES = [
    "wdt:P31",   # instance of
    "wdt:P279",  # subclass of
    "wdt:P361",  # part of
    "wdt:P527",  # has part
    "wdt:P101",  # field of work
    "wdt:P1269", # facet of
    "wdt:P921",  # main subject
    "wdt:P910",  # topic's main category
]

# --------- Wikidata entity search ---------
def wikidata_search_entity(name: str, limit: int = 1):
    """Return top Wikidata QID(s) for a surface string."""
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": limit,
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    # Retry a couple times in case of transient 403/rate limiting
    for attempt in range(3):
        r = requests.get(WIKIDATA_API, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        if r.status_code == 403:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        return [item["id"] for item in data.get("search", []) if "id" in item]

    return []

# --------- Entity extraction (spaCy + fallback) ---------
def extract_entity_strings(text: str):
    """
    Extract entity-like strings from text.
    Primary: spaCy NER (PERSON/ORG/etc.)
    Fallback: capture technical/Capitalized tokens (GeoSPARQL, LinkedGeoData, OpenStreetMap, etc.)
    """
    doc = nlp(text)

    ents = []
    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT", "WORK_OF_ART"}:
            ents.append(ent.text.strip())

    # De-dup while keeping order
    seen = set()
    out = []
    for e in ents:
        key = e.lower()
        if key not in seen:
            seen.add(key)
            out.append(e)

    # Fallback if spaCy misses technical terms
    if len(out) < 2:
        candidates = re.findall(r"\b[A-Z][A-Za-z0-9\-]+\b", text)
        # De-dup while keeping order
        out = list(dict.fromkeys(candidates))

    return out

# --------- SPARQL: fetch related facts (filtered) ---------
def fetch_related_facts(qid: str, limit: int = 50):
    sparql = SPARQLWrapper(WIKIDATA_SPARQL)
    values_block = " ".join(INTERESTING_PREDICATES)

    query = f"""
    SELECT ?p ?pLabel ?o ?oLabel WHERE {{
      VALUES ?p {{ {values_block} }}
      wd:{qid} ?p ?o .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT {limit}
    """

    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.addCustomHttpHeader("User-Agent", USER_AGENT)
    results = sparql.query().convert()

    facts = []
    for b in results.get("results", {}).get("bindings", []):
        # Prefer labels; fallback to raw values if labels missing
        p = b.get("pLabel", {}).get("value") or b.get("p", {}).get("value")
        o = b.get("oLabel", {}).get("value") or b.get("o", {}).get("value")
        if p and o:
            facts.append((p, o))
    return facts

# --------- Main: text -> top-k related facts ---------
def text_to_topk_related(text: str, k: int = 10):
    ent_strings = extract_entity_strings(text)

    # map text entities -> QIDs
    qids = []
    for e in ent_strings:
        hits = wikidata_search_entity(e, limit=1)
        if hits:
            qids.append(hits[0])

    # collect related facts and rank
    counter = Counter()

    for qid in qids:
        for p, o in fetch_related_facts(qid, limit=80):
            counter[(p, o)] += 1

    # Better ranking: higher frequency first, then predicate alphabetical for tie-break
    top_items = sorted(counter.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))[:k]

    return {
        "entities_found": ent_strings,
        "qids": qids,
        "topk_facts": [{"predicate": p, "object": o, "score": c} for ((p, o), c) in top_items],
    }

# --------- Demo run ---------
if __name__ == "__main__":
    sample = (
        "GeoSPARQL is an OGC standard for querying geospatial RDF data. "
        "LinkedGeoData converts OpenStreetMap into RDF and can be queried with SPARQL."
    )

    out = text_to_topk_related(sample, k=10)
    print("Entities:", out["entities_found"])
    print("QIDs:", out["qids"])
    print("\nTop-k related facts:")
    for f in out["topk_facts"]:
        print(f"- {f['predicate']} -> {f['object']} (score={f['score']})")