from bs4 import BeautifulSoup
import asyncio
import random

NOISY_TAGS = ["script", "style", "noscript", "svg", "iframe", "head"]


class PageFetcher:
    def __init__(self, browser, retries=2):
        self.browser = browser
        self.retries = retries

    @staticmethod
    def _extract_text(element) -> str:
        for tag in element.find_all(NOISY_TAGS):
            tag.decompose()

        lines = [
            line.strip()
            for line in element.get_text(separator="\n").splitlines()
            if line.strip()
        ]
        return "\n".join(lines)

    async def fetch(self, url: str):
        for attempt in range(self.retries + 1):
            page = await self.browser.new_page()

            try:
                await page.goto(
                    url,
                    timeout=60000,
                    wait_until="domcontentloaded"
                )

                try:
                    await page.wait_for_selector("main", timeout=10000)
                except Exception:
                    print(f"  No encontro <main> en {url}, usando fallback")

                await page.wait_for_timeout(2000)

                content = await page.content()
                soup = BeautifulSoup(content, "lxml")
                main_content = soup.find("main") or soup.find("body") or soup

                text = self._extract_text(main_content)
                title = soup.title.string.strip() if soup.title else None

                return {
                    "text": text,
                    "full_html": content,
                    "title": title
                }

            except Exception as e:
                print(f"[Retry {attempt}] Error fetching {url}: {e}")
                if attempt == self.retries:
                    return None
                await asyncio.sleep(random.uniform(3, 6))

            finally:
                await page.close()
