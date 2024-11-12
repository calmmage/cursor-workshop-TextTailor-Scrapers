import json
import random
import re
from collections import defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString
from loguru import logger
from mvodolagin_personal_imports.langchain_stuff import *
from pathvalidate import sanitize_filename


# region Utils


def get_links_from_html(html, root_url=None):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for link in soup.find_all("a"):
        if link.has_attr("href"):
            links.add(link["href"])

    proper_links = set()
    for link in links:
        if root_url and root_url in link:
            proper_links.add(link.split(root_url, 1)[-1])
        elif link.startswith("/"):
            proper_links.add(link)
    return proper_links


def get_regexp_from_llm_answer(llm_answer: AIMessage):
    regex_string = llm_answer.content

    # Convert to a proper regex pattern (note: removing unnecessary escapes)
    # Since we're dealing with Python, we don't need to escape forward slashes.
    pattern = regex_string.replace("\\/", "/").strip('"')

    return pattern


def get_diverse_sample(links_list, n=3):
    if len(links_list) <= n:
        return links_list

    result = set()
    result.add(random.sample(links_list, 1)[0])

    for i in range((n + 1) ** 2):
        candidates = []
        for link in links_list:
            if any(link.startswith(r[:3]) for r in result):
                continue
            candidates.append(link)
        if len(candidates) == 0:
            candidates = links_list

        better_candidates = []

        for candidate in candidates:
            if any(candidate.endswith(r[-3:]) for r in result):
                continue
            better_candidates.append(candidate)
        if len(better_candidates) == 0:
            better_candidates = candidates

        result.add(random.sample(better_candidates, 1)[0])
        if len(result) == n:
            return list(result)


def parse_pages(collection_pages_candidates, root_url, data_dir, failed_dir):
    for link in collection_pages_candidates:
        full_link = "http://" + root_url + link
        sanitized_link = sanitize_filename(link, replacement_text="_")
        filepath = (data_dir / sanitized_link).with_suffix(".html")
        filepath.parent.mkdir(exist_ok=True, parents=True)
        try:
            logger.debug(f"Downloading {full_link}")
            res = requests.get(full_link)
            if res.ok:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(res.text)
            else:
                with open(failed_dir / filepath.name, "w", encoding="utf-8") as f:
                    f.write(res.text)
        except Exception as e:
            logger.error(e)


# endregion

# region Categories


def get_prompt_for_category_links_regexp(ll):
    role_message = """You will be given a numbered list of internal links from a web store or marketplace website. Your task is to analyze these links and identify which of them lead to product listing pages (PLPs) or category pages. These are pages designed to list multiple products, either by brand or category, often for the purposes of browsing or making a selection. The links to these pages are crucial for understanding the structure and navigational layout of the site. Return only a Python-style regular expression (regexp) pattern that could be used to distinguish these PLP or category links from others."""

    example_input = """1. /bedroom/cabinets/room-type.aspx
2. /terms-conditions.inc
3. /southern-motion/brand-type.aspx
4. /designcenter.inc
5. /office-furniture/desks/category-type.aspx
6. /homepage.aspx?logout=true
7. /living-room/chaises/room-type.aspx
8. /brand/john-thomas/
9. /in-home-design-staging.inc"""

    example_output = "\/(room-type|brand-type|category-type)\.aspx"

    formatted_list = "\n".join([f"{i + 1}. {link}" for i, link in enumerate(ll)])

    messages = [("system", role_message), ("human", example_input), ("ai", example_output), ("human", formatted_list)]
    messages = [(role, trim_extra_whitespace(message)) for role, message in messages]

    full_prompt = ChatPromptTemplate.from_messages(messages)
    return full_prompt


def get_regexp_for_category(links_list):
    prompt = get_prompt_for_category_links_regexp(links_list)
    res_o_smart = (prompt | smart_llm).invoke({})
    return get_regexp_from_llm_answer(res_o_smart)


# endregion

# region Items


def get_prompt_for_item_links_regexp(ll):
    role_message = """You will be given a numbered list of internal links from a web store or marketplace website. Your task is to analyze these links and identify which of them lead to Product Detail Pages (PDPs). PDPs are pages dedicated to presenting detailed information about a single product, including but not limited to its price, features, descriptions, customer reviews, and purchase options. Return only a Python-style regular expression (regexp) pattern that could be used to distinguish these PDP links from others."""

    example_input = """1. /products/bedroom-set-queen-size
2. /category/bedroom-furniture
3. /product/wooden-dining-chair
4. /help/shipping-info
5. /product-detail/modern-sofa-sectional
6. /about-us"""

    example_output = "\/(products|product-detail)\/[a-z-]+"

    formatted_list = "\n".join([f"{i + 1}. {link}" for i, link in enumerate(ll)])

    messages = [("system", role_message), ("human", example_input), ("ai", example_output), ("human", formatted_list)]
    messages = [(role, trim_extra_whitespace(message)) for role, message in messages]

    full_prompt = ChatPromptTemplate.from_messages(messages)
    return full_prompt


def get_regexp_for_items(item_candidate_links):
    prompt = get_prompt_for_item_links_regexp(item_candidate_links)
    res_o_smart = (prompt | smart_llm).invoke({})
    return get_regexp_from_llm_answer(res_o_smart)


def get_item_candidates(data_dir, root_url):
    item_candidate_links = []
    for fp in data_dir.glob("*.html"):
        with open(fp, "r", encoding="utf-8") as f:
            html_text = f.read()
        links_list = get_links_from_html(html_text, root_url=root_url)
        item_candidate_links.extend(links_list)
    item_candidate_links = list(set(item_candidate_links))
    return item_candidate_links


# endregion


def main(fp: Path):
    # Init & runtime

    with open(fp, "r", encoding="utf-8") as f:
        html_text = f.read()
    root_url = fp.stem

    data_dir = fp.parent / root_url
    debug_dir = data_dir / "debug"
    failed_dir = debug_dir / "failed"
    failed_dir.mkdir(exist_ok=True, parents=True)

    result_fp = data_dir / "patterns.json"
    if result_fp.exists():
        with result_fp.open("r", encoding="utf-8") as f:
            resulting_patterns = json.load(f)
    else:
        resulting_patterns = {}

    # Find category links from the main page

    links_list = get_links_from_html(html_text, root_url=root_url)

    if not (category_pattern := resulting_patterns.get("category")):
        category_pattern = get_regexp_for_category(links_list)
        resulting_patterns["category"] = category_pattern
        with result_fp.open("w", encoding="utf-8") as f:
            json.dump(resulting_patterns, f, indent=2, ensure_ascii=False)
        logger.success(f"Saved category pattern for {root_url}")
    regex = re.compile(category_pattern)

    links_that_pass = [link for link in links_list if regex.match(link)]
    links_that_fail = [link for link in links_list if not regex.match(link)]  # For simpler debug

    with (debug_dir / "category_debug.json").open("w", encoding="utf-8") as f:
        json.dump(
            {"pattern": category_pattern, "links_that_pass": links_that_pass, "links_that_fail": links_that_fail},
            f,
            indent=2,
            ensure_ascii=False,
        )

    # Parse some category pages

    if len(list(data_dir.glob("*.html"))) < 3:
        collection_pages_candidates = get_diverse_sample(links_that_pass, n=3)
        parse_pages(collection_pages_candidates, root_url, data_dir, failed_dir)

    # Find item links from the category pages

    item_candidate_links = get_item_candidates(data_dir, root_url)
    item_candidate_links = get_diverse_sample(item_candidate_links, n=100)

    if not (item_pattern := resulting_patterns.get("item")):
        item_pattern = get_regexp_for_items(item_candidate_links)
        resulting_patterns["item"] = item_pattern
        with result_fp.open("w", encoding="utf-8") as f:
            json.dump(resulting_patterns, f, indent=2, ensure_ascii=False)
        logger.success(f"Saved item pattern for {root_url}")
    regex = re.compile(item_pattern)

    links_that_pass = [link for link in item_candidate_links if regex.match(link)]
    links_that_fail = [link for link in item_candidate_links if not regex.match(link)]  # For simpler debug

    with (debug_dir / "item_debug.json").open("w", encoding="utf-8") as f:
        json.dump(
            {"pattern": item_pattern, "links_that_pass": links_that_pass, "links_that_fail": links_that_fail},
            f,
            indent=2,
            ensure_ascii=False,
        )

    # Parse some item pages

    if len(list(data_dir.glob("*.html"))) < 10:
        product_pages_candidates = get_diverse_sample(links_that_pass, n=10)
        parse_pages(product_pages_candidates, root_url, data_dir, failed_dir)



