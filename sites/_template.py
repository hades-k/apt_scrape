"""
sites._template — Copy this file to create a new site adapter.

Steps:
  1. cp sites/_template.py sites/your_site.py
  2. Fill in CONFIG with the site's URL structure and CSS selectors
  3. Register in sites/__init__.py:  from .your_site import YourSiteAdapter
     and add  YourSiteAdapter()  to the ADAPTERS list
  4. (Optional) Override parse_search / parse_detail if the default
     config-driven logic doesn't work for the site's HTML structure

Finding selectors:
  - Run:  python cli.py dump --url "https://yoursite.com/search?..." -o dump.html
  - Open dump.html in a browser, inspect the listing cards
  - Note the selectors for each field, add 2-3 fallbacks per group
"""

from .base import (
    DetailSelectors,
    SearchSelectors,
    SelectorGroup,
    SiteAdapter,
    SiteConfig,
)

CONFIG = SiteConfig(
    # ---- Identity ----
    site_id="yoursite",  # short slug, used as --source value
    display_name="YourSite.it",  # human-readable, appears in output
    base_url="https://www.yoursite.it",
    domain_pattern=r"yoursite\.it",  # regex for URL matching

    # ---- Search URL structure ----
    # Available placeholders: {operation}, {property_type}, {city}
    search_path_template="/{operation}-{property_type}/{city}/",

    # Map normalized filter names → this site's query param names.
    # Only include params the site actually supports.
    query_param_map={
        "min_price": "prezzoMinimo",      # e.g. ?prezzoMinimo=500
        "max_price": "prezzoMassimo",
        "min_sqm": "superficieMinima",
        "max_sqm": "superficieMassima",
        "min_rooms": "localiMinimo",
        "max_rooms": "localiMassimo",
        "published_within": "giorniPubblicazione",
    },

    page_param="pag",  # e.g. ?pag=2

    # Selector to wait for on page load (Camoufox waits for this before parsing)
    search_wait_selector="li.listing-item",
    detail_wait_selector="h1",

    # ---- Property type / operation slug mapping ----
    # normalized name → site-specific slug used in URL
    property_type_map={
        "case": "case",
        "appartamenti": "appartamenti",
        "ville": "ville",
        # add more as needed...
    },
    operation_map={
        "affitto": "affitto",
        "vendita": "vendita",
    },

    # ---- Search page selectors ----
    # Each SelectorGroup is a list of CSS selectors tried in order.
    # First match wins. Add 2-3 fallbacks per field.
    search_selectors=SearchSelectors(
        listing_card=SelectorGroup([
            "li.listing-item",
            "div[class*='listing']",
            "article[class*='result']",
        ]),
        title=SelectorGroup([
            "a[class*='title']",
            "h2 a",
            "a[href*='/annunci/']",
        ]),
        price=SelectorGroup([
            "[class*='price']",
            "span[class*='prezzo']",
        ]),
        features=SelectorGroup([
            "li[class*='feature']",
            "span[class*='info']",
        ]),
        address=SelectorGroup([
            "[class*='address']",
            "[class*='location']",
        ]),
        thumbnail=SelectorGroup([
            "img[data-src]",
            "img",
        ]),
        description=SelectorGroup([
            "[class*='description']",
            "p[class*='excerpt']",
        ]),
    ),

    # ---- Detail page selectors ----
    detail_selectors=DetailSelectors(
        title=SelectorGroup(["h1"]),
        price=SelectorGroup(["[class*='price']"]),
        description=SelectorGroup(["[class*='description']"]),
        features_keys=SelectorGroup(["dl dt", "[class*='feature'] [class*='label']"]),
        features_values=SelectorGroup(["dl dd", "[class*='feature'] [class*='value']"]),
        address=SelectorGroup(["[class*='address']"]),
        photos=SelectorGroup(["[class*='gallery'] img", "img[data-src]"]),
        energy_class=SelectorGroup(["[class*='energy']"]),
        agency=SelectorGroup(["[class*='agency']"]),
        costs_keys=SelectorGroup(["[class*='cost'] dt"]),
        costs_values=SelectorGroup(["[class*='cost'] dd"]),
    ),
)


class YourSiteAdapter(SiteAdapter):
    """Your site description.

    Uses config-driven parsing by default. Override methods below if the
    site needs custom logic beyond what selectors can express.

    Common reasons to override:
    - Site uses JSON-LD or <script> tags for data instead of visible HTML
    - URL structure has non-standard encoding or path nesting
    - Pagination uses infinite scroll instead of page params
    - Features are in a single string that needs regex splitting
    """

    def __init__(self):
        super().__init__(CONFIG)

    # Uncomment and customize if needed:
    #
    # def build_search_url(self, filters: SearchFilters) -> str:
    #     \"\"\"Override for non-standard URL building.\"\"\"
    #     ...
    #
    # def parse_search(self, html: str) -> list[ListingSummary]:
    #     \"\"\"Override for custom search result parsing.\"\"\"
    #     ...
    #
    # def parse_detail(self, html: str, url: str) -> ListingDetail:
    #     \"\"\"Override for custom detail page parsing.\"\"\"
    #     ...
