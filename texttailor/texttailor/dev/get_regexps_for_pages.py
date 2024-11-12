from bs4 import BeautifulSoup
from loguru import logger
from mvodolagin_personal_imports import *

load_dotenv()

from mvodolagin_personal_imports.langchain_stuff import *


def get_links_for_shop_directory(dir_path):
    html_files = list(dir_path.glob("*.html"))
    if len(html_files) < 10:
        return None

    # region Extracting links

    all_links = []

    for fp in html_files:
        with open(fp, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html5lib")
        links = soup.find_all("a")
        links = [link.get("href") for link in links]
        links = list(set(links))
        all_links.extend(links)

    root_url = dir_path.name
    logger.debug(f"Root URL: {root_url}")

    unprocessed_links = [link for link in all_links if link]
    contact_links = [
        link
        for link in unprocessed_links
        if any([link.lower().startswith(prefix) for prefix in ["mailto:", "tel:", "sms:", "whatsapp:"]])
    ]
    unprocessed_links = [link for link in unprocessed_links if link not in contact_links]

    internal_links = [
        link for link in unprocessed_links if (not link.startswith("//") and (link.startswith("/") or root_url in link))
    ]
    unprocessed_links = [link for link in unprocessed_links if link not in internal_links]

    external_links = [link for link in unprocessed_links if (link.startswith("//") or link.startswith("http"))]
    unprocessed_links = [link for link in unprocessed_links if link not in external_links]

    logger.debug(
        f"Links: {len(all_links)}, Contacts: {len(contact_links)}, Internals: {len(internal_links)}, Externals: {len(external_links)}, Unprocessed: {len(unprocessed_links)}"
    )

    # endregion

    # region Splitting links

    link_counts = Counter(internal_links)
    threshold = 0.3
    universal_links = [link for link, count in link_counts.items() if count == len(html_files)]
    common_links = [
        link for link, count in link_counts.items() if len(html_files) > count >= threshold * len(html_files)
    ]
    rare_links = [link for link, count in link_counts.items() if count < threshold * len(html_files)]
    logger.debug(
        f"Total links: {len(link_counts)}, Universal: {len(universal_links)}, Common: {len(common_links)}, Rare: {len(rare_links)}"
    )

    # endregion

    return {
        "universal": universal_links,
        "common": common_links,
        "rare": rare_links,
        "contact": contact_links,
    }


def check_regexp_match(dir_path, categorized_links=None, patterns=None):
    if not categorized_links:
        categorized_links = get_links_for_shop_directory(dir_path)

    # region Checking patterns

    if not patterns:
        patterns = json.load((dir_path / "patterns.json").open("r", encoding="utf-8"))
        logger.debug(f"Base patterns for {dir_path.name}:\n {patterns}")
    else:
        logger.debug(f"Checking patterns for {dir_path.name}:\n {patterns}")

    counts = {k: get_regexp_match_counts(categorized_links[k], patterns) for k in ["universal", "common", "rare"]}
    counts = pd.DataFrame(counts).T

    # endregion

    return counts, patterns


def get_new_regexp(categorized_links):
    res = RegExpPrompts.full_chain.invoke(categorized_links)
    new_patterns = safe_json_loads(res.content)
    key_remapping = {
        "product_page_regex": "item",
        "catalog_page_regex": "category",
    }
    new_patterns = {key_remapping[key]: value for key, value in new_patterns.items()}
    return new_patterns


def get_regexp_match_counts(link_list, patterns):
    both_patterns = [link for link in link_list if all([re.match(pat, link) for pat in patterns.values()])]
    category_patterns = [link for link in link_list if re.match(patterns["category"], link)]
    category_patterns = [link for link in category_patterns if link not in both_patterns]
    item_patterns = [link for link in link_list if re.match(patterns["item"], link)]
    item_patterns = [link for link in item_patterns if link not in both_patterns]

    counts = {
        "both": len(both_patterns),
        "category": len(category_patterns),
        "item": len(item_patterns),
        "miss": len(link_list) - len(both_patterns) - len(category_patterns) - len(item_patterns),
        "total": len(link_list),
    }
    return counts


def check_regexp_quality(counts):
    # if `both` match many, it's bad product and good category
    # if `both` + `category` matches all, it's bad category
    # if `item` is 0, it's bad item
    is_ok_quality = {"category": True, "item": True}
    summed = counts.sum()
    if summed["both"] > 0.2 * summed["total"]:
        is_ok_quality["category"] = False
    if summed["both"] + summed["category"] >= summed["total"] - 5:
        is_ok_quality["category"] = False
    if summed["item"] == 0:
        is_ok_quality["item"] = False
    return is_ok_quality


class RegExpPrompts:
    @ClassProperty
    @classmethod
    def choose_links_prompt(cls):
        # Role message for the language model
        role_message = "You will categorize internal web links into three categories: 'catalog_pages', 'product_pages', and 'other_pages'. For 'catalog_pages', identify links that lead to collections or broad categories of products. 'Product_pages' are links that directly access specific product details. 'Other_pages' include all links not fitting into the other categories, like informational or administrative content. Output the indices of links in a JSON dictionary under the appropriate category based on the input list of links."

        # Example input
        example_input = """
        1. /furniture/beds/king-size
        2. /help/returns-policy
        3. /sale
        4. /furniture/beds/king-size/342322
        5. /about-us
        6. /blog/how-to-choose-a-bed
        """

        # Expected output in JSON format
        example_output = """
        {{
          "product_pages": [4],
          "catalog_pages": [1, 3],
          "other_pages": [2, 5, 6]
        }}
        """

        input_template = """{formatted_list}"""

        messages = [
            ("system", role_message),
            ("human", example_input),
            ("ai", example_output),
            ("human", input_template),
        ]
        messages = [(role, trim_extra_whitespace(message)) for role, message in messages]
        return ChatPromptTemplate.from_messages(messages)

    @ClassProperty
    @classmethod
    def get_regexp_prompt(cls):
        # Role message for the language model
        role_message = (
            "You are tasked with generating Python regular expressions to identify URLs that categorize web pages into product or catalog pages. Focus on extracting meaningful patterns that help differentiate between product details and broader catalog listings. Use elements in the URL path like 'collections', 'products', or similar indicators to guide the creation of these expressions. "
            "Write the results as JSON."
        )

        # Example input
        example_input = """
        Product Pages:
        - /collections/bedrooms/products/carlton-bedroom-set
        - /collections/dining-rooms/products/oak-dining-table

        Catalog Pages:
        - /collections/bedrooms
        - /collections/dining-rooms
        """

        # Expected output in Python regular expressions
        example_output = """{{"product_page_regex": "^/collections/[^/]+/products/.*$", "catalog_page_regex": "^/collections/[^/]+/?$"}}"""

        input_template = """{formatted_link_examples}"""

        messages = [
            ("system", role_message),
            ("human", example_input),
            ("ai", example_output),
            ("human", input_template),
        ]
        messages = [(role, trim_extra_whitespace(message)) for role, message in messages]

        return ChatPromptTemplate.from_messages(messages)

    @ClassProperty
    @classmethod
    def full_chain(cls):
        """
        Input is a dict with keys "universal", "common", "rare" (a links dict from get_links_for_shop_directory)
        :return:
        """
        chain = (
            RunnablePassthrough.assign(formatted_list=lambda d: cls.format_links(d))
            | RunnablePassthrough.assign(llm_answer=cls.choose_links_prompt | basic_llm)
            | RunnablePassthrough.assign(links_dict=lambda d: cls.unpack_links(d, d["llm_answer"]))
            | RunnablePassthrough.assign(formatted_link_examples=lambda d: cls.choose_example_links(d["links_dict"]))
            | cls.get_regexp_prompt
            | basic_llm
        )
        return chain

    @staticmethod
    def format_links(links_dict):
        links_to_process = []
        examples_count = {
            "universal": 20,
            "common": 20,
            "rare": 20,
        }
        for category, n in examples_count.items():
            links_to_process.extend(random.sample(links_dict[category], min(n, len(links_dict[category]))))

        formatted_list = "\n".join([f"{i + 1}. {link}" for i, link in enumerate(links_to_process)])
        return formatted_list

    @staticmethod
    def unpack_links(links_dict, llm_answer):
        internal_links = links_dict["universal"] + links_dict["common"] + links_dict["rare"]
        llm_answer = safe_json_loads(llm_answer.content)
        out_of_bounds = [
            i
            for i in llm_answer.get("product_pages", [])
            + llm_answer.get("catalog_pages", [])
            + llm_answer.get("other_pages", [])
            if i > len(internal_links)
        ]
        if out_of_bounds:
            logger.warning(f"Indices out of bounds: {out_of_bounds}")
        product_pages = [
            internal_links[i - 1] for i in llm_answer.get("product_pages", []) if 0 < i <= len(internal_links)
        ]
        catalog_pages = [
            internal_links[i - 1] for i in llm_answer.get("catalog_pages", []) if 0 < i <= len(internal_links)
        ]
        other_pages = [internal_links[i - 1] for i in llm_answer.get("other_pages", []) if 0 < i <= len(internal_links)]
        return {
            "product_pages": product_pages,
            "catalog_pages": catalog_pages,
            "other_pages": other_pages,
        }

    @staticmethod
    def choose_example_links(categorized_links_dict, sample_size=5):
        all_product_links = categorized_links_dict["product_pages"]
        all_catalog_links = categorized_links_dict["catalog_pages"]
        product_links = random.sample(all_product_links, min(sample_size, len(all_product_links)))
        catalog_links = random.sample(all_catalog_links, min(sample_size, len(all_catalog_links)))
        newline = "\n"
        formatted_text = f"""
        Product Pages:
        {newline.join([f"- {link}" for link in product_links])}

        Catalog Pages:
        {newline.join([f"- {link}" for link in catalog_links])}
        """
        return trim_extra_whitespace(formatted_text)
