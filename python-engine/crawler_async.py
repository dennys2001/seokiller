import asyncio
import os
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from browser_fetch import fetch_html_with_playwright, is_unusable_page, playwright_enabled

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
        self.robots_url = urljoin(start_url, "/robots.txt")
        self.robots_allowed_check = False
        self.playwright_fallback_count = 0
        self.playwright_fallback_max = int(os.getenv("PLAYWRIGHT_MAX_FALLBACKS", "2"))

    async def _load_robots(self):
        try:
            async with self.session.get(
                self.robots_url,
                timeout=ClientTimeout(total=self.timeout),
                headers=DEFAULT_HEADERS,
            ) as resp:
                if resp.status != 200:
                    # If robots cannot be read (403/404/5xx), keep crawler permissive.
                    self.robots_allowed_check = False
                    return
                text = await resp.text(errors="ignore")
        except Exception:
            # If robots cannot be fetched due to network/CDN constraints, keep permissive.
            self.robots_allowed_check = False
            return

        lines = [line.strip() for line in text.splitlines()]
        if not lines:
            self.robots_allowed_check = False
            return

        self.robots.parse(lines)
        self.robots_allowed_check = True

    async def fetch(self, url: str):
        if self.robots_allowed_check and not self.robots.can_fetch(DEFAULT_HEADERS["User-Agent"], url):
            return None
        try:
            async with self.sem:
                async with self.session.get(
                    url,
                    timeout=ClientTimeout(total=self.timeout),
                    headers=DEFAULT_HEADERS,
                ) as resp:
                    text = await resp.text(errors="ignore")
                    if resp.status != 200:
                        if resp.status in (403, 429):
                            return await self._fetch_with_playwright(url)
                        return None
                    if is_unusable_page(text):
                        return await self._fetch_with_playwright(url)
                    await asyncio.sleep(self.delay)
                    return text
        except Exception:
            return await self._fetch_with_playwright(url)

    async def _fetch_with_playwright(self, url: str):
        if not playwright_enabled():
            return None
        if self.playwright_fallback_count >= self.playwright_fallback_max:
            return None
        self.playwright_fallback_count += 1
        try:
            html, _ = await asyncio.to_thread(fetch_html_with_playwright, url, self.timeout)
            if is_unusable_page(html):
                return None
            return html
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
        return {"url": url, "title": title, "h1": h1, "text": text, "html": html}

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
            await self._load_robots()
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
