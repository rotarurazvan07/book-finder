"""
Web Scraping Framework using Scrapling
Static utility with three entry points:
    WebScraper.fetch(url)          — fast HTTP GET with stealth headers
    WebScraper.browser(...)        — interactive headless browser session
    WebScraper.scrape(urls, ...)   — batch scrape with concurrency + callback

REQUIREMENTS:
    pip install "scrapling[fetchers]"
    scrapling install
"""

import asyncio
import time
import sys
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from scrapling.fetchers import (
    Fetcher,
    DynamicSession,
    StealthySession,
    AsyncStealthySession,
)

RETRY_INDICATORS = [
    "403 Forbidden",
    "Access Denied",
    "429 Too Many Requests",
    "Too Many Requests",
    "rate limit exceeded",
    "rate limited",
    "Request throttled",
    "Service Unavailable",
    "503 Service Unavailable",
    "Temporarily Unavailable",
    "overloaded",
    "quota exceeded",
    "Just a moment",
    "Checking your browser",
    "verify you are a human",
    "turnstile",
    "cf-chl-widget",
    "Cloudflare",
]

class ScrapeMode:
    """Scraping mode constants."""
    FAST = "fast"          # Simple HTTP with TLS impersonation
    STEALTH = "stealth"    # Headless browser, Cloudflare bypass


class InteractiveSession:
    """Wrapper around Scrapling session to provide persistent page and JS execution."""
    def __init__(self, session):
        self.session = session
        self.page = None

    def __enter__(self):
        self.session.start()
        # Create a persistent page that we control
        self.page = self.session.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.page:
                self.page.close()
        except Exception:
            # Silent close failure during cleanup is acceptable but should be known in logs if needed
            pass
        self.session.close()

    def fetch(self, url, timeout=90000, wait_until="load"):
        if not self.page:
            error_msg = "Session not started. Use 'with WebScraper.browser(...) as session:'"
            raise RuntimeError(error_msg)

        self.page.goto(url, wait_until=wait_until, timeout=timeout)
        # Forebet and others need a moment for background scripts to run
        self.page.wait_for_timeout(2000)

        return SimpleNamespace(html_content=self.page.content())

    def execute_script(self, script):
        if not self.page:
            raise RuntimeError("Call fetch() first")

        clean_script = script.strip()
        try:
            if clean_script.startswith("return "):
                return self.page.evaluate(f"() => {{ {clean_script} }}")
            return self.page.evaluate(script)
        except Exception as e:
            print(f"[InteractiveSession] Script Execution Error: {e}", file=sys.stderr)
            raise

    def wait_for_selector(self, selector, timeout=30000):
        if not self.page: raise RuntimeError("Call fetch() first")
        self.page.wait_for_selector(selector, timeout=timeout)

    def wait_for_function(self, expression, timeout=30000):
        if not self.page: raise RuntimeError("Call fetch() first")
        self.page.wait_for_function(expression, timeout=timeout)

    def click(self, selector, timeout=30000):
        if not self.page: raise RuntimeError("Call fetch() first")
        self.page.click(selector, timeout=timeout)

    def wait_for_timeout(self, ms):
        if not self.page: raise RuntimeError("Call fetch() first")
        self.page.wait_for_timeout(ms)

    def __getattr__(self, name):
        """Delegate other attributes to the underlying Scrapling session."""
        return getattr(self.session, name)


class WebScraper:
    """Static scraping utility."""

    @staticmethod
    def fetch(url: str, stealthy_headers: bool = False,
              retries: int = 3, backoff: float = 5.0) -> str:
        """Fast HTTP GET with TLS impersonation and stealth headers.
        Retries on any RETRY_INDICATORS match with exponential backoff.
        Escalates to browser session if persistently blocked.
        """
        for attempt in range(1, retries + 1):
            try:
                page = Fetcher.get(url, stealthy_headers=stealthy_headers)

                # Check status code (Scrapling Response uses .status or .status_code)
                status = getattr(page, "status", getattr(page, "status_code", 200))
                if status in [403, 429, 503]:
                    wait = backoff * attempt
                    print(f"[fetch] Status {status} on {url} — retrying in {wait:.0f}s (attempt {attempt}/{retries})", file=sys.stderr)
                    time.sleep(wait)
                    continue

                html = page.html_content
                matched = next((ind for ind in RETRY_INDICATORS if ind.lower() in html.lower()), None)

                if matched:
                    if attempt < retries:
                        wait = backoff * attempt
                        print(f"[fetch] '{matched}' indicator on {url} — retrying in {wait:.0f}s (attempt {attempt}/{retries})", file=sys.stderr)
                        time.sleep(wait)
                        continue
                    else:
                        return WebScraper._escalate_to_browser(url, matched)

                return html

            except Exception as e:
                if attempt < retries:
                    wait = backoff * attempt
                    print(f"[fetch] Error on {url}: {e} — retrying in {wait:.0f}s (attempt {attempt}/{retries})", file=sys.stderr)
                    time.sleep(wait)
                else:
                    print(f"[fetch] Failed after {retries} attempts on {url}: {e}", file=sys.stderr)
                    return ""

        return ""

    @staticmethod
    def _escalate_to_browser(url: str, blocked_by: str) -> str:
        """Uses a real browser to solve more complex challenges (Cloudflare)."""
        print(f"[fetch] '{blocked_by}' on {url} — Escalating to browser for challenge solving...", file=sys.stderr)
        try:
            with WebScraper.browser(solve_cloudflare=True, headless=True, interactive=True) as session:
                resp = session.fetch(url, timeout=120000, wait_until="networkidle")
                if resp and hasattr(resp, "html_content"):
                    print(f"[fetch] Browser successfully bypassed challenge for {url}", file=sys.stderr)
                    return resp.html_content
        except Exception as browser_e:
            print(f"[fetch] Browser escalation failed for {url}: {browser_e}", file=sys.stderr)
        return ""

    @staticmethod
    def is_blocked(html: str) -> bool:
        """Helper to detect shadowbans or Cloudflare blocks."""
        if not html:
            return True
        block_indicators = ["verify you are a human", "403 Forbidden", "429 Too Many Requests", "Attention Required!"]
        return any(indicator.lower() in html.lower() for indicator in block_indicators)

    @staticmethod
    def browser(headless: bool = True, solve_cloudflare: bool = False, interactive: bool = False, **kwargs):
        """Get a browser session as a context manager."""
        # Config defaulting logic
        kwargs.setdefault("disable_resources", not interactive and not solve_cloudflare)
        kwargs.setdefault("network_idle", interactive or solve_cloudflare)
        kwargs.setdefault("wait_until", "load")

        if solve_cloudflare:
            session = StealthySession(headless=headless, solve_cloudflare=True, **kwargs)
        else:
            session = DynamicSession(headless=headless, **kwargs)

        return InteractiveSession(session) if interactive else session

    @staticmethod
    def scrape(urls: List[str], callback: Callable, mode: str = ScrapeMode.FAST, max_concurrency: int = 1):
        """Batch scrape URLs with concurrency."""
        if not urls: return

        if mode == ScrapeMode.FAST:
            WebScraper._scrape_fast(urls, callback, max_concurrency)
        elif mode == ScrapeMode.STEALTH:
            WebScraper._scrape_stealth(urls, callback, max_concurrency)

    @staticmethod
    def _scrape_fast(urls, callback, max_concurrency):
        def _fetch_worker(url):
            try:
                # Attempt 1: Fast (standard headers)
                html = WebScraper.fetch(url, stealthy_headers=False)
                if not WebScraper.is_blocked(html):
                    callback(url, html)
                    return
                # Attempt 2: Stealth headers
                html = WebScraper.fetch(url, stealthy_headers=True)
                if not WebScraper.is_blocked(html):
                    callback(url, html)
                    return
            except Exception as e:
                print(f"[scrape/fast] Error on {url}: {e}", file=sys.stderr)

        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            pool.map(_fetch_worker, urls)

    @staticmethod
    def _scrape_stealth(urls, callback, max_concurrency):
        async def _async_worker():
            async with AsyncStealthySession(max_pages=max_concurrency, headless=True, solve_cloudflare=True) as session:
                sem = asyncio.Semaphore(max_concurrency)

                async def _fetch_one(url):
                    async with sem:
                        for attempt in range(1, 3):
                            try:
                                page = await session.fetch(url, disable_resources=False, network_idle=True, timeout=90000)
                                callback(url, page.html_content)
                                return
                            except Exception as e:
                                if attempt < 2:
                                    wait = 15 * attempt
                                    print(f"[scrape/stealth] Challenge/Timeout on {url} (attempt {attempt}) — retrying in {wait}s...", file=sys.stderr)
                                    await asyncio.sleep(wait)
                                else:
                                    print(f"[scrape/stealth] Failed persistently on {url}: {e}", file=sys.stderr)

                await asyncio.gather(*[_fetch_one(u) for u in urls])

        asyncio.run(_async_worker())
