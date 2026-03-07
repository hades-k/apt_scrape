"""
sites — Site adapter registry.

All registered adapters are available via:
  - get_adapter(site_id)      → look up by slug (e.g. "immobiliare")
  - adapter_for_url(url)      → auto-detect site from listing URL
  - list_adapters()           → all registered site_ids
  - ADAPTERS                  → the full list of adapter instances

To add a new site:
  1. Create sites/your_site.py (copy from _template.py)
  2. Import and add the adapter class below
"""

from __future__ import annotations

from .base import (
    SiteAdapter,
    SiteConfig,
    SearchFilters,
    ListingSummary,
    ListingDetail,
    SelectorGroup,
    SearchSelectors,
    DetailSelectors,
    extract_text,
    extract_attr,
    classify_feature,
)
from .immobiliare import ImmobiliareAdapter
from .casa import CasaAdapter

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Add new adapters here — order matters for URL matching (first match wins)
ADAPTERS: list[SiteAdapter] = [
    ImmobiliareAdapter(),
    CasaAdapter(),
]

_BY_ID: dict[str, SiteAdapter] = {a.site_id: a for a in ADAPTERS}


def get_adapter(site_id: str) -> SiteAdapter:
    """Get an adapter by its site_id slug.

    Raises KeyError if not found.
    """
    if site_id not in _BY_ID:
        available = ", ".join(sorted(_BY_ID.keys()))
        raise KeyError(f"Unknown site '{site_id}'. Available: {available}")
    return _BY_ID[site_id]


def adapter_for_url(url: str) -> SiteAdapter | None:
    """Auto-detect the right adapter for a given listing URL.

    Returns None if no adapter matches.
    """
    for adapter in ADAPTERS:
        if adapter.matches_url(url):
            return adapter
    return None


def list_adapters() -> list[str]:
    """Return all registered site_id values."""
    return [a.site_id for a in ADAPTERS]


def list_adapter_details() -> list[dict[str, str]]:
    """Return metadata for all registered adapters (for tool descriptions)."""
    return [
        {
            "site_id": a.site_id,
            "display_name": a.config.display_name,
            "base_url": a.config.base_url,
        }
        for a in ADAPTERS
    ]
