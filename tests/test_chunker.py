"""Tests unitarios para el módulo de chunking (processing)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "processing" / "app"))

from chunker import Chunker


def test_chunker_splits_long_text():
    chunker = Chunker()
    text = "Esta es una oración de prueba. " * 300  # texto largo
    chunks = chunker.chunk(text)
    assert len(chunks) > 1, "Texto largo debe producir múltiples chunks"


def test_chunker_short_text_single_chunk():
    chunker = Chunker()
    text = "Bancolombia ofrece cuentas de ahorro para personas naturales."
    chunks = chunker.chunk(text)
    assert len(chunks) == 1


def test_chunker_returns_dicts_with_required_keys():
    chunker = Chunker()
    text = "Texto de prueba para verificar la estructura del resultado. " * 5
    chunks = chunker.chunk(text)
    assert len(chunks) > 0
    for chunk in chunks:
        assert "content" in chunk
        assert "token_count" in chunk


def test_chunker_no_empty_chunks():
    chunker = Chunker()
    text = "Este es un texto de prueba. " * 100
    chunks = chunker.chunk(text)
    assert all(c["content"].strip() for c in chunks), "No debe haber chunks vacíos"


def test_chunker_token_count_positive():
    chunker = Chunker()
    text = "Bancolombia ofrece créditos de vivienda con excelentes condiciones. " * 10
    chunks = chunker.chunk(text)
    for chunk in chunks:
        assert chunk["token_count"] > 0
