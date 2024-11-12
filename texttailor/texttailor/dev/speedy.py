# Copied from notebook to properly straiten the code later
from concurrent.futures import ThreadPoolExecutor

import requests
from mvodolagin_personal_imports import *

load_dotenv()


data_dir = Path(r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\notebooks\root_pages")
failed_dir = data_dir / "failed"


def scrape_page(url):
    target_fp = data_dir / (url + ".html")
    if target_fp.exists():
        return
    try:
        res = requests.get("http://" + url)
        if res.ok:
            with target_fp.open("w", encoding="utf-8") as f:
                f.write(res.text)
        else:
            with open(failed_dir / (url + ".html"), "w", encoding="utf-8") as f:
                f.write(res.text)
    except Exception as e:
        print(e)


if __name__ == "__main__":
    stores_df = pd.read_pickle(r"E:\Work\Personal\repos\TextTailor\resources\furniture_stores_example.pickle")
    stores_df["url_root"] = stores_df["website"].apply(lambda x: x.split("://", 1)[-1].split("/", 1)[0])

    locations_count = stores_df["name"].value_counts()
    locations_count_by_url_root = stores_df.groupby("url_root").size()
    big_names = locations_count[locations_count >= 5].index
    big_urls = locations_count_by_url_root[locations_count_by_url_root >= 5].index
    big_chains = stores_df[(stores_df["name"].isin(big_names)) | (stores_df["url_root"].isin(big_urls))]
    small_stores = stores_df[(~stores_df["name"].isin(big_names)) & (~stores_df["url_root"].isin(big_urls))]

    urls_to_try = small_stores["url_root"].unique().tolist()
    random.shuffle(urls_to_try)

    with ThreadPoolExecutor() as pool:
        # pool.map(scrape_page, urls_to_try)
        # with tqdm
        list(tqdm(pool.map(scrape_page, urls_to_try), total=len(urls_to_try)))
