# Copied from notebook to properly straiten the code later

from mvodolagin_personal_imports import *

load_dotenv()


stores_df = pd.read_pickle(r"E:\Work\Personal\repos\TextTailor\resources\furniture_stores_example.pickle")
stores_df["url_root"] = stores_df["website"].apply(lambda x: x.split("://", 1)[-1].split("/", 1)[0])


locations_count = stores_df["name"].value_counts()
locations_count_by_url_root = stores_df.groupby("url_root").size()
big_names = locations_count[locations_count >= 5].index
big_urls = locations_count_by_url_root[locations_count_by_url_root >= 5].index
big_chains = stores_df[(stores_df["name"].isin(big_names)) | (stores_df["url_root"].isin(big_urls))]
small_stores = stores_df[(~stores_df["name"].isin(big_names)) & (~stores_df["url_root"].isin(big_urls))]

urls_to_try = small_stores["url_root"].unique().tolist()
