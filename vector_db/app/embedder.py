from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-small"


class Embedder:
    """
    Wrapper sobre multilingual-e5-small.

    El modelo e5 requiere prefijos específicos:
    - "passage: " para documentos que se van a indexar
    - "query: "   para la consulta en tiempo de búsqueda

    normalize_embeddings=True → similitud coseno == producto punto,
    lo que permite usar "cosine" como métrica en ChromaDB.
    """

    def __init__(self):
        print(f"Cargando modelo {MODEL_NAME}...")
        self.model = SentenceTransformer(MODEL_NAME)
        self.dimensions = self.model.get_sentence_embedding_dimension()
        print(f"Modelo listo. Dimensiones: {self.dimensions}")

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"passage: {t}" for t in texts]
        vectors = self.model.encode(
            prefixed,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        prefixed = f"query: {query}"
        vector = self.model.encode(
            prefixed,
            normalize_embeddings=True,
        )
        return vector.tolist()
