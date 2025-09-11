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

def query_similar(vector: list, k: int = 10):
    # query interface differs slightly across versions; try the common signature
    try:
        results = collection.query(embedding=vector, n_results=k)
    except TypeError:
        # some older versions use 'n_results' or 'k' naming
        try:
            results = collection.query(embedding=vector, n_results=k)
        except Exception:
            results = collection.query(embedding=vector, n_results=k)

    # normalize result shape robustly
    out = []
    try:
        ids = results["ids"][0]
        docs = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results.get("distances", [[None]*len(ids)])[0]
        for id_, doc, meta, dist in zip(ids, docs, metadatas, distances):
            out.append({"id": id_, "document": doc, "metadata": meta, "score": float(dist) if dist is not None else None})
    except Exception:
        # If results come as list-of-dicts fallback
        if isinstance(results, list):
            for item in results[:k]:
                out.append({
                    "id": item.get("id") or item.get("ids"),
                    "document": item.get("document") or item.get("documents"),
                    "metadata": item.get("metadata") or item.get("metadatas"),
                    "score": float(item.get("distance") or item.get("score")) if item.get("distance") or item.get("score") else None
                })
        else:
            raise RuntimeError("Unexpected Chroma query result format: " + str(type(results)))
    return out