"""
rental_scraper_mcp — MCP server for scraping Italian real estate listings.

Thin server layer: defines MCP tools and delegates to site adapters.
Each site (Immobiliare.it, Casa.it, ...) is a self-contained plugin in sites/.
"""

import asyncio
import csv
import io
import json
import logging
import sys
import time
from enum import Enum
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sites import (
    SearchFilters,
    adapter_for_url,
    get_adapter,
    list_adapter_details,
    list_adapters,
)

# ---------------------------------------------------------------------------
# Logging (stderr only — stdout is MCP stdio)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("rental_scraper_mcp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REQUEST_DELAY_SECONDS = 2.0
DEFAULT_MAX_PAGES = 1
MAX_PAGES_LIMIT = 10

# ---------------------------------------------------------------------------
# Browser Manager (Camoufox)
# ---------------------------------------------------------------------------


class BrowserManager:
    """Manages a Camoufox browser instance for stealth scraping."""

    def __init__(self):
        self._browser = None
        self._camoufox_ctx = None
        self._last_request_time = 0.0

    async def _ensure_browser(self):
        if self._browser is not None:
            return

        logger.info("Starting Camoufox browser...")
        from camoufox.async_api import AsyncCamoufox

        self._camoufox_ctx = AsyncCamoufox(headless=True)
        self._browser = await self._camoufox_ctx.__aenter__()
        logger.info("Camoufox browser started.")

    async def _rate_limit(self):
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            await asyncio.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_time = time.monotonic()

    async def fetch_page(self, url: str, wait_selector: Optional[str] = None) -> str:
        """Fetch a page via stealth browser and return raw HTML."""
        await self._ensure_browser()
        await self._rate_limit()

        page = await self._browser.new_page()
        try:
            logger.info(f"Fetching: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.warning(
                        f"Selector '{wait_selector}' not found, using page as-is"
                    )

            await asyncio.sleep(1.5)
            return await page.content()
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise
        finally:
            await page.close()

    async def close(self):
        if self._browser and self._camoufox_ctx:
            try:
                await self._camoufox_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._browser = None
            logger.info("Browser closed.")


browser = BrowserManager()


# ---------------------------------------------------------------------------
# Tool input models
# ---------------------------------------------------------------------------

# Build source choices dynamically from registered adapters
_site_ids = list_adapters()


class SearchListingsInput(BaseModel):
    """Input for searching rental/sale listings."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    city: str = Field(
        ...,
        description="City slug (e.g. 'milano', 'bologna', 'roma', 'torino')",
        min_length=1,
        max_length=100,
    )
    area: Optional[str] = Field(
        default=None,
        description="Optional area slug inside city (e.g. 'precotto', 'turro')",
        min_length=1,
        max_length=100,
    )
    operation: str = Field(
        default="affitto",
        description="Contract type: 'affitto' (rent) or 'vendita' (sale)",
    )
    property_type: str = Field(
        default="case",
        description=(
            "Property category: case, appartamenti, attici, "
            "case-indipendenti, loft, rustici, ville, villette"
        ),
    )
    min_price: Optional[int] = Field(
        default=None, description="Minimum price in EUR", ge=0
    )
    max_price: Optional[int] = Field(
        default=None, description="Maximum price in EUR", ge=0
    )
    min_sqm: Optional[int] = Field(
        default=None, description="Minimum surface in square meters", ge=0
    )
    max_sqm: Optional[int] = Field(
        default=None, description="Maximum surface in square meters", ge=0
    )
    min_rooms: Optional[int] = Field(
        default=None, description="Minimum number of rooms (locali)", ge=1, le=10
    )
    max_rooms: Optional[int] = Field(
        default=None, description="Maximum number of rooms (locali)", ge=1, le=10
    )
    published_within: Optional[str] = Field(
        default=None,
        description="Recency filter in days: '1' (today), '3', '7', '14', '30'",
        pattern=r"^(1|3|7|14|30)$",
    )
    sort: str = Field(
        default="rilevanza",
        description="Sort order (e.g. 'rilevanza', 'piu-recenti')",
    )
    source: str = Field(
        default=_site_ids[0] if _site_ids else "immobiliare",
        description=f"Site to scrape: {', '.join(_site_ids)}",
    )
    max_pages: int = Field(
        default=DEFAULT_MAX_PAGES,
        description="Number of result pages to scrape (1-10)",
        ge=1,
        le=MAX_PAGES_LIMIT,
    )
    start_page: int = Field(
        default=1,
        description="First result page to scrape (1-based)",
        ge=1,
        le=MAX_PAGES_LIMIT,
    )
    end_page: Optional[int] = Field(
        default=None,
        description=(
            "Last result page to scrape (inclusive, 1-10). "
            "If provided, it overrides max_pages."
        ),
        ge=1,
        le=MAX_PAGES_LIMIT,
    )
    include_details: bool = Field(
        default=False,
        description=(
            "If true, fetch each listing URL and enrich output with full detail "
            "fields (description, features, costs, etc.)"
        ),
    )
    detail_limit: Optional[int] = Field(
        default=None,
        description=(
            "Maximum number of listing detail pages to fetch when "
            "include_details=true. Default: all listings."
        ),
        ge=1,
    )
    include_csv: bool = Field(
        default=False,
        description="If true, include CSV export in response under 'csv'",
    )
    include_table: bool = Field(
        default=False,
        description="If true, include markdown table export in response under 'table'",
    )
    table_max_rows: int = Field(
        default=20,
        description="Maximum number of rows in markdown table preview",
        ge=1,
        le=200,
    )

    @field_validator("city")
    @classmethod
    def normalize_city(cls, v: str) -> str:
        return v.lower().strip().replace(" ", "-")

    @field_validator("area")
    @classmethod
    def normalize_area(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.lower().strip().replace(" ", "-")

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        available = list_adapters()
        if v not in available:
            raise ValueError(
                f"Unknown source '{v}'. Available: {', '.join(available)}"
            )
        return v


class GetListingDetailInput(BaseModel):
    """Input for fetching full details of a single listing."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    url: str = Field(
        ...,
        description="Full URL of the listing page (from search results)",
        min_length=10,
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith("http"):
            raise ValueError("URL must start with http:// or https://")
        return v


class DumpPageInput(BaseModel):
    """Input for dumping raw HTML of a page (for debugging selectors)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    url: str = Field(..., description="URL to fetch and dump", min_length=10)
    wait_selector: Optional[str] = Field(
        default=None,
        description="CSS selector to wait for before capturing HTML",
    )


# ---------------------------------------------------------------------------
# MCP Server & Tools
# ---------------------------------------------------------------------------

mcp = FastMCP("rental_scraper_mcp")


@mcp.tool(
    name="rental_search_listings",
    annotations={
        "title": "Search Real Estate Listings",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def search_listings(params: SearchListingsInput) -> str:
    """Search for rental or sale property listings.

    Builds a search URL with the provided filters, fetches result pages using
    a stealth browser (Camoufox), and parses listing cards into structured JSON.

    Supported sites (add more via sites/ plugins): immobiliare, casa.

    Args:
        params (SearchListingsInput): Search filters including city, operation,
            property_type, price range, sqm range, rooms, published_within,
            source (site plugin id), and max_pages.

    Returns:
        str: JSON with 'count', 'source', 'search_url', 'listings' array.
             Each listing: title, price, sqm, rooms, bathrooms, address, url,
             thumbnail, description_snippet, features_raw, source.
    """
    adapter = get_adapter(params.source)
    all_listings: list[dict[str, Any]] = []
    pages_scraped = 0

    if params.end_page is not None:
        start_page = params.start_page
        end_page = params.end_page
    else:
        start_page = params.start_page
        end_page = params.start_page + params.max_pages - 1

    if end_page > MAX_PAGES_LIMIT:
        return _json(
            {
                "error": (
                    f"Requested end_page={end_page} exceeds MAX_PAGES_LIMIT="
                    f"{MAX_PAGES_LIMIT}"
                )
            }
        )

    if end_page < start_page:
        return _json(
            {
                "error": "Invalid page range: end_page must be >= start_page",
                "start_page": start_page,
                "end_page": end_page,
            }
        )

    for page_num in range(start_page, end_page + 1):
        filters = SearchFilters(
            city=params.city,
            area=params.area,
            operation=params.operation,
            property_type=params.property_type,
            min_price=params.min_price,
            max_price=params.max_price,
            min_sqm=params.min_sqm,
            max_sqm=params.max_sqm,
            min_rooms=params.min_rooms,
            max_rooms=params.max_rooms,
            published_within=params.published_within,
            sort=params.sort,
            page=page_num,
        )
        url = adapter.build_search_url(filters)

        try:
            html = await browser.fetch_page(
                url, wait_selector=adapter.config.search_wait_selector
            )
        except Exception as e:
            return _json(
                {"error": f"Failed to fetch page {page_num}: {e}", "url": url}
            )

        page_listings = adapter.parse_search(html)
        pages_scraped = page_num

        if not page_listings:
            logger.info(f"No more listings on page {page_num}, stopping.")
            break

        all_listings.extend([ls.to_dict() for ls in page_listings])
        logger.info(f"Page {page_num}: {len(page_listings)} listings")

    # Reference URL for page 1
    ref = SearchFilters(
        city=params.city,
        area=params.area,
        operation=params.operation,
        property_type=params.property_type,
        min_price=params.min_price,
        max_price=params.max_price,
        min_sqm=params.min_sqm,
        max_sqm=params.max_sqm,
        min_rooms=params.min_rooms,
        max_rooms=params.max_rooms,
        published_within=params.published_within,
        sort=params.sort,
        page=start_page,
    )

    detail_enriched = 0
    detail_errors: list[dict[str, str]] = []
    post_date_enriched = 0
    post_date_errors: list[dict[str, str]] = []

    if params.include_details and all_listings:
        to_enrich = all_listings
        if params.detail_limit is not None:
            to_enrich = all_listings[: params.detail_limit]

        for listing in to_enrich:
            listing_url = str(listing.get("url", "")).strip()
            if not listing_url:
                continue

            listing_adapter = adapter_for_url(listing_url) or adapter
            try:
                detail_html = await browser.fetch_page(
                    listing_url,
                    wait_selector=listing_adapter.config.detail_wait_selector,
                )
                detail = listing_adapter.parse_detail(detail_html, listing_url).to_dict()
                listing["detail"] = detail
                listing["post_date"] = detail.get("post_date", "") or listing.get("post_date", "")

                # Convenience flattened fields for simpler downstream filtering.
                listing["detail_description"] = detail.get("description", "")
                listing["detail_address"] = detail.get("address", "")
                listing["detail_features"] = detail.get("features", {})
                listing["detail_costs"] = detail.get("costs", {})
                listing["detail_energy_class"] = detail.get("energy_class", "")
                listing["detail_agency"] = detail.get("agency", "")
                detail_enriched += 1
            except Exception as e:
                detail_errors.append({"url": listing_url, "error": str(e)})

    # post_date is extracted by default for all searches.
    for listing in all_listings:
        if str(listing.get("post_date", "")).strip():
            continue

        listing_url = str(listing.get("url", "")).strip()
        if not listing_url:
            continue

        listing_adapter = adapter_for_url(listing_url) or adapter
        try:
            detail_html = await browser.fetch_page(
                listing_url,
                wait_selector=listing_adapter.config.detail_wait_selector,
            )
            post_date = listing_adapter.extract_post_date_from_detail_html(detail_html)
            listing["post_date"] = post_date
            if post_date:
                post_date_enriched += 1
        except Exception as e:
            post_date_errors.append({"url": listing_url, "error": str(e)})

    csv_output = _listings_to_csv(all_listings) if params.include_csv else ""
    table_output = (
        _listings_to_markdown_table(all_listings, params.table_max_rows)
        if params.include_table
        else ""
    )

    return _json(
        {
            "count": len(all_listings),
            "source": adapter.config.display_name,
            "search_url": adapter.build_search_url(ref),
            "city": params.city,
            "area": params.area,
            "pages_scraped": pages_scraped,
            "start_page": start_page,
            "end_page": end_page,
            "details_requested": params.include_details,
            "details_enriched": detail_enriched,
            "detail_errors": detail_errors,
            "post_date_enriched": post_date_enriched,
            "post_date_errors": post_date_errors,
            "csv": csv_output,
            "table": table_output,
            "listings": all_listings,
        }
    )


@mcp.tool(
    name="rental_get_listing_detail",
    annotations={
        "title": "Get Full Listing Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_listing_detail(params: GetListingDetailInput) -> str:
    """Fetch full details of a single property listing.

    Auto-detects the site from the URL and uses the matching adapter.
    Extracts: title, price, full description, features, photos, energy class,
    agency info, costs, and address.

    Args:
        params (GetListingDetailInput): Contains url (str) — full listing URL.

    Returns:
        str: JSON with title, price, description, features, photos, etc.
    """
    url = params.url
    adapter = adapter_for_url(url)

    if adapter is None:
        available = list_adapter_details()
        return _json(
            {"error": f"No adapter found for URL: {url}", "supported_sites": available}
        )

    try:
        html = await browser.fetch_page(
            url, wait_selector=adapter.config.detail_wait_selector
        )
    except Exception as e:
        return _json({"error": f"Failed to fetch listing: {e}", "url": url})

    detail = adapter.parse_detail(html, url)
    return _json(detail.to_dict())


@mcp.tool(
    name="rental_list_sites",
    annotations={
        "title": "List Supported Real Estate Sites",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_sites() -> str:
    """List all registered real estate site adapters.

    Returns site IDs (for the 'source' parameter), display names, and base URLs.

    Returns:
        str: JSON array of {site_id, display_name, base_url} objects.
    """
    return _json(list_adapter_details())


@mcp.tool(
    name="rental_dump_page",
    annotations={
        "title": "Dump Raw HTML of a Page (Debug)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def dump_page(params: DumpPageInput) -> str:
    """Fetch a page and return the raw HTML for debugging selectors.

    Use this to inspect a site's HTML structure when building or fixing
    a site adapter. The HTML is captured after JS rendering via Camoufox.

    Args:
        params (DumpPageInput): url and optional wait_selector.

    Returns:
        str: Raw HTML string (not JSON).
    """
    try:
        return await browser.fetch_page(params.url, wait_selector=params.wait_selector)
    except Exception as e:
        return _json({"error": str(e), "url": params.url})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape_md(text: Any) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def _listing_export_row(listing: dict[str, Any]) -> dict[str, str]:
    return {
        "title": str(listing.get("title", "")),
        "price": str(listing.get("price", "")),
        "post_date": str(listing.get("post_date", "")),
        "sqm": str(listing.get("sqm", "")),
        "rooms": str(listing.get("rooms", "")),
        "bathrooms": str(listing.get("bathrooms", "")),
        "address": str(listing.get("detail_address") or listing.get("address", "")),
        "url": str(listing.get("url", "")),
    }


def _listings_to_csv(listings: list[dict[str, Any]]) -> str:
    fieldnames = ["title", "price", "post_date", "sqm", "rooms", "bathrooms", "address", "url"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for listing in listings:
        writer.writerow(_listing_export_row(listing))
    return output.getvalue()


def _listings_to_markdown_table(
    listings: list[dict[str, Any]],
    max_rows: int,
) -> str:
    rows = [_listing_export_row(ls) for ls in listings[:max_rows]]
    header = "| title | price | post_date | sqm | rooms | address | url |"
    sep = "|---|---|---|---|---|---|---|"
    body = [
        "| "
        + " | ".join(
            [
                _escape_md(r["title"]),
                _escape_md(r["price"]),
                _escape_md(r["post_date"]),
                _escape_md(r["sqm"]),
                _escape_md(r["rooms"]),
                _escape_md(r["address"]),
                _escape_md(r["url"]),
            ]
        )
        + " |"
        for r in rows
    ]
    table = "\n".join([header, sep] + body)
    if len(listings) > max_rows:
        table += f"\n\nShown {max_rows} of {len(listings)} rows."
    return table


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sites = list_adapter_details()
    logger.info(
        f"Starting rental_scraper_mcp with {len(sites)} sites: "
        + ", ".join(s["display_name"] for s in sites)
    )
    mcp.run()
