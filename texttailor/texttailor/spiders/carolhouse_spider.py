import json
import re
from collections import defaultdict
from pathlib import Path

# from yourprojectname.items import YourItemClass  # Ensure you have defined this class in your items.py
from urllib.parse import urljoin

import scrapy
from loguru import logger
from scrapy.exceptions import CloseSpider


class MySpider(scrapy.Spider):
    name = "carolhouse_spider"
    allowed_domains = ["carolhouse.com"]
    start_urls = []
    start_urls += ["http://www.carolhouse.com"]
    # start_urls += ["https://www.carolhouse.com/living-room/cabinets/room-type.aspx"]  # "http://www.carolhouse.com",
    item_count = 0  # Initialize the counter
    item_limit = 200

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "texttailor.middlewares.UndetectedChromeMiddleware": 800,
        },

    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(MySpider, cls).from_crawler(crawler, *args, **kwargs)
        # Access settings from the crawler object
        data_dir_path = crawler.settings.get("DATA_DIR", "data")  # Default to 'data' if not set
        spider.data_dir = Path(data_dir_path) / spider.name
        spider.raw_data_dir = Path(data_dir_path) / spider.name / "raw_data"
        # Ensure the directory exists
        spider.raw_data_dir.mkdir(parents=True, exist_ok=True)
        return spider

    def parse(self, response, **kwargs):
        # Define your regex patterns
        contact_us_pattern = re.compile(r".*contact-us.*", re.IGNORECASE)
        item_information_pattern = re.compile(r".*iteminformation\.aspx.*")
        general_pattern = re.compile(r"^/[\w-]+(/[\w-]+)*(/[\w-]+(\.aspx|\.inc)?)?/?$")

        for href in response.xpath("//a/@href").extract():
            absolute_url = urljoin(response.url, href)

            # Check for 'Contact Us' link
            if contact_us_pattern.match(href):
                yield response.follow(absolute_url, self.parse_contact, meta={"is_contact_page": True})
                continue  # Skip further checks for this link

            # Check for item links
            elif item_information_pattern.match(href):
                yield response.follow(absolute_url, self.parse_item)
                continue  # Skip further checks for this link

            # Check and follow other potential links
            elif general_pattern.match(href) and not any(
                substr in absolute_url for substr in ["contact-us", "iteminformation.aspx"]
            ):
                yield response.follow(absolute_url, self.parse)

            else:
                logger.debug(f"No matches for {href}, abs link {absolute_url}")

    def parse_contact(self, response):
        if self.item_count >= self.item_limit:
            raise CloseSpider("Reached item limit.")
        else:
            self.item_count += 1
        filename = f"contact_page_{self.item_count}.html"
        with open(self.raw_data_dir / filename, "wb") as f:
            f.write(response.body)
        # add phone number as well

    def parse_item(self, response):
        if self.item_count >= self.item_limit:
            raise CloseSpider("Reached item limit.")
        else:
            self.item_count += 1
        classes_to_parse = [
            "ProductDescriptionHeading",
            "ProductInfoSpanValue ProductInfoSpanValueProductDescription",
            "ProductInfoSpanValue ProductInfoSpanValueCollectionFeatures",
        ]

        filename = f"item_{self.item_count}.html"
        with open(self.raw_data_dir / filename, "wb") as f:
            f.write(response.body)

        descriptions = defaultdict(list)
        for class_name in classes_to_parse:
            for tag in response.xpath(f"//span[@class='{class_name}']/text()").extract():
                descriptions[class_name].append(tag)

        with open(self.data_dir / f"item_{self.item_count}.json", "w") as f:
            f.write(json.dumps(descriptions, indent=2))

        yield descriptions
