# backend/app/utils/vectorstore.py
import os
from dotenv import load_dotenv

load_dotenv()
PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COL_NAME = "profiles"

# Import chroma and its Settings where available
import chromadb
try:
    from chromadb.config import Settings
except Exception:
    Settings = None

def _create_client():
    """
    Try multiple ways to create a Chroma client so this file works across
    different chromadb versions:
      1) chromadb.PersistentClient(path=...)         - new persistent client API
      2) chromadb.Client(settings=Settings(...))     - older style with Settings
      3) chromadb.Client()                           - in-memory fallback
    """
    # 1) Try PersistentClient (recommended for local persistence)
    try:
        PersistentClient = getattr(chromadb, "PersistentClient", None)
        if PersistentClient is not None:
            client = PersistentClient(path=PERSIST_DIR)
            return client
    except Exception:
        # swallow and try next
        pass

    # 2) Try old-style Client with Settings (some versions)
    try:
        if Settings is not None:
            # attempt the duckdb+parquet persistent config
            try:
                settings = Settings(chroma_db_impl="duckdb+parquet", persist_directory=PERSIST_DIR)
            except Exception:
                # alternative key name in some versions
                settings = Settings(chroma_api_impl="chromadb.api.fastapi.FastAPI", allow_reset=True)
            client = chromadb.Client(settings=settings)
            return client
    except Exception:
        pass

    # 3) Fallback to in-memory client (non-persistent)
    try:
        client = chromadb.Client()
        return client
    except Exception as e:
        # last resort - re-raise so startup fails with helpful message
        raise RuntimeError(f"Failed to create chromadb client: {e}")

# create client
client = _create_client()

# create/get collection (robust to API variations)
collection = None
try:
    # preferred: get_collection
    collection = client.get_collection(name=COL_NAME)
except Exception:
    # try get_or_create_collection
    try:
        # some clients expose get_or_create_collection
        if hasattr(client, "get_or_create_collection"):
            collection = client.get_or_create_collection(name=COL_NAME)
        else:
            # try create_collection (it may succeed even if exists)
            collection = client.create_collection(name=COL_NAME)
    except Exception:
        # final fallback: try create_collection with minimal args
        try:
            collection = client.create_collection(name=COL_NAME)
        except Exception as e:
            raise RuntimeError(f"Failed to create or get Chroma collection: {e}")

def upsert_profile(profile_id: str, text: str, vector: list, metadata: dict = None):
    metadata = metadata or {}
    # upsert vs add: try multiple API names depending on version
    try:
        collection.upsert(
            ids=[profile_id],
            metadatas=[metadata],
            documents=[text],
            embeddings=[vector]
        )
    except Exception:
        # older versions sometimes use add
        try:
            collection.add(
                ids=[profile_id],
                metadatas=[metadata],
                documents=[text],
                embeddings=[vector]
            )
        except Exception as e:
            raise RuntimeError(f"Failed to upsert/add profile to Chroma collection: {e}")




import traceback
import logging

logger = logging.getLogger("uvicorn.error")

def _normalize_query_result(res):
    """
    Normalize various chroma return shapes into a list of dicts:
    [{'id': ..., 'document': ..., 'metadata': ..., 'score': ...}, ...]
    """
    ids, docs, metas, scores = [], [], [], []

    if res is None:
        return []

    # If res is a dict-like response from some chroma versions
    if isinstance(res, dict):
        ids = res.get("ids") or res.get("ids", [])
        docs = res.get("documents") or res.get("documents", [])
        metas = res.get("metadatas") or res.get("metadatas", [])
        # distances or scores
        scores = res.get("distances") or res.get("scores") or res.get("distances", [])

        # some APIs return nested lists (list per query). take first entry
        if ids and isinstance(ids[0], list):
            ids = ids[0]
        if docs and isinstance(docs[0], list):
            docs = docs[0]
        if metas and isinstance(metas[0], list):
            metas = metas[0]
        if scores and isinstance(scores[0], list):
            scores = scores[0]

    # If res is a list of dicts already
    elif isinstance(res, list):
        # try to detect simple list of results
        out = []
        for item in res:
            if isinstance(item, dict) and "id" in item:
                out.append({
                    "id": item.get("id"),
                    "document": item.get("document") or item.get("doc") or "",
                    "metadata": item.get("metadata") or item.get("meta") or {},
                    "score": item.get("score") or item.get("distance") or None,
                })
        if out:
            return out
        # otherwise leave as empty and try other paths below

    # Build normalized list from parallel arrays
    results = []
    max_len = max(len(ids or []), len(docs or []), len(metas or []), len(scores or []))
    for i in range(max_len):
        _id = ids[i] if i < len(ids) else None
        _doc = docs[i] if i < len(docs) else ""
        _meta = metas[i] if i < len(metas) else {}
        _score = scores[i] if i < len(scores) else None
        results.append({"id": _id, "document": _doc, "metadata": _meta, "score": _score})
    return results

def query_similar(query_vector, k=10):
    """
    Robust query wrapper: try several signature variants supported by different Chroma versions.
    Returns normalized list of results: [{'id','document','metadata','score'}, ...]
    """
    # `collection` should be defined earlier in this module (your existing chroma collection)
    try:
        # 1) Preferred modern API: query(query_embeddings=[vec], n_results=k)
        try:
            res = collection.query(query_embeddings=[query_vector], n_results=k)
            return _normalize_query_result(res)
        except TypeError:
            pass
        except Exception as e:
            logger.debug("query(query_embeddings...) error: %s", e)
            # continue to other attempts

        # 2) Alternative: query(embedding=[vec], n_results=k)
        try:
            res = collection.query(embedding=[query_vector], n_results=k)
            return _normalize_query_result(res)
        except TypeError:
            pass
        except Exception as e:
            logger.debug("query(embedding...) error: %s", e)

        # 3) Another variant: query(query_vector=query_vector, top_k=k) (rare)
        try:
            res = collection.query(query_vector=query_vector, top_k=k)
            return _normalize_query_result(res)
        except Exception as e:
            logger.debug("query(query_vector...) error: %s", e)

        # 4) Fallback: some versions expose .similarity_search or .search_by_vector
        if hasattr(collection, "similarity_search"):
            try:
                res = collection.similarity_search(query_vector, k)
                # similarity_search often returns list of documents, or list of tuples (doc, score)
                out = []
                for item in res:
                    if isinstance(item, tuple) and len(item) >= 2:
                        doc, score = item[0], item[1]
                        out.append({"id": None, "document": getattr(doc, "page_content", str(doc)), "metadata": {}, "score": score})
                    else:
                        out.append({"id": None, "document": str(item), "metadata": {}, "score": None})
                return out
            except Exception as e:
                logger.debug("similarity_search error: %s", e)

        # 5) Last resort: try query by text (not ideal)
        try:
            res = collection.query(query_texts=[""], n_results=k)
            return _normalize_query_result(res)
        except Exception as e:
            logger.debug("query(query_texts) fallback error: %s", e)

        # If we reach here, nothing worked
        logger.error("All Chroma query attempts failed. See debug logs.")
        return []
    except Exception as exc:
        logger.error("query_similar unexpected error: %s\n%s", exc, traceback.format_exc())
        return []






























































































































































































