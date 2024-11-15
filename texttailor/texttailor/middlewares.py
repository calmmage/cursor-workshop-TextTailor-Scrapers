# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import logging
import os
import signal

import undetected_chromedriver as uc
from scrapy import signals
from scrapy.http import HtmlResponse
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type


# useful for handling different item types with a single interface


class TexttailorSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class TexttailorDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class UndetectedChromeMiddleware:
    def __init__(self, proxy=None):
        chrome_options = Options()

        if proxy:
            proxy_options = {
                "proxy": {
                    "https": f"http://{proxy}",
                }
            }
        else:
            proxy_options = None

        # Additional options for undetected Chrome
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--use-subprocess")
        self.driver = uc.Chrome(options=chrome_options, seleniumwire_options=proxy_options)
        self.driver.implicitly_wait(5)
        self.chrome_pid = self.driver.service.process.pid

        logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    @classmethod
    def from_crawler(cls, crawler):
        proxy = crawler.settings.get("SOCKS5_PROXY")
        middleware = cls(proxy)
        crawler.signals.connect(middleware.spider_closed, signals.spider_closed)
        return middleware

    @retry(
        stop=stop_after_attempt(3),  # Stop after 3 attempts
        wait=wait_fixed(1),  # Wait for 1 second between retries
        retry=retry_if_exception_type(TimeoutException),  # Retry on TimeoutException
    )
    def process_request(self, request, spider):
        self.driver.set_page_load_timeout(10)
        self.driver.get(
            request.url,
        )
        # Wait for JavaScript to render (if necessary)
        # import time
        #
        # time.sleep(5)
        # You can use explicit waits here for specific elements
        logging.info(f"Processed: {request.url}, response size: {len(self.driver.page_source)}")
        return HtmlResponse(self.driver.current_url, body=self.driver.page_source, encoding="utf-8", request=request)

    def spider_closed(self):
        self.driver.quit()
        try:
            # Try to terminate the Chrome process
            os.kill(self.chrome_pid, signal.SIGTERM)
            logging.info(f"Successfully terminated Chrome process PID {self.chrome_pid}.")
        except Exception as e:
            logging.error(f"Failed to terminate Chrome process PID {self.chrome_pid}: {e}")
