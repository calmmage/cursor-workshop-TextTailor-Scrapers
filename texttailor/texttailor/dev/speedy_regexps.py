from concurrent.futures import ThreadPoolExecutor

from get_regexps_for_pages import *


def process_single_dir(dir_path: Path):
    results_path = dir_path / "regexp_refinement.json"
    if results_path.exists():
        return

    categorized_links = get_links_for_shop_directory(dir_path)
    if not categorized_links:
        return

    counts, base_patterns = check_regexp_match(dir_path, categorized_links)
    original_quality = check_regexp_quality(counts)
    if original_quality["category"] and original_quality["item"]:
        logger.success(f"Quality is already good for {dir_path}")
        to_dump = {
            "original_patterns": base_patterns,
            "original_quality": original_quality,
        }
        with results_path.open("w", encoding="utf-8") as f:
            json.dump(to_dump, f, indent=2, ensure_ascii=False)

        return

    new_patterns = get_new_regexp(categorized_links)
    new_counts, _ = check_regexp_match(dir_path, categorized_links, new_patterns)
    new_quality = check_regexp_quality(new_counts)

    to_dump = {
        "new_patterns": new_patterns,
        "original_patterns": base_patterns,
        "new_quality": new_quality,
        "original_quality": original_quality,
    }
    with results_path.open("w", encoding="utf-8") as f:
        json.dump(to_dump, f, indent=2, ensure_ascii=False)

    if new_quality["category"] and new_quality["item"]:
        logger.success(f"New quality is good for {dir_path.name}")
    else:
        logger.error(f"New quality is bad for {dir_path.name}")


def wrapper_for_process_single_dir(dir_path: Path):
    try:
        return process_single_dir(dir_path)
    except Exception as e:
        logger.exception(f"Error in {dir_path}: {e}")
        return "error", str(dir_path), str(e)


def process_all_dirs():
    root_dir = Path(r"E:\Work\Personal\repos\web_scrapers\spiders\texttailor\texttailor\notebooks\root_pages")
    all_dirs = list(root_dir.iterdir())
    all_dirs = [d for d in all_dirs if d.name != "failed"]
    random.shuffle(all_dirs)

    # for i, d in enumerate(all_dirs):
    #     wrapper_for_process_single_dir(d)
    #     if i > 10:
    #         exit()

    errors = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(tqdm(pool.map(wrapper_for_process_single_dir, all_dirs), total=len(all_dirs)))

    for res in results:
        if isinstance(res, tuple) and res[0] == "error":
            errors.append(res)

    if errors:
        with (root_dir / "errors.json").open("w", encoding="utf-8") as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    process_all_dirs()
