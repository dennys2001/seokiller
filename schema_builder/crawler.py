# crawler.py
import asyncio
import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import re
import logging
from urllib.robotparser import RobotFileParser

logger = logging.getLogger("geo_crawler")
logger.setLevel(logging.INFO)

DEFAULT_HEADERS = {
    "User-Agent": "GEO-AEO-Bot/1.0 (+https://your-agency.example)"
}

class AsyncCrawler:
    def __init__(self, start_url, max_pages=50, max_tasks=10, delay=0.5, timeout=10):
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
            # falha na leitura - assume permissivo
            pass

    async def fetch(self, url):
        if not self.robots.can_fetch(DEFAULT_HEADERS["User-Agent"], url):
            logger.info("Blocked by robots.txt: %s", url)
            return None
        try:
            async with self.sem:
                async with self.session.get(url, timeout=ClientTimeout(total=self.timeout), headers=DEFAULT_HEADERS) as resp:
                    if resp.status != 200:
                        logger.info("HTTP %s for %s", resp.status, url)
                        return None
                    text = await resp.text(errors="ignore")
                    await asyncio.sleep(self.delay)  # politeness
                    return text
        except Exception as e:
            logger.info("Fetch error %s: %s", url, e)
            return None

    def extract_links(self, html, base_url):
        soup = BeautifulSoup(html, "html.parser")
        hrefs = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            # Ignore mailto and javascript
            if href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            next_url = urljoin(base_url, href)
            parsed = urlparse(next_url)
            # only same host
            if parsed.netloc == self.parsed_start.netloc:
                # remove fragments
                next_url = parsed._replace(fragment="").geturl()
                hrefs.append(next_url)
        return hrefs

    def extract_content(self, html, url):
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string or "").strip() if soup.title else ""
        h1 = " ".join([h.get_text(separator=" ", strip=True) for h in soup.find_all("h1")]).strip()
        main = soup.find("main") or soup.find("article")
        if main:
            text = " ".join(main.get_text(separator=" ", strip=True).split())
        else:
            # fallback to paragraphs
            ps = soup.find_all("p")
            text = " ".join([p.get_text(separator=" ", strip=True) for p in ps])
        text = re.sub(r'\s+', ' ', text)[:10000]
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
            logger.info("[EXTRAÍDO] %s (%s)", url, len(self.results))
            # enqueue internal links
            links = self.extract_links(html, url)
            for l in links:
                if l not in self.seen and self.to_crawl.qsize() + len(self.seen) < self.max_pages:
                    await self.to_crawl.put(l)
            self.to_crawl.task_done()

    async def crawl(self):
        timeout = ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session
            # seed
            await self.to_crawl.put(self.start_url)
            workers = []
            for _ in range(5):
                w = asyncio.create_task(self.worker())
                workers.append(w)
            await self.to_crawl.join()
            for w in workers:
                w.cancel()
        return self.results

def crawl_site(url, max_pages=30, max_tasks=10, delay=0.5, timeout=10):
    crawler = AsyncCrawler(url, max_pages=max_pages, max_tasks=max_tasks, delay=delay, timeout=timeout)
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(crawler.crawl())
