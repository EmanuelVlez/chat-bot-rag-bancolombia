import sqlite3
from pathlib import Path

from embedder import Embedder
from vector_store import VectorStore

CHUNKS_DB = Path(__file__).parent.parent.parent / "processing" / "data" / "chunks.db"
BATCH_SIZE = 32  # chunks por lote — ajustar según RAM disponible


def load_chunks(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, url, title, category, chunk_index, content FROM chunks"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def main():
    print(f"Leyendo chunks de {CHUNKS_DB}")
    chunks = load_chunks(CHUNKS_DB)
    print(f"  {len(chunks)} chunks encontrados\n")

    if not chunks:
        print("No hay chunks. Ejecuta primero el processing layer.")
        return

    embedder = Embedder()
    store = VectorStore()

    total = len(chunks)

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]

        texts = [c["content"] for c in batch]
        embeddings = embedder.embed_passages(texts)

        # ID único por chunk: db id garantiza unicidad
        ids = [str(c["id"]) for c in batch]

        metadatas = [
            {
                "url": c["url"],
                "title": c["title"] or "",
                "category": c["category"] or "",
                "chunk_index": c["chunk_index"],
            }
            for c in batch
        ]

        store.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        end = min(i + BATCH_SIZE, total)
        print(f"  [{end}/{total}] chunks indexados")

    stats = store.stats()
    print(f"\nResumen ChromaDB:")
    print(f"  Total chunks  : {stats['total_chunks']}")
    print(f"  Total paginas : {stats['total_pages']}")
    print(f"  Categorias    : {', '.join(stats['categories'])}")
    print(f"  Modelo        : {stats['embedding_model']} ({stats['dimensions']} dims)")


if __name__ == "__main__":
    main()
