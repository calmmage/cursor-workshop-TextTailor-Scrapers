import json
import re
from pathlib import Path
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup, Tag
from loguru import logger
from mvodolagin_personal_imports import trim_extra_whitespace


class UniversalShopSpider(scrapy.Spider):
    # region Settings

    _debug = False

    name = None
    allowed_domains: list = None
    start_urls: list = None

    item_regex = None
    category_regex = None
    contact_us_regex = re.compile(r"/contact|/support|/help|/about-us|/connect", re.IGNORECASE)

    best_css_selector_for_description = None
    common_texts: list = None

    # custom_settings = {
    #     "DOWNLOADER_MIDDLEWARES": {
    #         "texttailor.middlewares.UndetectedChromeMiddleware": 800,
    #     },
    #     "SOCKS5_PROXY": proxy_url_default,
    # }

    item_limit = 200
    pages_limit = 2000

    # endregion

    # region Runtime Variables

    item_count = 0
    pages_count = 0
    reached_item_limit = False
    reached_pages_limit = False
    contacts_found = []

    # endregion

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(UniversalShopSpider, cls).from_crawler(crawler, *args, **kwargs)
        # Access settings from the crawler object
        data_dir_path = crawler.settings.get("DATA_DIR", "data")  # Default to 'data' if not set
        spider.data_dir = Path(data_dir_path) / spider.name
        spider.raw_data_dir = Path(data_dir_path) / spider.name / "raw_data"
        # Ensure the directory exists
        spider.raw_data_dir.mkdir(parents=True, exist_ok=True)

        # region Blacklists

        already_scraped_fp = spider.data_dir / "already_scraped.json"
        spider.already_scraped_links = []
        if already_scraped_fp.exists():
            with open(already_scraped_fp, "r", encoding="utf-8") as f:
                spider.already_scraped_links = json.load(f)

        # endregion

        return spider

    def check_new_contacts(self, all_urls):
        new_contact_links = [
            link
            for link in all_urls
            if any([link.lower().startswith(prefix) for prefix in ["mailto:", "tel:", "sms:", "whatsapp:"]])
        ]
        self.contacts_found.extend(new_contact_links)
        self.contacts_found = list(set(self.contacts_found))
        with open(self.data_dir / "contacts.json", "w", encoding="utf-8") as f:
            json.dump(self.contacts_found, f, indent=2)

    def parse(self, response, **kwargs):
        if self.pages_count >= self.pages_limit:
            self.reached_pages_limit = True
            return

        self.pages_count += 1
        all_urls = response.xpath("//a/@href").extract()

        if self._debug:
            logger.debug(f"Page {self.pages_count}, URL: {response.url}, URLs found: {all_urls}")

        self.check_new_contacts(all_urls)

        for href in all_urls:
            absolute_url = urljoin(response.url, href)

            if self.already_scraped_links and (absolute_url in self.already_scraped_links):
                continue

            # Check for 'Contact Us' link, follow them always
            if self.contact_us_regex.match(href):
                yield response.follow(absolute_url, self.parse_contact, meta={"is_contact_page": True})
                continue

            if not self.reached_item_limit:
                if self.item_regex.match(href):
                    yield response.follow(absolute_url, self.parse_item)
                    continue
                elif self.category_regex.match(href):
                    yield response.follow(absolute_url, self.parse)
                    continue
                # else:
                #     logger.debug(f"No matches for {href}, abs link {absolute_url}")

    def parse_contact(self, response):
        all_urls = response.xpath("//a/@href").extract()
        self.check_new_contacts(all_urls)

        filename = f"contact_page_{self.item_count}.html"
        with open(self.raw_data_dir / filename, "wb") as f:
            f.write(response.body)

    def parse_item(self, response):
        if self.item_count >= self.item_limit:
            self.reached_item_limit = True
            return

        self.item_count += 1

        filename = f"item_{self.item_count}.html"
        with open(self.raw_data_dir / filename, "wb") as f:
            f.write(response.body)

        if not self.best_css_selector_for_description:
            yield

        else:
            unique_content = extract_unique_content_from_page(response.body, self.common_texts)

            matching_texts = [
                c["text"] for c in unique_content if self.best_css_selector_for_description == c["css_selector"]
            ]
            payload = {
                "url": response.url,
                "unique_content": unique_content,
                "matching_texts": matching_texts,
                "type": "item",
            }
            with open(self.data_dir / f"item_{self.item_count}.json", "w") as f:
                f.write(json.dumps(payload, indent=2))

            yield payload


def create_spider_class(
    _name: str,
    _store_url: str,
    _item_regex: str,
    _category_regex: str,
    _best_css_selector_for_description: str,
    _common_texts: list,
):
    class CustomSpider(UniversalShopSpider):
        name = _name
        allowed_domains = [_store_url.split("://", 1)[-1].split("/", 1)[0]]
        start_urls = ["http://" + _store_url]
        item_regex = re.compile(_item_regex)
        category_regex = re.compile(_category_regex)
        best_css_selector_for_description = _best_css_selector_for_description
        common_texts = _common_texts

        # name = None
        # allowed_domains: list = None
        # start_urls: list = None
        #
        # item_regex = None
        # category_regex = None
        # contact_us_regex = re.compile(r"/contact|/support|/help|/about-us|/connect", re.IGNORECASE)
        #
        # best_css_selector_for_description = None
        # common_texts: list = None

    return CustomSpider


def is_text_content_allowed(s):
    if s.endswith("..."):
        return False
    if "...\n" in s:
        return False
    if len(s) < 10:
        return False
    if s.count("{") > 5:
        return False
    return True


def extract_unique_content_from_page(page_html, common_texts):
    TARGET_TAGS = ["title", "h1", "h2", "h3", "p", "span", "a", "div"]  # ToDo: check if something's missing

    result = []
    soup = BeautifulSoup(page_html, "html5lib")

    for tag in soup.find_all(TARGET_TAGS):
        text_content = trim_extra_whitespace(tag.get_text(strip=False))
        if text_content in common_texts:
            continue
        if not is_text_content_allowed(text_content):
            continue
        data = determine_tag_location(tag)
        data["text"] = text_content
        result.append(data)

    return result


def determine_tag_location(tag):
    # Helper function to create a CSS selector for a given tag
    def generate_css_selector(tag):
        selector = tag.name
        if tag.attrs:
            if "id" in tag.attrs:
                selector += f"#{tag['id']}"
            elif "class" in tag.attrs:
                # Join all classes into one selector
                classes = ".".join(tag["class"])
                selector += f".{classes}"
        return selector

    # Helper function to create an XPath for a given tag
    def generate_xpath(tag):
        path = []
        current = tag
        while current.parent and isinstance(current.parent, Tag):
            siblings = [t for t in current.parent.children if isinstance(t, Tag) and t.name == current.name]
            count = 1 + siblings.index(current)
            path.append(f"{current.name}[{count}]")
            current = current.parent
        return "/" + "/".join(reversed(path))

    result = {
        "css_selector": generate_css_selector(tag),
        "xpath": generate_xpath(tag),
    }
    return result
