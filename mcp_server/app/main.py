import sys
import os
import logging
from pathlib import Path

# MCP usa stdio: stdout debe estar limpio para JSON-RPC.
# Redirigir todos los prints/logs de librerías a stderr antes de importarlas.
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TQDM_DISABLE"] = "1"
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
for _noisy in ("sentence_transformers", "transformers", "huggingface_hub",
               "chromadb", "httpx", "torch"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

# Comparte embedder y vector_store del módulo vector_db sin duplicar código
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "vector_db" / "app"))

# MCP usa stdout para JSON-RPC: redirigir durante la carga del modelo
# para que prints de sentence-transformers/chromadb no corrompan el stream.
_real_stdout = sys.stdout
sys.stdout = sys.stderr

from embedder import Embedder
from vector_store import VectorStore
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "bancolombia-rag",
    instructions=(
        "Servidor RAG con la base de conocimiento del sitio web de Bancolombia personas. "
        "Contiene información sobre productos financieros (créditos, cuentas, tarjetas, seguros, "
        "vivienda, inversiones), servicios, tarifas, beneficios y canales de atención. "
        "Úsalo para responder preguntas de clientes sobre el banco."
    ),
)

# Se inicializan una sola vez al arrancar el servidor
# (stdout sigue redirigido a stderr durante la carga)
_embedder = Embedder()
_store = VectorStore()

# Restaurar stdout para que FastMCP pueda usar stdio JSON-RPC
sys.stdout = _real_stdout


# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

@mcp.tool()
def search_knowledge_base(
    query: str,
    n_results: int = 5,
    category: str | None = None,
) -> dict:
    """
    Busca información relevante en la base de conocimiento de Bancolombia.

    Úsala cuando el usuario pregunte sobre productos (créditos, cuentas, tarjetas,
    seguros, vivienda, inversiones), servicios, tarifas, requisitos, beneficios,
    canales de atención o cualquier tema relacionado con Bancolombia personas.

    Args:
        query: Pregunta o consulta en lenguaje natural del usuario.
        n_results: Número de fragmentos a retornar. Default 5, máximo 10.
        category: Categoría para filtrar la búsqueda. Opcional.
                  Valores posibles: creditos, cuentas, seguros, vivienda,
                  tarjetas_de_credito, tarjetas_debito, beneficios, movilidad,
                  transacciones, contactanos, documentos_legales, entre otros.
                  Usar list_categories() para ver todas las disponibles.

    Returns:
        dict con 'query', 'total_found' y lista 'results'. Cada resultado incluye:
        content (fragmento de texto), url, title, category y score de relevancia (0-1).
    """
    n_results = min(max(n_results, 1), 10)
    try:
        embedding = _embedder.embed_query(query)
        results = _store.search(embedding, n_results=n_results, category=category)
    except Exception as e:
        logging.error(f"search_knowledge_base error: {e}")
        return {"query": query, "total_found": 0, "results": [], "error": str(e)}

    if not results:
        return {"query": query, "total_found": 0, "results": [],
                "message": "No se encontraron resultados para la consulta."}

    return {
        "query": query,
        "total_found": len(results),
        "results": results,
    }


@mcp.tool()
def get_article_by_url(url: str) -> dict:
    """
    Retorna el contenido completo de una página indexada de Bancolombia dado su URL.

    Úsala cuando el usuario solicite información de una página específica, o cuando
    quieras profundizar en un resultado de search_knowledge_base consultando el
    artículo completo en lugar de solo el fragmento.

    Args:
        url: URL completa de la página en bancolombia.com.
             Ejemplo: https://www.bancolombia.com/personas/creditos/vivienda

    Returns:
        dict con 'found' (bool), 'title', 'category', 'full_content' (texto completo)
        y 'chunks' (lista de fragmentos ordenados por posición).
        Si la URL no está indexada, retorna found=False.
    """
    try:
        chunks = _store.get_by_url(url)
    except Exception as e:
        logging.error(f"get_article_by_url error: {e}")
        return {"url": url, "found": False, "error": str(e), "chunks": []}

    if not chunks:
        return {
            "url": url,
            "found": False,
            "message": "URL no encontrada en la base de conocimiento.",
            "chunks": [],
        }

    full_content = "\n\n".join(c["content"] for c in chunks)

    return {
        "url": url,
        "found": True,
        "title": chunks[0].get("title", ""),
        "category": chunks[0].get("category", ""),
        "full_content": full_content,
        "chunks": chunks,
    }


@mcp.tool()
def list_categories() -> dict:
    """
    Retorna las categorías disponibles en la base de conocimiento de Bancolombia.

    Úsala para orientar al usuario sobre los temas cubiertos, o para pasar
    el valor de 'category' a search_knowledge_base y refinar la búsqueda.

    Returns:
        dict con 'total' y lista 'categories' con los nombres de cada categoría.
    """
    try:
        categories = _store.list_categories()
    except Exception as e:
        logging.error(f"list_categories error: {e}")
        return {"total": 0, "categories": [], "error": str(e)}

    return {
        "total": len(categories),
        "categories": categories,
    }


# ─────────────────────────────────────────────
# RESOURCES
# ─────────────────────────────────────────────

@mcp.resource("knowledgebase://stats")
def get_stats() -> str:
    """
    Estadísticas de la base de conocimiento: chunks indexados, páginas procesadas,
    categorías disponibles, modelo de embeddings y fecha de última actualización.
    """
    stats = _store.stats()
    lines = [
        "=== Base de conocimiento Bancolombia ===",
        f"Chunks indexados  : {stats['total_chunks']}",
        f"Páginas           : {stats['total_pages']}",
        f"Categorías        : {', '.join(stats['categories'])}",
        f"Modelo embeddings : {stats['embedding_model']} ({stats['dimensions']} dims)",
        f"Última actualización: {stats['last_updated']}",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()  # stdio — transporte obligatorio según la prueba
