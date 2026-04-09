"""Tests unitarios para VectorStore (vector_db) usando ChromaDB en memoria."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "vector_db" / "app"))

from vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    """VectorStore con persistencia en directorio temporal."""
    return VectorStore(persist_path=str(tmp_path / "chroma_test"))


def test_upsert_and_count(store):
    store.upsert(
        ids=["chunk_1"],
        embeddings=[[0.1] * 384],
        documents=["Bancolombia ofrece cuentas de ahorro."],
        metadatas=[{"url": "https://bancolombia.com", "title": "Cuentas", "category": "cuentas", "chunk_index": 0}],
    )
    assert store.collection.count() == 1


def test_upsert_idempotent(store):
    payload = dict(
        ids=["chunk_1"],
        embeddings=[[0.1] * 384],
        documents=["Texto de prueba."],
        metadatas=[{"url": "https://bancolombia.com", "title": "T", "category": "general", "chunk_index": 0}],
    )
    store.upsert(**payload)
    store.upsert(**payload)  # segunda vez no debe duplicar
    assert store.collection.count() == 1


def test_search_returns_results(store):
    store.upsert(
        ids=["chunk_1", "chunk_2"],
        embeddings=[[0.1] * 384, [0.9] * 384],
        documents=["Crédito de vivienda.", "Tarjeta de crédito."],
        metadatas=[
            {"url": "https://bancolombia.com/vivienda", "title": "Vivienda", "category": "vivienda", "chunk_index": 0},
            {"url": "https://bancolombia.com/tarjetas", "title": "Tarjetas", "category": "tarjetas", "chunk_index": 0},
        ],
    )
    results = store.search(query_embedding=[0.1] * 384, n_results=2)
    assert len(results) == 2
    assert "content" in results[0]
    assert "url" in results[0]
    assert "score" in results[0]


def test_search_score_between_0_and_1(store):
    store.upsert(
        ids=["chunk_1"],
        embeddings=[[0.5] * 384],
        documents=["Texto cualquiera."],
        metadatas=[{"url": "https://bancolombia.com", "title": "T", "category": "general", "chunk_index": 0}],
    )
    results = store.search(query_embedding=[0.5] * 384, n_results=1)
    assert 0.0 <= results[0]["score"] <= 1.0


def test_list_categories(store):
    store.upsert(
        ids=["c1", "c2"],
        embeddings=[[0.1] * 384, [0.2] * 384],
        documents=["doc1", "doc2"],
        metadatas=[
            {"url": "u1", "title": "T1", "category": "cuentas", "chunk_index": 0},
            {"url": "u2", "title": "T2", "category": "creditos", "chunk_index": 0},
        ],
    )
    cats = store.list_categories()
    assert "cuentas" in cats
    assert "creditos" in cats


def test_get_by_url(store):
    store.upsert(
        ids=["c1", "c2"],
        embeddings=[[0.1] * 384, [0.2] * 384],
        documents=["Parte 1.", "Parte 2."],
        metadatas=[
            {"url": "https://bancolombia.com/cuentas", "title": "Cuentas", "category": "cuentas", "chunk_index": 0},
            {"url": "https://bancolombia.com/cuentas", "title": "Cuentas", "category": "cuentas", "chunk_index": 1},
        ],
    )
    chunks = store.get_by_url("https://bancolombia.com/cuentas")
    assert len(chunks) == 2
    assert chunks[0]["chunk_index"] == 0
