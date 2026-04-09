import aiohttp
from urllib.robotparser import RobotFileParser

class RobotsChecker:
    def __init__(self):
        self.cache = {}

    async def get_parser(self, base_url):
        if base_url in self.cache:
            return self.cache[base_url]

        robots_url = f"{base_url}/robots.txt"
        parser = RobotFileParser()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url) as resp:
                    text = await resp.text()

            parser.parse(text.splitlines())
            self.cache[base_url] = parser
            return parser

        except Exception:
            return None

    async def can_fetch(self, base_url, url):
        parser = await self.get_parser(base_url)

        if not parser:
            return True

        return parser.can_fetch("*", url)