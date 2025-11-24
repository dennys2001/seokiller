import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup


logger = logging.getLogger("geo_crawler")
logger.setLevel(logging.INFO)

DEFAULT_HEADERS = {
    "User-Agent": "GEO-AEO-Bot/1.0 (+https://github.com/your-org)"
}


class AsyncCrawler:
    def __init__(self, start_url, max_pages=10, max_tasks=5, delay=0.3, timeout=10):
        self.start_url = start_url
        self.parsed_start = urlparse(start_url)
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.seen = set()
        self.to_crawl = asyncio.Queue()
        self.results = []
        self.sem = asyncio.Semaphore(max_tasks)
        self.session = None
        self.robots = RobotFileParser()
        try:
            self.robots.set_url(urljoin(start_url, "/robots.txt"))
            self.robots.read()
        except Exception:
            pass

    async def fetch(self, url):
        if not self.robots.can_fetch(DEFAULT_HEADERS["User-Agent"], url):
            logger.info("Blocked by robots.txt: %s", url)
            return None
        try:
            async with self.sem:
                async with self.session.get(
                    url,
                    timeout=ClientTimeout(total=self.timeout),
                    headers=DEFAULT_HEADERS,
                ) as resp:
                    if resp.status != 200:
                        logger.info("HTTP %s for %s", resp.status, url)
                        return None
                    text = await resp.text(errors="ignore")
                    await asyncio.sleep(self.delay)
                    return text
        except Exception as exc:
            logger.info("Fetch error %s: %s", url, exc)
            return None

    def extract_links(self, html, base_url):
        soup = BeautifulSoup(html, "html.parser")
        hrefs = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "javascript:")):
                continue
            next_url = urljoin(base_url, href)
            parsed = urlparse(next_url)
            if parsed.netloc == self.parsed_start.netloc:
                next_url = parsed._replace(fragment="").geturl()
                hrefs.append(next_url)
        return hrefs

    def extract_content(self, html, url):
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string or "").strip() if soup.title else ""
        h1 = " ".join(
            h.get_text(separator=" ", strip=True) for h in soup.find_all("h1")
        ).strip()
        main = soup.find("main") or soup.find("article")
        if main:
            text = " ".join(main.get_text(separator=" ", strip=True).split())
        else:
            ps = soup.find_all("p")
            text = " ".join(p.get_text(separator=" ", strip=True) for p in ps)
        text = re.sub(r"\s+", " ", text)[:8000]
        return {"url": url, "title": title, "h1": h1, "text": text}

    async def worker(self):
        while not self.to_crawl.empty() and len(self.results) < self.max_pages:
            url = await self.to_crawl.get()
            if url in self.seen:
                self.to_crawl.task_done()
                continue
            self.seen.add(url)
            html = await self.fetch(url)
            if html:
                page = self.extract_content(html, url)
                self.results.append(page)
                for link in self.extract_links(html, url):
                    if link not in self.seen and self.to_crawl.qsize() + len(self.seen) < self.max_pages:
                        await self.to_crawl.put(link)
            self.to_crawl.task_done()

    async def crawl(self):
        timeout = ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session
            await self.to_crawl.put(self.start_url)
            workers = [asyncio.create_task(self.worker()) for _ in range(5)]
            await self.to_crawl.join()
            for w in workers:
                w.cancel()
        return self.results


def crawl_site(url, max_pages=5, max_tasks=5, delay=0.3, timeout=10):
    crawler = AsyncCrawler(
        url,
        max_pages=max_pages,
        max_tasks=max_tasks,
        delay=delay,
        timeout=timeout,
    )
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(crawler.crawl())
    finally:
        asyncio.set_event_loop(None)
