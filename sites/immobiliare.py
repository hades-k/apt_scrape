"""
sites.immobiliare — Adapter for Immobiliare.it

URL pattern: /{operation}-{property_type}/{city}/?prezzoMinimo=X&prezzoMassimo=Y&...
Detail URL:  /annunci/{id}/
"""

from .base import (
    DetailSelectors,
    ListingSummary,
    SearchFilters,
    SearchSelectors,
    SelectorGroup,
    SiteAdapter,
    SiteConfig,
    Tag,
    classify_feature,
    extract_attr,
    extract_text,
)

CONFIG = SiteConfig(
    site_id="immobiliare",
    display_name="Immobiliare.it",
    base_url="https://www.immobiliare.it",
    domain_pattern=r"immobiliare\.it",
    # ---- URL structure ----
    search_path_template="/{operation}-{property_type}/{city}/",
    query_param_map={
        "min_price": "prezzoMinimo",
        "max_price": "prezzoMassimo",
        "min_sqm": "superficieMinima",
        "max_sqm": "superficieMassima",
        "min_rooms": "localiMinimo",
        "max_rooms": "localiMassimo",
        "published_within": "giorniPubblicazione",
        "sort": "ordine",
    },
    page_param="pag",
    search_wait_selector="li.nd-list__item",
    detail_wait_selector="h1",
    # ---- property type mapping (normalized → immobiliare slug) ----
    property_type_map={
        "case": "case",
        "appartamenti": "appartamenti",
        "attici": "attici",
        "case-indipendenti": "case-indipendenti",
        "loft": "loft",
        "rustici": "rustici",
        "ville": "ville",
        "villette": "villette",
    },
    operation_map={
        "affitto": "affitto",
        "vendita": "vendita",
    },
    # ---- search result selectors (fallback chains) ----
    search_selectors=SearchSelectors(
        listing_card=SelectorGroup([
            "li.nd-list__item.ListItem_item__sugJm.ListItem_item__card__8WHcE",
            "li.nd-list__item.ListItem_item__card__8WHcE",
            "li.nd-list__item.in-realEstateResults__item",
            "[class*='RealEstateResults'] li",
            "div.in-realEstateResults__item",
            "ul.in-realEstateResults li",
        ]),
        title=SelectorGroup([
            "a.Title_title__kPgMu",
            "a.in-card__title",
            "a[class*='title']",
            "a[href*='/annunci/']",
        ]),
        price=SelectorGroup([
            "div.Price_price__kHY5L span",
            "li.in-feat__item--main",
            "div[class*='price']",
            "[class*='Price']",
        ]),
        features=SelectorGroup([
            "div.FeatureList_item__D3KYH",
            "li.in-feat__item",
            "span[class*='feature']",
            "[class*='feat']",
        ]),
        address=SelectorGroup([
            "span[class*='address']",
            "[class*='Address']",
            "p[class*='location']",
        ]),
        thumbnail=SelectorGroup([
            "img[src*='pwm.im.it']",
            "img[data-src*='pwm.im.it']",
            "img",
        ]),
        description=SelectorGroup([
            "p.in-card__description",
            "[class*='description']",
        ]),
    ),
    # ---- detail page selectors ----
    detail_selectors=DetailSelectors(
        title=SelectorGroup([
            "h1.re-title__title",
            "h1[class*='title']",
            "h1",
        ]),
        price=SelectorGroup([
            "div.re-overview__price",
            "p[data-testid='listing-price-primary']",
            "[class*='price']",
            "[class*='Price']",
        ]),
        description=SelectorGroup([
            "div.ReadAll_readAll__nryPL",
            "div[class*='ReadAll_readAll']",
            "div[id='description'] + *",
            "div.in-readAll",
            "div[class*='description']",
            "div[class*='Description']",
        ]),
        features_keys=SelectorGroup([
            "dl.FeaturesGrid_list__qtXl5 dt",
            "dl[class*='FeaturesGrid'] dt",
            "dt[class*='Item_title']",
            "dl.re-features__list dt",
            "div[class*='features'] dt",
            "[class*='feature'] [class*='label']",
        ]),
        features_values=SelectorGroup([
            "dl.FeaturesGrid_list__qtXl5 dd",
            "dl[class*='FeaturesGrid'] dd",
            "dd[class*='Item_description']",
            "dl.re-features__list dd",
            "div[class*='features'] dd",
            "[class*='feature'] [class*='value']",
        ]),
        address=SelectorGroup([
            "span.re-title__location",
            "[class*='address']",
            "[class*='Address']",
            "span[class*='location']",
        ]),
        photos=SelectorGroup([
            "button[aria-label*='foto'] img",
            "div[class*='ListingPhotos'] img",
            "img[src*='pwm.im.it']",
            "img[data-src*='pwm.im.it']",
            "[class*='gallery'] img",
            "[class*='slider'] img",
            "[class*='carousel'] img",
        ]),
        energy_class=SelectorGroup([
            "[class*='energy']",
            "[class*='Energy']",
            "[class*='energetica']",
        ]),
        agency=SelectorGroup([
            "[class*='agency']",
            "[class*='Agency']",
            "[class*='advertiser']",
        ]),
        costs_keys=SelectorGroup([
            "div.SectionTitle_container__9bW_7 + dl dt",
            "[class*='cost'] dt",
            "[class*='costs'] dt",
        ]),
        costs_values=SelectorGroup([
            "div.SectionTitle_container__9bW_7 + dl dd",
            "[class*='cost'] dd",
            "[class*='costs'] dd",
        ]),
    ),
)


class ImmobiliareAdapter(SiteAdapter):
    """Immobiliare.it — Italy's #1 real estate portal.

    Uses the default config-driven parsing. Override methods here only
    if Immobiliare needs site-specific logic beyond selector changes.
    """

    def __init__(self):
        super().__init__(CONFIG)

    def build_search_url(self, filters: SearchFilters) -> str:
        """Build Immobiliare URL with site-specific sort handling.

        Immobiliare uses `criterio=data&ordine=desc` for newest listings,
        not `ordine=piu-recenti`.
        """
        from urllib.parse import urlencode

        op = self.config.operation_map.get(filters.operation, filters.operation)
        pt = self.config.property_type_map.get(filters.property_type, filters.property_type)

        location = filters.city
        if filters.area:
            location = f"{location}/{filters.area.strip('/')}"

        path = self.config.search_path_template.format(
            operation=op,
            property_type=pt,
            city=location,
        )

        qmap = self.config.query_param_map
        query = {}

        if filters.min_price is not None and "min_price" in qmap:
            query[qmap["min_price"]] = filters.min_price
        if filters.max_price is not None and "max_price" in qmap:
            query[qmap["max_price"]] = filters.max_price
        if filters.min_sqm is not None and "min_sqm" in qmap:
            query[qmap["min_sqm"]] = filters.min_sqm
        if filters.max_sqm is not None and "max_sqm" in qmap:
            query[qmap["max_sqm"]] = filters.max_sqm
        if filters.min_rooms is not None and "min_rooms" in qmap:
            query[qmap["min_rooms"]] = filters.min_rooms
        if filters.max_rooms is not None and "max_rooms" in qmap:
            query[qmap["max_rooms"]] = filters.max_rooms
        if filters.published_within and "published_within" in qmap:
            query[qmap["published_within"]] = filters.published_within

        sort_value = (filters.sort or "").strip().lower()
        if sort_value in {"piu-recenti", "recenti", "data", "newest", "latest"}:
            query["criterio"] = "data"
            query["ordine"] = "desc"
        elif sort_value and sort_value != "rilevanza" and "sort" in qmap:
            query[qmap["sort"]] = filters.sort

        if filters.page >= 1:
            query[self.config.page_param] = filters.page

        url = self.config.base_url + path
        if query:
            url += "?" + urlencode(query)
        return url

    def _parse_one_card(self, card: Tag, sels: SearchSelectors) -> ListingSummary:
        """Parse a single listing card, handling aria-label for features."""
        from urllib.parse import urljoin

        title_el = sels.title.find(card)
        title = extract_text(title_el)

        # URL — try href from the title link, or from any link in the card
        href = extract_attr(title_el, "href")
        if not href:
            any_link = card.select_one("a[href]")
            href = extract_attr(any_link, "href")
        if href and not href.startswith("http"):
            href = urljoin(self.config.base_url, href)

        price = extract_text(sels.price.find(card))

        # For Immobiliare, features are in aria-label
        features_els = sels.features.find_all(card)
        feature_texts = []
        for f in features_els:
            aria = f.get("aria-label", "").strip()
            if aria:
                feature_texts.append(aria)
            else:
                # fallback to text
                txt = extract_text(f)
                if txt:
                    feature_texts.append(txt)

        sqm = ""
        rooms = ""
        bathrooms = ""
        for ft in feature_texts:
            classified = classify_feature(ft)
            if classified:
                name, val = classified
                if name == "sqm" and not sqm:
                    sqm = val
                elif name == "rooms" and not rooms:
                    rooms = val
                elif name == "bathrooms" and not bathrooms:
                    bathrooms = val

        address = extract_text(sels.address.find(card))

        thumbnail = extract_attr(sels.thumbnail.find(card), "src")
        if thumbnail and not thumbnail.startswith("http"):
            thumbnail = urljoin(self.config.base_url, thumbnail)

        description = extract_text(sels.description.find(card))
        post_date = self.extract_post_date_from_search_card(card, feature_texts)

        return ListingSummary(
            source=self.config.display_name,
            title=title,
            url=href or "",
            price=price,
            sqm=sqm,
            rooms=rooms,
            bathrooms=bathrooms,
            address=address,
            thumbnail=thumbnail,
            description_snippet=description,
            post_date=post_date,
            features_raw=feature_texts,
        )
