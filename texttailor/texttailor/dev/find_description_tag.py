from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from bs4 import BeautifulSoup, Tag
from trafilatura import extract
from loguru import logger
import html

from mvodolagin_personal_imports import *

load_dotenv()


TARGET_TAGS = ["title", "h1", "h2", "h3", "p", "span", "a", "div"]  # ToDo: check if something's missing


def process_dir(dir_path: Path):
    # region Early Exit

    if (htmls_count := len(list(dir_path.glob("*.html")))) < 5:
        logger.debug(f"Skipping {dir_path} because of {htmls_count} htmls")
        return

    # endregion

    # region Regexps

    item_pattern = None
    patterns = {}

    new_patterns_file = dir_path / "regexp_refinement.json"
    if new_patterns_file.exists():
        new_regexps = json.load(new_patterns_file.open(encoding="utf-8"))
        patterns = new_regexps.get("new_patterns") or new_regexps.get("original_patterns")
    else:
        patterns_file = dir_path / "patterns.json"
        if not patterns_file.exists():
            logger.debug(f"No patterns file found in {dir_path}")
        else:
            patterns = json.load(patterns_file.open(encoding="utf-8"))
    if patterns:
        try:
            item_pattern = re.compile(patterns["item"])
        except Exception as e:
            logger.debug(f"Error while compiling item pattern: {e}")

    # endregion

    # region Load Items

    item_html_texts = []
    html_names = []

    if item_pattern:
        for fp in dir_path.glob("*.html"):
            html_text = fp.read_text(encoding="utf-8")
            data = extract(html_text, output_format="json")
            data = json.loads(data)
            if not data["source"]:
                continue
            partial_url = "/" + data["source"].split("://", 1)[-1].split("/", 1)[-1]
            if item_pattern.match(partial_url):
                item_html_texts.append(html_text)
                html_names.append(fp.stem)

    if len(item_html_texts) == 0:
        logger.debug(f"No items found in {dir_path} with proper regexp approach")
        item_html_texts = [fp.read_text(encoding="utf-8") for fp in dir_path.glob("*.html")]
        html_names = [fp.stem for fp in dir_path.glob("*.html")]

    # endregion

    # region Choose The Tag

    unique_content, common_texts = extract_unique_content(item_html_texts)

    candidates_with_votes = defaultdict(float)
    for i, page_content in unique_content.items():
        to_add = get_description_selector(item_html_texts[i], page_content)
        for v in to_add:
            candidates_with_votes[v] += 1 / len(to_add)

    # winner_candidates = Counter(sum(candidates_per_page, []))
    # if not winner_candidates:
    #     logger.debug(f"No winners for {dir_path}")
    #     return

    max_value = max(candidates_with_votes.values())
    winner_selector = [k for k, v in candidates_with_votes.items() if v == max_value]
    best_selector = choose_best_selector(winner_selector)
    to_dump = {
        "best_css_selector": best_selector,
        "common_texts": common_texts,
        "css_selector_candidates": winner_selector,
    }
    with open(dir_path / "description_selector.json", "w", encoding="utf-8") as f:
        json.dump(to_dump, f)
    logger.success(f"Winner for {dir_path}: {winner_selector} with {max_value} votes")
    logger.debug(f"Best selector: {best_selector}")

    # endregion

    # region Try Parsing From Scratch

    parsed_result_raw = {}
    for i, html_text in enumerate(item_html_texts):
        soup = BeautifulSoup(html_text, "html5lib")
        tag = soup.select_one(best_selector)
        if tag:
            parsed_result_raw[html_names[i]] = trim_extra_whitespace(tag.get_text(strip=False))
        else:
            parsed_result_raw[html_names[i]] = "No tag found"

    parsed_result_stripped = {}
    for i, v in unique_content.items():
        matching_texts = [c["text"] for c in v if best_selector == c["css_selector"]]
        parsed_result_stripped[html_names[i]] = matching_texts

    parsed_result = {"raw": parsed_result_raw, "stripped": parsed_result_stripped, "version": "2024-04-15-0"}

    with open(dir_path / "parsed_descriptions.json", "w", encoding="utf-8") as f:
        json.dump(parsed_result, f, indent=2)

    # endregion

    return winner_selector


def choose_best_selector(winner_selector):
    if len(winner_selector) == 1:
        return winner_selector[0]

    candidates = deepcopy(winner_selector)
    if any(["description" in c.lower() for c in candidates]):
        candidates = [c for c in winner_selector if "description" in c.lower()]
        if len(candidates) == 1:
            return candidates[0]

    if any(["desc" in c.lower() for c in candidates]):
        candidates = [c for c in winner_selector if "desc" in c.lower()]
        if len(candidates) == 1:
            return candidates[0]

    if any(["product" in c.lower() for c in candidates]):
        candidates = [c for c in winner_selector if "product" in c.lower()]
        if len(candidates) == 1:
            return candidates[0]

    return sorted(candidates, key=lambda x: len(x), reverse=True)[0]  # Lol but not sure how


def get_description_selector(html_text, page_unique_content):
    # - look if the meta "description" exists
    #
    # - choose out ~unique texts
    # - choose from them:
    # - if the text is prefixed with the meta tag
    # - if the "description" is in the css tag
    # - take longest if all fails

    meta_description = None
    soup = BeautifulSoup(html_text, "html5lib")
    meta_tags = soup.find_all("meta", attrs={"name": "description"})
    if meta_tags:
        if len(meta_tags) > 1:
            logger.warning(f"Multiple meta descriptions found: {meta_tags}")
        meta_description = meta_tags[0]["content"]
        meta_description = normalize_string(meta_description)

    selector_candidates = []

    # - if the text is prefixed with the meta tag
    if meta_description:
        selector_candidates.extend(
            [c["css_selector"] for c in page_unique_content if meta_description[:100] in normalize_string(c["text"])]
        )
    if selector_candidates:
        return list(set(selector_candidates))

    # - if the "description" is in the css tag
    selector_candidates.extend(
        [c["css_selector"] for c in page_unique_content if "description" in c["css_selector"].lower()]
    )
    if selector_candidates:
        return list(set(selector_candidates))

    selector_candidates.extend([c["css_selector"] for c in page_unique_content if "desc" in c["css_selector"].lower()])
    if selector_candidates:
        return list(set(selector_candidates))

    # - take longest if all fails
    tags_by_length = {len(c["text"]): c["css_selector"] for c in page_unique_content}
    if tags_by_length:
        return tags_by_length[max(tags_by_length.keys())]

    return []


def determine_tag_location(tag):
    # Helper function to create a CSS selector for a given tag
    def generate_css_selector(tag):
        selector = tag.name
        if tag.attrs:
            if "id" in tag.attrs:
                selector += f"#{tag['id']}"
            elif "class" in tag.attrs:
                # Join all classes into one selector
                classes = ".".join(tag["class"])
                selector += f".{classes}"
        return selector

    # Helper function to create an XPath for a given tag
    def generate_xpath(tag):
        path = []
        current = tag
        while current.parent and isinstance(current.parent, Tag):
            siblings = [t for t in current.parent.children if isinstance(t, Tag) and t.name == current.name]
            count = 1 + siblings.index(current)
            path.append(f"{current.name}[{count}]")
            current = current.parent
        return "/" + "/".join(reversed(path))

    result = {
        "css_selector": generate_css_selector(tag),
        "xpath": generate_xpath(tag),
    }
    return result


def is_text_content_allowed(s):
    if s.endswith("..."):
        return False
    if "...\n" in s:
        return False
    if len(s) < 10:
        return False
    if s.count("{") > 5:
        return False
    return True


def extract_unique_content(html_pages, threshold_ratio=0.7):
    """
    Given a list of html pages, finds which texts are common (like navigation, footer, cookies disclaimers, etc.)
    Returns a dictionary with unique texts per page and a list of common texts.
    The common texts can then be reused for the rest of the site.

    :param html_pages:
    :param threshold_ratio:
    :return:
    """
    texts_per_page = []

    for html in html_pages:
        soup = BeautifulSoup(html, "html5lib")

        page_texts = []
        for tag in soup.find_all(TARGET_TAGS):
            text_content = trim_extra_whitespace(tag.get_text(strip=False))
            page_texts.append(text_content)

        page_texts = list(set(page_texts))
        texts_per_page.append(page_texts)

    all_texts = sum(texts_per_page, [])
    all_texts_counter = Counter(all_texts)

    threshold = int(threshold_ratio * len(html_pages))

    common_texts = [k for k, v in all_texts_counter.items() if v >= threshold]  # A list of strings

    unique_texts_per_page = {}

    for i, html in enumerate(html_pages):
        unique_texts_per_page[i] = extract_unique_content_from_page(html, common_texts)

    return unique_texts_per_page, common_texts


def extract_unique_content_from_page(page_html, common_texts):
    result = []
    soup = BeautifulSoup(page_html, "html5lib")

    for tag in soup.find_all(TARGET_TAGS):
        text_content = trim_extra_whitespace(tag.get_text(strip=False))
        if text_content in common_texts:
            continue
        if not is_text_content_allowed(text_content):
            continue
        data = determine_tag_location(tag)
        data["text"] = text_content
        result.append(data)

    return result


def normalize_string(s):
    # Unescape HTML entities
    s = html.unescape(s)
    # Replace all whitespace sequences with a single space
    s = re.sub(r"\s+", " ", s)
    # Trim spaces at the beginning and the end
    s = s.strip()
    return s.lower()  # Convert to lower case for case-insensitive comparison


def process_dir_wrapper(dir_path):
    try:
        return process_dir(dir_path)
    except Exception as e:
        logger.exception(f"Error in {dir_path}: {e}")


if __name__ == "__main__":
    data_dir = Path(r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\notebooks\root_pages")

    with ThreadPoolExecutor() as pool:
        list(tqdm(pool.map(process_dir_wrapper, data_dir.glob("*")), total=len(list(data_dir.glob("*")))))

    # for dir_path in tqdm(data_dir.glob("*")):
    #     try:
    #         process_dir(dir_path)
    #     except Exception as e:
    #         logger.exception(f"Error in {dir_path}: {e}")

    # data_dir = Path(
    #     r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\notebooks\root_pages\lavishfurnitureoutlet.com"
    # )
    # process_dir(data_dir)
