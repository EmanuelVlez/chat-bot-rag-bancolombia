import os
import sqlite3
from pathlib import Path

from cleaner import TextCleaner
from chunker import Chunker
from chunk_store import ChunkStore

# raw.db producido por el scraper
RAW_DB = Path(os.getenv("RAW_DB_PATH", Path(__file__).parent.parent.parent / "scraper" / "data" / "raw.db"))


def load_pages(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT url, title, category, content FROM pages"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def main():
    print(f"Leyendo paginas de {RAW_DB}")
    pages = load_pages(RAW_DB)
    print(f"  {len(pages)} paginas encontradas\n")

    cleaner = TextCleaner()
    chunker = Chunker()
    store = ChunkStore()
    store.init()

    total_chunks = 0
    skipped = 0

    for page in pages:
        url = page["url"]
        cleaned = cleaner.clean(page["content"] or "")

        if not cleaned:
            print(f"  [SKIP] Sin contenido util: {url}")
            skipped += 1
            continue

        chunks = chunker.chunk(cleaned)

        if not chunks:
            print(f"  [SKIP] Sin chunks: {url}")
            skipped += 1
            continue

        store.clear_url(url)  # idempotente: permite reprocesar
        store.save_chunks(
            url=url,
            title=page["title"],
            category=page["category"],
            chunks=chunks,
        )

        total_chunks += len(chunks)
        print(f"  {len(chunks):>3} chunks  [{page['category']}]  {url}")

    stats = store.stats()
    store.close()

    print("\nResumen:")
    print(f"  Paginas procesadas : {len(pages) - skipped}")
    print(f"  Paginas saltadas   : {skipped}")
    print(f"  Total chunks       : {stats['total_chunks']}")
    print(f"  Total tokens       : {stats['total_tokens']}")


if __name__ == "__main__":
    main()
