class TextCleaner:
    """
    Limpieza adicional del texto extraído por el scraper.
    Elimina líneas muy cortas (ruido de UI) y líneas duplicadas
    que React repite en cada página (nav, footer boilerplate).
    """

    MIN_LINE_LENGTH = 20

    def clean(self, text: str) -> str:
        lines = text.splitlines()
        seen: set[str] = set()
        cleaned: list[str] = []

        for line in lines:
            line = line.strip()

            if len(line) < self.MIN_LINE_LENGTH:
                continue

            if line in seen:
                continue

            seen.add(line)
            cleaned.append(line)

        return "\n".join(cleaned)
