"""
sites.casa — Adapter for Casa.it

URL pattern: /{operation}/residenziale/{city}/?prezzo_min=X&prezzo_max=Y&...
"""

from .base import (
    DetailSelectors,
    SearchSelectors,
    SelectorGroup,
    SiteAdapter,
    SiteConfig,
)

CONFIG = SiteConfig(
    site_id="casa",
    display_name="Casa.it",
    base_url="https://www.casa.it",
    domain_pattern=r"casa\.it",
    # ---- URL structure ----
    search_path_template="/{operation}/residenziale/{city}/",
    query_param_map={
        "min_price": "prezzo_min",
        "max_price": "prezzo_max",
        "min_sqm": "superficie_min",
        "max_sqm": "superficie_max",
        "min_rooms": "num_locali_min",
        "max_rooms": "num_locali_max",
    },
    page_param="page",
    search_wait_selector="article",
    detail_wait_selector="h1",
    # ---- property type mapping ----
    # Casa.it uses "residenziale" in the path and doesn't differentiate
    # subtypes the same way in the URL — the template already has it.
    property_type_map={
        "case": "residenziale",
        "appartamenti": "residenziale",
        "attici": "residenziale",
        "ville": "residenziale",
        "villette": "residenziale",
    },
    operation_map={
        "affitto": "affitto",
        "vendita": "vendita",
    },
    # ---- search result selectors ----
    search_selectors=SearchSelectors(
        listing_card=SelectorGroup([
            "article[class*='listing']",
            "div[class*='listingCard']",
            "[data-testid*='listing']",
            "[class*='srp-listing']",
        ]),
        title=SelectorGroup([
            "a[class*='title']",
            "h2 a",
            "a[href*='/dettaglio/']",
            "a[href]",
        ]),
        price=SelectorGroup([
            "[class*='price']",
            "[class*='Price']",
            "span[class*='prezzo']",
        ]),
        features=SelectorGroup([
            "[class*='feature']",
            "[class*='spec']",
            "li[class*='info']",
        ]),
        address=SelectorGroup([
            "[class*='address']",
            "[class*='location']",
            "[class*='zona']",
        ]),
        thumbnail=SelectorGroup([
            "img[data-src]",
            "img[src]",
            "img",
        ]),
        description=SelectorGroup([
            "[class*='description']",
            "[class*='excerpt']",
        ]),
    ),
    # ---- detail page selectors ----
    detail_selectors=DetailSelectors(
        title=SelectorGroup([
            "h1[class*='title']",
            "h1",
        ]),
        price=SelectorGroup([
            "[class*='price']",
            "[class*='Price']",
        ]),
        description=SelectorGroup([
            "[class*='description']",
            "[class*='Description']",
        ]),
        features_keys=SelectorGroup([
            "[class*='feature'] dt",
            "dl dt",
            "[class*='detail'] [class*='label']",
        ]),
        features_values=SelectorGroup([
            "[class*='feature'] dd",
            "dl dd",
            "[class*='detail'] [class*='value']",
        ]),
        address=SelectorGroup([
            "[class*='address']",
            "[class*='location']",
        ]),
        photos=SelectorGroup([
            "[class*='gallery'] img",
            "[class*='carousel'] img",
            "img[class*='photo']",
        ]),
        energy_class=SelectorGroup([
            "[class*='energy']",
            "[class*='energetica']",
        ]),
        agency=SelectorGroup([
            "[class*='agency']",
            "[class*='advertiser']",
        ]),
        costs_keys=SelectorGroup([
            "[class*='cost'] dt",
        ]),
        costs_values=SelectorGroup([
            "[class*='cost'] dd",
        ]),
    ),
)


class CasaAdapter(SiteAdapter):
    """Casa.it — Italy's oldest real estate portal (since 1996).

    Uses the default config-driven parsing. The URL structure uses
    "residenziale" as a fixed category in the path rather than property
    subtypes, so the property_type_map collapses all types to that.
    """

    def __init__(self):
        super().__init__(CONFIG)
