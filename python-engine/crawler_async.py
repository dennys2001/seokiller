import asyncio
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "GEO-AEO-Bot/1.0 (+https://your-agency.example)"
}


class AsyncCrawler:
    def __init__(self, start_url: str, max_pages: int = 30, max_tasks: int = 8, delay: float = 0.5, timeout: int = 180):
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
        self.robots.set_url(urljoin(start_url, "/robots.txt"))
        try:
            self.robots.read()
        except Exception:
            # assume permissive when robots cannot be read
            pass

    async def fetch(self, url: str):
        if not self.robots.can_fetch(DEFAULT_HEADERS["User-Agent"], url):
            return None
        try:
            async with self.sem:
                async with self.session.get(
                    url,
                    timeout=ClientTimeout(total=self.timeout),
                    headers=DEFAULT_HEADERS,
                ) as resp:
                    if resp.status != 200:
                        return None
                    text = await resp.text(errors="ignore")
                    await asyncio.sleep(self.delay)
                    return text
        except Exception:
            return None

    def extract_links(self, html: str, base_url: str):
        soup = BeautifulSoup(html, "html.parser")
        hrefs = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            next_url = urljoin(base_url, href)
            parsed = urlparse(next_url)
            if parsed.netloc == self.parsed_start.netloc:
                next_url = parsed._replace(fragment="").geturl()
                hrefs.append(next_url)
        return hrefs

    def extract_content(self, html: str, url: str):
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string or "").strip() if soup.title else ""
        h1 = " ".join([h.get_text(separator=" ", strip=True) for h in soup.find_all("h1")]).strip()
        main = soup.find("main") or soup.find("article")
        if main:
            text = " ".join(main.get_text(separator=" ", strip=True).split())
        else:
            ps = soup.find_all("p")
            text = " ".join([p.get_text(separator=" ", strip=True) for p in ps])
        text = " ".join(text.split())[:10000]
        return {"url": url, "title": title, "h1": h1, "text": text}

    async def worker(self):
        while not self.to_crawl.empty() and len(self.results) < self.max_pages:
            url = await self.to_crawl.get()
            if url in self.seen:
                self.to_crawl.task_done()
                continue
            self.seen.add(url)
            html = await self.fetch(url)
            if not html:
                self.to_crawl.task_done()
                continue
            page = self.extract_content(html, url)
            self.results.append(page)
            links = self.extract_links(html, url)
            for link in links:
                if link not in self.seen and (self.to_crawl.qsize() + len(self.seen)) < self.max_pages:
                    await self.to_crawl.put(link)
            self.to_crawl.task_done()

    async def crawl(self):
        timeout = ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session
            await self.to_crawl.put(self.start_url)
            workers = []
            for _ in range(5):
                workers.append(asyncio.create_task(self.worker()))
            await self.to_crawl.join()
            for w in workers:
                w.cancel()
        return self.results


def crawl_site(url: str, max_pages: int = 30, max_tasks: int = 8, delay: float = 0.5, timeout: int = 180):
    crawler = AsyncCrawler(url, max_pages=max_pages, max_tasks=max_tasks, delay=delay, timeout=timeout)
    return asyncio.run(crawler.crawl())
