from loguru import logger
from mvodolagin_personal_imports import *
from scrapy.crawler import CrawlerProcess

load_dotenv()

source_root = r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor"

sys.path.append(source_root)

from texttailor.spiders import shop_parser_spider

root_dir = Path(r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\notebooks\root_pages")


def gather_spider_classes():
    spider_settings = {}

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

        spider_settings[name] = spider_class

    logger.info(f"Found {len(spider_settings)} spiders.")
    return spider_settings


def check_if_spiders_worked(spider_names):
    data_dir = Path(r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\dev\data")
    results = {n: False for n in spider_names}
    for n in spider_names:
        local_data_dir = data_dir / n
        if not local_data_dir.exists():
            continue
        if len(list(local_data_dir.glob("*.json"))) > 100:
            results[n] = True
            continue
        if not (local_data_dir / "raw_data").exists():
            continue
        if len(list((local_data_dir / "raw_data").glob("*.html"))) > 100:
            results[n] = True
            continue

    return results


def main():
    all_spiders = gather_spider_classes()
    data_dir = Path(r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\dev\data")

    spider_names = list(all_spiders.keys())
    spider_results = {n: False for n in spider_names}

    for iter_num in tqdm(range(100)):
        objective_spider_results = check_if_spiders_worked(spider_names)
        spider_results = {n: spider_results[n] or objective_spider_results[n] for n in spider_names}
        spiders_to_run = [n for n, r in spider_results.items() if not r]
        if not spiders_to_run:
            break
        spiders_to_run = random.sample(spiders_to_run, min(20, len(spiders_to_run)))

        process = CrawlerProcess(
            settings={
                "FEED_FORMAT": "json",  # default format, can be overridden per spider
            }
        )
        for spider_name in spiders_to_run:
            spider_class = all_spiders[spider_name]
            process.crawl(spider_class, feed_uri=data_dir / spider_name / "final_data.json")
        process.start()
        for spider_name in spiders_to_run:
            spider_results[spider_name] = True

    logger.success(f"Finished running spiders.")


if __name__ == "__main__":
    main()
