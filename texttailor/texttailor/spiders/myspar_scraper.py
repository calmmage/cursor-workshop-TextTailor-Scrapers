import re

from .shop_parser_spider import UniversalShopSpider


class MySparSpider(UniversalShopSpider):
    # region Settings

    _debug = False

    name = "myspar_spider"
    allowed_domains: list = ["www.myspar.ru", "myspar.ru"]
    start_urls: list = [
        "https://myspar.ru/",
        "https://myspar.ru/catalog/",
    ]

    item_regex = re.compile(r"/catalog/[^/]*/[^/]*/$", re.IGNORECASE)
    category_regex = re.compile(r"/catalog/[^/]*/$", re.IGNORECASE)
    contact_us_regex = re.compile(r"/contact|/support|/help|/about-us|/connect", re.IGNORECASE)

    best_css_selector_for_description = None
    common_texts: list = None

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "texttailor.middlewares.UndetectedChromeMiddleware": 800,
        },
    }

    item_limit = 2 * 10**5
    pages_limit = 2 * 10**6

    # endregion
