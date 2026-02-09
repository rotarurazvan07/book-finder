from abc import abstractmethod
from datetime import datetime, timedelta
import threading
import time
import re
from typing import Callable, Iterable, List, Optional, Tuple

from book_framework.WebScraper import WebScraper
from book_framework.core.Book import BookCategory
from book_framework.utils import log
from book_framework.SettingsManager import settings_manager
from abc import ABC

class BaseBookstore(ABC):
    def __init__(self, add_book_callback: Callable):
        super().__init__()
        self.add_book_callback = add_book_callback
        self._stop_logging = False
        self.web_scraper: Optional[WebScraper] = None

    @abstractmethod
    def get_books(self, category):
        raise NotImplementedError()

    def add_book(self, book) -> bool:
        try:
            self.add_book_callback(book)
            return True
        except Exception as e:
            print(f"Error while adding book: {e}")
            return False

    # --- Helpers -------------------------------------------------
    def get_web_scraper(self,
                        profile: Optional[str] = None,
                        headless: Optional[bool] = None,
                        stealth_mode: Optional[bool] = None,
                        max_retries: Optional[int] = None,
                        min_request_delay: Optional[float] = None,
                        detection_keywords: Optional[List[str]] = None,
                        **kwargs) -> WebScraper:
        """Create or return a shared WebScraper using defaults merged with
        values from `config/web_scraper_config.yaml` (if loaded into
        SettingsManager) and any explicit overrides.
        """
        # Load defaults from settings manager if present. Be flexible with common
        # naming: either 'web_scraper', 'web_scraper_config' or older 'webdriver'.
        cfg = settings_manager.get_config('web_scraper_config')

        # If the loaded config nests web_scraper under a top-level key, normalize it
        if isinstance(cfg, dict) and 'web_scraper' in cfg:
            cfg = cfg.get('web_scraper') or {}

        # apply base config overrides
        headless = cfg.get('headless', headless)
        stealth_mode = cfg.get('stealth_mode', stealth_mode)
        max_retries = cfg.get('max_retries', max_retries)
        min_request_delay = cfg.get('min_request_delay', min_request_delay)
        detection_keywords = cfg.get('detection_keywords', detection_keywords)

        # apply profile-specific overrides when provided (e.g., 'slow' or 'fast')
        if profile and isinstance(cfg, dict):
            profile_cfg = cfg.get('profiles', {}).get(profile) or cfg.get(profile) or {}
            if isinstance(profile_cfg, dict):
                headless = profile_cfg.get('headless', headless)
                stealth_mode = profile_cfg.get('stealth_mode', stealth_mode)
                max_retries = profile_cfg.get('max_retries', max_retries)
                min_request_delay = profile_cfg.get('min_request_delay', min_request_delay)
                detection_keywords = profile_cfg.get('detection_keywords', detection_keywords)

        self.web_scraper = WebScraper(
            headless=headless,
            stealth_mode=stealth_mode,
            max_retries=max_retries,
            min_request_delay=min_request_delay,
            detection_keywords=detection_keywords,
            **kwargs
        )

        return self.web_scraper

    def destroy_scraper_thread(self):
        """Safely destroy the thread-local browser for this finder if present."""
        try:
            if self.web_scraper:
                self.web_scraper.destroy_current_thread()
        except Exception:
            # Best-effort cleanup; don't raise during thread cleanup
            pass

    def run_workers(self, items: Iterable, worker_fn: Callable, num_threads: int):
        """Run `worker_fn` across `items` using `num_threads` worker threads.

        `worker_fn` is called as worker_fn(items_slice, thread_id).
        This helper will start a progress logging thread that calls
        `_log_progress(items)` if the subclass implements it.
        """
        items = list(items)
        self._stop_logging = False

        # Optionally create a shared scraper (finder may override afterwards)
        if self.web_scraper is None:
            self.get_web_scraper()

        # Start progress logging thread if subclass provides _log_progress
        info_thread = None
        if hasattr(self, '_log_progress'):
            info_thread = threading.Thread(target=self._log_progress, args=(items,))
            info_thread.start()

        # Start workers
        threads = []
        total = len(items)
        for i in range(num_threads):
            slice_start = int(i * total / num_threads)
            slice_end = int((i + 1) * total / num_threads)
            items_slice = items[slice_start:slice_end]
            thread = threading.Thread(target=worker_fn, args=(items_slice, i))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Stop logging
        self._stop_logging = True
        if info_thread:
            info_thread.join()