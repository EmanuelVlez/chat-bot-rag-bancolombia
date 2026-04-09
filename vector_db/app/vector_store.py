import chromadb
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_PERSIST = Path(__file__).parent.parent / "data" / "chroma"
COLLECTION_NAME = "bancolombia_knowledge"


class VectorStore:
    def __init__(self, persist_path=None):
        path = str(persist_path or DEFAULT_PERSIST)
        Path(path).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ):
        """Inserta o actualiza chunks. Idempotente: se puede correr varias veces."""
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        category: str | None = None,
    ) -> list[dict]:
        """
        Búsqueda semántica. Retorna lista de dicts con content, metadata y score.
        Si se indica category, filtra por esa categoría.
        """
        where = {"category": category} if category else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "content": doc,
                "url": meta.get("url", ""),
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "score": round(1 - dist, 4),  # distancia coseno → similitud
            })

        return hits

    def get_by_url(self, url: str) -> list[dict]:
        """Retorna todos los chunks de una URL específica, ordenados por chunk_index."""
        results = self.collection.get(
            where={"url": url},
            include=["documents", "metadatas"],
        )

        chunks = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            chunks.append({
                "content": doc,
                "chunk_index": meta.get("chunk_index", 0),
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
            })

        return sorted(chunks, key=lambda x: x["chunk_index"])

    def list_categories(self) -> list[str]:
        results = self.collection.get(include=["metadatas"])
        categories = {m["category"] for m in results["metadatas"] if m.get("category")}
        return sorted(categories)

    def stats(self) -> dict:
        total_chunks = self.collection.count()
        results = self.collection.get(include=["metadatas"])
        urls = {m["url"] for m in results["metadatas"] if m.get("url")}
        categories = {m["category"] for m in results["metadatas"] if m.get("category")}

        return {
            "total_chunks": total_chunks,
            "total_pages": len(urls),
            "categories": sorted(categories),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "embedding_model": "intfloat/multilingual-e5-small",
            "dimensions": 384,
        }
