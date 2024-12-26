import asyncio
import sys

import aiohttp
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

from book_framework.utils import log

cookies = {}
headers = {
     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
}

CHROME_PATH = "C:/Users/Administrator/Downloads/chrome-win64/chrome.exe"
CHROMEDRIVER_PATH = "chromedriver.exe"


class WebDriver:
    def __init__(self, chrome_path=CHROME_PATH):
        self.chrome_path = chrome_path
        self.driver = self.init_driver()

    def init_driver(self):
        options = webdriver.ChromeOptions()
        options.binary_location = self.chrome_path
        options.add_argument('--ignore-certificate-errors')
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')  # Last I checked this was necessary.
        # options.add_experimental_option("detach", True)

        try:
            driver = webdriver.Chrome(service=Service(), options=options)
        except WebDriverException:
            print("Wrong paths!")
            sys.exit()

        return driver


async def _make_request(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, cookies=cookies, headers=headers, ssl=False) as resp:
            return await resp.text()

RETRY_INDICATORS = ["502 Bad Gateway", "Goodreads - unexpected error"]
EXIT_INDICATORS = ["404 Not Found"]

def make_request(url):
    retry_cnt = 0
    while retry_cnt < 3:
        log(url)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response_text = loop.run_until_complete(_make_request(url))
        loop.close()
        if any(x in response_text for x in RETRY_INDICATORS):
            retry_cnt += 1
            continue
        if any(x in response_text for x in EXIT_INDICATORS):
            return None
        return response_text
    return None
