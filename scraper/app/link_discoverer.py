from urllib.parse import urljoin, urlparse, urlunparse

class LinkDiscoverer:
    def __init__(self, base_domain):
        self.base_domain = base_domain

    def normalize(self, url: str) -> str:
        """Elimina query params y fragmentos — URLs distintas con mismo path son la misma página."""
        parsed = urlparse(url)
        return urlunparse(parsed._replace(query="", fragment=""))

    def is_valid(self, url: str) -> bool:
        parsed = urlparse(url)
        return (
            self.base_domain in parsed.netloc
            and "/personas" in parsed.path
            and not any(ext in parsed.path for ext in [".pdf", ".jpg", ".png"])
        )

    def discover(self, base_url, html):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        links = set()

        for a in soup.find_all("a", href=True):
            href = self.normalize(urljoin(base_url, a["href"]))
            if self.is_valid(href):
                links.add(href)

        return list(links)
    
    def get_category(self, url: str) -> str:
        path = urlparse(url).path.strip("/").split("/")

        if len(path) >= 2 and path[0] == "personas":
            return path[1].replace("-", "_")

        return "general"