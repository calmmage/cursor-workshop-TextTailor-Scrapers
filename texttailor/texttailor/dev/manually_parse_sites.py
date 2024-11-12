from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from tqdm.auto import tqdm

logger.debug(f"Env vars loading: {load_dotenv()}")

from get_data_for_spider import main


def scrape_site(fp):
    try:
        main(fp)
    except Exception as e:
        logger.error(f"Error in {fp}: {e}")


if __name__ == "__main__":
    root_pages_dir = Path(r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\notebooks\root_pages")
    root_htmls = list(root_pages_dir.glob("*.html"))

    # for root_html in root_htmls:
    #     scrape_site(root_html)

    with ThreadPoolExecutor(4) as pool:
        list(tqdm(pool.map(scrape_site, root_htmls), total=len(root_htmls)))
