import os


DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

CHALLENGE_MARKERS = (
    "just a moment",
    "cf-chl",
    "cf-browser-verification",
    "attention required",
    "captcha",
    "verify you are human",
)


def is_bot_challenge(html: str) -> bool:
    text = (html or "").lower()
    return any(marker in text for marker in CHALLENGE_MARKERS)


def playwright_enabled() -> bool:
    return os.getenv("PLAYWRIGHT_FALLBACK", "1").strip().lower() not in ("0", "false", "no")


def fetch_html_with_playwright(url: str, timeout: int = 120):
    from playwright.sync_api import sync_playwright

    timeout_ms = max(1, int(timeout)) * 1000
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=DEFAULT_BROWSER_UA,
            locale="pt-BR",
            viewport={"width": 1366, "height": 768},
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(2500)
        html = page.content()
        final_url = page.url
        context.close()
        browser.close()
        return html, final_url
