"""Retrieve relevant chunks from ChromaDB by domain or free-text query."""

import random
from pathlib import Path
from typing import Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
    _CHROMADB_AVAILABLE = True
except ImportError:
    _CHROMADB_AVAILABLE = False

DATA_DIR = Path(__file__).parent.parent / "data"
CHROMA_PATH = DATA_DIR / "chroma_db"

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = _client.get_collection(
            name="az900_chunks",
            embedding_function=ef,
        )
    return _collection


def _get_collection_safe():
    """Return collection or None if not available (e.g. on Railway without chroma_db)."""
    if not _CHROMADB_AVAILABLE:
        return None
    try:
        return _get_collection()
    except Exception:
        return None


def get_chunks_for_domain(domain: str, n: int = 5) -> list[str]:
    """Return n randomly sampled chunks filtered to a specific domain."""
    col = _get_collection_safe()
    if col is None:
        return []
    # Fetch a larger pool so we can randomly sample, giving variety each call
    pool_size = min(col.count(), max(n * 6, 30))
    results = col.query(
        query_texts=[domain],
        n_results=pool_size,
        where={"domain": domain},
    )
    docs = results["documents"][0] if results["documents"] else []
    if len(docs) <= n:
        return docs
    return random.sample(docs, n)


def get_chunks_for_query(query: str, domain: Optional[str] = None, n: int = 4) -> list[str]:
    """Semantic search; optionally filter by domain."""
    col = _get_collection_safe()
    if col is None:
        return []
    where = {"domain": domain} if domain else None
    results = col.query(
        query_texts=[query],
        n_results=n,
        where=where,
    )
    return results["documents"][0] if results["documents"] else []


def is_ready() -> bool:
    """Return True if the vector store has been built."""
    try:
        col = _get_collection()
        return col.count() > 0
    except Exception:
        return False
