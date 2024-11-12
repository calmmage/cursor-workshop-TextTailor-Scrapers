from mvodolagin_personal_imports import *
from scrapy.crawler import CrawlerProcess

load_dotenv()

source_root = r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor"

sys.path.append(source_root)

from texttailor.spiders import shop_parser_spider

root_dir = Path(r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\notebooks\root_pages")

if __name__ == "__main__":
    for d in root_dir.iterdir():
        new_regexps_fp = d / "regexp_refinement.json"
        description_selector_fp = d / "description_selector.json"
        if not all([new_regexps_fp.exists(), description_selector_fp.exists()]):
            continue

        with open(new_regexps_fp, "r") as f:
            new_regexps = json.load(f)
            # {
            #     "new_patterns": new_patterns,
            #     "original_patterns": base_patterns,
            #     "new_quality": new_quality,
            #     "original_quality": original_quality,
            # }

        if new_quality := new_regexps.get("new_quality"):
            if not all(new_quality.values()):
                continue

        regexps = new_regexps.get("new_patterns") or new_regexps.get("original_patterns")

        with open(description_selector_fp, "r") as f:
            description_selector = json.load(f)
            # {
            #     "best_css_selector": best_selector,
            #     "common_texts": common_texts,
            #     "css_selector_candidates": winner_selector,
            # }

        if not isinstance(description_selector, dict):
            continue

        if not description_selector.get("best_css_selector"):
            continue

        # def create_spider_class(_name, _store_url, _item_regex, _category_regex, _best_css_selector_for_description, _common_texts):
        name = d.name.split("www.", 1)[-1].split(".")[0]
        store_url = d.name
        item_regex = regexps.get("item")
        category_regex = regexps.get("category")
        best_selector = description_selector.get("best_css_selector")
        common_texts = description_selector.get("common_texts")

        spider_class = shop_parser_spider.create_spider_class(
            name, store_url, item_regex, category_regex, best_selector, common_texts
        )

        break

    process = CrawlerProcess()
    process.crawl(spider_class)
    process.start()
