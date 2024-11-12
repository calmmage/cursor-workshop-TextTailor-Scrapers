# region Description Tags


def extract_significant_text_blocks(html, min_text_length=20, excluded_tags=None):
    if excluded_tags is None:
        excluded_tags = {"script", "style", "header", "footer", "nav", "form"}

    soup = BeautifulSoup(html, "html.parser")
    significant_blocks = defaultdict(list)
    label_to_tags = defaultdict(list)  # New mapping from labels to tags
    visited_texts = set()

    def accumulate_text(tag, accumulated_text=""):
        if isinstance(tag, NavigableString):
            accumulated_text += tag.strip()
            if len(accumulated_text) >= min_text_length:
                return accumulated_text
        elif tag.name not in excluded_tags:
            for content in tag.contents:
                accumulated_text = accumulate_text(content, accumulated_text)
                if len(accumulated_text) >= min_text_length:
                    break
        return accumulated_text

    def process_tag(tag):
        for child in tag.descendants:
            if isinstance(child, NavigableString) and child.parent.name not in excluded_tags:
                full_text = accumulate_text(child)
                if full_text and full_text not in visited_texts:
                    label = generate_human_readable_label(child.parent)
                    significant_blocks[label].append(full_text)
                    label_to_tags[label].append(child.parent)  # Associate label with tag
                    visited_texts.add(full_text)

    for tag in soup.find_all(True):
        if tag.name not in excluded_tags:
            process_tag(tag)

    return significant_blocks, label_to_tags


def generate_human_readable_label(tag):
    """Generate a label with a focus on unique and distinctive attributes."""
    parts = [tag.name]  # Start with the tag name

    # Define a priority list of attributes that are helpful for identifying content
    priority_attributes = ["id", "class", "data-*", "role", "aria-label", "itemprop"]

    # Function to add attributes to the label
    def add_attributes_to_parts(attributes):
        for attr in priority_attributes:
            if attr == "data-*":  # Special handling for data-* attributes
                for key, value in tag.attrs.items():
                    if key.startswith("data-"):
                        parts.append(f'{key}="{value}"')
            elif attr in tag.attrs:
                value = tag[attr] if not isinstance(tag[attr], list) else " ".join(tag[attr])
                parts.append(f'{attr}="{value}"')

    add_attributes_to_parts(tag.attrs)

    return " > ".join(parts)


def postfilter_results(blocks, min_length=100):
    result = {k: v for k, v in blocks.items() if len(" ".join(v)) > min_length}
    return result


def parse_labels_from_llm_output(llm_output, labels):
    lists_names = json.loads(llm_output.content)  # Expect ["List 4", "List 5", "List 6"], starting from 1
    indices = [int(name.split()[-1]) - 1 for name in lists_names]
    return [labels[i] for i in indices]


def find_common_ancestor(tags):
    # Maps each tag to its ancestors
    tag_ancestors = defaultdict(set)
    for tag in tags:
        ancestors = set(tag.parents)
        for ancestor in ancestors:
            tag_ancestors[ancestor].add(tag)

    # Find the common ancestor with the maximum depth that includes all tags
    deepest_common_ancestor = None
    max_depth = -1
    for ancestor, descendants in tag_ancestors.items():
        if len(descendants) == len(tags) and ancestor not in tags:  # Exclude self if it's one of the tags
            depth = len(list(ancestor.parents))
            if depth > max_depth:
                max_depth = depth
                deepest_common_ancestor = ancestor

    return deepest_common_ancestor


def get_description_tags_candidates(html_text):
    significant_text_blocks, labels_to_tags = extract_significant_text_blocks(html_text, min_text_length=100)
    significant_text_blocks = postfilter_results(significant_text_blocks)

    labels = list(significant_text_blocks.keys())
    prompt = get_prompt_for_description_tags(significant_text_blocks)
    res_o_smart = (prompt | smart_llm).invoke({})

    tag_labels = parse_labels_from_llm_output(res_o_smart, labels)
    tags = [labels_to_tags[label] for label in tag_labels]
    tag_parents = [find_common_ancestor(tag) for tag in tags]
    return tag_parents


def get_prompt_for_description_tags(keys_with_blocks):
    role_message = """You will be presented with several lists of text snippets extracted from a website's product listings. Your task is to review these lists and determine which ones are related to describing the product in some way. This may include detailed descriptions of the product, lists of product features, dimensions, or any other information that directly pertains to product specifics. Your goal is to identify and return a JSON with the names of the lists (e.g., ["List 1", "List 2"]) that contain text snippets relevant to product descriptions or features. The challenge lies in distinguishing between general website content (such as contact info, terms and conditions, etc.) and the specific information that describes a product."""

    example_input = """- **List 1:** ['FAQs', 'Warranty Information', 'User Guides']
- **List 2:** ['Ergonomic design', 'Battery life: up to 18 hours', 'Water-resistant up to 50 meters']
- **List 3:** ['Contact Support', 'Download Software', 'Warranty Registration']"""

    example_output = '["List 2"]'

    formatted_list = "\n".join(
        [f"- **List {i+1}:** {value}" for i, (key, value) in enumerate(keys_with_blocks.items())]
    )

    messages = [("system", role_message), ("human", example_input), ("ai", example_output), ("human", formatted_list)]
    messages = [(role, trim_extra_whitespace(message)) for role, message in messages]

    full_prompt = ChatPromptTemplate.from_messages(messages)
    return full_prompt


# endregion