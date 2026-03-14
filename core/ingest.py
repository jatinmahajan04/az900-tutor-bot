"""
PDF ingestion pipeline: all PDFs in data/ → chunks by domain → ChromaDB
Run once (or re-run after adding new PDFs): python -m core.ingest
"""

import hashlib
from pathlib import Path

import fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions

DATA_DIR = Path(__file__).parent.parent / "data"
CHROMA_PATH = DATA_DIR / "chroma_db"

# AZ-900 official domain names (from Skills Measured doc)
DOMAINS = [
    "Cloud Concepts",
    "Azure Architecture and Services",
    "Azure Management and Governance",
]

# Keywords to auto-tag chunks by domain
DOMAIN_KEYWORDS = {
    "Cloud Concepts": [
        "cloud computing", "iaas", "paas", "saas", "public cloud", "private cloud",
        "hybrid cloud", "scalability", "elasticity", "high availability", "fault tolerance",
        "disaster recovery", "capital expenditure", "operational expenditure", "capex", "opex",
        "consumption-based", "shared responsibility",
    ],
    "Azure Architecture and Services": [
        "azure region", "availability zone", "resource group", "azure subscription",
        "management group", "virtual machine", "azure vm", "container", "kubernetes",
        "azure functions", "app service", "azure storage", "blob storage", "azure sql",
        "cosmos db", "virtual network", "vnet", "load balancer", "vpn gateway",
        "azure active directory", "azure ad", "entra id", "azure monitor", "azure backup",
    ],
    "Azure Management and Governance": [
        "azure portal", "azure cli", "azure powershell", "arm template", "bicep",
        "azure policy", "rbac", "role-based access control", "cost management",
        "pricing calculator", "total cost of ownership", "tco", "service level agreement",
        "sla", "azure advisor", "azure service health", "compliance", "trust center",
        "microsoft purview", "azure arc",
    ],
}


def tag_domain(text: str) -> str:
    """Return the best-matching domain for a chunk of text."""
    text_lower = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)
    return max(scores, key=scores.get)


def chunk_pdf(pdf_path: Path, chunk_size: int = 150, overlap: int = 30) -> list[dict]:
    """Extract and chunk text from PDF, tagging each chunk with a domain."""
    doc = fitz.open(str(pdf_path))
    chunks = []

    for page_num, page in enumerate(doc):
        text = page.get_text()
        if not text.strip():
            continue

        # Split into overlapping windows by word count
        words = text.split()
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i : i + chunk_size]
            if len(chunk_words) < 20:  # skip tiny fragments
                continue
            chunk_text = " ".join(chunk_words)
            chunks.append({
                "text": chunk_text,
                "page": page_num + 1,
                "domain": tag_domain(chunk_text),
                "id": hashlib.md5(chunk_text.encode()).hexdigest(),
            })

    doc.close()
    print(f"Extracted {len(chunks)} chunks from {pdf_path.name}")
    return chunks


def build_vector_store(chunks: list[dict]) -> chromadb.Collection:
    """Store chunks in ChromaDB with sentence-transformer embeddings."""
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    # Drop and recreate for a clean rebuild
    try:
        client.delete_collection("az900_chunks")
    except Exception:
        pass

    collection = client.create_collection(
        name="az900_chunks",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        collection.add(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[{"page": c["page"], "domain": c["domain"]} for c in batch],
        )
        print(f"  Indexed {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")

    return collection


def run():
    pdf_files = sorted(DATA_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {DATA_DIR}")
        return

    print(f"Found {len(pdf_files)} PDF(s): {[p.name for p in pdf_files]}\n")

    all_chunks = []
    for pdf_path in pdf_files:
        all_chunks.extend(chunk_pdf(pdf_path))

    # Show domain distribution
    from collections import Counter
    dist = Counter(c["domain"] for c in all_chunks)
    for domain, count in dist.items():
        print(f"  {domain}: {count} chunks")

    print("\nBuilding vector store...")
    collection = build_vector_store(all_chunks)
    print(f"\nDone. {collection.count()} chunks stored in {CHROMA_PATH}")


if __name__ == "__main__":
    run()
