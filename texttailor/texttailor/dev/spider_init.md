### Kludge process, to be refactored and refined

1. Landing pages are scraped speedy.py 
   - speedy.py
2. A small subset of category and product pages are scraped, regexps for category and product pages are made in the process
   - get_data_for_spider.py
   - manually_parse_sites.py
3. Description tags are found and extracted from the product pages, common texts are made in the process
   - find_description_tag.py
4. Regexps are rechecked (and refined?)
   - speedy_regexps.py
   - get_regexps_for_pages.py
5. The spider is run on the full set of category and product pages. It's created with:
    - root url
    - regexps for category and product pages
      - if not, scrape all?
    - regexp for contact pages
      - same for all
    - tags for description, and common texts to extract only the unique content
   
    It is only created if "common_texts" key is not empty in `description_selector.json`
6. The spider is run to collect 50? product items
    - not sure why I want so many, but I want them
    - is saves raw html and what it managed to extract from the page

### Next steps
- Contacts parsing
- Store stuff in mongo
- Write the final prompts for the actual text rewriting