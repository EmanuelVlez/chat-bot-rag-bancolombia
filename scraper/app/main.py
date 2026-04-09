import asyncio
import random
from urllib.parse import urlparse

from browser import BrowserManager
from page_fetcher import PageFetcher
from link_discoverer import LinkDiscoverer
from robots_checker import RobotsChecker
from raw_store import RawStore

START_URL = "https://www.bancolombia.com/personas"
MAX_PAGES = 60
CONCURRENCY = 5


async def worker(queue, browser, store, discoverer, robots, base_domain, counter, lock):
    fetcher = PageFetcher(browser)

    while True:
        async with lock:
            if counter["count"] >= MAX_PAGES:
                return

        try:
            url = await asyncio.wait_for(queue.get(), timeout=90)
   
        except asyncio.TimeoutError:
            return

        if await store.exists(url):
            queue.task_done()
            continue

        allowed = await robots.can_fetch(base_domain, url)
        if not allowed:
            print(f" Bloqueado por robots.txt: {url}")
            queue.task_done()
            continue

        print(f"Fetching: {url}")

        data = await fetcher.fetch(url)

        if data:
            category = discoverer.get_category(url)

            saved = await store.save(
                url=url,
                content=data["text"],
                title=data["title"],
                category=category
            )

            if saved:
                async with lock:
                    counter["count"] += 1
                    print(f"Total procesadas: {counter['count']}")

                    if counter["count"] >= MAX_PAGES:
                        queue.task_done()
                        return
            else:
                print(f"  [DUP] Contenido duplicado, ignorado: {url}")

            links = discoverer.discover(url, data["full_html"])

            for link in links:
                if not await store.exists(link):
                    await queue.put(link)

        await asyncio.sleep(random.uniform(2, 5))

        queue.task_done()


async def main():
    browser = BrowserManager()
    await browser.start()

    store = RawStore()
    await store.init()

    parsed = urlparse(START_URL)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"

    discoverer = LinkDiscoverer(parsed.netloc)
    robots = RobotsChecker()

    queue = asyncio.Queue()
    await queue.put(START_URL)

    # contador global seguro
    counter = {"count": 0}
    lock = asyncio.Lock()

    tasks = [
        asyncio.create_task(
            worker(queue, browser, store, discoverer, robots, base_domain, counter, lock)
        )
        for _ in range(CONCURRENCY)
    ]

    await asyncio.gather(*tasks)

    await browser.close()
    await store.close()


if __name__ == "__main__":
    asyncio.run(main())