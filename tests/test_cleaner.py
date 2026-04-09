"""Tests unitarios para el módulo de limpieza de texto (processing)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "processing" / "app"))

from cleaner import TextCleaner


def test_cleaner_removes_short_lines():
    cleaner = TextCleaner()
    # Líneas menores a MIN_LINE_LENGTH (20 chars) deben eliminarse
    text = "ok\nEsta línea es suficientemente larga para mantenerse en el resultado."
    result = cleaner.clean(text)
    assert "ok" not in result
    assert "suficientemente larga" in result


def test_cleaner_removes_duplicate_lines():
    cleaner = TextCleaner()
    line = "Esta es una línea que se repite varias veces en el texto."
    text = f"{line}\n{line}\n{line}"
    result = cleaner.clean(text)
    assert result.count(line) == 1


def test_cleaner_strips_each_line():
    cleaner = TextCleaner()
    text = "   Esta línea tiene espacios al inicio y al final.   "
    result = cleaner.clean(text)
    for line in result.splitlines():
        assert line == line.strip()


def test_cleaner_returns_string():
    cleaner = TextCleaner()
    result = cleaner.clean("cualquier texto para la prueba de tipo de retorno")
    assert isinstance(result, str)


def test_cleaner_handles_empty_string():
    cleaner = TextCleaner()
    result = cleaner.clean("")
    assert isinstance(result, str)
    assert result == ""
