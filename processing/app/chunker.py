import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 512    # tokens
CHUNK_OVERLAP = 64  # tokens
ENCODING = "cl100k_base"  # mismo tokenizer que text-embedding-3-small


class Chunker:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=ENCODING,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self._enc = tiktoken.get_encoding(ENCODING)

    def chunk(self, text: str) -> list[dict]:
        """
        Retorna lista de dicts con 'content' y 'token_count'
        para cada chunk generado.
        """
        raw_chunks = self.splitter.split_text(text)
        return [
            {
                "content": chunk,
                "token_count": len(self._enc.encode(chunk)),
            }
            for chunk in raw_chunks
            if chunk.strip()
        ]
