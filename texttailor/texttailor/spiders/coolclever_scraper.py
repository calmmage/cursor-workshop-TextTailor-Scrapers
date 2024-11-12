import re

from .shop_parser_spider import UniversalShopSpider


class CoolCleverSpider(UniversalShopSpider):
    # region Settings

    name = "coolclever_spider"
    allowed_domains: list = ["www.coolclever.ru", "coolclever.ru"]
    start_urls: list = [
        "https://www.coolclever.ru/",
        "https://www.coolclever.ru/catalog/otdokhni/",
        "https://www.coolclever.ru/catalog/myasnov/",
    ]

    # https://www.coolclever.ru/catalog/product/konservy-myasnye-myaso-krolika-tushenoe-zhb-338g-90025587
    item_regex = re.compile(r"/catalog/product/.*", re.IGNORECASE)

    # https://www.coolclever.ru/catalog/myasnov/kolbasy-sosiski-delikatesy-tushenka
    # https: // www.coolclever.ru / catalog / myasnov / tryufelnaya - kollektsiya
    # https://www.coolclever.ru/catalog/otdokhni/dzhin-grappa-kalvados
    # https://www.coolclever.ru/catalog/otdokhni/pivo
    category_regex = re.compile(r"/catalog/(myasnov|otdokhni).*", re.IGNORECASE)

    contact_us_regex = re.compile(r"/contact|/support|/help|/about-us|/connect", re.IGNORECASE)

    best_css_selector_for_description = None
    common_texts: list = None

    # custom_settings = {
    #     "DOWNLOADER_MIDDLEWARES": {
    #         "texttailor.middlewares.UndetectedChromeMiddleware": 800,
    #     },
    # }

    item_limit = 2 * 10**5
    pages_limit = 2 * 10**6

    # endregion
